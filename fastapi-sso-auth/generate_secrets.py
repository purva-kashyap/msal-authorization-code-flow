"""
Quick setup script to generate required secrets.
Run this once before starting the application.
"""
from cryptography.fernet import Fernet
import secrets

print("=" * 60)
print("FastAPI SSO - Secret Generation")
print("=" * 60)
print()
print("Add these to your .env file:")
print()
print(f"ENCRYPTION_KEY={Fernet.generate_key().decode()}")
print(f"SECRET_KEY={secrets.token_urlsafe(32)}")
print()
print("=" * 60)
