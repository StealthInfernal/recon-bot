#!/usr/bin/env python3
"""
Recon pipeline for one domain: enumerate -> resolve -> probe -> diff -> tag -> notify -> save state.

Usage: pipeline.py <domain>
Env:   TG_TOKEN, TG_CHAT_ID   (required)
       STATE_DIR  (default: state)
       SCRIPT_DIR (default: directory this file lives in)

State is kept per domain in STATE_DIR/<domain>.json — a dict of
hostname -> {resolved, status, title, tech, first_seen, last_seen}.
The first run for a domain saves a silent baseline. After that, only
new or changed hosts trigger a Telegram message.
"""
import json
import os
import re
import subprocess
import sys
import time

import requests

STATE_DIR = os.environ.get("STATE_DIR", "state")
SCRIPT_DIR = os.environ.get("SCRIPT_DIR", os.path.dirname(os.path.abspath(__file__)))
TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT = os.environ["TG_CHAT_ID"]
API = f"https://api.telegram.org/bot{TG_TOKEN}"

# Keywords that bump priority — tune these to your targets over time.
HIGH_HOST_KW = ["admin", "internal", "vpn", "jenkins", "grafana", "kibana", "sso",
                "staging", "stage", "uat", "dev", "test", "actuator", "debug"]
HIGH_TITLE_KW = ["login", "sign in", "dashboard", "jenkins", "grafana", "kibana",
                 "swagger", "graphql", "api docs", "actuator"]
MED_HOST_KW = ["api", "graphql", "gateway", "portal"]

# CNAME targets commonly associated with subdomain takeover when the
# subdomain itself does not resolve (NXDOMAIN). This is a hint, not proof —
# always verify manually before reporting.
TAKEOVER_SIGS = ["s3.amazonaws.com", "github.io", "herokuapp.com", "azurewebsites.net",
                 "cloudfront.net", "wordpress.com", "zendesk.com", "surge.sh",
                 "bitbucket.io", "shopify.com", "fastly.net", "wpengine.com"]


def tg_send(text):
    requests.post(f"{API}/sendMessage", timeout=30, data={
        "chat_id": TG_CHAT, "text": text[:4000], "disable_web_page_preview": True})


def tg_file(path, caption=""):
    with open(path, "rb") as f:
        requests.post(f"{API}/sendDocument", timeout=60,
                      data={"chat_id": TG_CHAT, "caption": caption}, files={"document": f})


def run(cmd, input_text=None, timeout=1800):
    r = subprocess.run(cmd, input=input_text, capture_output=True, text=True, timeout=timeout)
    return r.stdout


def load_state(domain):
    p = f"{STATE_DIR}/{domain}.json"
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}


def save_state(domain, state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(f"{STATE_DIR}/{domain}.json", "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)


def priority(host, status, title):
    title = (title or "").lower()
    score = "low"
    if any(k in host for k in HIGH_HOST_KW) or any(k in title for k in HIGH_TITLE_KW):
        score = "high"
    elif any(k in host for k in MED_HOST_KW):
        score = "medium"
    if status in (401, 403) and score == "low":
        score = "medium"
    return score


def parse_httpx_line(line):
    try:
        d = json.loads(line)
    except Exception:
        return None
    cname = d.get("cname")
    if isinstance(cname, list):
        cname = cname[0] if cname else None
    return {
        "url": d.get("url") or d.get("input"),
        "status": d.get("status_code"),
        "title": d.get("title", ""),
        "tech": ",".join(d.get("tech", []) or []),
        "cname": cname,
    }


def check_dangling(host):
    """Best-effort: does a non-resolving host's CNAME point at a service
    known to be takeover-prone? Returns the CNAME if so, else None."""
    out = run(["dig", "+short", "CNAME", host])
    lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
    if not lines:
        return None
    cname = lines[-1]
    return cname if any(sig in cname for sig in TAKEOVER_SIGS) else None


def main():
    domain = sys.argv[1].strip().lower()
    now = int(time.time())
    state = load_state(domain)
    is_baseline = len(state) == 0

    raw = run(["bash", f"{SCRIPT_DIR}/enumerate.sh", domain])
    hosts = sorted(set(h for h in raw.splitlines() if h))
    if not hosts:
        tg_send(f"[{domain}] enumeration returned nothing this run")
        return

    resolved = run(["dnsx", "-silent"], input_text="\n".join(hosts)).splitlines()
    resolved = sorted(set(h.strip() for h in resolved if h.strip()))
    resolved_set = set(resolved)

    probed = {}
    if resolved:
        httpx_out = run(["httpx", "-silent", "-json", "-sc", "-title", "-td", "-cname",
                          "-timeout", "8", "-threads", "50"], input_text="\n".join(resolved))
        for line in httpx_out.splitlines():
            parsed = parse_httpx_line(line)
            if parsed and parsed["url"]:
                h = re.sub(r"^https?://", "", parsed["url"]).rstrip("/")
                probed[h] = parsed

    new_hosts, changed_hosts = [], []
    updated_state = dict(state)

    for h in hosts:
        p = probed.get(h)
        prev = state.get(h)
        entry = {
            "resolved": h in resolved_set,
            "status": p["status"] if p else None,
            "title": p["title"] if p else None,
            "tech": p["tech"] if p else None,
            "first_seen": prev["first_seen"] if prev else now,
            "last_seen": now,
        }
        if not prev:
            new_hosts.append((h, entry))
        elif p and (prev.get("status") != entry["status"] or prev.get("title") != entry["title"]):
            changed_hosts.append((h, prev, entry))
        updated_state[h] = entry

    save_state(domain, updated_state)

    if is_baseline:
        tg_send(f"[{domain}] baseline saved: {len(hosts)} subdomains, {len(resolved)} resolving")
        return

    if not new_hosts and not changed_hosts:
        return  # quiet run — nothing to report

    order = {"high": 0, "medium": 1, "low": 2}
    lines = [f"[{domain}] {len(new_hosts)} new, {len(changed_hosts)} changed"]

    tagged_new = []
    for h, e in new_hosts:
        pr = priority(h, e["status"], e["title"])
        reason = ""
        if not e["resolved"]:
            cname = check_dangling(h)
            if cname:
                pr = "high"
                reason = f" (CNAME -> {cname}, check for takeover)"
        tagged_new.append((pr, h, e, reason))
    tagged_new.sort(key=lambda x: order[x[0]])

    for pr, h, e, reason in tagged_new:
        status = e["status"] or ("resolves, no http" if e["resolved"] else "NXDOMAIN")
        lines.append(f"[{pr.upper()}] {h} — {status} {e['title'] or ''}{reason}".rstrip())

    for h, prev, e in changed_hosts:
        lines.append(f"[CHANGED] {h} — {prev.get('status')} -> {e['status']} | {e['title'] or ''}".rstrip())

    msg = "\n".join(lines)
    if len(msg) < 3800:
        tg_send(msg)
    else:
        path = f"/tmp/{domain}_alert.txt"
        with open(path, "w") as f:
            f.write(msg)
        tg_send(f"[{domain}] {len(new_hosts)} new, {len(changed_hosts)} changed (full list attached)")
        tg_file(path, f"{domain} alert")


if __name__ == "__main__":
    main()
