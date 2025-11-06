#!/usr/bin/env python3
"""
Minimal Authorization Code Flow (Flask) example using MSAL.

- Uses ConfidentialClientApplication (client secret) for a web app flow.
- Endpoints:
  /           - simple index with login link
  /login      - redirects user to Azure AD sign-in (authorization endpoint)
  /getAToken  - redirected to by Azure AD with code; exchanges code for tokens
- Persists token cache to token_cache.bin
- Calls Microsoft Graph /me as example protected resource
"""

import json
import sys
from pathlib import Path

from flask import Flask, redirect, request, session, url_for
import msal
import requests

# Configuration paths
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
CACHE_PATH = BASE_DIR / "token_cache.bin"
SECRET_KEY = "dev-secret-for-session"  # For demonstration only. Use a secure secret in production.

app = Flask(__name__)
app.secret_key = SECRET_KEY


def load_config():
    if not CONFIG_PATH.exists():
        print("Missing config.json. Copy config.example.json -> config.json and fill values.")
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def load_cache():
    cache = msal.SerializableTokenCache()
    if CACHE_PATH.exists():
        data = CACHE_PATH.read_text()
        cache.deserialize(data)
    return cache


def save_cache(cache):
    if cache.has_state_changed:
        serialized = cache.serialize()
        # Handle both string and bytes
        if isinstance(serialized, str):
            CACHE_PATH.write_text(serialized)
        else:
            CACHE_PATH.write_bytes(serialized)


config = load_config()
CLIENT_ID = config["client_id"]
CLIENT_SECRET = config.get("client_secret")
TENANT = config.get("tenant_id")
AUTHORITY = config.get("authority") or f"https://login.microsoftonline.com/{TENANT}"
SCOPES = config.get("scopes", ["User.Read"])
REDIRECT_URI = config.get("redirect_uri", "http://localhost:5000/getAToken")

if not CLIENT_SECRET:
    print("This example uses a confidential client and requires client_secret in config.json.")
    sys.exit(1)

# Application-level cache and MSAL app factory
def _build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=AUTHORITY,
        token_cache=cache,
    )


@app.route("/")
def index():
    cache = load_cache()
    msal_app = _build_msal_app(cache=cache)
    
    # Check if we have cached tokens
    accounts = msal_app.get_accounts()
    if accounts:
        # Try to get a token silently from cache
        result = msal_app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            return (
                "<h2>MSAL Authorization Code Flow (Flask)</h2>"
                f"<p>Already signed in as: <strong>{accounts[0].get('username')}</strong></p>"
                '<p><a href="/profile">View Profile</a> | <a href="/logout">Sign Out</a></p>'
            )
    
    return (
        "<h2>MSAL Authorization Code Flow (Flask)</h2>"
        '<a href="/login">Sign in with Azure AD</a>'
    )


@app.route("/login")
def login():
    cache = load_cache()
    msal_app = _build_msal_app(cache=cache)
    # Get an authorization request URL and redirect the user
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    # Save any intermediate state in session if desired (not required here)
    session["state"] = "auth_state_demo"
    return redirect(auth_url)


@app.route("/profile")
def profile():
    cache = load_cache()
    msal_app = _build_msal_app(cache=cache)
    
    # Get cached account
    accounts = msal_app.get_accounts()
    if not accounts:
        return redirect(url_for("index"))
    
    # Try to get token silently from cache
    result = msal_app.acquire_token_silent(SCOPES, account=accounts[0])
    
    # If silent acquisition failed, redirect to login
    if not result or "access_token" not in result:
        return redirect(url_for("login"))
    
    access_token = result["access_token"]
    
    # Call Microsoft Graph
    print(f"Making Graph API call with token: {access_token[:20]}...")
    try:
        resp = requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": "Bearer " + access_token},
        )
        print(f"Graph API response status: {resp.status_code}")
    except Exception as e:
        print(f"Error calling Graph API: {e}")
        return f"Error calling Graph API: {str(e)}", 500
    
    if resp.status_code == 200:
        profile = resp.json()
        display = (
            f"<h3>Signed in as: {profile.get('displayName') or profile.get('userPrincipalName')}</h3>"
            f"<pre>{json.dumps(profile, indent=2)}</pre>"
            '<p><a href="/">Home</a> | <a href="/logout">Sign Out</a></p>'
        )
        return display
    else:
        return f"Graph API error: {resp.status_code} - {resp.text}", 500


@app.route("/logout")
def logout():
    cache = load_cache()
    accounts = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=AUTHORITY,
        token_cache=cache,
    ).get_accounts()
    
    if accounts:
        # Remove account from cache
        for account in accounts:
            msal.ConfidentialClientApplication(
                client_id=CLIENT_ID,
                client_credential=CLIENT_SECRET,
                authority=AUTHORITY,
                token_cache=cache,
            ).remove_account(account)
        save_cache(cache)
    
    session.clear()
    return redirect(url_for("index"))


@app.route("/getAToken")
def authorized():
    error = request.args.get("error")
    if error:
        error_description = request.args.get("error_description")
        return f"Error returned from authorization server: {error} - {error_description}", 400

    code = request.args.get("code")
    if not code:
        return "Missing authorization code in response.", 400

    cache = load_cache()
    msal_app = _build_msal_app(cache=cache)

    # Exchange authorization code for tokens
    result = msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    if "error" in result:
        return (
            f"Failed to acquire token: {result.get('error')} - {result.get('error_description')}",
            400,
        )

    # Persist cache if changed
    save_cache(cache)

    # Redirect to profile page
    return redirect(url_for("profile"))


if __name__ == "__main__":
    # Run on localhost:5000
    app.run(host="0.0.0.0", port=8000, debug=True)