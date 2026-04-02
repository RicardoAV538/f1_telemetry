const connectionPill = document.getElementById("connection-pill");
const updatedAtEl = document.getElementById("updated-at");
const raceAlert = document.getElementById("race-alert");
const gridBody = document.getElementById("grid-body");

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
  raceAlert.className = "race-alert";
  raceAlert.textContent = raceControl?.label || "Green Flag";
  if (raceControl?.css_class) raceAlert.classList.add(raceControl.css_class);
}

function renderGrid(rows, driverName) {
  gridBody.innerHTML = (rows || []).map((row) => {
    const isSelf = row.name === driverName;
    return `
      <tr class="${isSelf ? "driver-self" : ""}">
        <td class="pos-cell">${row.position}</td>
        <td>${row.race_number}</td>
        <td>${row.name}</td>
        <td>${row.team_name}</td>
        <td>${tyreBadge(row.visual_compound)}</td>
        <td>${row.current_lap}</td>
        <td>${row.gap_to_ahead}</td>
        <td>${row.num_pit_stops ?? 0}</td>
        <td>${formatLapTime(row.last_lap_time)}</td>
        <td class="ers-cell">${row.ers_store_pct ?? 0}%</td>
        <td>${row.sector}</td>
        <td><span class="status-chip">${row.pit_status}</span></td>
        <td>${row.speed_kph}</td>
      </tr>
    `;
  }).join("");
}

const protocol = location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(`${protocol}://${location.host}/ws`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  connectionPill.textContent = data.meta?.connected ? "LIVE" : "OFFLINE";
  connectionPill.classList.toggle("live", !!data.meta?.connected);
  updatedAtEl.textContent = `Updated ${formatUpdatedAt(data.meta?.updated_at)}`;
  const gv = document.getElementById("game-version");
  if (gv) gv.textContent = data.meta?.game_version ?? "-";
  setRaceAlert(data.race_control);
  renderGrid(data.live_grid, data.driver?.name);
};

ws.onclose = () => {
  connectionPill.textContent = "OFFLINE";
  connectionPill.classList.remove("live");
};
