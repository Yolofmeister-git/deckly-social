"""Publish Deckly's scheduled Instagram posts through the official Instagram API.

Runs every 15 minutes from GitHub Actions. A post in queue.json goes out once its time has
passed, at most MAX_LATE after it (so a long outage never dumps old posts at once), and never
twice: every published post is recorded in published.json, which the workflow commits back.

    python publish.py            # publish what is due
    python publish.py --dry-run  # only print what would be published
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRAPH = "https://graph.facebook.com/v23.0"
MAX_LATE = timedelta(hours=6)

TOKEN = os.environ["IG_TOKEN"]
USER = os.environ["IG_USER_ID"]
MEDIA_BASE = os.environ["MEDIA_BASE"].rstrip("/")


def api(method: str, path: str, **params) -> dict:
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f"{GRAPH}/{path}"
    if method == "GET":
        url, data = f"{url}?{data.decode()}", None
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode()}") from None


def wait_ready(container: str, minutes: int = 10) -> None:
    for _ in range(minutes * 6):
        status = api("GET", container, fields="status_code,status")
        if status.get("status_code") == "FINISHED":
            return
        if status.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {container} failed: {status}")
        time.sleep(10)
    raise RuntimeError(f"container {container} not ready after {minutes} min")


def url_of(name: str) -> str:
    return f"{MEDIA_BASE}/media/{urllib.parse.quote(name)}"


def publish(post: dict) -> dict:
    kind, media, caption = post["type"], post["media"], post["caption"]
    if kind == "image":
        container = api("POST", f"{USER}/media", image_url=url_of(media[0]), caption=caption)["id"]
    elif kind == "carousel":
        children = [api("POST", f"{USER}/media", image_url=url_of(m), is_carousel_item="true")["id"]
                    for m in media]
        for child in children:
            wait_ready(child)
        container = api("POST", f"{USER}/media", media_type="CAROUSEL",
                         children=",".join(children), caption=caption)["id"]
    elif kind == "reel":
        container = api("POST", f"{USER}/media", media_type="REELS", video_url=url_of(media[0]),
                        caption=caption, share_to_feed="true")["id"]
    else:
        raise ValueError(f"unknown post type {kind!r}")
    wait_ready(container)
    media_id = api("POST", f"{USER}/media_publish", creation_id=container)["id"]
    link = api("GET", media_id, fields="permalink").get("permalink")
    return {"media_id": media_id, "permalink": link}


def main() -> int:
    dry = "--dry-run" in sys.argv
    queue = json.loads((HERE / "queue.json").read_text(encoding="utf-8"))
    done_path = HERE / "published.json"
    done = json.loads(done_path.read_text(encoding="utf-8")) if done_path.exists() else {}
    now = datetime.now(timezone.utc)
    failed = False
    for post in queue:
        if post["id"] in done:
            continue
        at = datetime.fromisoformat(post["at"])
        if at > now:
            print(f"waiting  {post['id']} at {post['at']}")
            continue
        if now - at > MAX_LATE:
            print(f"SKIPPED  {post['id']}: more than {MAX_LATE} late, not publishing old posts")
            continue
        if dry:
            print(f"would publish {post['id']} ({post['type']}, {len(post['media'])} file(s))")
            continue
        try:
            result = publish(post)
        except Exception as e:  # keep going with the rest; the run is marked failed below
            print(f"FAILED   {post['id']}: {e}")
            failed = True
            continue
        done[post["id"]] = {**result, "published_at": now.isoformat()}
        done_path.write_text(json.dumps(done, indent=2) + "\n", encoding="utf-8")
        print(f"PUBLISHED {post['id']} -> {result['permalink']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
