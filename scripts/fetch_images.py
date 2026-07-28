#!/usr/bin/env python3
"""Download all sign images listed in data/signs_full.json into assets/img/.
Run on a machine with internet access. Safe to re-run: skips existing files.
Usage: python3 scripts/fetch_images.py [--force]"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "signs_full.json")
FORCE = "--force" in sys.argv

def encode_url(url):
    """Percent-encode non-ASCII characters: some filenames on driving.cy contain
    an en-dash, which urllib cannot put into a request line as-is."""
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((
        p.scheme,
        p.netloc.encode("idna").decode("ascii"),
        urllib.parse.quote(p.path, safe="/%"),
        urllib.parse.quote(p.query, safe="=&%"),
        p.fragment,
    ))

def main():
    with open(DATA, encoding="utf-8") as f:
        cards = json.load(f)["cards"]
    ok = skip = fail = 0
    failures = []
    for c in cards:
        dst = os.path.join(ROOT, c["image"])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst) and not FORCE:
            skip += 1
            continue
        req = urllib.request.Request(
            encode_url(c["image_url"]),
            headers={"User-Agent": "Mozilla/5.0 (personal study flashcards fetcher)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r, open(dst, "wb") as out:
                out.write(r.read())
            ok += 1
            time.sleep(0.3)  # be polite to the server
        except Exception as e:
            fail += 1
            failures.append((c["id"], c["image_url"], str(e)))
    print(f"downloaded={ok} skipped={skip} failed={fail}")
    for fid, url, err in failures:
        print(f"  FAIL {fid}: {url} ({err})")
    if fail:
        sys.exit(1)

if __name__ == "__main__":
    main()
