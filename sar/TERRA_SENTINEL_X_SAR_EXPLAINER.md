# TERRA-SENTINEL X — SAR Signal Processing Explainer

**Owner:** Role 5 — SAR Signal Processing Engineer  
**Target branch:** `sar/preprocessing`  
**Study area:** Chókwè, Gaza Province, Mozambique; January 2026 Limpopo flooding  
**Status:** Engineering guidance and exploratory observations; **not** a validated flood product.

## 1. Input data and what the code actually does

The team uses **NASA–ISRO NISAR L-band (1.239 GHz; wavelength approximately 24.2 cm)**, **Level-2 GCOV BETA V1**, frequency A, dual polarization (`HHHH`/`HVHV`). The three matched passes use track/frame **114/165**, ascending geometry: **24 Dec 2025** (control), **5 Jan 2026** (before) and **17 Jan 2026** (after). See `docs/DATA_SOURCES.md` and `data/scenes_provenance.json`. The source grids have nominal 10 m sampling; the project extracts **60 m** rasters in **EPSG:32736** (UTM). Native grid spacing is not the same thing as independent spatial resolution.

**Two existing data paths — do not mix the units:**

| Repository path | What it contains | Units and processing |
| --- | --- | --- |
| `algorithm/data/before_HH.tif`, `after_HH.tif`, `before_HV.tif`, `after_HV.tif` | 60 m GCOV diagonal covariance layers, two bands in these exported files (data and alpha) | **Linear gamma-nought power**, NOT dB. `algorithm/flood_detection_v2.py` converts band 1 with `10*log10(power)`. |
| `algorithm/data/before_mask.tif`, `after_mask.tif` | Valid-subswath coverage masks | Treat zero as invalid. In the present extracted files, observed values are 0 and 1. Follow product mask definitions for other inputs. |
| `data/samples/before.tif`, `after.tif`, `control.tif` | HH-only layers for the frontend/backend path | **Already in dB**, float32, one band, nodata `-9999`, 60 m, EPSG:32736, 1093 × 620. **Do not apply `10*log10` again.** |
| `data/prepare.py` | Copies HH dB before/after into backend working directory | Does **not** perform calibration, filtering or reprojection. |
| `data/scripts/nisar_extract_v4.py` | Extracts GCOV layers, georeferences, clips, resamples | `resampleAlg="near"` for HH, HV **and** mask; locks output grids to match the first scene. It is **not** a speckle filter. |
| `algorithm/flood_detection_v2.py` | Existing dual-pol exploratory detector | Valid masks; HH/HV dB differences; low-after-HH and not-too-dark-before-HH filters; connected groups >=9 pixels; stability across three thresholds. Does **not** apply speckle filtering. |
| `backend/pipeline.json` | Defines future integration stage | Refers to `sar/process.py`, but that processor is **not part of this deliverable**; the stage is skipped if the script does not exist. |

**Observed in the supplied repository:** the six `algorithm/data` rasters share the same EPSG:32736, 60 m, 620 × 1093 grid. `algorithm/results_v2/evidence_v2.json` reports **676,866 valid pixels** (99.88%), **59,023 joint HH/HV candidate pixels**, or **212.483 km²** of *unvalidated detection candidates*. These are not confirmed flooded hectares or a validated event footprint. The existing web-ready HH TIFFs also share this grid.

**Algorithm v2 conditions (not SAR physics laws):** After-HH <= scene 40th percentile (**−11.223 dB**); Before-HH >= scene 15th percentile (**−16.842 dB**); and relative HH/HV decreases. Baseline thresholds: **ΔHH <= −3 dB; ΔHV <= −1.5 dB**. Relaxed: (−2, −0.5) dB; strict: (−4, −2.5) dB. Minimum connected cluster: **9 pixels = 0.0324 km²** at 60 m. `smart_doubt_stability.tif` values 0–3 count how many threshold tests detect the pixel: **not a probability or statistical confidence**. The HH-only comparison is less restrictive, not necessarily less or more accurate.

### Required integration contract

Deliver processed `before.tif` and `after.tif` with **exactly these names**; single band, float32, **dB**, shared extent/CRS/pixel alignment; preserve nodata and metadata. The existing raster CRS can remain **EPSG:32736**; **GeoJSON coordinates and web bounds** must be **EPSG:4326 in `(lon, lat)` order**. A negative `delta_db` always means **after minus before** is darker. The shared schema is in `schema/README.md`; do not substitute raw linear HH/HV layers for the dB inputs. Keep large raster files off GitHub and share them by external link.

## 2. Why open water often looks dark

Synthetic Aperture Radar sends microwaves towards Earth and records energy returned towards the satellite. A relatively smooth open-water surface acts approximately like a **mirror** (**specular reflection**): most of the radar energy reflects *away from the side-looking sensor*, leaving weak backscatter and a **dark pixel**. Ground that becomes smooth open water may therefore change from a brighter before value to a darker after value.

This is an **indicator, not proof of flooding**: roads, smooth bare soil, radar shadow and permanent water can also be dark. Wind-roughened water can become brighter. Under trees or near structures, flooding may increase **double-bounce** returns (water-to-trunk/building-to-radar), sometimes especially in HH; the current *darkening* algorithm can miss these cases.

### Frequency and polarization

- **L-band: 1.239 GHz, ~24 cm wavelength.** Compared with shorter wavelengths, it can interact more deeply with some vegetation structure, which makes flood-related scattering from trunks and branches potentially informative. It does **not** see through all vegetation or measure water depth directly. Penetration depends on canopy, moisture and geometry.
- **HH (horizontal transmit, horizontal receive):** co-polarized backscatter. Smooth open water usually has weak HH return; strong HH can also arise from trunks/buildings and double-bounce. Useful, but not sufficient on its own.
- **HV (horizontal transmit, vertical receive):** cross-polarized return, often sensitive to vegetation and depolarization/volume scattering. A coincident HV decrease strengthens the *open-water-like darkening* interpretation but does not prove flooding; vegetated inundation can behave differently.
- **No universal dB flood threshold:** thresholds depend on target, acquisition geometry, radiometric stability, noise floor, resolution and scene distribution.

## 3. Recommended calibration, dB and filtering settings

| Stage | Recommended setting | Reason / implementation warning |
| --- | --- | --- |
| Input/calibration | Start from the existing **Level-2 GCOV gamma0 power** layers; retain product calibration/terrain correction. **Do not multiply by a new calibration constant.** | GCOV is already radiometrically calibrated and terrain-corrected. **BETA** quality still warrants checks of noise, consistency and artefacts; calibrated imagery is not the same as a validated flood map. |
| Validity | Intersect before/after HH and HV validity and coverage masks; require finite, **positive** power before log conversion. | No-data, alpha and nonpositive values must not be logged. Mask extraction should use **nearest** to preserve categorical labels. |
| Co-registration | Same track/frame, CRS, extent, transform and pixel size; test pixel agreement in stable landmarks. | Small offsets can create false change edges. |
| Preferred resampling | From **native linear power**, use **area-weighted `average`** down to 60 m for HH and HV, using matched output grids. | `near` keeps a single roughly 10 m source sample per 60 m cell rather than averaging its footprint, so it discards spatial information and retains more speckle variability. This is the highest-priority recommendation. |
| dB conversion | For **linear GCOV power**: `gamma0_dB = 10 * log10(gamma0_linear)` **after** averaging/filtering. For already dB `data/samples/*.tif`: **no conversion**. | GCOV diagonal elements are powers, not amplitude; `20*log10` is incorrect. The average of dB values is **not** the dB of average linear power. |
| Speckle filtering | **First choice:** test **60 m linear-power average with no additional spatial filter**, since averaging already reduces speckle variance. **Optional comparison:** light **3×3 Lee filter** on positive *linear* power, separately for each date/polarization, if isolated salt-and-pepper artefacts remain. | Avoid smoothing narrow rivers, shorelines and small flood patches. Lee is a sensitivity experiment, **not a validated optimum**; use matching parameters on both dates and benchmark versus no extra filtering. Do not claim a 3×3 mean/median of dB is equivalent. |
| Fallback if only current 60 m products exist | Do **not** pretend smoothing reconstructs the skipped source pixels. Prefer re-extraction from original 10 m GCOV; otherwise use the unfiltered 60 m rasters as baseline and document optional 3×3 linear-power filter as a separate trial. | Proper spatial averaging must happen before 10→60 m downsampling. |
| Detection changes | `ΔHH_dB = HH_after_dB − HH_before_dB`; same for HV. Keep baseline −3/−1.5 dB as **exploratory**, compare relaxed/strict cases and control-pair false alarms. | The supplied v2 algorithm already does this but was run on nearest-neighbor inputs. Reprocess and re-evaluate thresholds if extraction changes. |
| Quality assurance | Compare stable-landcover sample statistics; use 24 Dec→5 Jan control pair; inspect spatial distribution of brightness shift; compare with independent observations acquired close to 17 Jan. | Don't normalize scene-wide brightness automatically: genuine rainfall-related change could be removed, while sensor-related differences could produce false candidates. |

**Processing order:** read GCOV `HHHH`/`HVHV` as **linear gamma0** → apply quality masks → align to shared grid → average linear powers to 60 m (masks nearest; invalid cells excluded from mean) → optionally test mild power-domain speckle filter → convert power to dB → export `before.tif`/`after.tif` (HH, float32 dB) plus optional HV companion rasters for the dual-pol detector → compute changes and validate. If an additional Lee filter is tested, document whether it was applied before or after spatial aggregation; do not filter and downsample twice without justification.

**Explicit filter line for the team:** `Recommended: area-weighted mean (average) of positive linear GCOV gamma0 power from native ~10 m to aligned 60 m pixels; categorical masks use nearest; no additional speckle filter by default (optional linear-power 3×3 Lee sensitivity test).`

### Important technical coordination items

1. `data/prepare.py` feeds only **HH in dB**, whereas `algorithm/flood_detection_v2.py` requires **HH + HV as linear powers** with masks. Decide on **one interface** with role 1/data engineer: either explicitly supply additional HV dB rasters and update the detector, or keep the standalone linear dual-pol input path and convert exactly once. Do not run both conversions.
2. An updated output must replace both dates using the **same** averaging method and precisely the **same** grid. The existing 60 m before/after PNGs and overlays were made from the old inputs; regenerate them if the raster values or alignment change.
3. Re-estimate percentile cuts, connected candidates, candidate area and stability after re-extraction; the current **212.483 km²** must not be presented as a result from newly averaged inputs.
4. The current `backend/pipeline.json` expects `sar/process.py`, but **only an explainer and settings are delivered here**. No preprocessing script or replacement TIFFs are claimed. Implement and test that stage in a separate task if desired.

## 4. Before/after examples from the supplied rasters

The two examples below are **actual individual 60 m grid-cell measurements**, computed from `algorithm/data/{before,after}_{HH,HV}.tif` by `10*log10(linear power)`. Locations are displayed in **EPSG:4326 (lon, lat)**, derived from the grid. They are **algorithm classes**, not ground-truth flood labels.

| Example (v2 class) | Grid (row, col; zero-based) | Longitude, latitude | HH before → after | ΔHH | HV before → after | ΔHV | Interpretation |
| --- | --- | --- | --- | ---: | --- | ---: | --- |
| **Flood-like candidate, not confirmed flooded** (joint HH+HV; stability 3/3) | `(317, 813)` | `(33.147184, −24.571304)` | **−11.45 → −16.83 dB** | **−5.39 dB** | **−20.28 → −23.44 dB** | **−3.15 dB** | Both channels darken sufficiently; flagged by current algorithm. |
| **No candidate / relatively stable signal, not confirmed dry** (stability 0/3) | `(342, 341)` | `(32.867485, −24.584865)` | **−9.64 → −9.46 dB** | **+0.18 dB** | **−12.64 → −12.78 dB** | **−0.14 dB** | Changes are small, so the current detector does not flag this cell. |

Rounded display values can differ by 0.01 dB from the unrounded differences. Do not label the first point *verified flooded* or the second *verified non-flooded* without independent ground truth. Values will change if the source is re-extracted with averaging.

The team also previously supplied an example **HH −10.5 → −18.9 dB (Δ −8.4 dB), HV decrease 6.4 dB**. This is useful as a team-provided example, but its pixel coordinate/provenance was **not** established in the supplied repository; do not cite it as an independently reproduced pixel measurement.

### About the +3.1 dB regional brightening

The provenance notes report **mean HH change about −0.82 dB** from **24 Dec → 5 Jan**, then **+3.07 dB** from **5 Jan → 17 Jan** (metadata-derived, frame-wide). Increased soil moisture after rain is a plausible physical explanation: wet soil changes its dielectric response and can return more radar energy. But **BETA calibration residuals, roughness/vegetation changes, scene-wide acquisition effects, and other land-cover changes have not been excluded**. Therefore do **not** call the full area flooded or apply a blanket −3.07 dB offset without controls. Compare stable-target distributions, HH and HV separately, the no-flood control pair, quality masks and independent rainfall/flood records.

## 5. Plain-language Evidence Card reason texts

Use concise explanations as **hypotheses**, with real numbers substituted from the selected feature or pixel. Avoid "proved" or "confirmed".

| Case | Suggested `reason` text |
| --- | --- |
| Strong joint darkening | "This area became darker in both radar channels (HH {delta_hh_db} dB, HV {delta_hv_db} dB). That pattern can indicate new open water." |
| Dark HH after event | "The radar return is low after the event, which is consistent with a smooth water surface reflecting energy away from the satellite." |
| Stable result across thresholds | "This change remains marked under all three detection settings. That makes it less sensitive to the selected thresholds, but does not confirm flooding." |
| Marginal threshold result | "This area appears only under the less strict setting. The change is uncertain and needs review." |
| HH-only signal | "The HH channel became darker, but the HV channel did not show enough matching change. This result needs extra checking." |
| Small change / noncandidate | "Radar measurements changed only slightly here. The current method did not flag a possible flood." |
| Invalid coverage | "There is not enough valid radar data here to assess the change reliably." |
| Possible soil-wetting effect | "A brighter radar return may reflect wetter soil, not necessarily deeper or more widespread flooding." |

**For the first actual example:** "HH fell by 5.39 dB and HV by 3.15 dB between 5 and 17 January. Both channels support a possible open-water change; this is not independently confirmed flooding."  
**For the second actual example:** "HH changed by +0.18 dB and HV by −0.14 dB. Neither shows the strong darkening used by this flood-candidate detector."

A threshold stability value **must never be directly relabeled as `confidence=0.33/0.67/1.0`**; these are not calibrated probabilities. If the frontend schema requires `confidence` (0–1), use a clearly documented and separately assessed estimation approach, or flag the value as heuristic and nonprobabilistic; coordinate schema constraints with the validation developer.

## 6. Radar vs. Clouds — optional feature

**Website-friendly text:** "Ordinary satellite cameras record sunlight reflected from the ground. Thick clouds can block that view. NISAR uses its own microwave radar signals, so it can often observe the land through clouds, by day or night. This helps us compare conditions before and after storms, when clear optical images may be unavailable. Radar is not magic: heavy rain, surface roughness, vegetation and radar viewing geometry can still complicate flood detection."

For a visual comparison, place a **real, dated optical image** next to a **real, dated NISAR radar image** with clear source credits and acquisition dates. **Do not imply** that NISAR images display true colours or that an unrelated cloudy optical image was acquired at the same time. As of the supplied repository, `docs/DATA_SOURCES.md` marks the optical source as **TBD**; this feature is explanatory until such a source is chosen.

## 7. Review checklist for the SAR handoff

- [x] Inspect the supplied `data/` extraction scripts, HH previews and dual-pol detector.
- [x] Document data units, projections, masks and the current `near` setting.
- [x] Reproduce two illustrative *actual* HH/HV pixel comparisons.
- [x] Recommend 10 m→60 m **linear-power `average`**, conversion and filtering order.
- [ ] Re-extract the original NISAR GCOV rasters with the approved averaging setting (**not done here**).
- [ ] Compare candidate maps and no-flood controls with the prior nearest-neighbor baseline.
- [ ] Produce updated `before.tif` and `after.tif` and regenerate dependent website layers (**not done here**).
- [ ] Validate candidate flood labels against temporally appropriate external evidence.

## References

1. **ASF, NISAR GCOV Data User Guide** — explains calibrated gamma0 power, geocoding and radiometric terrain correction: https://nisar-docs.asf.alaska.edu/gcov/
2. **NASA Earthdata, Synthetic Aperture Radar (SAR)** — scattering and polarization mechanisms: https://www.earthdata.nasa.gov/learn/earth-observation-data-basics/sar
3. **NASA Applied Sciences, Introduction to SAR Part 1 Q&A** — specular open water, double-bounce inundated vegetation, and false-positive surfaces: https://appliedsciences.nasa.gov/sites/default/files/2024-12/SAR_Part1_QandA.pdf
4. **NASA, NISAR Beta GCOV V1 data product** — release/product context: https://data.nasa.gov/dataset/nisar-beta-geocoded-polarimetric-covariance-product-version-1
5. **Team source and output contract** — `docs/DATA_SOURCES.md`, `data/README.md`, `data/scripts/nisar_extract_v4.py`, `algorithm/flood_detection_v2.py`, `algorithm/results_v2/evidence_v2.json`, `schema/README.md` (supplied repository ZIP).
