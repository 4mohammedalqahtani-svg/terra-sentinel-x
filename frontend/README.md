# Frontend

From the repository root, run `python backend/serve.py` and open
`http://localhost:8000`. See the [backend setup](../backend/README.md) for
Python dependencies and publishing. The site uses vendored Leaflet 1.9.4
([license](vendor/leaflet/LICENSE)) and the published radar images as the map
background. It needs no external map tiles or JavaScript build step.

- Drag the map divider or use the arrow keys on the comparison slider.
- Select **Reveal changes** to show the candidate raster and clickable areas.
- Enable **Smart Doubt** to color polygons by threshold sensitivity. **Needs
  review only** shows the high-doubt polygons.
- Click a polygon or use **Find a change area** and **Inspect** to open its
  Evidence Card.

The frontend reads `data/runs.json` and resolves all run assets relative to
their `run.json`. The index selects the initial run, and synthetic runs carry
a visible label. See the [shared output schema](../schema/README.md).
