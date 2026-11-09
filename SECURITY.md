# Security

- **Keys live only in environment variables** on the machine that runs the desk. Never commit them, paste
  them into chats or issues, or write them into logs.
- **Exchange API keys:** create them with view and trade permission only, never transfer or withdraw.
  Add an IP allowlist where the exchange offers one.
- **The phone API:**
  - listens on 127.0.0.1 and is published only to your Tailscale network
  - every request needs a bearer token stored in a local file
  - no unauthenticated control endpoint exists
- **The bot never moves money.** There is no withdrawal or transfer code.
- **Live trading is disabled by default.** See `docs/risk-management.md` for the locks.

Report vulnerabilities privately through GitHub's security advisory form on this repository.
