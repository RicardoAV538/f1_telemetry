const connectionPill = document.getElementById("connection-pill");
const updatedAtEl = document.getElementById("updated-at");
const gameVersionEl = document.getElementById("game-version");

const speedEl = document.getElementById("speed");
const gearEl = document.getElementById("gear");
const rpmEl = document.getElementById("rpm");
const throttleEl = document.getElementById("throttle");
const brakeEl = document.getElementById("brake");
const drsEl = document.getElementById("drs");

const tyreFl = document.getElementById("tyre-fl");
const tyreFr = document.getElementById("tyre-fr");
const tyreRl = document.getElementById("tyre-rl");
const tyreRr = document.getElementById("tyre-rr");

const fuelBar = document.getElementById("fuel-bar");
const ersBar = document.getElementById("ers-bar");
const flagBanner = document.getElementById("flag-banner");

const sessionGrid = document.getElementById("session-grid");
const driverGrid = document.getElementById("driver-grid");
const lapGrid = document.getElementById("lap-grid");
const carGrid = document.getElementById("car-grid");
const tyresGrid = document.getElementById("tyres-grid");
const energyGrid = document.getElementById("energy-grid");
const damageGrid = document.getElementById("damage-grid");
const eventsEl = document.getElementById("events");
const gridBody = document.getElementById("grid-body");

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    button.classList.add("active");
    document.getElementById(button.dataset.tab).classList.add("active");
  });
});

function item(label, value) {
  return `
    <div class="data-item">
      <span class="label">${label}</span>
      <span class="value">${value}</span>
    </div>
  `;
}

function formatArray(arr, suffix = "") {
  return Array.isArray(arr) ? arr.map(v => `${v}${suffix}`).join(" / ") : arr;
}

function renderGrid(el, rows) {
  el.innerHTML = rows.map(([label, value]) => item(label, value)).join("");
}

function formatUpdatedAt(value) {
  if (!value) return "--";
  return new Date(value).toLocaleTimeString("pt-BR");
}

function setFlag(flag) {
  flagBanner.className = "flag-banner";
  flagBanner.textContent = flag || "CLEAR";

  if (flag === "Green") flagBanner.classList.add("flag-green");
  if (flag === "Yellow") flagBanner.classList.add("flag-yellow");
  if (flag === "Red") flagBanner.classList.add("flag-red");
}

function renderEvents(events) {
  eventsEl.innerHTML = "";
  (events || []).forEach((eventText) => {
    const li = document.createElement("li");
    li.textContent = eventText;
    eventsEl.appendChild(li);
  });
}

function tyreChipLabel(compound) {
  if (!compound || compound === "-") return "-";
  return `<span class="tyre-chip">${compound}</span>`;
}

function renderLiveGrid(rows, driverName) {
  gridBody.innerHTML = (rows || []).map((row) => {
    const isSelf = row.name === driverName;
    return `
      <tr class="${isSelf ? "driver-self" : ""}">
        <td class="pos-cell">${row.position}</td>
        <td>${row.race_number}</td>
        <td>${row.name}</td>
        <td>${row.team_name}</td>
        <td>${tyreChipLabel(row.visual_compound)}</td>
        <td>${row.current_lap}</td>
        <td>${row.gap_to_ahead}</td>
        <td>${row.sector}</td>
        <td><span class="status-chip">${row.pit_status}</span></td>
        <td>${row.speed_kph}</td>
        <td>${row.gear}</td>
        <td>${row.throttle_pct}%</td>
        <td>${row.brake_pct}%</td>
        <td>${row.drs_on ? "ON" : "OFF"}</td>
      </tr>
    `;
  }).join("");
}

function render(data) {
  const { meta, session, driver, lap, car, tyres, energy, damage, events, live_grid } = data;

  connectionPill.textContent = meta?.connected ? "LIVE" : "OFFLINE";
  connectionPill.classList.toggle("live", !!meta?.connected);
  updatedAtEl.textContent = `Updated ${formatUpdatedAt(meta?.updated_at)}`;
  if (gameVersionEl) {
    gameVersionEl.textContent = meta?.game_version ?? "-";
  }

  speedEl.textContent = car?.speed_kph ?? 0;
  gearEl.textContent = car?.gear ?? "N";
  rpmEl.textContent = car?.rpm ?? 0;
  throttleEl.textContent = `${car?.throttle_pct ?? 0}%`;
  brakeEl.textContent = `${car?.brake_pct ?? 0}%`;
  drsEl.textContent = car?.drs_on ? "OPEN" : "OFF";

  const wear = tyres?.wear_pct ?? [0, 0, 0, 0];
  tyreFl.textContent = `${wear[0] ?? 0}%`;
  tyreFr.textContent = `${wear[1] ?? 0}%`;
  tyreRl.textContent = `${wear[2] ?? 0}%`;
  tyreRr.textContent = `${wear[3] ?? 0}%`;

  const fuelPct = Math.min(100, Math.max(0, ((energy?.fuel_in_tank_kg ?? 0) / Math.max(energy?.fuel_capacity_kg ?? 1, 1)) * 100));
  fuelBar.style.width = `${fuelPct}%`;

  const ersPct = Math.min(100, Math.max(0, ((energy?.ers_store_j ?? 0) / 4000000) * 100));
  ersBar.style.width = `${ersPct}%`;

  setFlag(damage?.fia_flag ?? "Clear");

  renderGrid(sessionGrid, [
    ["Track", session?.track_name ?? "-"],
    ["Weather", session?.weather_label ?? "-"],
    ["Lap", session?.current_lap ?? 0],
    ["Total Laps", session?.total_laps ?? 0],
    ["Time Left", `${session?.session_time_left_s ?? 0}s`],
    ["Air Temp", `${session?.air_temp_c ?? 0}°C`],
    ["Track Temp", `${session?.track_temp_c ?? 0}°C`],
    ["Safety Car", session?.safety_car_status ?? "-"],
  ]);

  renderGrid(driverGrid, [
    ["Driver", driver?.name ?? "-"],
    ["Team", driver?.team_name ?? "-"],
    ["Number", driver?.race_number ?? 0],
    ["Position", driver?.position ?? 0],
    ["Sector", driver?.sector ?? "-"],
    ["Pit", driver?.pit_status ?? "-"],
    ["Driver Status", driver?.driver_status ?? "-"],
    ["Result", driver?.result_status ?? "-"],
  ]);

  renderGrid(lapGrid, [
    ["Last Lap", `${lap?.last_lap_s ?? 0}s`],
    ["Best Lap", `${lap?.best_lap_s ?? 0}s`],
    ["Current Lap", `${lap?.current_lap_s ?? 0}s`],
    ["Penalties", `${lap?.penalties_s ?? 0}s`],
  ]);

  renderGrid(carGrid, [
    ["Steering", car?.steering ?? 0],
    ["DRS Allowed", car?.drs_allowed ? "Yes" : "No"],
    ["Rev Lights", `${car?.rev_lights_pct ?? 0}%`],
    ["Engine Temp", `${car?.engine_temp_c ?? 0}°C`],
    ["Brake Temps", formatArray(car?.brake_temps_c ?? [], "°C")],
  ]);

  renderGrid(tyresGrid, [
    ["Actual Compound", tyres?.actual_compound ?? "-"],
    ["Visual Compound", tyres?.visual_compound ?? "-"],
    ["Surface Temp", formatArray(tyres?.surface_temp_c ?? [], "°C")],
    ["Inner Temp", formatArray(tyres?.inner_temp_c ?? [], "°C")],
    ["Pressure", formatArray(tyres?.pressure_psi ?? [], " psi")],
    ["Damage", formatArray(tyres?.damage_pct ?? [], "%")],
  ]);

  renderGrid(energyGrid, [
    ["Fuel In Tank", `${energy?.fuel_in_tank_kg ?? 0} kg`],
    ["Fuel Capacity", `${energy?.fuel_capacity_kg ?? 0} kg`],
    ["Fuel Laps", energy?.fuel_remaining_laps ?? 0],
    ["ERS Store", `${energy?.ers_store_j ?? 0} J`],
    ["ERS Deploy Lap", `${energy?.ers_deployed_this_lap_j ?? 0} J`],
    ["ERS Mode", energy?.ers_mode ?? "-"],
  ]);

  renderGrid(damageGrid, [
    ["Front Left Wing", `${damage?.front_left_wing_pct ?? 0}%`],
    ["Front Right Wing", `${damage?.front_right_wing_pct ?? 0}%`],
    ["Rear Wing", `${damage?.rear_wing_pct ?? 0}%`],
    ["Engine", `${damage?.engine_pct ?? 0}%`],
    ["Gearbox", `${damage?.gearbox_pct ?? 0}%`],
    ["FIA Flag", damage?.fia_flag ?? "-"],
  ]);

  renderEvents(events);
  renderLiveGrid(live_grid, driver?.name);
}

const protocol = location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(`${protocol}://${location.host}/ws`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  render(data);
};

ws.onclose = () => {
  connectionPill.textContent = "OFFLINE";
  connectionPill.classList.remove("live");
};
