"""
Gmail OAuth2 Authentication Helper
-----------------------------------
Handles OAuth2 flow for Gmail API access.
On first run, opens a browser for consent. Subsequent runs use cached token.
"""

import os
import stat
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

TOKEN_PATH = Path(__file__).parent.parent / "token.json"
CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials.json"

SCOPES = os.getenv(
    "GMAIL_SCOPES",
    "https://www.googleapis.com/auth/gmail.readonly,"
    "https://www.googleapis.com/auth/gmail.send,"
    "https://www.googleapis.com/auth/gmail.modify",
).split(",")


def get_gmail_credentials() -> Credentials:
    """Authenticate and return valid Gmail credentials."""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_PATH}. Download it from Google Cloud Console:\n"
                    "  1. Go to https://console.cloud.google.com/apis/credentials\n"
                    "  2. Create an OAuth 2.0 Client ID (Desktop app)\n"
                    "  3. Download JSON → save as 'credentials.json' in project root"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json())
        TOKEN_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600 — owner-only

    return creds


_gmail_service_cache = None


def get_gmail_service():
    """Return an authenticated Gmail API service client (cached)."""
    global _gmail_service_cache
    if _gmail_service_cache is None:
        creds = get_gmail_credentials()
        _gmail_service_cache = build("gmail", "v1", credentials=creds)
    return _gmail_service_cache
