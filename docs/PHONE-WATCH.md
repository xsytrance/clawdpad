# Phone + watch control (Phase 3)

`clawdpadd` exposes two remote command surfaces, both speaking the same JSON
schema as the Unix socket. Secrets live in `~/.config/clawdpad/config.json`
(mode 0600, never commit it). Print them when you need them:

```bash
python3 -m json.tool ~/.config/clawdpad/config.json
```

- **HTTP (LAN / Tailscale):** `POST http://<host>:8137/` with header
  `Authorization: Bearer <token>` and a JSON command body. `GET /status` (same
  header) returns mood/energy/sessions. Plain HTTP — fine on the home LAN and
  inside the tailnet; don't port-forward it to the internet.
  - LAN: `<your-lan-ip>` · Tailscale (works from anywhere): `<your-tailscale-ip>`
- **ntfy.sh (anywhere, no VPN):** publish a JSON command to the secret topic,
  with the token as a `"token"` field inside the message:

```bash
curl -d '{"token":"<token>","cmd":"anim","arg":"celebrate"}' \
     https://ntfy.sh/<ntfy_topic>
```

## Command palette

| action | JSON body |
|---|---|
| set him pacing (thinking) | `{"cmd":"mode","arg":"thinking"}` |
| back to idle | `{"cmd":"clear"}` |
| bedtime | `{"cmd":"mode","arg":"sleep"}` |
| ping Claude's glass | `{"cmd":"say","arg":"hi from the phone","seconds":60}` |
| celebrate jump | `{"cmd":"anim","arg":"celebrate"}` |
| jingle (sound at the desk + light) | `{"cmd":"play","arg":"jingle"}` |
| thinking hum on/off | `{"cmd":"hum","arg":"on"}` / `"off"` |
| status (HTTP GET /status) | — |

## Pixel 10 Pro XL — HTTP Shortcuts

1. Install **HTTP Shortcuts** (Waboodoo, Play Store).
2. Per command above: new shortcut → Method `POST` →
   URL `http://<your-tailscale-ip>:8137/` (Tailscale, so it works away from home too;
   use the LAN IP if you skip Tailscale on the phone) →
   Request Headers: `Authorization: Bearer <token>` →
   Request Body type `custom text`, content-type `application/json`,
   body = the JSON from the table.
3. Long-press home screen → widgets → HTTP Shortcuts → one widget per shortcut.
4. Off-LAN without Tailscale: make the URL `https://ntfy.sh/<ntfy_topic>`,
   no auth header, and put the token inside the JSON body instead.

## Galaxy Watch7

Two verified-in-research paths (PLAN.md), in order of preference:

1. **Home Assistant Companion for Wear OS** — native tiles + complications,
   standalone over Wi-Fi. Wire an HA `rest_command` per palette entry pointing
   at the HTTP endpoint, expose them as scripts, pin as tiles. Side effect:
   watch control of the whole house.
2. **AutoWear + Tasker** — Tasker task per command using the HTTP Request
   action (same URL/header/body as HTTP Shortcuts), AutoWear tile to trigger
   it. No Home Assistant required.

Either way the watch just needs to land one HTTPS POST on ntfy.sh or one HTTP
POST on the tailnet/LAN — the daemon does the rest.
