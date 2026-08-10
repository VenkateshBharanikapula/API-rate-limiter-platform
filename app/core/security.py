"""
Security helpers.

Currently just secure API key generation (Module: "Secure API Key
Generation" -- uses secrets.token_urlsafe() per the spec). Kept in its own
module so auth-adjacent concerns aren't scattered across services.
"""

import secrets

# 32 random bytes -> ~43 url-safe base64 characters. Comfortably fits the
# api_key VARCHAR(64) column with room to spare, and token_urlsafe's output
# alphabet (A-Za-z0-9_-) is safe to put straight into an HTTP header.
API_KEY_BYTES = 32


def generate_api_key() -> str:
    """Generate a cryptographically secure, URL-safe API key."""
    return secrets.token_urlsafe(API_KEY_BYTES)
