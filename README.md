# TERRA-SENTINEL X

**Flood change detection with NASA-ISRO NISAR radar data.**
NASA Space Apps Challenge 2026 · Challenge: [Dancing with the SARs](https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/) · Riyadh local event

> We don't just detect floods. We explain the evidence behind them.

## What it does

TERRA-SENTINEL X is an interactive web app that compares NISAR radar acquisitions from before and after a flood and shows where the ground surface likely changed.

1. **Before / After slider** – the user drags a slider over the map to compare the two radar scenes.
2. **Reveal Changes** – the system analyses the pair and highlights areas whose change is likely linked to flooding.
3. **Evidence Card** – click any changed area to see the before/after radar measurements and why the system flagged it.
4. **Smart Doubt** – results are not treated as certain; the system tests how stable each detection is (e.g. across thresholds) and marks areas that need review.
5. **Radar vs. Clouds** *(extra)* – shows how radar sees the ground even when clouds block optical imagery.
6. **Impact Lens** *(optional, if time allows)* – area of likely change and its overlap with farmland using auxiliary data.

The pipeline uses simple, explainable image-processing methods on real NISAR data, with no heavy AI training.

## Repository layout

| Folder | Owner (role) | Contents |
|---|---|---|
| `data/` | 2 · NISAR Data Engineer | Scene search, download & co-registration scripts, data source notes (large files are git-ignored) |
| `algorithm/` | 1 · Flood Detection Algorithm | Python change-detection code that produces change maps + evidence measurements |
| `sar/` | 5 · SAR Signal Processing | Calibration, speckle filtering, polarisation notes, processing recommendations |
| `validation/` | 6 · Scientific Validation & Reliability | Threshold-sensitivity tests, Smart Doubt stability map, evaluation metrics |
| `frontend/` | 3 · Frontend & UI | Web app: map, slider, Reveal Changes, Evidence Card, Smart Doubt view |
| `backend/` | 4 · Backend & Integration | Serves analysis outputs to the frontend, integration glue, deployment |
| `schema/` | 4 · Backend & Integration (shared) | The shared JSON/GeoJSON output contract every role follows |
| `docs/` | Everyone | Project description, data sources, references, demo material |

## Data flow

```
NISAR scenes (ASF / Earthdata)
   └─> data/      co-registered before/after rasters (GeoTIFF)
        └─> sar/        calibrated + speckle-filtered rasters
             └─> algorithm/   change map (GeoTIFF/PNG) + changes.geojson
                  └─> validation/  stability score per area (Smart Doubt)
                       └─> backend/   API / static outputs
                            └─> frontend/  interactive map
```

All outputs exchanged between roles follow [`schema/`](schema/README.md): rasters as **GeoTIFF/PNG**, vector results and metadata as **GeoJSON/JSON**.

## Live demo

**https://4mohammedalqahtani-svg.github.io/terra-sentinel-x/** (deployed from `main` by GitHub Actions)

## Run it locally

Needs Python 3.10+.

```bash
git clone https://github.com/4mohammedalqahtani-svg/terra-sentinel-x.git
cd terra-sentinel-x
pip install -r backend/requirements.txt
python backend/serve.py            # open http://localhost:8000
```

To publish a new analysis run from the team's outputs:

```bash
python backend/pipeline.py --run-id <id> --aoi "<area name>" --collect <folder with before.tif, after.tif, changes.geojson>
python backend/validate.py --all
```

Details: [`backend/README.md`](backend/README.md).

## Getting started (contributors)

```bash
git checkout -b <your-role>/<short-task>   # e.g. algorithm/threshold-detection
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch and pull-request workflow.

## Team

| # | Role | Member |
|---|---|---|
| 1 | Flood Detection Algorithm Developer | Basma (@bassmahossam083-cpu) |
| 2 | NISAR Data Engineer | Ali (@Ali-AL-Zahrani) |
| 3 | Frontend & UI Developer | Fares Al-Buqami (@faresfaresfares911-max) |
| 4 | Backend & Integration Developer | Mohammed (@4mohammedalqahtani-svg) |
| 5 | SAR Signal Processing Engineer | Abdulaziz |
| 6 | Scientific Validation & Reliability Engineer | @aammmf10 |

## Submission checklist (closes 15 Nov 2026, 11:59 PM local time)

- [ ] Interactive prototype that analyses real NISAR data
- [ ] Public link to open or run the project
- [ ] GitHub link to the code and this README
- [ ] Demo video or presentation, per the submission requirements
- [ ] English description of the project, its technologies and its results
- [ ] List of data sources, references and licences (`docs/DATA_SOURCES.md`)
- [ ] Project page filled in and submitted before the deadline

## Data sources

- NISAR data via [ASF Vertex](https://search.asf.alaska.edu/) and [NASA Earthdata](https://www.earthdata.nasa.gov/)
- See [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) for the full list and licences.

## License

[MIT](LICENSE)
