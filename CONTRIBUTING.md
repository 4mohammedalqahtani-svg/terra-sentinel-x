# Contributing to TERRA-SENTINEL X

One repo, one branch per member, and every change reaches `main` through a reviewed pull request.

## 1. Get access
Send your GitHub username to Mohammed (Backend & Integration). He adds you as a collaborator; accept the invite e-mail or open https://github.com/4mohammedalqahtani-svg/terra-sentinel-x/invitations.

## 2. Branches
- `main` is always demo-ready. **Never push to `main` directly.**
- Work on a branch named `<folder>/<short-task>`, for example:
  - `algorithm/threshold-detection`
  - `data/scene-pair-search`
  - `frontend/before-after-slider`
  - `backend/geojson-api`
  - `sar/speckle-filter`
  - `validation/smart-doubt`
- Stay inside your role's folder. If you need to change `schema/` or another role's folder, say so in the PR and tag that owner.

```bash
git checkout main && git pull
git checkout -b algorithm/threshold-detection
# ...work...
git add . && git commit -m "algorithm: add log-ratio change detection"
git push -u origin algorithm/threshold-detection
```

## 3. Pull requests
1. Open a PR into `main` and link its issue (`Closes #12`).
2. Describe what changed and how to run/test it. Add a screenshot for UI changes.
3. At least **one other teammate reviews** it. Mohammed (integration) merges.
4. Keep PRs small. Pull `main` often to avoid conflicts.

## 4. Commit messages
`<folder>: <what changed>` — e.g. `frontend: add Evidence Card popup`.

## 5. Data rules
- Do **not** commit raw NISAR products or large rasters. Put download scripts and links in `data/`, and record sources in `docs/DATA_SOURCES.md`.
- Small demo outputs (PNG previews, small GeoJSON) are fine in `*/samples/` folders.
- Never commit credentials (`.env`, `.netrc`, Earthdata tokens).

## 6. Output contract
Everything passed between roles must follow [`schema/`](schema/README.md). Agree on any change there before using it.
