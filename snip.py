#!/usr/bin/env python3
"""snip — a minimal URL shortener with a tiny web UI.

Run:  python snip.py
Then visit http://localhost:8000
"""

import json
import os
import re
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, urlsplit

DB_PATH = os.environ.get("SNIP_DB", "snip.db")
HOST = os.environ.get("SNIP_HOST", "127.0.0.1")
PORT = int(os.environ.get("SNIP_PORT", "8000"))
SLUG_LEN = 7

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>snip</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; max-width: 40rem; margin: 4rem auto;
         padding: 0 1rem; line-height: 1.5; }
  form { display: flex; gap: .5rem; }
  input[type=url] { flex: 1; padding: .6rem; font-size: 1rem;
                    border: 1px solid #888; border-radius: 6px; }
  button { padding: .6rem 1rem; font-size: 1rem; cursor: pointer;
           border: 0; border-radius: 6px; background: #4a7cff; color: white; }
  #result { margin-top: 1.5rem; padding: 1rem; background: #0001;
            border-radius: 6px; display: none; word-break: break-all; }
  a { color: #4a7cff; }
  code { background: #0001; padding: .15rem .35rem; border-radius: 4px; }
</style>
</head>
<body>
  <h1>snip</h1>
  <p>A tiny URL shortener.</p>
  <form id="f">
    <input type="url" id="url" required placeholder="https://example.com/very/long/path"
           autocomplete="off" autofocus>
    <button>Shorten</button>
  </form>
  <div id="result"></div>
<script>
  const f = document.getElementById('f');
  const out = document.getElementById('result');
  f.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = document.getElementById('url').value.trim();
    out.style.display = 'none';
    try {
      const r = await fetch('/api/shorten', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url})
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'request failed');
      const short = location.origin + '/' + data.slug;
      out.innerHTML = `Short URL: <a href="${short}" target="_blank">${short}</a>` +
                      `<br><small>→ ${data.url}</small>`;
      out.style.display = 'block';
      f.reset();
    } catch (err) {
      out.textContent = 'Error: ' + err.message;
      out.style.display = 'block';
    }
  });
</script>
</body>
</html>
"""


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            slug TEXT PRIMARY KEY,
            url  TEXT NOT NULL UNIQUE,
            hits INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def is_valid_url(url: str) -> bool:
    try:
        p = urlsplit(url)
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc)


def new_slug() -> str:
    return secrets.token_urlsafe(SLUG_LEN)[:SLUG_LEN]


def shorten(conn: sqlite3.Connection, url: str) -> str:
    # Reuse existing slug for the same URL
    row = conn.execute("SELECT slug FROM urls WHERE url = ?", (url,)).fetchone()
    if row:
        return row[0]
    # Retry on the (astronomically unlikely) collision
    for _ in range(5):
        slug = new_slug()
        try:
            conn.execute("INSERT INTO urls (slug, url) VALUES (?, ?)", (slug, url))
            conn.commit()
            return slug
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("Could not allocate a slug; try again.")


def resolve(conn: sqlite3.Connection, slug: str):
    row = conn.execute("SELECT url FROM urls WHERE slug = ?", (slug,)).fetchone()
    if not row:
        return None
    conn.execute("UPDATE urls SET hits = hits + 1 WHERE slug = ?", (slug,))
    conn.commit()
    return row[0]


def stats(conn: sqlite3.Connection, slug: str):
    return conn.execute(
        "SELECT url, hits, created_at FROM urls WHERE slug = ?", (slug,)
    ).fetchone()


class Handler(BaseHTTPRequestHandler):
    server_version = "snip/1.0"

    # --- helpers ---------------------------------------------------------
    def _send(self, status, body=b"", content_type="text/plain; charset=utf-8",
              extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj).encode(), "application/json")

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")

    # --- routes ----------------------------------------------------------
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            return self._send(200, INDEX_HTML.encode(), "text/html; charset=utf-8")

        if path == "/api/stats":
            qs = parse_qs(urlparse(self.path).query)
            slug = (qs.get("slug") or [""])[0]
            row = stats(self.server.conn, slug)
            if not row:
                return self._json(404, {"error": "not found"})
            return self._json(200, {"slug": slug, "url": row[0],
                                    "hits": row[1], "created_at": row[2]})

        # /<slug>
        slug = path.lstrip("/")
        if slug and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", slug):
            url = resolve(self.server.conn, slug)
            if url:
                return self._send(302, extra_headers={"Location": url})
        self._send(404, b"Not found")

    def do_POST(self):
        if urlparse(self.path).path != "/api/shorten":
            return self._send(404, b"Not found")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "invalid JSON"})

        url = (data.get("url") or "").strip()
        if not is_valid_url(url):
            return self._json(400, {"error": "invalid URL (must be http/https)"})

        slug = shorten(self.server.conn, url)
        self._json(201, {"slug": slug, "url": url,
                         "short": f"http://{self.headers.get('Host', 'localhost')}/{slug}"})


def main():
    conn = init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.conn = conn
    print(f"snip listening on http://{HOST}:{PORT}  (db: {DB_PATH})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        server.server_close()
        conn.close()


if __name__ == "__main__":
    main()
