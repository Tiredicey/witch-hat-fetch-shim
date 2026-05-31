# CODA fetch shim

A tiny fetch service that requests a page with a real browser TLS fingerprint
(`curl_cffi`, Safari first) and returns the raw HTML. It speaks the same
`POST {url}` contract the CODA Worker's `generic` render backend already expects,
so the Worker can reach sites whose Cloudflare block is TLS-fingerprint based
(verified working on `entertainment.inquirer.net/category/movies`).

It does NOT run a browser and does NOT use proxies, so it cannot clear a
Cloudflare managed challenge that requires JavaScript or a residential IP
(verified: `www.cosmo.ph` still returns 502 from this shim). Those cases need a
paid residential proxy and there is no reliable free substitute.

## Endpoints

- `POST /content?key=YOURTOKEN` body `{"url": "https://..."}` -> `200` HTML, or
  `502` when every fingerprint is still blocked/challenged.
- `GET /health` -> `{"ok": true}`.

`key` is required only if `FETCH_SHIM_TOKEN` is set. Set it so the endpoint is
not an open proxy.

Successful responses are cached in memory per URL. Tune with `FETCH_SHIM_CACHE_TTL`
(seconds, default 600; set 0 to disable) and `FETCH_SHIM_CACHE_MAX` (entries,
default 200). A cache hit sets header `X-Shim-Cache: hit`.

## Run locally

    pip install -r requirements.txt
    FETCH_SHIM_TOKEN=pick-a-long-random-string python app.py
    curl -s -X POST "http://localhost:8080/content?key=pick-a-long-random-string" \
      -H "Content-Type: application/json" \
      -d '{"url":"https://entertainment.inquirer.net/category/movies"}' | head

## Free hosting (pick one)

All of these run the Dockerfile or `app.py` at no cost. None require a card for
the free tier except where noted.

- Oracle Cloud Always Free: a real always-on VM (ARM, generous). Best if you
  want it never to sleep. Card required for signup, not billed on Always Free.
- Render.com free web service: deploy the repo, it builds the Dockerfile. The
  free instance sleeps after 15 min idle and cold-starts in ~30s. Fine for feed
  polling. No card.
- Koyeb / Fly.io free allowance: same idea, Docker deploy. Check current free
  limits at signup.

Set the environment variable `FETCH_SHIM_TOKEN` on the host to a long random
string. The host gives you a public URL like `https://yourshim.onrender.com`.

## Wire it into CODA (Cloudflare Pages variables)

In your Pages project -> Settings -> Variables and Secrets, add:

- `RENDER_BACKEND` = `generic`
- `RENDER_URL` = `https://yourshim.onrender.com/content?key=YOURTOKEN`
- make sure `PROXY_ALLOW` includes the sites you want, or is `*`

Redeploy. Now when the Worker is blocked on a TLS-gated page, it calls the shim,
gets the real HTML back, and builds a feed from it. For the Inquirer movies page
this yields a movies-specific synthetic feed (the article links on the category
page), not just the site-wide root feed.

## What stays out of reach for free

- `www.cosmo.ph` and any origin that blocks on IP reputation or a JS challenge:
  needs a residential proxy (paid) and usually a real browser too.
- Private Facebook friend timelines: no legitimate feed exists; requires your
  login and breaks platform terms.
- X/Twitter at volume: needs auth or the paid API.
