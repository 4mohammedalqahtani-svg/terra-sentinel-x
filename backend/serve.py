#!/usr/bin/env python3
"""Local dev server with the same URL layout as the public site.

    http://localhost:8000/          -> frontend/ (or backend/preview/ until frontend/index.html exists)
    http://localhost:8000/data/...  -> backend/outputs/...

Usage: python backend/serve.py [--port 8000] [--preview]
Files are read live, so re-running the pipeline shows up on refresh.
"""
from __future__ import annotations

import argparse
import functools
import http.server
from pathlib import Path

import build_site
import common


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".geojson": "application/geo+json", ".json": "application/json"}

    def __init__(self, *a, site: Path, **kw):
        self.site = site
        super().__init__(*a, directory=str(site), **kw)

    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean == "/data" or clean.startswith("/data/"):
            rel = clean[len("/data"):].lstrip("/")
            target = (common.OUTPUTS / rel).resolve()
            if common.OUTPUTS.resolve() in target.parents or target == common.OUTPUTS.resolve():
                return str(target)
            return str(common.OUTPUTS / "__forbidden__")
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--preview", action="store_true", help="serve backend/preview/ even if frontend/ exists")
    args = ap.parse_args(argv)
    site = common.ROOT / "backend" / "preview" if args.preview else build_site.site_source()
    httpd = http.server.ThreadingHTTPServer((args.host, args.port), functools.partial(Handler, site=site))
    print(f"serving {site.relative_to(common.ROOT)} + /data -> backend/outputs at http://{args.host}:{args.port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
