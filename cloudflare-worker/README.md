# Cloudflare Worker Stock Site

This worker hosts the stock website directly and stores stock state in KV.

## Required Worker secrets/bindings

- `DISCORD_WEBHOOK_URL` (secret, for broadcast endpoints and cron)
- `STOCK_KV` (KV namespace binding)

## Routes

- `GET /stock` -> stock page HTML
- `GET /stock.js` -> stock page script
- `GET /stock.css` -> stock page style
- `GET /stock/snapshot` -> latest stock snapshot
- `POST /stock/update` -> modify stock (auto tick), no broadcast
- `POST /stock/test-tick` -> test modify stock only, no broadcast
- `POST /stock/broadcast` -> broadcast current snapshot to Discord
- `POST /stock/update-and-broadcast` -> modify stock then broadcast

## Cron

Configure a Cron Trigger in Cloudflare Worker (e.g. `0 * * * *`).
The scheduled handler auto-updates stock prices and sends a Discord webhook broadcast.

