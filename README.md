```markdown
# MSAL Python — Authorization Code Flow (Flask) Example

This is a minimal example showing the Authorization Code flow (web/server) with the msal Python library.

Files:
- auth_code_flow.py — Flask app demonstrating the auth code flow
- config.example.json — example config values
- requirements.txt — required packages

Quick setup:
1. Register an app in Azure AD:
   - Platform: Web
   - Redirect URI: http://localhost:5000/getAToken
   - Under "Certificates & secrets" create a client secret and copy it.
   - Add API permissions (e.g., Microsoft Graph -> Delegated -> User.Read) and grant consent.

2. Copy config.example.json -> config.json and fill in:
   - client_id
   - tenant_id (or use "common" if desired)
   - client_secret
   - redirect_uri (must match the registered redirect URI)
   - scopes (e.g., ["User.Read"])

3. Install dependencies:
   pip install -r requirements.txt

4. Run the app:
   python auth_code_flow.py

5. Open browser to:
   http://localhost:5000/login
   Sign in, consent, and you'll be redirected to /getAToken which will display the user's profile.

Notes:
- Token cache is saved to token_cache.bin so subsequent runs can reuse tokens.
- For public clients (no client secret) use PKCE and a PublicClientApplication; this example demonstrates the server-side confidential client usage.
```