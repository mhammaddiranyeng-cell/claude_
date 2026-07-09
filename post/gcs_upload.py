"""Upload a local clip to Google Cloud Storage and return a signed URL.

Instagram's Graph API needs a public URL to fetch the video from -- it
doesn't accept direct file uploads. This handles that by uploading to a
private GCS bucket and signing a temporary URL, so the bucket itself
never needs to be public.

Setup (one-time, you do this yourself, in the same Google Cloud project
you already made for YouTube):
  1. Enable the Cloud Storage API, then create a bucket
     (Cloud Storage -> Buckets -> Create). Any region/default settings
     are fine; keep it private (do not make it public).
  2. Create a service account (IAM & Admin -> Service Accounts) and grant
     it the "Storage Object Admin" role, scoped to that bucket.
  3. Create + download a JSON key for that service account.
  4. In .env, set:
       GCS_BUCKET_NAME=your-bucket-name
       GCS_SERVICE_ACCOUNT_FILE=./secrets/gcs_service_account.json
"""
import os
import time
import uuid
from datetime import timedelta

from google.cloud import storage


def upload_and_sign(local_path: str, expiration_hours: int = 24, max_attempts: int = 3) -> str:
    bucket_name = os.environ["GCS_BUCKET_NAME"]
    key_file = os.environ["GCS_SERVICE_ACCOUNT_FILE"]

    client = storage.Client.from_service_account_json(key_file)
    bucket = client.bucket(bucket_name)

    blob_name = f"clips/{uuid.uuid4().hex}_{os.path.basename(local_path)}"
    blob = bucket.blob(blob_name)
    # A single continuous request for a 50MB+ file doesn't survive some
    # networks (connection reset mid-transfer, unrelated to the timeout
    # value). Setting chunk_size forces the resumable-upload protocol to
    # split it into small requests, each retried independently on failure.
    blob.chunk_size = 5 * 1024 * 1024  # 5MB

    # Even chunked, some networks still drop a chunk's write mid-transfer
    # intermittently (observed: succeeds most of the time, occasionally
    # times out with no HTTP status at all) -- retrying the whole upload a
    # couple of times covers that instead of failing the post outright.
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            blob.upload_from_filename(local_path, content_type="video/mp4", timeout=(30, 600))
            last_error = None
            break
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                wait = 3 * attempt
                print(f"    GCS upload attempt {attempt} failed ({e}); retrying in {wait}s ...")
                time.sleep(wait)
    if last_error:
        raise RuntimeError(f"GCS upload failed after {max_attempts} attempts: {last_error}")

    return blob.generate_signed_url(expiration=timedelta(hours=expiration_hours), version="v4")
