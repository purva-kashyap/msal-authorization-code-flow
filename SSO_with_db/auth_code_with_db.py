from flask import Flask, redirect, request, session, jsonify, render_template_string
from msal import ConfidentialClientApplication
import os
from datetime import datetime
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, Column, String, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ============================================
# CONFIGURATION
# ============================================
CLIENT_ID = "your-client-id-here"
CLIENT_SECRET = "your-client-secret-here"
TENANT_ID = "your-tenant-id-here"
REDIRECT_URI = "http://localhost:5000/auth/callback"

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

# PostgreSQL Database Configuration
# Format: postgresql://username:password@host:port/database
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/entra_tokens"
)

# Encryption key (In production, store this securely in environment variable!)
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # Generate and print key for first time setup
    ENCRYPTION_KEY = Fernet.generate_key()
    print(f"\n⚠️  IMPORTANT: Save this encryption key in your environment:")
    print(f"export ENCRYPTION_KEY='{ENCRYPTION_KEY.decode()}'")
    print("=" * 60 + "\n")
else:
    if isinstance(ENCRYPTION_KEY, str):
        ENCRYPTION_KEY = ENCRYPTION_KEY.encode()

cipher = Fernet(ENCRYPTION_KEY)

# Initialize MSAL
msal_app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

# ============================================
# DATABASE SETUP (PostgreSQL with SQLAlchemy)
# ============================================

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    echo=False  # Set to True for SQL query logging
)

# Create session factory
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

# Base class for declarative models
Base = declarative_base()


# Define UserToken model
class UserToken(Base):
    __tablename__ = 'user_tokens'
    
    user_id = Column(String(255), primary_key=True)
    email = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=True)
    access_token = Column(String(4096), nullable=False)  # Encrypted
    refresh_token = Column(String(4096), nullable=True)  # Encrypted
    expires_at = Column(Float, nullable=False)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)
    
    def __repr__(self):
        return f"<UserToken(user_id='{self.user_id}', email='{self.email}')>"


# Create all tables
def init_db():
    """Initialize the database tables"""
    try:
        Base.metadata.create_all(engine)
        print("✓ PostgreSQL database initialized")
        print(f"✓ Connected to: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'database'}")
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        raise


@contextmanager
def get_db_session():
    """Context manager for database sessions"""
    db_session = Session()
    try:
        yield db_session
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()


# ============================================
# ENCRYPTION HELPERS
# ============================================

def encrypt_token(token):
    """Encrypt a token for storage"""
    if not token:
        return None
    return cipher.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token):
    """Decrypt a token from storage"""
    if not encrypted_token:
        return None
    return cipher.decrypt(encrypted_token.encode()).decode()


# ============================================
# DATABASE OPERATIONS
# ============================================

def save_user_tokens(user_id, email, name, access_token, refresh_token, expires_at):
    """Save or update user tokens in database"""
    with get_db_session() as db_session:
        now = datetime.now().isoformat()
        
        # Encrypt tokens before storing
        encrypted_access = encrypt_token(access_token)
        encrypted_refresh = encrypt_token(refresh_token)
        
        # Check if user exists
        user = db_session.query(UserToken).filter_by(user_id=user_id).first()
        
        if user:
            # Update existing user
            user.email = email
            user.name = name
            user.access_token = encrypted_access
            user.refresh_token = encrypted_refresh
            user.expires_at = expires_at
            user.updated_at = now
        else:
            # Create new user
            user = UserToken(
                user_id=user_id,
                email=email,
                name=name,
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                expires_at=expires_at,
                created_at=now,
                updated_at=now
            )
            db_session.add(user)
    
    print(f"✓ Tokens saved for user: {email}")


def get_user_tokens(user_id):
    """Retrieve user tokens from database"""
    with get_db_session() as db_session:
        user = db_session.query(UserToken).filter_by(user_id=user_id).first()
        
        if not user:
            return None
        
        # Decrypt tokens and return as dict
        return {
            "user_id": user.user_id,
            "email": user.email,
            "name": user.name,
            "access_token": decrypt_token(user.access_token),
            "refresh_token": decrypt_token(user.refresh_token),
            "expires_at": user.expires_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }


def update_tokens(user_id, access_token, expires_at, refresh_token=None):
    """Update only the tokens for a user"""
    with get_db_session() as db_session:
        user = db_session.query(UserToken).filter_by(user_id=user_id).first()
        
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        encrypted_access = encrypt_token(access_token)
        now = datetime.now().isoformat()
        
        user.access_token = encrypted_access
        user.expires_at = expires_at
        user.updated_at = now
        
        if refresh_token:
            user.refresh_token = encrypt_token(refresh_token)


def get_all_users():
    """Get list of all users (for admin purposes)"""
    with get_db_session() as db_session:
        users = db_session.query(
            UserToken.user_id,
            UserToken.email,
            UserToken.name,
            UserToken.created_at,
            UserToken.updated_at
        ).order_by(UserToken.updated_at.desc()).all()
        
        return [
            {
                "user_id": user.user_id,
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at,
                "updated_at": user.updated_at
            }
            for user in users
        ]


def delete_user_tokens(user_id):
    """Delete user tokens from database"""
    with get_db_session() as db_session:
        user = db_session.query(UserToken).filter_by(user_id=user_id).first()
        if user:
            db_session.delete(user)


def get_user_count():
    """Get total number of registered users"""
    with get_db_session() as db_session:
        return db_session.query(UserToken).count()


# ============================================
# ROUTES
# ============================================

@app.route("/")
def home():
    """Home page with onboarding link"""
    total_users = get_user_count()
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Microsoft Entra Onboarding</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #0078d4;
            }}
            .btn {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #0078d4;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-weight: bold;
                margin-right: 10px;
            }}
            .btn:hover {{
                background-color: #005a9e;
            }}
            .btn-secondary {{
                background-color: #6c757d;
            }}
            .btn-secondary:hover {{
                background-color: #5a6268;
            }}
            .info {{
                background-color: #e7f3ff;
                padding: 15px;
                border-left: 4px solid #0078d4;
                margin: 20px 0;
            }}
            .stats {{
                background-color: #f0f0f0;
                padding: 15px;
                border-radius: 4px;
                margin: 20px 0;
                text-align: center;
            }}
            .stats strong {{
                font-size: 24px;
                color: #0078d4;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Welcome to Our Application</h1>
            <div class="stats">
                <strong>{total_users}</strong> users registered
            </div>
            <div class="info">
                <p><strong>PostgreSQL Multi-User Support Enabled</strong></p>
                <ul>
                    <li>Tokens are encrypted and stored securely in PostgreSQL</li>
                    <li>Each user has isolated access</li>
                    <li>Sessions persist across server restarts</li>
                    <li>Scalable for production use</li>
                </ul>
            </div>
            <a href="/onboard" class="btn">Start Onboarding</a>
            <a href="/admin/users" class="btn btn-secondary">View All Users (Admin)</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/onboard")
def onboard():
    """Initiate the authorization code flow"""
    try:
        flow = msal_app.initiate_auth_code_flow(
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        if "error" in flow:
            return jsonify({
                "error": "Failed to initiate auth flow",
                "details": flow.get("error_description")
            }), 500
        
        session["auth_flow"] = flow
        return redirect(flow["auth_uri"])
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/auth/callback")
def callback():
    """Handle the callback from Microsoft and exchange code for tokens"""
    try:
        flow = session.get("auth_flow", {})
        
        if not flow:
            return jsonify({"error": "No auth flow found in session"}), 400
        
        result = msal_app.acquire_token_by_auth_code_flow(flow, request.args)
        
        if "error" in result:
            return jsonify({
                "error": result.get("error"),
                "description": result.get("error_description")
            }), 400
        
        # Extract data
        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        id_token_claims = result.get("id_token_claims", {})
        expires_in = result.get("expires_in", 3600)
        
        user_id = id_token_claims.get("oid")
        user_email = id_token_claims.get("preferred_username") or id_token_claims.get("email")
        user_name = id_token_claims.get("name")
        
        expires_at = datetime.now().timestamp() + expires_in
        
        # Save to PostgreSQL database (encrypted)
        save_user_tokens(user_id, user_email, user_name, access_token, refresh_token, expires_at)
        
        session.pop("auth_flow", None)
        session["user_id"] = user_id
        
        refresh_status = "✓ Received" if refresh_token else "✗ Not received"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Onboarding Success</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 50px auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .success {{
                    color: #107c10;
                    font-size: 24px;
                    margin-bottom: 20px;
                }}
                .user-info {{
                    background-color: #f0f0f0;
                    padding: 15px;
                    border-radius: 4px;
                    margin: 20px 0;
                }}
                .btn {{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #0078d4;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    margin-top: 20px;
                    margin-right: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✓ Onboarding Successful!</div>
                <p>Your tokens have been encrypted and securely stored in PostgreSQL.</p>
                <div class="user-info">
                    <strong>User Information:</strong><br>
                    Name: {user_name}<br>
                    Email: {user_email}<br>
                    User ID: {user_id}<br>
                    <br>
                    <strong>Token Status:</strong><br>
                    Access Token: ✓ Received & Encrypted<br>
                    Refresh Token: {refresh_status}
                </div>
                <a href="/profile" class="btn">View Profile</a>
                <a href="/tokens" class="btn">View Token Info</a>
                <a href="/" class="btn">Home</a>
            </div>
        </body>
        </html>
        """
        return render_template_string(html)
        
    except Exception as e:
        return jsonify({
            "error": "Authentication failed",
            "details": str(e)
        }), 500


@app.route("/profile")
def profile():
    """Fetch user profile using the stored access token"""
    try:
        user_id = session.get("user_id")
        
        if not user_id:
            return redirect("/")
        
        user_data = get_user_tokens(user_id)
        
        if not user_data:
            return jsonify({"error": "User not found"}), 404
        
        access_token = user_data["access_token"]
        
        import requests
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers=headers
        )
        
        if response.status_code == 200:
            profile_data = response.json()
            return jsonify({
                "message": "Profile fetched successfully",
                "profile": profile_data
            })
        elif response.status_code == 401:
            return jsonify({
                "error": "Access token expired",
                "suggestion": "Try /refresh endpoint"
            }), 401
        else:
            return jsonify({
                "error": "Failed to fetch profile",
                "status_code": response.status_code,
                "details": response.text
            }), response.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/tokens")
def view_tokens():
    """View token info (masked) for current user"""
    user_id = session.get("user_id")
    
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    
    user_data = get_user_tokens(user_id)
    
    if not user_data:
        return jsonify({"error": "No tokens found"}), 404
    
    # Mask tokens
    token_info = user_data.copy()
    if token_info.get("access_token"):
        token = token_info["access_token"]
        token_info["access_token"] = f"{token[:20]}...{token[-20:]}"
    if token_info.get("refresh_token"):
        token = token_info["refresh_token"]
        token_info["refresh_token"] = f"{token[:20]}...{token[-20:]}"
    
    token_info["expires_in_seconds"] = int(user_data["expires_at"] - datetime.now().timestamp())
    
    return jsonify(token_info)


@app.route("/refresh")
def refresh_token():
    """Refresh the access token using the refresh token"""
    try:
        user_id = session.get("user_id")
        
        if not user_id:
            return jsonify({"error": "Not logged in"}), 401
        
        user_data = get_user_tokens(user_id)
        
        if not user_data:
            return jsonify({"error": "User not found"}), 404
        
        refresh_token_value = user_data.get("refresh_token")
        
        if not refresh_token_value:
            return jsonify({"error": "No refresh token available"}), 400
        
        result = msal_app.acquire_token_by_refresh_token(
            refresh_token_value,
            scopes=SCOPES
        )
        
        if "error" in result:
            return jsonify({
                "error": result.get("error"),
                "description": result.get("error_description")
            }), 400
        
        # Update tokens in database
        new_access_token = result.get("access_token")
        new_refresh_token = result.get("refresh_token")
        expires_at = datetime.now().timestamp() + result.get("expires_in", 3600)
        
        update_tokens(user_id, new_access_token, expires_at, new_refresh_token)
        
        return jsonify({
            "message": "Token refreshed successfully",
            "expires_in": result.get("expires_in")
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/users")
def admin_users():
    """Admin endpoint to view all registered users"""
    users = get_all_users()
    
    return jsonify({
        "total_users": len(users),
        "users": users
    })


@app.route("/logout")
def logout():
    """Clear session (keep tokens in database)"""
    session.clear()
    return jsonify({"message": "Logged out successfully"})


@app.route("/delete-account")
def delete_account():
    """Delete user account and tokens from database"""
    user_id = session.get("user_id")
    
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    
    delete_user_tokens(user_id)
    session.clear()
    
    return jsonify({"message": "Account and tokens deleted successfully"})


@app.route("/health")
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        user_count = get_user_count()
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "total_users": user_count
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


# ============================================
# RUN APPLICATION
# ============================================
if __name__ == "__main__":
    # Initialize database on startup
    try:
        init_db()
    except Exception as e:
        print(f"\n✗ Failed to initialize database: {e}")
        print("\nPlease ensure:")
        print("1. PostgreSQL is running")
        print("2. Database 'entra_tokens' exists")
        print("3. Connection credentials are correct")
        print("\nCreate database with: CREATE DATABASE entra_tokens;")
        exit(1)
    
    print("=" * 60)
    print("Microsoft Entra ID Multi-User Onboarding Server")
    print("PostgreSQL Edition")
    print("=" * 60)
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"Scopes: {SCOPES}")
    print("=" * 60)
    print("\n✓ PostgreSQL database initialized with encryption")
    print("✓ Multi-user support enabled")
    print("✓ Tokens are encrypted at rest")
    print("✓ Connection pooling enabled")
    print("=" * 60)
    print("\nStarting server on http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=True, port=5000)