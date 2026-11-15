# validation/ — Scientific Validation & Reliability (role 6)
- Test result sensitivity to thresholds/filters; compute a stability score per change area (Smart Doubt).
- Compare with an independent reference if available.
- Output: stability map, evaluation metrics, written limitations.

## Delivered (issue #4)

**Read first: [`REPORT.md`](REPORT.md)** (metrics, method, limitations).

| File | Content |
|---|---|
| `REPORT.md` | Threshold sensitivity, per-area reliability, control-pair false-alarm test, Copernicus comparison, limitations |
| `control_pair_check.py` | Runs the algorithm unchanged on two pre-flood dates and compares with the event (`python validation/control_pair_check.py` from the repo root) |
| `compare_copernicus.py` | Spatial comparison with Copernicus EMS EMSR857 |
| `samples/control_{HH,HV,mask}.tif` | NISAR GCOV 2025-12-24 (pre-flood control), same grid as `algorithm/data/` |
| `results/control_pair_summary.json`, `results/control_vs_event.png` | Control-pair results |

Stability map: `algorithm/results_v2/smart_doubt_stability.tif` (per pixel, 0–3 tests passed), shown on the website as `backend/outputs/<run>/doubt_map.png`. Per-area `reliability` is filled in `changes.geojson` by `backend/vectorize.py`.
