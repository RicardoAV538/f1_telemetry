const connectionPill = document.getElementById("connection-pill");
const updatedAtEl = document.getElementById("updated-at");
const raceAlert = document.getElementById("race-alert");
const gridBody = document.getElementById("engineering-grid-body");

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

function renderRows(rows, driverName) {
  if (!gridBody) return;

  gridBody.innerHTML = (rows || []).map((row) => {
    const isSelf = row.name === driverName;
    const wear = Array.isArray(row.tyres_wear) ? row.tyres_wear : [0, 0, 0, 0];

    return `
      <tr class="${isSelf ? "driver-self" : ""}">
        <td class="pos-cell">${row.position ?? "-"}</td>
        <td>${row.race_number ?? "-"}</td>
        <td>${row.name ?? "-"}</td>
        <td>${row.team_name ?? "-"}</td>
        <td>${tyreBadge(row.visual_compound)}</td>
        <td>${row.current_lap ?? "-"}</td>
        <td>${row.gap_to_ahead ?? "-"}</td>
        <td>${row.gap_to_leader ?? "-"}</td>
        <td>${formatLapTime(row.sector1_time)}</td>
        <td>${formatLapTime(row.sector2_time)}</td>
        <td>${formatLapTime(row.sector3_time)}</td>
        <td>${formatLapTime(row.current_lap_time)}</td>
        <td>${formatLapTime(row.last_lap_time)}</td>
        <td>${row.num_pit_stops ?? 0}</td>
        <td>${wearCell(wear[0])}</td>
        <td>${wearCell(wear[1])}</td>
        <td>${wearCell(wear[2])}</td>
        <td>${wearCell(wear[3])}</td>
        <td><span class="mono-badge">${row.ers_mode ?? "-"}</span></td>
        <td>${row.ers_store_pct ?? 0}%</td>
        <td class="${row.drs_on ? "drs-on" : "drs-off"}">${row.drs_on ? "ON" : "OFF"}</td>
        <td>${row.pit_status ?? "-"}</td>
      </tr>
    `;
  }).join("");
}

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

  setRaceAlert(data.race_control);
  renderRows(data.live_grid, data.driver?.name);
};

ws.onclose = () => {
  if (connectionPill) {
    connectionPill.textContent = "OFFLINE";
    connectionPill.classList.remove("live");
  }
};
