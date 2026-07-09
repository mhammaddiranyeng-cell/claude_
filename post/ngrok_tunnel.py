"""Temporarily expose one local clip via ngrok so Instagram's Graph API can fetch it.

No cloud account or credit card needed -- this starts a tiny local HTTP
server for a single clip file, tunnels it through ngrok's free tier,
hands back the public URL for the duration of a `with` block, and tears
both the server and the tunnel down afterward.

Setup (one-time, free, no credit card):
  1. Sign up at https://dashboard.ngrok.com/signup
  2. Grab your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
  3. Put it in .env as NGROK_AUTHTOKEN=...
"""
import functools
import http.server
import os
import shutil
import tempfile
import threading
from contextlib import contextmanager

from pyngrok import conf, ngrok


class _ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


@contextmanager
def serve_clip_publicly(local_path: str):
    conf.get_default().auth_token = os.environ["NGROK_AUTHTOKEN"]

    tmp_dir = tempfile.mkdtemp()
    served_name = "clip.mp4"
    shutil.copy(local_path, os.path.join(tmp_dir, served_name))

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp_dir)
    # Threading server: Instagram's fetcher may open multiple/concurrent
    # connections (e.g. a HEAD probe plus range-based GETs); the plain
    # single-threaded TCPServer handled these badly, cutting transfers off
    # with a broken pipe partway through -- which corrupted the video Meta
    # received and made their processing fail downstream.
    httpd = _ThreadingHTTPServer(("localhost", 0), handler)
    port = httpd.server_address[1]

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    tunnel = ngrok.connect(port, "http")
    public_url = tunnel.public_url.replace("http://", "https://")

    try:
        yield f"{public_url}/{served_name}"
    finally:
        ngrok.disconnect(tunnel.public_url)
        httpd.shutdown()
        shutil.rmtree(tmp_dir, ignore_errors=True)
