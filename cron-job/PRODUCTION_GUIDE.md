# Production Deployment Guide

This guide covers deploying the meeting transcript processing cron job to production with all high-priority improvements implemented.

## ✅ Implemented Production Features

### 1. Database Migrations (Alembic)
- **Location**: `alembic/` directory
- **Configuration**: `alembic.ini`, `alembic/env.py`
- **Async support**: Fully configured for async SQLAlchemy

**Usage:**
```bash
# Create new migration after model changes
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View current version
alembic current

# View migration history
alembic history
```

### 2. Retry Logic with Exponential Backoff
- **Implementation**: `utils.py` - `@async_retry` decorator
- **Library**: `tenacity`
- **Features**:
  - Configurable max attempts
  - Exponential backoff with jitter
  - Selective retry on specific exceptions
  - Detailed logging before/after retries

**Configuration** (`.env`):
```env
MAX_RETRIES=3
RETRY_BACKOFF_BASE=2.0
RETRY_MAX_WAIT=60
```

### 3. Structured Logging + Monitoring
- **Logging**: `logging_config.py` - JSON structured logs via `structlog`
- **Monitoring**: `monitoring.py` - Prometheus metrics collection

**Key Metrics**:
- `meetings_processed_total` - Total meetings processed by platform
- `api_requests_total` - API requests by platform/endpoint/status
- `transcript_downloads_total` - Transcript downloads
- `cron_job_duration` - Job execution time
- `errors_total` - Errors by type and component

**Logging Features**:
- JSON output for easy parsing
- Contextual logging with auto fields
- Integration with log aggregation tools (Splunk, ELK, etc.)

### 4. Proper Secrets Management
- **Implementation**: `config.py` with enhanced `Settings` class
- **Features**:
  - Environment variable priority
  - Field validation
  - Support for secrets files
  - Commented integration points for:
    - AWS Secrets Manager
    - Azure Key Vault
    - HashiCorp Vault

**Adding Secrets Manager** (example for AWS):
```python
# In config.py, uncomment and configure:
if os.getenv("USE_AWS_SECRETS"):
    import boto3
    from botocore.exceptions import ClientError
    
    def get_secret(secret_name):
        client = boto3.client('secretsmanager')
        try:
            response = client.get_secret_value(SecretId=secret_name)
            return json.loads(response['SecretString'])
        except ClientError as e:
            raise ConfigurationError(f"Failed to fetch secrets: {e}")
```

### 5. Rate Limiting
- **Implementation**: `rate_limiters.py`
- **Library**: `aiolimiter`
- **Limiters**:
  - Microsoft Graph: 100 req/min
  - Zoom Recording: 8 req/sec
  - Zoom General: 60 req/sec
  - OpenAI: 10 req/min

**Usage in services**:
```python
from rate_limiters import rate_limiters

async def api_call():
    await rate_limiters.acquire_graph_limit()
    # Make API call
```

### 6. Comprehensive Error Handling
- **Implementation**: `exceptions.py` - Custom exception hierarchy
- **Service Updates**: 
  - `teams_service.py` - Full error handling with retries
  - Similar patterns for `zoom_service.py`, `summary_service.py`

**Exception Types**:
- `TokenExpiredError` - OAuth token expired
- `RateLimitError` - API rate limit hit
- `TeamsAPIError` / `ZoomAPIError` - Platform-specific errors
- `TranscriptNotFoundError` - Missing transcript
- `SummaryGenerationError` - AI summary failed

## Deployment Steps

### 1. Initial Setup

```bash
cd cron-job

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Initialize database
alembic upgrade head
# OR use the helper script:
python init_db.py
```

### 2. Production Configuration

**Environment Variables** (beyond .env):
```bash
# For production, use actual secrets manager
export USE_AWS_SECRETS=true
export AWS_SECRET_NAME=meeting-processor-secrets

# Or Azure Key Vault
export USE_AZURE_KEYVAULT=true
export AZURE_KEYVAULT_URL=https://your-vault.vault.azure.net/
```

### 3. Test Run

```bash
# Run once to verify
python cron_job.py

# Check logs (JSON format)
python cron_job.py 2>&1 | jq

# Check metrics
python -c "from monitoring import get_metrics; print(get_metrics().decode())"
```

### 4. Set Up Scheduled Execution

**Option A: Cron (Linux/Mac)**
```bash
crontab -e

# Add (every 15 minutes):
*/15 * * * * cd /path/to/cron-job && /path/to/python cron_job.py >> /var/log/meeting-processor.log 2>&1
```

**Option B: Systemd Timer (Linux - Recommended)**

Create `/etc/systemd/system/meeting-processor.service`:
```ini
[Unit]
Description=Meeting Transcript Processor
After=network.target postgresql.service

[Service]
Type=oneshot
User=app-user
WorkingDirectory=/path/to/cron-job
EnvironmentFile=/path/to/.env
ExecStart=/path/to/python /path/to/cron-job/cron_job.py
StandardOutput=journal
StandardError=journal

# Resource limits
MemoryLimit=1G
CPUQuota=50%
```

Create `/etc/systemd/system/meeting-processor.timer`:
```ini
[Unit]
Description=Run Meeting Processor every 15 minutes
Requires=meeting-processor.service

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Unit=meeting-processor.service

[Install]
WantedBy=timers.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable meeting-processor.timer
sudo systemctl start meeting-processor.timer

# Check status
sudo systemctl status meeting-processor.timer
sudo systemctl list-timers
```

**Option C: Kubernetes CronJob**

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: meeting-processor
spec:
  schedule: "*/15 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: processor
            image: your-registry/meeting-processor:latest
            envFrom:
            - secretRef:
                name: meeting-processor-secrets
            resources:
              requests:
                memory: "512Mi"
                cpu: "250m"
              limits:
                memory: "1Gi"
                cpu: "500m"
          restartPolicy: OnFailure
```

### 5. Monitoring Setup

**Expose Metrics Endpoint** (optional):

Add to `cron_job.py`:
```python
from monitoring import get_metrics
import aiohttp.web

async def metrics_handler(request):
    return aiohttp.web.Response(
        body=get_metrics(),
        content_type='text/plain'
    )

# Start metrics server
app = aiohttp.web.Application()
app.router.add_get('/metrics', metrics_handler)
aiohttp.web.run_app(app, host='0.0.0.0', port=9090)
```

**Prometheus Configuration**:
```yaml
scrape_configs:
  - job_name: 'meeting-processor'
    static_configs:
      - targets: ['localhost:9090']
```

**Grafana Dashboard Queries**:
```promql
# Total meetings processed
rate(meetings_processed_total[5m])

# Error rate
rate(errors_total[5m])

# API latency (p95)
histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))

# Success rate
sum(rate(meetings_processed_total{status="success"}[5m])) / 
sum(rate(meetings_processed_total[5m]))
```

### 6. Log Aggregation

**Filebeat Configuration** (for ELK Stack):
```yaml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/meeting-processor.log
  json.keys_under_root: true
  json.add_error_key: true

output.elasticsearch:
  hosts: ["localhost:9200"]
  index: "meeting-processor-%{+yyyy.MM.dd}"
```

**CloudWatch Logs** (AWS):
```bash
# Install CloudWatch agent
# Configure to send stdout to CloudWatch
# Logs will be in JSON format, easily queryable
```

### 7. Alerting

**Example Alerts** (Prometheus Alertmanager):
```yaml
groups:
- name: meeting_processor
  rules:
  - alert: HighErrorRate
    expr: rate(errors_total[5m]) > 0.1
    for: 10m
    annotations:
      summary: "High error rate in meeting processor"
  
  - alert: ProcessingDelayed
    expr: time() - cron_job_runs_total > 1800
    for: 5m
    annotations:
      summary: "Meeting processor hasn't run in 30 minutes"
  
  - alert: RateLimitHit
    expr: rate(api_requests_total{status="error_429"}[5m]) > 0
    annotations:
      summary: "API rate limits being hit"
```

## Rollback Procedures

### Database Rollback
```bash
# View current migration
alembic current

# Rollback one version
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision>
```

### Application Rollback
```bash
# Systemd
sudo systemctl stop meeting-processor.timer
# Deploy previous version
sudo systemctl start meeting-processor.timer

# Kubernetes
kubectl rollout undo cronjob/meeting-processor
```

## Health Checks

Add health check endpoint:
```python
# In cron_job.py
async def health_check():
    """Check if system is healthy."""
    from database import engine
    
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## Troubleshooting

### Check Logs
```bash
# Systemd
journalctl -u meeting-processor.service -f

# Direct log file
tail -f /var/log/meeting-processor.log | jq

# Filter errors
grep -i error /var/log/meeting-processor.log | jq
```

### Check Database
```sql
-- Recent processing runs
SELECT * FROM processing_logs ORDER BY run_timestamp DESC LIMIT 10;

-- Failed meetings
SELECT * FROM meeting_records 
WHERE transcript_status = 'failed' OR summary_status = 'failed'
ORDER BY created_at DESC LIMIT 20;

-- Processing statistics
SELECT 
    DATE(run_timestamp) as date,
    COUNT(*) as runs,
    AVG(meetings_processed) as avg_processed,
    SUM(errors_count) as total_errors
FROM processing_logs
GROUP BY DATE(run_timestamp)
ORDER BY date DESC;
```

### Common Issues

1. **Token Expired**: Ensure main app refreshes tokens
2. **Rate Limits**: Adjust rate limiter configuration
3. **Timeouts**: Increase timeout values or reduce batch size
4. **Memory Issues**: Reduce `max_meetings_per_user`

## Scaling Considerations

For 1000+ users:
1. Implement message queue (RabbitMQ/SQS)
2. Use distributed workers
3. Partition users across multiple jobs
4. Cache frequently accessed data
5. Consider event-driven architecture

## Security Checklist

- [ ] Secrets stored in secrets manager (not .env)
- [ ] Database uses SSL connections
- [ ] API tokens rotated regularly
- [ ] Logs don't contain sensitive data
- [ ] Network access restricted
- [ ] Resource limits configured
- [ ] Error messages sanitized

## Performance Tuning

Adjust these based on your workload:
```env
# Process more users in parallel
# Adjust database pool
POOL_SIZE=20
MAX_OVERFLOW=40

# Rate limits (if you have higher quotas)
GRAPH_API_RATE_LIMIT=200
ZOOM_API_RATE_LIMIT=100

# Processing limits
MAX_MEETINGS_PER_USER=100
LOOKBACK_HOURS=48
```

## Support

For issues:
1. Check logs with structured queries
2. Review metrics in Grafana/Prometheus
3. Check processing_logs table
4. Enable DEBUG=true for verbose logging
