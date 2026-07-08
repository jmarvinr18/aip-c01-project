# Clarvo Web (streaming chat UI)

Minimal single-page chat client for Clarvo. Streams answers token-by-token over an
API Gateway WebSocket. No build step, no framework — just static files.

## Files
| File | Purpose |
|---|---|
| `index.html` | The whole app (UI + WebSocket streaming logic) |
| `config.js` | Holds the `WS_URL` — edit this, not the app |
| `amplify.yml` | Amplify build spec (deploys files as-is, no build) |
| `README.md` | This file |

## Before deploying
Edit `config.js` and set `WS_URL` to your WebSocket endpoint:
```
wss://<api-id>.execute-api.ap-southeast-1.amazonaws.com/prod
```
(API Gateway → `clarvo-ws` → Stages → `prod` → "WebSocket URL".)

## Local test
Just open `index.html` in a browser (or `python3 -m http.server` in this folder,
then visit http://localhost:8000). Type a question — it opens the socket and streams.

## Deploy via Amplify
See the connection steps below / in the chat guide.
