# FastAPI SSO Authentication with Microsoft Entra ID

🚀 **Production-ready** OAuth2 authentication system built with FastAPI, featuring encrypted token storage, async database operations, and modern Python best practices.

## ✨ Features

- ✅ **Async/Await** - High-performance async operations throughout
- ✅ **Type Safety** - Full Pydantic validation and type hints
- ✅ **Encrypted Storage** - Fernet encryption for OAuth tokens
- ✅ **PostgreSQL** - Async SQLAlchemy with connection pooling
- ✅ **Auto Documentation** - Interactive API docs (OpenAPI/Swagger)
- ✅ **Security Hardened** - CORS, session security, HTTPS-ready
- ✅ **Environment Config** - Pydantic Settings for 12-factor apps
- ✅ **Production Ready** - Error handling, health checks, monitoring hooks

## 📋 Prerequisites

- Python 3.11+ (recommended)
- PostgreSQL 13+
- Microsoft Entra ID (Azure AD) application registration

## 🔧 Setup

### 1. Clone and Navigate

```bash
cd fastapi-sso-auth
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create PostgreSQL Database

```bash
createdb entra_tokens
# Or via psql:
# psql -U postgres -c "CREATE DATABASE entra_tokens;"
```

### 5. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```bash
# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Required Variables:**
- `CLIENT_ID` - Azure AD Application ID
- `CLIENT_SECRET` - Azure AD Client Secret
- `TENANT_ID` - Azure AD Tenant ID
- `ENCRYPTION_KEY` - Fernet encryption key (generated above)
- `SECRET_KEY` - Session secret key (generated above)

### 6. Configure Azure AD App Registration

In Azure Portal > App Registrations:

1. **Redirect URI**: Add `http://localhost:8000/auth/callback`
2. **API Permissions**: Grant `User.Read` (Microsoft Graph)
3. **Client Secret**: Create and copy to `.env`

## 🚀 Running the Application

### Development Mode

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
# Using Uvicorn with workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Or using Gunicorn with Uvicorn workers (recommended)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

Access the application:
- **Home**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📚 API Endpoints

### Public Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Home page with stats |
| GET | `/health` | Health check endpoint |
| GET | `/onboard` | Initiate OAuth flow |
| GET | `/auth/callback` | OAuth callback handler |

### Authenticated Endpoints (requires session)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/profile` | Fetch user profile from Graph API |
| GET | `/tokens` | View masked token information |
| POST | `/refresh` | Refresh access token |
| POST | `/logout` | Clear session |
| DELETE | `/delete-account` | Delete user and tokens |

### Admin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/users` | List all users (⚠️ needs auth) |

## 🏗️ Project Structure

```
fastapi-sso-auth/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, routes, middleware
│   ├── config.py            # Pydantic settings
│   ├── database.py          # SQLAlchemy async setup
│   ├── models.py            # Pydantic response models
│   └── services/
│       ├── __init__.py
│       ├── encryption.py    # Token encryption utilities
│       └── token_service.py # Database operations
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 🔒 Security Features

### Implemented
- ✅ Fernet encryption for tokens at rest
- ✅ Secure session cookies (HttpOnly, SameSite)
- ✅ CORS protection
- ✅ Environment-based secrets
- ✅ SQL injection protection (SQLAlchemy ORM)
- ✅ Input validation (Pydantic)

### Recommended for Production
- 🔲 Enable HTTPS/TLS (use reverse proxy like Nginx)
- 🔲 Add authentication to admin endpoints
- 🔲 Implement rate limiting (slowapi or redis)
- 🔲 Add CSRF protection for state-changing operations
- 🔲 Enable security headers (helmet middleware)
- 🔲 Set up error monitoring (Sentry)
- 🔲 Configure logging (structured JSON logs)
- 🔲 Database connection secrets via vault (AWS Secrets Manager, etc.)

## 🔄 Token Flow

1. User visits `/onboard`
2. Redirected to Microsoft login
3. User authenticates with Microsoft
4. Callback to `/auth/callback` with auth code
5. Exchange code for access + refresh tokens
6. Tokens encrypted and stored in PostgreSQL
7. User session established
8. Access `/profile` to use stored token
9. Use `/refresh` when token expires

## 🧪 Testing

```bash
# Install dev dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

## 📊 Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "total_users": 42,
  "timestamp": "2026-01-29T10:30:00"
}
```

### Metrics (Optional)

Add Prometheus instrumentation:

```bash
pip install prometheus-fastapi-instrumentator
```

## 🐳 Docker Deployment (Optional)

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t fastapi-sso .
docker run -p 8000:8000 --env-file .env fastapi-sso
```

## 🚨 Troubleshooting

### Database Connection Error
```bash
# Check PostgreSQL is running
pg_isready

# Verify database exists
psql -l | grep entra_tokens
```

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Token Encryption Error
```bash
# Regenerate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 🆚 Comparison: FastAPI vs Flask

| Feature | This (FastAPI) | Flask Version |
|---------|----------------|---------------|
| Performance | ⚡⚡⚡⚡⚡ Async | ⚡⚡⚡ Sync |
| Type Safety | ✅ Full Pydantic | ❌ Manual |
| API Docs | ✅ Auto-generated | ❌ Manual |
| Validation | ✅ Built-in | ❌ Manual |
| Production Ready | ✅ Yes | ⚠️ Needs work |

## 📝 License

MIT

## 👨‍💻 Author

Production-ready implementation with FastAPI best practices.

---

**Ready for production?** Don't forget to:
1. Set `DEBUG=false` in `.env`
2. Use HTTPS in production
3. Protect admin endpoints
4. Set up monitoring
5. Configure backup strategy
