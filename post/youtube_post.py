"""Upload a vertical clip to YouTube Shorts via the official YouTube Data API v3.

Setup (one-time, you do this yourself in Google Cloud Console):
  1. Create a project at console.cloud.google.com, enable "YouTube Data API v3".
  2. Create an OAuth client ID of type "Desktop app", download the JSON,
     save it where YOUTUBE_CLIENT_SECRETS_FILE (.env) points.
  3. First run opens a browser for you to grant access to your own channel;
     the resulting token is cached at YOUTUBE_TOKEN_FILE for reuse.
"""
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_credentials(client_secrets_file: str, token_file: str) -> Credentials:
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(token_file) or ".", exist_ok=True)
        with open(token_file, "w") as f:
            f.write(creds.to_json())

    return creds


def upload_short(video_path: str, title: str, description: str, tags=None, privacy_status: str = "private") -> str:
    """Uploads video_path as a YouTube Short. Returns the resulting video ID.

    privacy_status defaults to "private" -- flip to "public" yourself once
    you've reviewed the upload. Title/description should include #Shorts.
    """
    client_secrets_file = os.environ["YOUTUBE_CLIENT_SECRETS_FILE"]
    token_file = os.environ["YOUTUBE_TOKEN_FILE"]
    creds = _get_credentials(client_secrets_file, token_file)
    youtube = build("youtube", "v3", credentials=creds)

    if "#shorts" not in description.lower() and "#shorts" not in title.lower():
        description = f"{description}\n#Shorts"

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags or [],
            "categoryId": "22",
        },
        "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
    }

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True),
    )
    response = request.execute()
    return response["id"]
