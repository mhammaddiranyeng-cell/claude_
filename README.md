# Video Clipper — ContentRewards Automation

Automates the parts of a clipping workflow that are safe to automate, and
deliberately leaves the risky parts (logging into ContentRewards, joining
campaigns) as a manual, one-click human step. See "Why not fully automate
ContentRewards itself?" below before changing that.

## Pipeline

```
source video (from a campaign brief)
        |
        v
  src/pipeline.py
        |  transcribe -> pick highlight windows -> cut -> reframe to 9:16 -> burn captions
        v
  output/manifest.json + output/clip_XX_final.mp4  (review these yourself)
        |
        v
  post/scheduler.py --manifest ... --index N --platforms youtube,tiktok,instagram
        |  uploads via each platform's OFFICIAL API, as PRIVATE/SELF_ONLY by default
        v
  you review the live post, flip it public yourself, then submit the post URL
  to the campaign on contentrewards.com manually
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# ffmpeg must be installed on the system separately (not a pip package):
#   macOS: brew install ffmpeg   |  Ubuntu: apt install ffmpeg

cp config.example.yaml config.yaml   # edit per campaign: hashtags, trigger phrases, etc.
cp .env.example .env                 # fill in after doing the account setup below
```

### 1. Editing pipeline — no accounts needed

```bash
python -m src.pipeline --input /path/to/campaign_source.mp4 --config config.yaml
```

Produces vertical, captioned clips + a `manifest.json` with suggested captions.
**Review every clip before posting** — the highlight-picking is a heuristic
(trigger phrases + speech density), not perfect judgment.

### 2. Social accounts + API credentials (you do this part yourself)

These require your own identity/phone/business verification, so I can't do
them for you — but here's exactly what each one needs:

**YouTube (fastest, do this first)**
1. Go to [console.cloud.google.com](https://console.cloud.google.com), create a project.
2. Enable "YouTube Data API v3".
3. Create OAuth credentials → OAuth client ID → type "Desktop app" → download the JSON.
4. Put its path in `.env` as `YOUTUBE_CLIENT_SECRETS_FILE`.
5. First upload will open a browser for you to authorize your own channel.

**TikTok**
1. Create a developer account at [developers.tiktok.com](https://developers.tiktok.com).
2. Create an app, request the `video.publish` scope.
3. Complete their OAuth authorization-code flow once for your own account to get
   an access/refresh token; put them in `.env`.
4. **Until TikTok audits your app, you can only post as `SELF_ONLY` (private)** —
   this is enforced on their end, not something we can bypass. Public posting
   requires their app review process to complete.

**Instagram (Reels)**
1. Your IG account needs to be a Business or Creator account.
2. Create a Meta app at [developers.facebook.com](https://developers.facebook.com), add Instagram Graph API.
3. Get a long-lived access token with `instagram_content_publish` + your IG Business Account ID.
4. Graph API fetches the video from a **public URL** you provide — it doesn't accept
   direct file uploads. You'll need to host the rendered clip somewhere reachable
   (a private S3/GCS bucket with a signed URL works fine) before calling `publish_reel`.

### 3. Posting

```bash
python -m post.scheduler --manifest output/manifest.json --index 1 --platforms youtube,tiktok
```

Uploads default to private/self-only. Review the actual upload, then flip it
public yourself (YouTube Studio, or once your TikTok app is audited).

### 4. Campaign notifier (optional, best-effort)

```bash
python -m notifier.whop_notifier
```

Checks `contentrewards.com/discover` for campaign titles you haven't seen
before and prints them — **it does not log in, join, or submit anything.**
Two important caveats:

- The preferred path is Whop's official REST API (`docs.whop.com`) — Content
  Rewards runs on Whop's platform and Whop has a documented API + SDK. The
  endpoint in `whop_notifier.py` is a **placeholder** — I couldn't reach
  `docs.whop.com` to confirm the exact path/response shape from this sandbox,
  so verify it yourself against the API reference (with your `WHOP_API_KEY`)
  before relying on it.
- The HTML-scraping fallback is best-effort against a Cloudflare-protected,
  JS-rendered page — it may break or get blocked. If it stops working, that's
  a signal to check the page manually, not a bug to route around aggressively
  (retrying harder against anti-bot protection is exactly the kind of
  "behavioral pattern" that gets accounts flagged).

## Why not fully automate ContentRewards itself?

ContentRewards' Terms of Service (for clippers) explicitly maintains a
**Bot Score / Trust Score** per submission based on account authenticity and
*behavioral patterns*, and states that automation used to inflate views, or
any attempt to circumvent enforcement, results in a permanent ban and
forfeited earnings. There's no public API for joining campaigns or
submitting clips (only the general Whop API, which may or may not expose
this). A browser bot clicking through campaign selection doesn't look human
and risks tanking your Trust Score — which kills the income stream this is
supposed to build. Keeping campaign selection/joining/submission manual
avoids that risk entirely; it's also just a few clicks, so there's little
time saved by automating it anyway.
