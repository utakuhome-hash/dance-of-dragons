# Alternate deployment notes

This branch is prepared for a single-container Python web service.

## Runtime

- Build: Dockerfile at the repository root
- Start: `python main.py`
- The app binds to `0.0.0.0` and reads the platform-provided `PORT`.
- The same aiohttp process serves the game API and Telegram webhook.

## Required environment variables

Set these in the hosting provider's secret/environment-variable dashboard. Never commit them to Git:

- `BOT_TOKEN`: the existing Telegram bot token
- `DATABASE_URL`: the existing production Neon PostgreSQL connection string
- `WEBHOOK_BASE_URL`: the public HTTPS base URL assigned to the new web service, without a trailing slash

Keep using the existing production Neon database. Do not point this service at a newly created empty database, and do not delete or reset the existing database.

After the public URL is assigned, set `WEBHOOK_BASE_URL` to that URL and redeploy so the app can register the Telegram webhook at `/telegram-webhook`.

## Operational note

The app is a web service rather than a separate worker: it receives Telegram updates through its webhook route. Free compute tiers may scale to zero while idle, so cold starts and webhook delays are possible. Confirm provider limits and billing before treating a free instance as always-on production hosting.
