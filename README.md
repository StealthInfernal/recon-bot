# recon-bot

Mobile-controlled subdomain discovery with priority-tagged Telegram alerts.
Runs entirely on GitHub Actions — no server, VPS or laptop needed.

## How it works

1. **recon.yml** runs every 6 hours (and on demand). For each domain in
   `targets.txt` it enumerates subdomains (subfinder, assetfinder, crt.sh),
   resolves them (dnsx), probes the live ones (httpx: status/title/tech),
   and diffs against the saved state for that program.
2. State is kept per **program** (target organization) under `programs/<name>/`:
   - `assets.json` — current known hosts and their last-seen details
   - `history.json` — one entry per scan: date, total asset count, how many
     were new, how many changed, and the actual hostnames for both
   - `programs/index.json` — a top-level list of every program with its
     last scan date and asset count, for the dashboard
3. The **first run** for a program is a silent baseline — no alert, just
   a saved snapshot. After that, you only hear about:
   - **new hosts**, tagged `HIGH` / `MEDIUM` / `LOW` by keyword and status
     (admin/dev/staging panels, login pages, swagger/graphql, 401/403, etc.)
   - **changed hosts** — an existing host whose status code or title changed
   - **possible dangling CNAMEs** — a new hostname that doesn't resolve but
     has a CNAME pointing at a takeover-prone service (S3, GitHub Pages,
     Heroku, Azure, etc.) — flagged HIGH, always verify manually
4. **deepprobe.yml** is a separate, manual-only workflow. You pick hosts
   from an alert and run it to check a short list of common paths
   (admin, login, swagger, .git/config, .env, actuator, etc.) — read-only,
   no scanning.
5. **index.html** is a dashboard, hosted free with GitHub Pages. It reads
   `programs/index.json` and each program's `history.json` directly — no
   backend. Click a program to see its scan timeline; click a date to
   expand which hosts were new or changed that run.
6. **cloudflare-worker/** is optional: it lets you message your Telegram
   bot `/scan example.com` directly, instead of opening GitHub Actions to
   trigger a scan. See that folder's own README to set it up.

## One-time setup

1. Create a **private** GitHub repo and upload everything in this folder,
   keeping the `.github/workflows/` path exactly as is.
2. Message **@BotFather** on Telegram → `/newbot` → copy the token.
3. Message **@userinfobot** on Telegram → copy your numeric chat ID.
4. In the repo: Settings → Secrets and variables → Actions → add:
   - `TG_TOKEN` = your bot token
   - `TG_CHAT_ID` = your chat ID
5. Edit `targets.txt`, one in-scope domain per line.
6. Turn on the dashboard: Settings -> Pages -> Source: "Deploy from a
   branch" -> Branch: `main`, folder `/ (root)` -> Save. GitHub gives you
   a URL like `https://<you>.github.io/<repo>/` — that's your dashboard,
   bookmark it on your phone. It updates automatically as scans run.

## Using it from your phone

- **Test it:** Actions tab → "recon" → Run workflow → leave domain blank
  (scans everything in `targets.txt`) or type one domain to add + scan it.
- **Ongoing alerts:** nothing to do — the schedule runs itself, Telegram
  pings you only when something is new or changed.
- **Investigate a lead:** Actions tab → "deep-probe" → Run workflow →
  paste the host(s) from an alert (comma or newline separated).
- **Trigger a scan without opening GitHub:** set up `cloudflare-worker/`
  once, then just message your bot `/scan example.com`.
- **Browse everything found so far:** open your GitHub Pages dashboard URL.

## Notes and limits

- Keep this to passive enumeration, DNS resolution and light HTTP probing.
  Heavy scanning or brute-forcing from GitHub's runners can violate their
  terms and risks your account — do that by hand, from your own connection,
  only against confirmed in-scope targets.
- State lives in the repo under `programs/`. The workflow commits it back
  after every run, so history and diffs are all in your git log too.
- Free GitHub plans include 2,000 Actions minutes/month on private repos.
  A full run is a few minutes per domain; scanning a handful of domains
  every 6 hours comfortably fits. If you add many targets, switch the
  cron in `recon.yml` to `0 */12 * * *`.
- Dangling-CNAME and path-probe hits are leads, not findings — always
  confirm manually before reporting anything.
