"""
FastAPI SSO Authentication - Application Entry Point

This file initializes the FastAPI app, configures middleware,
and includes all routers. Run with: python main.py
"""
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import init_db, close_db
from app.api import router


# ============================================
# LIFESPAN CONTEXT MANAGER
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    await init_db()
    print("=" * 60)
    print("FastAPI SSO Authentication Server - PRODUCTION READY")
    print("=" * 60)
    print(f"✓ Environment: {'Development' if settings.debug else 'Production'}")
    print(f"✓ Encryption: Enabled")
    print(f"✓ CORS Origins: {', '.join(settings.cors_origins_list)}")
    print("=" * 60)
    print(f"\n🌐 Server running at: http://{settings.host}:{settings.port}")
    print(f"📚 API Docs: http://{settings.host}:{settings.port}/docs")
    print("=" * 60)
    
    yield
    
    # Shutdown
    await close_db()


# ============================================
# CREATE FASTAPI APP
# ============================================

app = FastAPI(
    title="Microsoft Entra ID SSO Authentication",
    description="Production-ready OAuth2 authentication with encrypted token storage",
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)


# ============================================
# MIDDLEWARE CONFIGURATION
# ============================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="entra_session",
    max_age=3600,  # 1 hour
    same_site="lax",
    https_only=not settings.debug,
)

# Trusted host middleware (production only)
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.yourdomain.com", "yourdomain.com"]
    )


# ============================================
# INCLUDE ROUTERS
# ============================================

app.include_router(router)


# ============================================
# RUN APPLICATION
# ============================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )

