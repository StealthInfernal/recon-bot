# recon-bot

Mobile-controlled subdomain discovery with priority-tagged Telegram alerts.
Runs entirely on GitHub Actions — no server, VPS or laptop needed.

## How it works

1. **recon.yml** runs every 6 hours (and on demand). For each domain in
   `targets.txt` it enumerates subdomains (subfinder, assetfinder, crt.sh),
   resolves them (dnsx), probes the live ones (httpx: status/title/tech),
   and diffs against the saved state in `state/<domain>.json`.
2. The **first run** for a domain is a silent baseline — no alert, just
   a saved snapshot. After that, you only hear about:
   - **new hosts**, tagged `HIGH` / `MEDIUM` / `LOW` by keyword and status
     (admin/dev/staging panels, login pages, swagger/graphql, 401/403, etc.)
   - **changed hosts** — an existing host whose status code or title changed
   - **possible dangling CNAMEs** — a new hostname that doesn't resolve but
     has a CNAME pointing at a takeover-prone service (S3, GitHub Pages,
     Heroku, Azure, etc.) — flagged HIGH, always verify manually
3. **deepprobe.yml** is a separate, manual-only workflow. You pick hosts
   from an alert and run it to check a short list of common paths
   (admin, login, swagger, .git/config, .env, actuator, etc.) — read-only,
   no scanning.

## One-time setup

1. Create a **private** GitHub repo and upload everything in this folder,
   keeping the `.github/workflows/` path exactly as is.
2. Message **@BotFather** on Telegram → `/newbot` → copy the token.
3. Message **@userinfobot** on Telegram → copy your numeric chat ID.
4. In the repo: Settings → Secrets and variables → Actions → add:
   - `TG_TOKEN` = your bot token
   - `TG_CHAT_ID` = your chat ID
5. Edit `targets.txt`, one in-scope domain per line.

## Using it from your phone

- **Test it:** Actions tab → "recon" → Run workflow → leave domain blank
  (scans everything in `targets.txt`) or type one domain to add + scan it.
- **Ongoing alerts:** nothing to do — the schedule runs itself, Telegram
  pings you only when something is new or changed.
- **Investigate a lead:** Actions tab → "deep-probe" → Run workflow →
  paste the host(s) from an alert (comma or newline separated).

## Notes and limits

- Keep this to passive enumeration, DNS resolution and light HTTP probing.
  Heavy scanning or brute-forcing from GitHub's runners can violate their
  terms and risks your account — do that by hand, from your own connection,
  only against confirmed in-scope targets.
- State lives in the repo under `state/`. The workflow commits it back
  after every run, so history and diffs are all in your git log too.
- Free GitHub plans include 2,000 Actions minutes/month on private repos.
  A full run is a few minutes per domain; scanning a handful of domains
  every 6 hours comfortably fits. If you add many targets, switch the
  cron in `recon.yml` to `0 */12 * * *`.
- Dangling-CNAME and path-probe hits are leads, not findings — always
  confirm manually before reporting anything.
