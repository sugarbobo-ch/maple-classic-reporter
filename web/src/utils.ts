const DISCORD_WEBHOOK_PATH = /^\/api\/webhooks\/[0-9]+\/[A-Za-z0-9._-]+\/?$/;

/** Normalize a user-entered URL only when it resolves to a safe HTTPS address. */
export function normalizeSafeHttpsUrl(value: string): string | null {
  if (typeof value !== 'string' || !value.trim()) return null;

  const input = value.trim();
  const normalized = /^[a-z][a-z\d+.-]*:\/\//i.test(input) ? input : `https://${input}`;

  try {
    const url = new URL(normalized);
    if (
      url.protocol !== 'https:' ||
      !url.hostname ||
      url.username ||
      url.password ||
      url.hash ||
      (url.port && url.port !== '443')
    ) {
      return null;
    }
    return url.toString();
  } catch {
    return null;
  }
}

/** Mirror the backend's strict Discord webhook destination validation. */
export function isValidDiscordWebhookUrl(value: string): boolean {
  const normalized = normalizeSafeHttpsUrl(value);
  if (!normalized) return false;

  try {
    const url = new URL(normalized);
    return (
      ['discord.com', 'discordapp.com'].includes(url.hostname.toLowerCase()) &&
      !url.search &&
      DISCORD_WEBHOOK_PATH.test(url.pathname)
    );
  } catch {
    return false;
  }
}
