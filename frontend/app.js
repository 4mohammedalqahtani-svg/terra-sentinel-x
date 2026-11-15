const CHANGE = {
  likely_flood: { label: "Likely flood", color: "#6ad5ff" },
  possible_flood: { label: "Possible flood", color: "#ffc374" },
  other_change: { label: "Other change", color: "#e4deef" },
};

const DOUBT = {
  low: { label: "Low doubt · more stable", color: "#6de0b0" },
  medium: { label: "Medium doubt", color: "#ffd479" },
  high: { label: "High doubt · needs review", color: "#ff94ad", dashArray: "6 4" },
};

const $ = (id) => document.getElementById(id);
const count = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });
const area = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });
const date = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeZone: "UTC" });
const indexUrl = new URL("data/runs.json", document.baseURI);

const map = L.map("map", {
  crs: L.CRS.EPSG4326,
  zoomControl: false,
  scrollWheelZoom: false,
  zoomAnimation: false,
  zoomSnap: 0.25,
  minZoom: 1,
  maxZoom: 17,
  attributionControl: false,
});
L.control.zoom({ position: "bottomright" }).addTo(map);
L.control.scale({ imperial: false }).addTo(map);

// Layer order is fixed so changing filters cannot move a raster above the polygons.
map.createPane("radar").style.zIndex = "300";
map.createPane("changeRaster").style.zIndex = "350";

let entries = [];
let activeRequest;
let scene;
let reveal = false;
let popupTrigger;

async function readJson(url, signal) {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`HTTP ${response.status} loading ${url.pathname}`);
  return response.json();
}

async function loadImage(url) {
  const image = new Image();
  image.src = url;
  await image.decode();
  return image;
}

function fitScene() {
  map.fitBounds(scene.bounds, { padding: [14, 14], maxZoom: 15, animate: false });
}

function updateSwipe() {
  const percent = Number($("slider").value);
  $("map-frame").style.setProperty("--swipe-position", `${percent}%`);
  $("slider").setAttribute("aria-valuetext", `${percent}% before, ${100 - percent}% after`);
  const before = scene?.before.getElement();
  const after = scene?.after.getElement();
  if (!before || !after) return;

  const frame = map.getContainer().getBoundingClientRect();
  const imageBounds = after.getBoundingClientRect();
  const split = frame.left + frame.width * percent / 100;
  const crop = Math.max(0, Math.min(imageBounds.width, split - imageBounds.left));
  before.style.clipPath = `inset(0 ${imageBounds.width - crop}px 0 0)`;
  after.style.clipPath = `inset(0 0 0 ${crop}px)`;
}

function paragraph(text, className) {
  const element = document.createElement("p");
  element.textContent = text;
  if (className) element.className = className;
  return element;
}

function evidenceCard({ id, properties }) {
  const { evidence, reliability } = properties;
  const card = document.createElement("article");
  card.className = "evidence-card";
  const title = document.createElement("h2");
  title.tabIndex = -1;
  title.textContent = `Evidence Card · ${id}`;
  card.append(title, paragraph(CHANGE[properties.change_type].label));

  const fields = [
    ["Before", `${evidence.before_backscatter_db.toFixed(1)} dB`],
    ["After", `${evidence.after_backscatter_db.toFixed(1)} dB`],
    ["Change (after − before)", `${evidence.delta_db.toFixed(1)} dB`],
    ["Area", `${area.format(properties.area_km2)} km²`],
    ["Smart Doubt", DOUBT[reliability.doubt_level].label],
  ];
  if (Number.isFinite(reliability.stable_across_thresholds)) {
    fields.push([
      "Threshold Stability",
      `${count.format(reliability.stable_across_thresholds * 100)}%`,
    ]);
  }
  if (evidence.polarization) fields.push(["Polarization", evidence.polarization]);
  if (Number.isFinite(evidence.delta_hv_db)) {
    fields.push(["HV change", `${evidence.delta_hv_db.toFixed(1)} dB`]);
  }
  const list = document.createElement("dl");
  for (const [label, value] of fields) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = label;
    detail.textContent = value;
    row.append(term, detail);
    list.append(row);
  }
  card.append(list, paragraph(evidence.reason));
  if (reliability.notes) card.append(paragraph(reliability.notes, "evidence-notes"));
  return card;
}

function openEvidence(feature, position, trigger) {
  map.closePopup();
  const card = evidenceCard(feature);
  popupTrigger = trigger;
  L.popup({
    maxWidth: Math.min(290, map.getSize().x - 64),
    autoPanPaddingTopLeft: [14, 70],
    autoPanPaddingBottomRight: [14, 70],
  }).setLatLng(position).setContent(card).openOn(map);
  if (trigger) {
    card.closest(".leaflet-popup").scrollIntoView({ block: "nearest" });
    card.querySelector("h2").focus({ preventScroll: true });
  }
}

function regionStyle({ properties }) {
  const smartDoubt = $("smart-doubt").checked;
  const entry = smartDoubt ? DOUBT[properties.reliability.doubt_level] : CHANGE[properties.change_type];
  return { color: entry.color, dashArray: entry.dashArray, weight: 2, fillOpacity: smartDoubt ? 0.31 : 0.16 };
}

function renderLegend(smartDoubt, reviewOnly) {
  const key = smartDoubt ? DOUBT : CHANGE;
  const entries = reviewOnly ? [DOUBT.high] : Object.values(key);
  $("legend-title").textContent = smartDoubt ? "Threshold sensitivity" : "Change classification";
  $("legend-note").textContent = smartDoubt
    ? "Lower doubt indicates greater stability across tested detection thresholds."
    : "The raster shows candidate pixels. Outlines mark areas with Evidence Cards.";
  const items = entries.map(({ label, color, dashArray }) => {
    const item = document.createElement("li");
    const swatch = document.createElement("span");
    swatch.className = dashArray ? "legend-swatch dashed" : "legend-swatch";
    swatch.style.color = color;
    swatch.setAttribute("aria-hidden", "true");
    item.append(swatch, label);
    return item;
  });
  $("legend").replaceChildren(...items);
}

function syncChanges() {
  if (!scene) return;
  map.closePopup();
  const smartDoubt = $("smart-doubt").checked;
  const reviewOnly = $("review-only").checked;
  const selected = $("region").value;
  scene.polygons.clearLayers();
  scene.changeRaster.remove();
  $("layer-key").hidden = !reveal;
  $("layer-status").hidden = !reveal;
  $("inspect").hidden = true;
  $("reveal").setAttribute("aria-pressed", String(reveal));
  $("analysis-controls").disabled = !reveal;
  $("review-only").disabled = !smartDoubt;
  if (!reveal) return;

  // The raster includes candidates outside the filtered polygon set.
  if (!smartDoubt) scene.changeRaster.addTo(map);
  const visible = reviewOnly
    ? scene.features.filter((feature) => feature.properties.reliability.doubt_level === "high")
    : scene.features;
  scene.polygons.addData(visible);
  renderLegend(smartDoubt, reviewOnly);

  $("region").replaceChildren(new Option("Select an area", ""), ...visible.map(({ id, properties }) =>
    new Option(`${id} · ${area.format(properties.area_km2)} km²`, id)));
  $("region").value = visible.some(({ id }) => id === selected) ? selected : "";
  $("show-evidence").disabled = !$("region").value;
  $("inspect").hidden = visible.length === 0;
  if (visible.length === 0) {
    $("layer-status").textContent = reviewOnly ? "No areas need review in this run." : "No candidate areas in this run.";
  } else {
    const total = count.format(visible.length);
    const high = count.format(scene.highDoubt);
    $("layer-status").textContent = reviewOnly ? `Showing ${total} of ${count.format(scene.features.length)} areas`
      : `${total} mapped · ${high} need review`;
  }
}

function renderMethod(run) {
  const text = [];
  if (run.method?.name) text.push(paragraph(run.method.name));
  if (run.method?.notes) text.push(paragraph(run.method.notes));
  const validation = run.validation;
  if (validation?.reference) {
    const reference = [validation.reference, validation.reference_date].filter(Boolean).join(" · ");
    text.push(paragraph(reference));
    if (validation.agreement) text.push(paragraph(validation.agreement));
    if (Number.isFinite(validation.share_reference_overlapping_nisar_percent)) {
      text.push(paragraph(`${validation.share_reference_overlapping_nisar_percent}% of the reference flood extent overlaps NISAR candidates.`));
    }
  }
  if (run.limitations?.length) {
    const list = document.createElement("ul");
    for (const limitation of run.limitations) {
      const item = document.createElement("li");
      item.textContent = limitation;
      list.append(item);
    }
    text.push(list);
  }
  $("method-content").replaceChildren(...text);
  $("method").hidden = text.length === 0;
}

function showScene(run, changes, images) {
  const [west, south, east, north] = run.bounds;
  const bounds = L.latLngBounds([south, west], [north, east]);
  const before = L.imageOverlay(images[0], bounds, { pane: "radar" });
  const after = L.imageOverlay(images[1], bounds, { pane: "radar" });
  const changeRaster = L.imageOverlay(images[2], bounds, { pane: "changeRaster", opacity: 0.65 });
  const polygons = L.geoJSON(null, {
    style: regionStyle,
    onEachFeature(feature, layer) {
      layer.on("click", ({ latlng }) => openEvidence(feature, latlng));
    },
  });
  const features = changes.features;
  scene = {
    bounds, before, after, changeRaster, polygons, features,
    highDoubt: features.filter(({ properties }) => properties.reliability.doubt_level === "high").length,
  };
  before.addTo(map);
  after.addTo(map);
  polygons.addTo(map);
  fitScene();
  updateSwipe();

  $("location").textContent = run.aoi_name;
  $("event").textContent = run.demo ? "" : run.event ?? "";
  $("event").hidden = !$("event").textContent;
  $("run-status").textContent = run.demo ? "Synthetic demo data"
    : run.status === "EXPLORATORY_NOT_VALIDATED" ? "Exploratory analysis · validation pending"
      : (run.status ?? "").replaceAll("_", " ");
  $("run-status").hidden = !$("run-status").textContent;
  for (const time of ["before", "after"]) {
    const label = $(`${time}-date`);
    label.dateTime = run[time].date;
    label.textContent = date.format(new Date(run[time].date));
  }
  $("radar-channel").textContent = run.before.polarization === run.after.polarization && run.before.polarization
    ? `${run.before.polarization} backscatter` : "Backscatter";
  $("area-count").textContent = count.format(features.length);
  $("area-total").textContent = area.format(features.reduce((sum, { properties }) => sum + properties.area_km2, 0));
  for (const id of ["scene-labels", "swipe"]) $(id).hidden = false;
  for (const id of ["reveal", "reset-view"]) $(id).disabled = false;
  $("map-message").hidden = true;
  renderMethod(run);
  syncChanges();
}

async function loadRun(entry) {
  activeRequest?.abort();
  const request = new AbortController();
  activeRequest = request;
  map.closePopup();
  if (scene) {
    for (const layer of [scene.before, scene.after, scene.changeRaster, scene.polygons]) layer.remove();
    scene = null;
  }
  for (const id of ["scene-labels", "swipe", "retry", "event", "run-status", "layer-key", "layer-status", "inspect", "method"]) {
    $(id).hidden = true;
  }
  for (const id of ["reveal", "reset-view", "analysis-controls"]) $(id).disabled = true;
  $("location").textContent = entry.aoi_name;
  $("area-count").textContent = $("area-total").textContent = "—";
  $("region").replaceChildren();
  $("map-message").hidden = false;
  $("load-status").textContent = "Loading radar scenes…";

  try {
    const url = new URL(entry.path, indexUrl);
    const run = await readJson(url, request.signal);
    const [changes, ...images] = await Promise.all([
      readJson(new URL(run.changes, url), request.signal),
      ...[run.before.png, run.after.png, run.change_map.png].map((file) => loadImage(new URL(file, url))),
    ]);
    if (!request.signal.aborted) showScene(run, changes, images);
  } catch (error) {
    if (request.signal.aborted) return;
    console.error(error);
    $("load-status").textContent = "Could not load this run’s radar imagery or change data.";
    $("retry").hidden = false;
  }
}

function loadSelected() {
  return loadRun(entries.find(({ run_id }) => run_id === $("run").value));
}

async function initialize() {
  $("retry").hidden = true;
  $("load-status").textContent = "Loading radar scenes…";
  try {
    const index = await readJson(indexUrl);
    entries = index.runs;
    if (!entries.length) throw new Error("No published runs");
    $("run").replaceChildren(...entries.map((entry) => new Option(entry.aoi_name, entry.run_id)));
    $("run").value = entries.find(({ run_id }) => run_id === index.default)?.run_id ?? entries[0].run_id;
    $("run").disabled = false;
    await loadSelected();
  } catch (error) {
    console.error(error);
    $("load-status").textContent = "Could not load the list of analysis runs.";
    $("retry").hidden = false;
  }
}

$("run").addEventListener("change", loadSelected);
$("retry").addEventListener("click", () => entries.length ? loadSelected() : initialize());
$("slider").addEventListener("input", updateSwipe);
$("reset-view").addEventListener("click", fitScene);
$("reveal").addEventListener("click", () => {
  reveal = !reveal;
  syncChanges();
});
$("smart-doubt").addEventListener("change", () => {
  if (!$("smart-doubt").checked) $("review-only").checked = false;
  syncChanges();
});
$("review-only").addEventListener("change", syncChanges);
$("region").addEventListener("change", () => {
  $("show-evidence").disabled = !$("region").value;
});
$("show-evidence").addEventListener("click", () => {
  const layer = scene.polygons.getLayers().find(({ feature }) => feature.id === $("region").value);
  if (!layer) return;
  map.fitBounds(layer.getBounds(), { padding: [40, 40], maxZoom: 13, animate: false });
  openEvidence(layer.feature, layer.getBounds().getCenter(), $("show-evidence"));
});
map.on("move zoom resize", updateSwipe);
map.on("popupopen", () => $("map-frame").classList.add("has-popup"));
map.on("popupclose", () => {
  $("map-frame").classList.remove("has-popup");
  const focus = document.activeElement;
  if (popupTrigger && !popupTrigger.disabled && (focus === document.body || $("map").contains(focus))) {
    popupTrigger.focus();
  }
  popupTrigger = null;
});
$("map").addEventListener("keydown", (event) => {
  if (event.key === "Escape") map.closePopup();
});
new ResizeObserver(() => map.invalidateSize({ pan: false })).observe($("map"));
initialize();
