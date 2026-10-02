#!/usr/bin/env python3
"""
On-demand deeper probe for selected hosts. You trigger this manually
(from the deep-probe GitHub Actions workflow) once the main pipeline's
alert has pointed you at something worth a closer look.

Usage: deep_probe.py "host1,host2,host3"   (comma or newline separated)
Env:   TG_TOKEN, TG_CHAT_ID
"""
import os
import sys

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT = os.environ["TG_CHAT_ID"]
API = f"https://api.telegram.org/bot{TG_TOKEN}"

# Light, read-only checks only — this is a triage aid, not a scanner.
PATHS = ["/admin", "/login", "/api", "/api/docs", "/swagger.json", "/graphql",
         "/.git/config", "/.env", "/actuator/health", "/actuator", "/wp-admin",
         "/.well-known/security.txt", "/robots.txt", "/sitemap.xml"]


def tg_send(text):
    requests.post(f"{API}/sendMessage", timeout=30, data={
        "chat_id": TG_CHAT, "text": text[:4000], "disable_web_page_preview": True})


def probe(host):
    base = host if host.startswith("http") else f"https://{host}"
    found = []
    for p in PATHS:
        try:
            r = requests.get(base + p, timeout=8, allow_redirects=False, verify=False)
            if r.status_code in (200, 201, 301, 302, 401, 403):
                found.append(f"{p} -> {r.status_code}")
        except requests.RequestException:
            continue
    return found


def main():
    hosts = [h.strip() for h in sys.argv[1].replace(",", "\n").splitlines() if h.strip()]
    for h in hosts:
        results = probe(h)
        if results:
            tg_send(f"[{h}] interesting paths:\n" + "\n".join(results))
        else:
            tg_send(f"[{h}] no interesting paths found in quick probe")


if __name__ == "__main__":
    main()
