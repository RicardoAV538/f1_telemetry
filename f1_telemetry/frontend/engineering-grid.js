const connectionPill = document.getElementById("connection-pill");
const updatedAtEl = document.getElementById("updated-at");
const raceAlert = document.getElementById("race-alert");
const gridBody = document.getElementById("engineering-grid-body");
const gridHead = document.getElementById("engineering-grid-head");

function formatUpdatedAt(value) {
  if (!value) return "--";
  return new Date(value).toLocaleTimeString("pt-BR");
}

function formatLapTime(seconds) {
  const s = Number(seconds || 0);
  if (!s) return "-";
  const minutes = Math.floor(s / 60);
  const remaining = s - minutes * 60;
  const formattedSeconds = remaining.toFixed(3).padStart(minutes > 0 ? 6 : 0, "0");
  return minutes > 0 ? `${minutes}:${formattedSeconds}` : `${formattedSeconds}s`;
}

function tyreBadge(compound) {
  const key = String(compound || "").toLowerCase();
  let css = "tyre-unknown";
  let label = compound || "-";

  if (key.includes("soft")) css = "tyre-soft";
  else if (key.includes("medium")) css = "tyre-medium";
  else if (key.includes("hard")) css = "tyre-hard";
  else if (key.includes("inter")) css = "tyre-inter";
  else if (key.includes("wet")) css = "tyre-wet";

  return `<span class="tyre-badge ${css}">${label}</span>`;
}

function setRaceAlert(raceControl) {
  if (!raceAlert) return;
  raceAlert.className = "race-alert";
  raceAlert.textContent = raceControl?.label || "Bandeira Verde";
  if (raceControl?.css_class) raceAlert.classList.add(raceControl.css_class);
}

function wearClass(value) {
  const wear = Number(value || 0);
  if (wear >= 60) return "wear-high";
  if (wear >= 30) return "wear-mid";
  return "wear-good";
}

function wearCell(value) {
  const wear = Number(value ?? 0);
  return `<span class="${wearClass(wear)}">${wear.toFixed(0)}%</span>`;
}

/* ── Column definitions ── */
const COLUMN_DEFS = [
  { id: "pos",       label: "Pos",      cell: (r) => `<td class="pos-cell">${r.position ?? "-"}</td>` },
  { id: "num",       label: "#",        cell: (r) => `<td>${r.race_number ?? "-"}</td>` },
  { id: "driver",    label: "Driver",   cell: (r) => `<td>${r.name ?? "-"}</td>` },
  { id: "team",      label: "Team",     cell: (r) => `<td>${r.team_name ?? "-"}</td>` },
  { id: "tyre",      label: "Tyre",     cell: (r) => `<td>${tyreBadge(r.visual_compound)}</td>` },
  { id: "lap",       label: "Lap",      cell: (r) => `<td>${r.current_lap ?? "-"}</td>` },
  { id: "ahead",     label: "Ahead",    cell: (r) => `<td>${r.gap_to_ahead ?? "-"}</td>` },
  { id: "leader",    label: "Leader",   cell: (r) => `<td>${r.gap_to_leader ?? "-"}</td>` },
  { id: "s1",        label: "S1",       cell: (r) => `<td>${formatLapTime(r.sector1_time)}</td>` },
  { id: "s2",        label: "S2",       cell: (r) => `<td>${formatLapTime(r.sector2_time)}</td>` },
  { id: "s3",        label: "S3",       cell: (r) => `<td>${formatLapTime(r.sector3_time)}</td>` },
  { id: "current",   label: "Current",  cell: (r) => `<td>${formatLapTime(r.current_lap_time)}</td>` },
  { id: "last",      label: "Last",     cell: (r) => `<td>${formatLapTime(r.last_lap_time)}</td>` },
  { id: "pits",      label: "Pits",     cell: (r) => `<td>${r.num_pit_stops ?? 0}</td>` },
  { id: "fl",        label: "FL",       cell: (r) => { const w = Array.isArray(r.tyres_wear) ? r.tyres_wear : [0,0,0,0]; return `<td>${wearCell(w[0])}</td>`; } },
  { id: "fr",        label: "FR",       cell: (r) => { const w = Array.isArray(r.tyres_wear) ? r.tyres_wear : [0,0,0,0]; return `<td>${wearCell(w[1])}</td>`; } },
  { id: "rl",        label: "RL",       cell: (r) => { const w = Array.isArray(r.tyres_wear) ? r.tyres_wear : [0,0,0,0]; return `<td>${wearCell(w[2])}</td>`; } },
  { id: "rr",        label: "RR",       cell: (r) => { const w = Array.isArray(r.tyres_wear) ? r.tyres_wear : [0,0,0,0]; return `<td>${wearCell(w[3])}</td>`; } },
  { id: "ers_mode",  label: "ERS Mode", cell: (r) => `<td><span class="mono-badge">${r.ers_mode ?? "-"}</span></td>` },
  { id: "ers_pct",   label: "ERS %",    cell: (r) => `<td>${r.ers_store_pct ?? 0}%</td>` },
  { id: "drs",       label: "DRS",      cell: (r) => `<td class="${r.drs_on ? "drs-on" : "drs-off"}">${r.drs_on ? "ON" : "OFF"}</td>` },
  { id: "status",    label: "Status",   cell: (r) => `<td>${r.pit_status ?? "-"}</td>` },
];

const STORAGE_KEY = "eng_grid_col_order";
const DEFAULT_ORDER = COLUMN_DEFS.map((c) => c.id);

function loadColumnOrder() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return DEFAULT_ORDER.slice();
    const parsed = JSON.parse(saved);
    const validIds = new Set(DEFAULT_ORDER);
    const filtered = parsed.filter((id) => validIds.has(id));
    for (const id of DEFAULT_ORDER) {
      if (!filtered.includes(id)) filtered.push(id);
    }
    return filtered;
  } catch {
    return DEFAULT_ORDER.slice();
  }
}

function saveColumnOrder(order) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(order)); } catch {}
}

let columnOrder = loadColumnOrder();

function getOrderedDefs() {
  const map = {};
  for (const def of COLUMN_DEFS) map[def.id] = def;
  return columnOrder.map((id) => map[id]).filter(Boolean);
}

/* ── Drag-and-drop header reordering ── */
let dragSrcIdx = null;

function renderHeader() {
  if (!gridHead) return;
  const ordered = getOrderedDefs();
  gridHead.innerHTML = ordered.map((col, i) => {
    return `<th draggable="true" data-col-idx="${i}" title="Drag to reorder">${col.label}</th>`;
  }).join("");

  const ths = gridHead.querySelectorAll("th");
  ths.forEach((th) => {
    th.addEventListener("dragstart", onDragStart);
    th.addEventListener("dragover", onDragOver);
    th.addEventListener("dragenter", onDragEnter);
    th.addEventListener("dragleave", onDragLeave);
    th.addEventListener("drop", onDrop);
    th.addEventListener("dragend", onDragEnd);
  });
}

function onDragStart(e) {
  dragSrcIdx = Number(this.dataset.colIdx);
  this.classList.add("col-dragging");
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", String(dragSrcIdx));
}

function onDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
}

function onDragEnter(e) {
  e.preventDefault();
  this.classList.add("col-drag-over");
}

function onDragLeave() {
  this.classList.remove("col-drag-over");
}

function onDrop(e) {
  e.preventDefault();
  e.stopPropagation();
  this.classList.remove("col-drag-over");
  const targetIdx = Number(this.dataset.colIdx);
  if (dragSrcIdx === null || dragSrcIdx === targetIdx) return;

  const moved = columnOrder.splice(dragSrcIdx, 1)[0];
  const adjustedTarget = dragSrcIdx < targetIdx ? targetIdx - 1 : targetIdx;
  columnOrder.splice(adjustedTarget, 0, moved);
  saveColumnOrder(columnOrder);
  renderHeader();
  if (lastRows !== null) renderRows(lastRows, lastDriverName);
}

function onDragEnd() {
  this.classList.remove("col-dragging");
  if (gridHead) {
    gridHead.querySelectorAll("th").forEach((th) => th.classList.remove("col-drag-over"));
  }
}

/* ── Reset button ── */
const resetBtn = document.getElementById("reset-columns");
if (resetBtn) {
  resetBtn.addEventListener("click", () => {
    columnOrder = DEFAULT_ORDER.slice();
    saveColumnOrder(columnOrder);
    renderHeader();
    if (lastRows !== null) renderRows(lastRows, lastDriverName);
  });
}

/* ── Render rows ── */
let lastRows = null;
let lastDriverName = null;

function renderRows(rows, driverName) {
  if (!gridBody) return;
  lastRows = rows;
  lastDriverName = driverName;

  const ordered = getOrderedDefs();
  gridBody.innerHTML = (rows || []).map((row) => {
    const isSelf = row.name === driverName;
    return `<tr class="${isSelf ? "driver-self" : ""}">${ordered.map((col) => col.cell(row)).join("")}</tr>`;
  }).join("");
}

/* ── Initial header render ── */
renderHeader();

/* ── WebSocket ── */
const protocol = location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(`${protocol}://${location.host}/ws`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (connectionPill) {
    connectionPill.textContent = data.meta?.connected ? "LIVE" : "OFFLINE";
    connectionPill.classList.toggle("live", !!data.meta?.connected);
  }

  if (updatedAtEl) {
    updatedAtEl.textContent = `Updated ${formatUpdatedAt(data.meta?.updated_at)}`;
  }

  const gv = document.getElementById("game-version");
  if (gv) gv.textContent = data.meta?.game_version ?? "-";

  setRaceAlert(data.race_control);
  renderRows(data.live_grid, data.driver?.name);
};

ws.onclose = () => {
  if (connectionPill) {
    connectionPill.textContent = "OFFLINE";
    connectionPill.classList.remove("live");
  }
};
