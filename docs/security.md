# Security and privacy

- Require `X-Webhook-Secret`; use a strong, rotated value in production.
- Terminate HTTPS at a trusted reverse proxy and never send secrets in URLs.
- Keep `.env` files, databases, virtual environments, and implementation notes out of Git.
- Use separate, least-privilege credentials for OpenAI-compatible providers, Slack/Discord webhooks, and HighLevel.
- Do not pass inbound values as outbound URLs or executable code.
- Notifications contain a summary rather than the raw webhook body.
- Review database retention and access controls before processing live personal data.

The application stores raw events to support reliable troubleshooting and retries. Deployers should establish a retention period, encrypted backups, access controls, and incident procedures appropriate for their jurisdiction and customer agreements.
