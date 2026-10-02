# Telegram -> GitHub trigger

Lets you message your Telegram bot `/scan example.com` and have it kick off
the GitHub Actions recon workflow — no need to open GitHub at all. Runs on
Cloudflare's free Workers plan (100,000 requests/day, no card required).

## 1. Make a GitHub token the worker can use

GitHub Settings -> Developer settings -> Fine-grained personal access tokens
-> Generate new token. Scope it to this one repo only, with Repository
permissions -> Actions: Read and write. Copy the token.

## 2. Deploy the worker

On your phone's browser:

1. Sign up at dash.cloudflare.com (free, no card).
2. Workers & Pages -> Create -> Create Worker. Give it a name, deploy the
   default "Hello World" first.
3. Open the worker -> Edit code, delete everything, paste in `worker.js`
   from this folder, and deploy.
4. Back on the worker's page, go to Settings -> Variables and Secrets ->
   add each of these as a secret (not a plain variable):
   - `TG_TOKEN` — your bot token
   - `TG_CHAT_ID` — your numeric chat id
   - `GH_TOKEN` — the fine-grained PAT from step 1
   - `GH_OWNER` — your GitHub username
   - `GH_REPO` — the repo name, e.g. `recon-bot`
5. Note the worker's URL, shown at the top of its page
   (`https://<name>.<your-subdomain>.workers.dev`).

## 3. Point Telegram at the worker

Open this URL in your browser once (replace both placeholders), then close
the tab — it's a one-time registration, not something you keep open:

```
https://api.telegram.org/bot<TG_TOKEN>/setWebhook?url=<WORKER_URL>
```

You should see `{"ok":true,"result":true,...}`.

## 4. Use it

Message your bot in Telegram:

```
/scan microsoft.com
```

Replace with a domain you're actually authorized to test. The worker
replies "Starting scan…" immediately, then GitHub Actions runs the
pipeline and the usual alert (or silent baseline) follows a few minutes
later from the same Telegram bot.

## Notes

- Only messages from `TG_CHAT_ID` are honored — anyone else messaging your
  bot is ignored.
- This only triggers `recon.yml`. Deep-probe stays manual, from the
  Actions tab, by design — it's a step you want to take deliberately,
  not fire off reflexively from a chat message.
