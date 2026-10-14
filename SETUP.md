# Deploying behind Cloudflare Tunnel

Each game is served from its own hostname, and the proxy picks the game by
the Host header. So the tunnel just has to forward every subdomain to it.

## `.env`

```sh
DGB_PUBLIC_URL=https://daily.example.com
DGB_GAME_HOST={game}-daily.example.com
DGB_PROXY_PORT=8080
```

Use `{game}-daily`, not `{game}.daily`: Cloudflare's free certificate
covers only one subdomain level.

## Cloudflare

- **DNS:** a proxied CNAME `*` → `<tunnel-id>.cfargotunnel.com`.
- **Tunnel public hostname:** `*.example.com` → `http://<container>:8080`,
  where `<container>` is the bot as the cloudflared connector reaches it.
  If the dashboard rejects the `*`, set it through the
  [tunnel configuration API](https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/subresources/configurations/methods/update/).

This is set up once; adding a game needs no changes. Hostnames that aren't
the launcher or a game get a 404 from the proxy.
