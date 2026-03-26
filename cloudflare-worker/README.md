# Cloudflare Worker Stock Backend

This worker is designed to be the stock source-of-truth and Discord broadcaster.

## Required Worker secrets/bindings

- `DISCORD_WEBHOOK_URL` (secret)
- `RELAY_API_KEY` (secret, shared with Render `STOCK_BACKEND_KEY`)
- `STOCK_KV` (KV namespace binding)

## Required routes used by Render app

- `GET /stock/snapshot`
- `POST /stock/update` (requires `X-Relay-Key`)
- `POST /stock/broadcast` (requires `X-Relay-Key`)
- `POST /stock/update-and-broadcast` (requires `X-Relay-Key`)

## Cron

Configure a Cron Trigger in Cloudflare Worker for hourly execution (e.g. `0 * * * *`).
The scheduled handler auto-updates stock prices and sends a Discord webhook broadcast.

