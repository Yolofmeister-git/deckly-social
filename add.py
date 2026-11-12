"""Add a post to queue.json, converting its images to JPEG (the Instagram API only takes JPEG).

    python add.py <id> <at ISO with -06:00> <image|carousel|reel> <caption.txt> <file> [<file> ...]
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent


def main() -> None:
    post_id, at, kind, caption_file, *files = sys.argv[1:]
    media = []
    for i, src in enumerate(files, 1):
        src = Path(src)
        if src.suffix.lower() == ".mp4":
            name = f"{post_id}.mp4"
            shutil.copy(src, HERE / "media" / name)
        else:
            name = f"{post_id}-{i}.jpg" if len(files) > 1 else f"{post_id}.jpg"
            Image.open(src).convert("RGB").save(HERE / "media" / name, quality=92, optimize=True)
        media.append(name)
    queue = json.loads((HERE / "queue.json").read_text(encoding="utf-8"))
    queue = [p for p in queue if p["id"] != post_id]
    queue.append({"id": post_id, "at": at, "type": kind, "media": media,
                  "caption": Path(caption_file).read_text(encoding="utf-8").strip()})
    queue.sort(key=lambda p: p["at"])
    (HERE / "queue.json").write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"queued {post_id} at {at}: {len(media)} file(s)")


if __name__ == "__main__":
    main()
