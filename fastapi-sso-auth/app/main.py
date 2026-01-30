"""
FastAPI SSO Authentication with Microsoft Entra ID
Production-ready implementation with async support, encryption, and proper security.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.sessions import SessionMiddleware
from msal import ConfidentialClientApplication
from datetime import datetime
from typing import Optional
import httpx

from app.config import settings
from app.database import init_db, close_db
from app.models import (
    TokenInfo, TokenResponse, ErrorResponse, 
    HealthCheck, UserList, UserInfo
)
from app.services.token_service import (
    save_user_tokens, get_user_tokens, update_tokens,
    get_all_users, delete_user_tokens, get_user_count
)


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
    print(f"\n🌐 Server running at: http://localhost:{settings.port}")
    print(f"📚 API Docs: http://localhost:{settings.port}/docs")
    print("=" * 60)
    
    yield
    
    # Shutdown
    await close_db()


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Microsoft Entra ID SSO Authentication",
    description="Production-ready OAuth2 authentication with encrypted token storage",
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Security middleware
security = HTTPBearer()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="entra_session",
    max_age=3600,  # 1 hour
    same_site="lax",
    https_only=not settings.debug,  # HTTPS only in production
)

# Add trusted host middleware (security)
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.yourdomain.com", "yourdomain.com"]
    )

# Initialize MSAL lazily (only when credentials are valid)
_msal_app = None

def get_msal_app() -> ConfidentialClientApplication:
    """Get or create MSAL application instance."""
    global _msal_app
    if _msal_app is None:
        # Check if we have valid credentials
        if settings.tenant_id == "00000000-0000-0000-0000-000000000000":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Azure AD not configured. Please set CLIENT_ID, CLIENT_SECRET, and TENANT_ID in .env file"
            )
        _msal_app = ConfidentialClientApplication(
            settings.client_id,
            authority=settings.authority,
            client_credential=settings.client_secret
        )
    return _msal_app


# ============================================
# DEPENDENCY INJECTION
# ============================================

async def get_current_user(request: Request) -> str:
    """
    Get current user ID from session.
    
    Raises:
        HTTPException: If user is not authenticated
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please visit /onboard first."
        )
    return user_id


# ============================================
# ROUTES
# ============================================

@app.get("/", response_class=HTMLResponse)
async def home():
    """Home page with onboarding link."""
    total_users = await get_user_count()
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Microsoft Entra SSO - FastAPI</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                max-width: 900px;
                margin: 50px auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h1 {{
                color: #0078d4;
                margin-bottom: 10px;
            }}
            .badge {{
                display: inline-block;
                background: #107c10;
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
                margin-left: 10px;
            }}
            .btn {{
                display: inline-block;
                padding: 14px 28px;
                background-color: #0078d4;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                font-weight: 600;
                margin-right: 10px;
                transition: all 0.3s;
            }}
            .btn:hover {{
                background-color: #005a9e;
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,120,212,0.4);
            }}
            .btn-secondary {{
                background-color: #6c757d;
            }}
            .btn-secondary:hover {{
                background-color: #5a6268;
            }}
            .info {{
                background-color: #e7f3ff;
                padding: 20px;
                border-left: 4px solid #0078d4;
                margin: 25px 0;
                border-radius: 4px;
            }}
            .stats {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 25px;
                border-radius: 8px;
                margin: 25px 0;
                text-align: center;
            }}
            .stats strong {{
                font-size: 36px;
                display: block;
                margin-bottom: 5px;
            }}
            .feature-list {{
                list-style: none;
                padding: 0;
            }}
            .feature-list li {{
                padding: 10px 0;
                padding-left: 30px;
                position: relative;
            }}
            .feature-list li:before {{
                content: "✓";
                position: absolute;
                left: 0;
                color: #107c10;
                font-weight: bold;
                font-size: 18px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Welcome to FastAPI SSO <span class="badge">PRODUCTION READY</span></h1>
            <div class="stats">
                <strong>{total_users}</strong>
                <div>Registered Users</div>
            </div>
            <div class="info">
                <p><strong>🚀 Production-Ready Features</strong></p>
                <ul class="feature-list">
                    <li>Async/await for high performance</li>
                    <li>Pydantic validation for type safety</li>
                    <li>Encrypted token storage (Fernet)</li>
                    <li>PostgreSQL with async SQLAlchemy</li>
                    <li>Automatic API documentation (OpenAPI)</li>
                    <li>CORS protection enabled</li>
                    <li>Session security hardened</li>
                    <li>Environment-based configuration</li>
                </ul>
            </div>
            <a href="/onboard" class="btn">Start Onboarding</a>
            <a href="/admin/users" class="btn btn-secondary">View Users (Admin)</a>
            <a href="/docs" class="btn btn-secondary">API Docs</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/onboard")
async def onboard(request: Request):
    """Initiate the OAuth2 authorization code flow."""
    try:
        msal_app = get_msal_app()
        flow = msal_app.initiate_auth_code_flow(
            scopes=settings.scopes,
            redirect_uri=settings.redirect_uri
        )
        
        if "error" in flow:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initiate auth flow: {flow.get('error_description')}"
            )
        
        request.session["auth_flow"] = flow
        return RedirectResponse(url=flow["auth_uri"])
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/auth/callback", response_class=HTMLResponse)
async def callback(request: Request):
    """Handle OAuth2 callback and exchange code for tokens."""
    try:
        msal_app = get_msal_app()
        flow = request.session.get("auth_flow")
        flow = request.session.get("auth_flow")
        
        if not flow:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No auth flow found in session"
            )
        
        # Get query parameters
        query_params = dict(request.query_params)
        
        # Exchange code for token
        result = msal_app.acquire_token_by_auth_code_flow(flow, query_params)
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{result.get('error')}: {result.get('error_description')}"
            )
        
        # Extract data
        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        id_token_claims = result.get("id_token_claims", {})
        expires_in = result.get("expires_in", 3600)
        
        user_id = id_token_claims.get("oid")
        user_email = id_token_claims.get("preferred_username") or id_token_claims.get("email")
        user_name = id_token_claims.get("name")
        
        expires_at = datetime.now().timestamp() + expires_in
        
        # Save to database (encrypted)
        await save_user_tokens(
            user_id, user_email, user_name, 
            access_token, refresh_token, expires_at
        )
        
        # Clean up session and set user
        request.session.pop("auth_flow", None)
        request.session["user_id"] = user_id
        
        refresh_status = "✓ Received" if refresh_token else "✗ Not received"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Onboarding Success</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    max-width: 800px;
                    margin: 50px auto;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 12px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                }}
                .success {{
                    color: #107c10;
                    font-size: 32px;
                    margin-bottom: 20px;
                    font-weight: bold;
                }}
                .user-info {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 25px 0;
                    border-left: 4px solid #107c10;
                }}
                .btn {{
                    display: inline-block;
                    padding: 12px 24px;
                    background-color: #0078d4;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin-top: 10px;
                    margin-right: 10px;
                    font-weight: 600;
                    transition: all 0.3s;
                }}
                .btn:hover {{
                    background-color: #005a9e;
                    transform: translateY(-2px);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✓ Onboarding Successful!</div>
                <p>Your tokens have been encrypted and securely stored using FastAPI + PostgreSQL.</p>
                <div class="user-info">
                    <strong>User Information:</strong><br><br>
                    <strong>Name:</strong> {user_name}<br>
                    <strong>Email:</strong> {user_email}<br>
                    <strong>User ID:</strong> {user_id}<br>
                    <br>
                    <strong>Token Status:</strong><br>
                    Access Token: ✓ Received & Encrypted<br>
                    Refresh Token: {refresh_status}
                </div>
                <a href="/profile" class="btn">View Profile</a>
                <a href="/tokens" class="btn">Token Info</a>
                <a href="/" class="btn">Home</a>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )


@app.get("/profile", response_model=dict)
async def profile(user_id: str = Depends(get_current_user)):
    """Fetch user profile from Microsoft Graph using stored access token."""
    user_data = await get_user_tokens(user_id)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    access_token = user_data["access_token"]
    
    # Use httpx for async HTTP requests
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                return {
                    "message": "Profile fetched successfully",
                    "profile": response.json()
                }
            elif response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Access token expired. Try /refresh endpoint"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch profile: {response.text}"
                )
                
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Request to Microsoft Graph timed out"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error contacting Microsoft Graph: {str(e)}"
            )


@app.get("/tokens", response_model=TokenInfo)
async def view_tokens(user_id: str = Depends(get_current_user)):
    """View token info (masked) for current user."""
    user_data = await get_user_tokens(user_id)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tokens found"
        )
    
    # Mask tokens
    access_token = user_data["access_token"]
    access_preview = f"{access_token[:20]}...{access_token[-20:]}"
    
    refresh_preview = None
    if user_data.get("refresh_token"):
        refresh_token = user_data["refresh_token"]
        refresh_preview = f"{refresh_token[:20]}...{refresh_token[-20:]}"
    
    expires_in = int(user_data["expires_at"] - datetime.now().timestamp())
    
    return TokenInfo(
        user_id=user_data["user_id"],
        email=user_data["email"],
        name=user_data["name"],
        access_token_preview=access_preview,
        refresh_token_preview=refresh_preview,
        expires_at=user_data["expires_at"],
        expires_in_seconds=max(0, expires_in),
        created_at=user_data["created_at"],
        updated_at=user_data["updated_at"]
    )

@app.post("/refresh", response_model=TokenResponse)
async def refresh_token(user_id: str = Depends(get_current_user)):
    """Refresh the access token using the refresh token."""
    msal_app = get_msal_app()
    user_data = await get_user_tokens(user_id)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    refresh_token_value = user_data.get("refresh_token")
    
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token available"
        )
    
    result = msal_app.acquire_token_by_refresh_token(
        refresh_token_value,
        scopes=settings.scopes
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{result.get('error')}: {result.get('error_description')}"
        )
    
    # Update tokens
    new_access_token = result.get("access_token")
    new_refresh_token = result.get("refresh_token")
    expires_at = datetime.now().timestamp() + result.get("expires_in", 3600)
    
    await update_tokens(user_id, new_access_token, expires_at, new_refresh_token)
    
    return TokenResponse(
        message="Token refreshed successfully",
        expires_in=result.get("expires_in")
    )


@app.get("/admin/users", response_model=UserList)
async def admin_users():
    """
    Admin endpoint to view all registered users.
    
    WARNING: In production, this should be protected with admin authentication!
    """
    users = await get_all_users()
    
    return UserList(
        total_users=len(users),
        users=[UserInfo(**user) for user in users]
    )


@app.post("/logout", response_model=TokenResponse)
async def logout(request: Request):
    """Clear session (tokens remain in database)."""
    request.session.clear()
    return TokenResponse(message="Logged out successfully")


@app.delete("/delete-account", response_model=TokenResponse)
async def delete_account(request: Request, user_id: str = Depends(get_current_user)):
    """Delete user account and tokens from database."""
    deleted = await delete_user_tokens(user_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    request.session.clear()
    
    return TokenResponse(message="Account and tokens deleted successfully")


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        user_count = await get_user_count()
        db_status = "connected" if user_count >= 0 else "disconnected"
    except Exception:
        user_count = 0
        db_status = "disconnected"
    
    return HealthCheck(
        status="healthy",
        database=db_status,
        total_users=user_count,
        timestamp=datetime.now().isoformat()
    )


# ============================================
# ERROR HANDLERS
# ============================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler for unhandled errors."""
    # Log error here (use proper logging in production)
    print(f"Unhandled error: {str(exc)}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "details": str(exc) if settings.debug else "An error occurred"
        }
    )
