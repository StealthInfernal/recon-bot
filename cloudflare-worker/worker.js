/**
 * Telegram -> GitHub Actions bridge.
 *
 * Message your bot:
 *   /scan example.com       runs recon.yml (full enumeration pass)
 *   /wayback example.com    runs wayback.yml (uses that program's
 *                            already-saved subdomain list, no new
 *                            enumeration — fast, read-only OSINT)
 *
 * This worker checks the message came from your chat, then tells GitHub
 * Actions to run the matching workflow for that domain/program. Deploy
 * with Cloudflare's free Workers plan (no card required) and point
 * Telegram's webhook at this worker's URL (see README in this folder
 * for both steps).
 *
 * Required secrets (set with `wrangler secret put <NAME>`):
 *   TG_TOKEN       your bot token
 *   TG_CHAT_ID     your numeric Telegram chat id — only this chat can trigger scans
 *   GH_TOKEN       a GitHub fine-grained PAT with "Actions: read and write" on this repo
 *   GH_OWNER       your GitHub username
 *   GH_REPO        the repo name, e.g. recon-bot
 */

const DOMAIN_RE = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$/;

export default {
  async fetch(request, env) {
    if (request.method !== 'POST') return new Response('ok');

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response('bad request', { status: 400 });
    }

    const msg = update.message;
    if (!msg || !msg.text) return new Response('ok');

    // Only the configured chat can trigger anything.
    if (String(msg.chat.id) !== String(env.TG_CHAT_ID)) {
      return new Response('ok');
    }

    const text = msg.text.trim();
    const parts = text.split(/\s+/);
    const cmd = parts[0].toLowerCase();

    if (cmd === '/scan' || cmd === '/monitor') {
      const domain = (parts[1] || '').toLowerCase();
      if (!DOMAIN_RE.test(domain)) {
        await tgSend(env, 'Usage: /scan example.com');
        return new Response('ok');
      }
      await tgSend(env, `Starting scan for ${domain}…`);
      const ok = await triggerWorkflow(env, 'recon.yml', { domain });
      if (!ok) await tgSend(env, `Failed to trigger the workflow — check GH_TOKEN permissions.`);
    } else if (cmd === '/wayback') {
      const program = (parts[1] || '').toLowerCase();
      if (!DOMAIN_RE.test(program)) {
        await tgSend(env, 'Usage: /wayback example.com\n(pulls wayback URLs for subdomains already found for that program — run /scan on it at least once first)');
        return new Response('ok');
      }
      await tgSend(env, `Pulling wayback URLs for ${program}'s known subdomains…`);
      const ok = await triggerWorkflow(env, 'wayback.yml', { program });
      if (!ok) await tgSend(env, `Failed to trigger the workflow — check GH_TOKEN permissions.`);
    } else if (cmd === '/help' || cmd === '/start') {
      await tgSend(env,
        'Commands:\n' +
        '/scan <domain> — enumerate and alert on new subdomains\n' +
        '/wayback <domain> — pull wayback URLs for that program\'s already-known subdomains'
      );
    }

    return new Response('ok');
  },
};

async function tgSend(env, text) {
  await fetch(`https://api.telegram.org/bot${env.TG_TOKEN}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: env.TG_CHAT_ID, text }),
  });
}

async function triggerWorkflow(env, workflowFile, inputs) {
  const url = `https://api.github.com/repos/${env.GH_OWNER}/${env.GH_REPO}/actions/workflows/${workflowFile}/dispatches`;
  const r = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.GH_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'recon-bot-worker',
    },
    body: JSON.stringify({ ref: 'main', inputs }),
  });
  return r.status === 204;
}
