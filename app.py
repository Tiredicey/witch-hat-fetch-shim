import ipaddress
import os
import socket
import threading
import time
from urllib.parse import urlparse

from curl_cffi import requests as creq
from flask import Flask, Response, request

app = Flask(__name__)

TOKEN = os.environ.get("FETCH_SHIM_TOKEN", "")
TIMEOUT = int(os.environ.get("FETCH_SHIM_TIMEOUT", "25"))
CACHE_TTL = int(os.environ.get("FETCH_SHIM_CACHE_TTL", "600"))
CACHE_MAX = int(os.environ.get("FETCH_SHIM_CACHE_MAX", "200"))
FINGERPRINTS = ["safari17_0", "chrome124", "chrome120"]
CHALLENGE_MARKERS = ("just a moment", "challenge-platform", "cf-challenge", "attention required")

_cache = {}
_cache_lock = threading.Lock()


def cache_get(url):
    if CACHE_TTL <= 0:
        return None
    with _cache_lock:
        hit = _cache.get(url)
        if hit and hit[0] > time.time():
            return hit[1]
        if hit:
            _cache.pop(url, None)
    return None


def cache_put(url, html):
    if CACHE_TTL <= 0:
        return
    with _cache_lock:
        if len(_cache) >= CACHE_MAX:
            oldest = min(_cache, key=lambda k: _cache[k][0])
            _cache.pop(oldest, None)
        _cache[url] = (time.time() + CACHE_TTL, html)


def is_public_url(raw):
    try:
        u = urlparse(raw)
    except ValueError:
        return False
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    try:
        infos = socket.getaddrinfo(u.hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def looks_challenged(text):
    head = text[:600].lower()
    return any(m in head for m in CHALLENGE_MARKERS)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/content")
def content():
    if TOKEN and request.args.get("key") != TOKEN:
        return Response("forbidden", status=403)
    body = request.get_json(silent=True) or {}
    target = body.get("url") or request.args.get("url", "")
    if not target or not is_public_url(target):
        return Response("invalid or non-public url", status=400)
    cached = cache_get(target)
    if cached is not None:
        return Response(cached, status=200, mimetype="text/html; charset=utf-8", headers={"X-Shim-Cache": "hit"})
    last = 0
    for imp in FINGERPRINTS:
        try:
            r = creq.get(target, impersonate=imp, timeout=TIMEOUT, allow_redirects=True)
        except Exception:
            continue
        last = r.status_code
        if r.status_code == 200 and not looks_challenged(r.text):
            cache_put(target, r.text)
            return Response(r.text, status=200, mimetype="text/html; charset=utf-8", headers={"X-Shim-Cache": "miss"})
    return Response("", status=502 if last else 504)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
