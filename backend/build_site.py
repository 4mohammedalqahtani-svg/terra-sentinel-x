#!/usr/bin/env python3
"""Assemble the public website into _site/ (what GitHub Pages serves).

    _site/            <- frontend/ (if frontend/index.html exists) else backend/preview/
    _site/data/       <- backend/outputs/ (runs.json + one folder per run)

The frontend should therefore load `data/runs.json`, then
`data/<run_id>/run.json`, then the files named inside it (relative to that
run.json). `python backend/serve.py` serves exactly the same layout locally.

Usage: python backend/build_site.py [--out _site]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import common
import validate

PUBLISH_EXT = {".json", ".geojson", ".png", ".jpg", ".jpeg", ".webp"}


def site_source() -> Path:
    fe = common.ROOT / "frontend"
    if (fe / "index.html").exists():
        return fe
    return common.ROOT / "backend" / "preview"


def build(out: Path) -> None:
    src = site_source()
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out, ignore=shutil.ignore_patterns("README.md", "node_modules", ".*"))
    data = out / "data"
    if data.exists():
        shutil.rmtree(data)
    data.mkdir()
    for p in common.OUTPUTS.rglob("*"):
        if p.is_file() and p.suffix.lower() in PUBLISH_EXT:
            dst = data / p.relative_to(common.OUTPUTS)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    (out / ".nojekyll").write_text("")
    print(f"site built from {src.relative_to(common.ROOT)} + backend/outputs -> {out}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=common.ROOT / "_site")
    args = ap.parse_args(argv)
    if validate.main(["--all"]) != 0:
        print("outputs failed validation - fix them before publishing", file=sys.stderr)
        return 1
    build(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
