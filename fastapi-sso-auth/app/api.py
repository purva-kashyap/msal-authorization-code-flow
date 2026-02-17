"""
FastAPI SSO Authentication - API Routes

All authentication and user management endpoints.
"""
from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from msal import ConfidentialClientApplication
from datetime import datetime
from typing import Optional
import httpx

from app.config import settings
from app.models import (
    TokenInfo, TokenResponse, ErrorResponse, 
    HealthCheck, UserList, UserInfo
)
from app.services.token_service import (
    save_user_tokens, get_user_tokens, update_tokens,
    get_all_users, delete_user_tokens, get_user_count
)


# ============================================
# CREATE API ROUTER AND TEMPLATES
# ============================================

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================
# MSAL CLIENT (LAZY INITIALIZATION)
# ============================================

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

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with onboarding link."""
    total_users = await get_user_count()
    return templates.TemplateResponse("home.html", {
        "request": request,
        "total_users": total_users
    })


@router.get("/debug/config")
async def debug_config():
    """Debug endpoint to show current OAuth configuration."""
    return {
        "redirect_uri_configured": settings.redirect_uri,
        "client_id": settings.client_id[:8] + "..." if settings.client_id else "Not set",
        "tenant_id": settings.tenant_id[:8] + "..." if settings.tenant_id else "Not set",
        "authority": settings.authority,
        "port": settings.port,
        "scopes": settings.scopes,
        "note": "Check your Azure Portal → App Registrations → Authentication → Redirect URIs"
    }


@router.get("/onboard")
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
        
        # DEBUG: Log what redirect_uri is being sent to Microsoft
        print("=" * 60)
        print("🔍 DEBUG: OAuth Flow Initiated")
        print(f"📍 Redirect URI configured: {settings.redirect_uri}")
        print(f"📍 Redirect URI in flow: {flow.get('redirect_uri')}")
        print(f"🔗 Auth URL being sent: {flow['auth_uri']}")
        print("=" * 60)
        
        request.session["auth_flow"] = flow
        return RedirectResponse(url=flow["auth_uri"])
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/auth/callback", response_class=HTMLResponse)
async def callback(request: Request):
    """Handle OAuth2 callback and exchange code for tokens."""
    try:
        msal_app = get_msal_app()
        flow = request.session.get("auth_flow")
        
        if not flow:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No auth flow found in session"
            )
        
        # Get query parameters
        query_params = dict(request.query_params)
        
        # DEBUG: Log what's happening during token exchange
        print("=" * 60)
        print("🔍 DEBUG: Token Exchange")
        print(f"📍 Redirect URI from flow: {flow.get('redirect_uri')}")
        print(f"🌐 Actual callback URL: {request.url}")
        print(f"📦 Query params: {list(query_params.keys())}")
        print("=" * 60)
        
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
        
        return templates.TemplateResponse("callback_success.html", {
            "request": request,
            "user_name": user_name,
            "user_email": user_email,
            "user_id": user_id,
            "refresh_status": refresh_status
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )


@router.get("/profile", response_model=dict)
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


@router.get("/tokens", response_model=TokenInfo)
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

@router.post("/refresh", response_model=TokenResponse)
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


@router.get("/admin/users", response_model=UserList)
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


@router.post("/logout", response_model=TokenResponse)
async def logout(request: Request):
    """Clear session (tokens remain in database)."""
    request.session.clear()
    return TokenResponse(message="Logged out successfully")


@router.delete("/delete-account", response_model=TokenResponse)
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


@router.get("/health", response_model=HealthCheck)
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


