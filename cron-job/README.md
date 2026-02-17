# Meeting Transcript Processing Cron Job

A service that automatically processes Teams and Zoom meeting recordings, generates AI-powered summaries, and posts them to meeting chats.

## Features

- 🔄 Runs every 15 minutes (configurable via cron)
- 📊 Fetches recorded Teams meetings via Microsoft Graph API
- 🎥 Fetches recorded Zoom meetings via Zoom API
- 📝 Downloads meeting transcripts
- 🤖 Generates AI-powered summaries using OpenAI
- 💬 Posts summaries to meeting chats
- 📈 Tracks processing status and logs

## Architecture

The cron job:
1. Fetches all active users from the database
2. For each user:
   - Retrieves new Teams meetings with recordings
   - Retrieves new Zoom meetings with recordings
   - Downloads available transcripts
   - Generates summaries using AI
   - Posts summaries to meeting chats
3. Updates processing status and logs results

## Database Tables

### `user_processing_status`
Tracks the last time each user's meetings were checked.
- `user_id`: User identifier
- `last_teams_check`: Last Teams check timestamp
- `last_zoom_check`: Last Zoom check timestamp
- `is_active`: Whether to process this user

### `meeting_records`
Records of all processed meetings to avoid duplicates.
- `meeting_id`: Unique meeting identifier
- `platform`: 'teams' or 'zoom'
- `transcript_status`: pending, downloaded, processed, failed
- `summary_status`: pending, generated, posted, failed
- `summary_text`: Generated summary

### `processing_logs`
Logs of cron job executions.
- `run_timestamp`: When the job ran
- `status`: success, partial, failed
- `users_processed`: Number of users processed
- `meetings_processed`: Number of meetings processed

## Setup

### 1. Environment Variables

Create a `.env` file:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/entra_tokens

# Encryption (shared with main app)
ENCRYPTION_KEY=your-fernet-encryption-key

# Microsoft Azure/Entra ID
CLIENT_ID=your-azure-client-id
CLIENT_SECRET=your-azure-client-secret
TENANT_ID=your-azure-tenant-id

# Zoom API (optional)
ZOOM_CLIENT_ID=your-zoom-client-id
ZOOM_CLIENT_SECRET=your-zoom-client-secret
ZOOM_ACCOUNT_ID=your-zoom-account-id

# OpenAI (for summaries)
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini

# Processing settings
LOOKBACK_HOURS=24
MAX_MEETINGS_PER_USER=50
DEBUG=false
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize Database

The cron job will automatically create tables on first run. Or manually:

```python
python -c "from database import create_tables; import asyncio; asyncio.run(create_tables())"
```

### 4. Run Manually (for testing)

```bash
python cron_job.py
```

### 5. Setup Cron Job (Linux/Mac)

Edit crontab:
```bash
crontab -e
```

Add line to run every 15 minutes:
```cron
*/15 * * * * cd /path/to/cron-job && /path/to/python cron_job.py >> /var/log/meeting-processor.log 2>&1
```

Or using absolute paths:
```cron
*/15 * * * * /usr/bin/python3 /Users/purvakashyap/Projects/msal-authorization-code-flow/cron-job/cron_job.py >> /var/log/meeting-processor.log 2>&1
```

### 6. Setup as Systemd Service (Linux)

Create `/etc/systemd/system/meeting-processor.service`:

```ini
[Unit]
Description=Meeting Transcript Processor
After=network.target

[Service]
Type=oneshot
User=your-user
WorkingDirectory=/path/to/cron-job
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python cron_job.py
```

Create `/etc/systemd/system/meeting-processor.timer`:

```ini
[Unit]
Description=Run Meeting Processor every 15 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
Unit=meeting-processor.service

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable meeting-processor.timer
sudo systemctl start meeting-processor.timer
sudo systemctl status meeting-processor.timer
```

## File Structure

```
cron-job/
├── cron_job.py           # Main entry point
├── config.py             # Configuration management
├── database.py           # Database models and connection
├── teams_service.py      # Microsoft Teams/Graph API integration
├── zoom_service.py       # Zoom API integration
├── summary_service.py    # AI summary generation
├── utils.py              # Utility functions
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## API Permissions Required

### Microsoft Graph API
- `OnlineMeetings.Read`
- `OnlineMeetings.ReadWrite`
- `Chat.ReadWrite`
- `Files.Read.All` (for accessing recordings)
- `Calendars.Read`

### Zoom API
- View and manage cloud recordings
- View and manage meetings

## Logging

The cron job logs to stdout. To save logs:

```bash
# Redirect to log file
python cron_job.py >> meeting-processor.log 2>&1

# Or use systemd journal
journalctl -u meeting-processor.service -f
```

## Monitoring

Check the `processing_logs` table for execution history:

```sql
SELECT * FROM processing_logs ORDER BY run_timestamp DESC LIMIT 10;
```

Check recent meeting records:

```sql
SELECT platform, transcript_status, summary_status, COUNT(*) 
FROM meeting_records 
GROUP BY platform, transcript_status, summary_status;
```

## Troubleshooting

### No meetings found
- Verify user tokens are valid and not expired
- Check API permissions
- Verify lookback window (`LOOKBACK_HOURS`)

### Transcript not available
- Some meetings may not have transcripts enabled
- Check if recording feature is enabled in Teams/Zoom

### Summary generation fails
- Verify OpenAI API key is valid
- Check API rate limits
- Review transcript format compatibility

### Token expired
- The main application should handle token refresh
- Verify refresh tokens are stored and valid

## Development

Run in debug mode:
```bash
DEBUG=true python cron_job.py
```

## License

Same as parent project.
