# Alternate deployment notes

This branch is prepared for a single-container Python web service.

## Runtime

- Build: Dockerfile at the repository root
- Start: `python main.py`
- Expose port `8000` publicly over HTTP with route `/`.
- Koyeb sets `PORT` to the lowest exposed port unless you override it; this app reads `PORT` and binds to `0.0.0.0`.
- The same aiohttp process serves the game API and Telegram webhook; no separate worker process is required.

## Required environment variables

Set these in the hosting provider's secret/environment-variable dashboard. Never commit them to Git:

- `BOT_TOKEN`: the existing Telegram bot token
- `DATABASE_URL`: the existing production Neon PostgreSQL connection string
- `WEBHOOK_BASE_URL`: the public HTTPS base URL assigned to the new web service, without a trailing slash

Keep using the existing production Neon database. Do not point this service at a newly created empty database, and do not delete or reset the existing database.

After the public URL is assigned, set `WEBHOOK_BASE_URL` to that URL and redeploy so the app can register the Telegram webhook at `/telegram-webhook`.

## Free-tier limitations

Koyeb's Free Instance is a single Web Service with limited CPU/RAM and scales to zero after one hour without incoming traffic. It is not an always-on production guarantee; cold starts can delay game requests and Telegram webhook handling. Check the current provider limits and billing before treating it as production hosting.
