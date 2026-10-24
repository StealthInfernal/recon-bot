#!/usr/bin/env python3
"""
On-demand Wayback Machine URL discovery for a program's already-known
subdomains. You trigger this manually (via the "wayback-urls" GitHub
Actions workflow, or the /wayback Telegram command through the
Cloudflare worker) once the main pipeline has built up a subdomain list
for a program.

It does NOT do its own subdomain enumeration — it reads the hostnames
recon.py already found in programs/<program>/assets.json and feeds those
into `waybackurls`. This is read-only passive OSINT against archive.org,
not active scanning, so it's safe to run any time.

Usage: wayback_scan.py <program>
Env:   TG_TOKEN, TG_CHAT_ID (required)
       PROGRAMS_DIR (default: programs)

Output: programs/<program>/wayback_urls.txt (overwritten each run — the
previous version is diffed first so only genuinely new URLs get a
separate alert; the full current list is always attached as a file).
"""
import datetime
import json
import os
import subprocess
import sys

import requests

PROGRAMS_DIR = os.environ.get("PROGRAMS_DIR", "programs")
TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT = os.environ["TG_CHAT_ID"]
API = f"https://api.telegram.org/bot{TG_TOKEN}"

MAX_PREVIEW_URLS = 40


def tg_send(text):
    requests.post(f"{API}/sendMessage", timeout=30, data={
        "chat_id": TG_CHAT, "text": text[:4000], "disable_web_page_preview": True})


def tg_file(path, caption=""):
    with open(path, "rb") as f:
        requests.post(f"{API}/sendDocument", timeout=60,
                      data={"chat_id": TG_CHAT, "caption": caption}, files={"document": f})


def load_hosts(program):
    """Hosts recon.py already found for this program, i.e. "the latest
    subs it got" — this is what makes a separate subdomain pass
    unnecessary here."""
    assets_path = f"{PROGRAMS_DIR}/{program}/assets.json"
    if not os.path.exists(assets_path):
        return None
    with open(assets_path) as f:
        data = json.load(f)
    return sorted(data.keys())


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        tg_send("Usage: wayback_scan.py <program>  (program must already have a saved scan)")
        return
    program = sys.argv[1].strip().lower()

    hosts = load_hosts(program)
    if hosts is None:
        tg_send(f"[{program}] no saved subdomains yet — run a recon scan for it first")
        return
    if not hosts:
        tg_send(f"[{program}] subdomain list for this program is empty")
        return

    out_dir = f"{PROGRAMS_DIR}/{program}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/wayback_urls.txt"

    prev_urls = set()
    if os.path.exists(out_path):
        with open(out_path) as f:
            prev_urls = set(line.strip() for line in f if line.strip())

    # cat subs | waybackurls, done in-process via stdin/stdout
    result = subprocess.run(
        ["waybackurls"],
        input="\n".join(hosts),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    urls = sorted(set(line.strip() for line in result.stdout.splitlines() if line.strip()))

    if not urls:
        tg_send(f"[{program}] waybackurls returned nothing for {len(hosts)} known subdomains")
        return

    with open(out_path, "w") as f:
        f.write("\n".join(urls) + "\n")

    new_urls = sorted(set(urls) - prev_urls)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    tg_send(
        f"[{program}] wayback scan: {len(urls)} total URLs "
        f"({len(new_urls)} new) from {len(hosts)} known subdomains — saved to wayback_urls.txt"
    )
    tg_file(out_path, f"{program} wayback urls — {now_iso}")

    if new_urls:
        preview = "\n".join(new_urls[:MAX_PREVIEW_URLS])
        more = f"\n...+{len(new_urls) - MAX_PREVIEW_URLS} more in the attached file" \
            if len(new_urls) > MAX_PREVIEW_URLS else ""
        tg_send(f"[{program}] new URLs since the last wayback run:\n{preview}{more}")


if __name__ == "__main__":
    main()
