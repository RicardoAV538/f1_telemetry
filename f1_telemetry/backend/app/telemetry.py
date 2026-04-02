import socket
import threading
from datetime import datetime

from .state import race_state
from .mappings import (
    TRACKS, TEAMS, WEATHER, SECTORS, PIT_STATUS, DRIVER_STATUS,
    RESULT_STATUS, SAFETY_CAR, ERS_MODE, FIA_FLAGS,
    ACTUAL_TYRE_COMPOUND, VISUAL_TYRE_COMPOUND, EVENT_CODES,
    GAME_VERSION_LABEL,
)
from .adapters import (
    unpack_packet,
    SESSION, PARTICIPANTS, LAP_DATA, CAR_TELEMETRY,
    CAR_STATUS, EVENT, CAR_DAMAGE,
    normalize_session, normalize_participants, normalize_lap_data,
    normalize_car_telemetry, normalize_car_status, normalize_car_damage,
    normalize_event,
)

player_index = 0
current_game_version = 0
participants_snapshot = {}
lap_snapshot = {}
telemetry_snapshot = {}
status_snapshot = {}
damage_snapshot = {}  # F1 2021: separate damage packet

def decode_name(raw_name):
    if isinstance(raw_name, bytes):
        return raw_name.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
    return str(raw_name)

def append_event(text):
    race_state["events"] = ([text] + race_state["events"])[:12]

def set_meta(packet_type, game_version=0):
    race_state["meta"]["connected"] = True
    race_state["meta"]["packet_type"] = packet_type
    race_state["meta"]["updated_at"] = datetime.utcnow().isoformat() + "Z"
    if game_version:
        race_state["meta"]["game_version"] = GAME_VERSION_LABEL.get(
            game_version, f"F1 {game_version}"
        )

def normalize_gear(gear):
    if gear == -1:
        return "R"
    if gear == 0:
        return "N"
    return str(gear)

def estimate_gaps(sorted_grid):
    leader = sorted_grid[0] if sorted_grid else None
    previous = None

    for row in sorted_grid:
        if previous is None:
            row["gap_to_ahead"] = "LÍDER"
        else:
            same_lap_prev = row.get("current_lap", 0) == previous.get("current_lap", 0)
            if same_lap_prev:
                delta_distance = float(previous.get("lap_distance", 0.0)) - float(row.get("lap_distance", 0.0))
                if delta_distance < 0:
                    delta_distance += 5500
                speed_ms = max(float(row.get("speed_kph", 150)) / 3.6, 1.0)
                row["gap_to_ahead"] = f"+{delta_distance / speed_ms:.1f}s"
            else:
                lap_gap = previous.get("current_lap", 0) - row.get("current_lap", 0)
                row["gap_to_ahead"] = f"+{lap_gap} VOLTA(S)"

        if leader is None or row is leader:
            row["gap_to_leader"] = "LÍDER"
        else:
            same_lap_leader = row.get("current_lap", 0) == leader.get("current_lap", 0)
            if same_lap_leader:
                delta_distance = float(leader.get("lap_distance", 0.0)) - float(row.get("lap_distance", 0.0))
                if delta_distance < 0:
                    delta_distance += 5500
                speed_ms = max(float(row.get("speed_kph", 150)) / 3.6, 1.0)
                row["gap_to_leader"] = f"+{delta_distance / speed_ms:.1f}s"
            else:
                lap_gap = leader.get("current_lap", 0) - row.get("current_lap", 0)
                row["gap_to_leader"] = f"+{lap_gap} VOLTA(S)"

        previous = row


def rebuild_live_grid():
    rows = []

    for idx, participant in participants_snapshot.items():
        # Skip empty/placeholder participant slots (e.g. F1 2020 sends 22
        # slots but only 20 are real drivers; the blanks default to team 0
        # which maps to Mercedes, creating phantom entries).
        name = participant.get("name", "")
        if not name or not name.strip():
            continue

        lap = lap_snapshot.get(idx, {})
        tel = telemetry_snapshot.get(idx, {})
        status = status_snapshot.get(idx, {})

        result_status = lap.get("result_status_code", 0)
        if result_status == 1:
            continue

        row = {
            "car_index": idx,
            "position": lap.get("position", 99),
            "name": participant.get("name", f"Driver {idx}"),
            "team_name": participant.get("team_name", "-"),
            "race_number": participant.get("race_number", 0),
            "current_lap": lap.get("current_lap", 0),
            "sector": lap.get("sector", "-"),
            "pit_status": lap.get("pit_status", "-"),
            "driver_status": lap.get("driver_status", "-"),
            "result_status": lap.get("result_status", "-"),
            "lap_distance": lap.get("lap_distance", 0.0),
            "total_distance": lap.get("total_distance", 0.0),
            "current_lap_time": lap.get("current_lap_time", 0.0),
            "last_lap_time": lap.get("last_lap_time", 0.0),
            "best_lap_time": lap.get("best_lap_time", 0.0),
            "sector1_time": lap.get("sector1_time", 0.0),
            "sector2_time": lap.get("sector2_time", 0.0),
            "sector3_time": lap.get("sector3_time", 0.0),
            "num_pit_stops": lap.get("num_pit_stops", 0),
            "speed_kph": tel.get("speed_kph", 0),
            "drs_on": tel.get("drs_on", False),
            "visual_compound": status.get("visual_compound", "-"),
            "actual_compound": status.get("actual_compound", "-"),
            "ers_mode": status.get("ers_mode", "-"),
            "ers_store_pct": status.get("ers_store_pct", 0),
            "fuel_remaining_laps": status.get("fuel_remaining_laps", 0),
            "tyre_wear_avg": status.get("tyre_wear_avg", 0),
            "tyres_wear": status.get("tyres_wear", [0, 0, 0, 0]),
        }

        rows.append(row)

    rows.sort(key=lambda x: (x["position"], -x["current_lap"], -x["total_distance"]))
    estimate_gaps(rows)
    race_state["live_grid"] = rows

def process_packet(game_version, canonical_type, packet, pkt_player_index):
    """Process a normalized packet from any supported game version."""
    global player_index, current_game_version

    player_index = pkt_player_index
    current_game_version = game_version
    set_meta(canonical_type, game_version)

    if canonical_type == SESSION:
        data = normalize_session(game_version, packet)
        race_state["session"].update({
            "track_name": TRACKS.get(data["track_id"], f"Track {data['track_id']}"),
            "weather_label": WEATHER.get(data["weather"], f"Weather {data['weather']}"),
            "total_laps": data["total_laps"],
            "session_time_left_s": data["session_time_left"],
            "air_temp_c": data["air_temperature"],
            "track_temp_c": data["track_temperature"],
            "safety_car_status": SAFETY_CAR.get(
                data["safety_car_status"], str(data["safety_car_status"])
            ),
        })

    elif canonical_type == PARTICIPANTS:
        participants = normalize_participants(game_version, packet)
        for idx, p in enumerate(participants):
            participants_snapshot[idx] = {
                "name": decode_name(p["name"]),
                "team_name": TEAMS.get(p["team_id"], f"Team {p['team_id']}"),
                "race_number": p["race_number"],
            }

        participant = participants_snapshot.get(player_index, {})
        race_state["driver"].update({
            "name": participant.get("name", "-"),
            "team_name": participant.get("team_name", "-"),
            "race_number": participant.get("race_number", 0),
        })
        rebuild_live_grid()

    elif canonical_type == LAP_DATA:
        laps = normalize_lap_data(game_version, packet)
        for idx, lap in enumerate(laps):
            sector1 = round(lap["sector1_time_s"], 3)
            sector2 = round(lap["sector2_time_s"], 3)
            current_lap_t = round(lap["current_lap_time_s"], 3)
            last_lap_t = round(lap["last_lap_time_s"], 3)

            sector3 = 0.0
            if last_lap_t > 0 and sector1 > 0 and sector2 > 0:
                sector3 = round(max(last_lap_t - sector1 - sector2, 0.0), 3)

            lap_snapshot[idx] = {
                "position": lap["car_position"],
                "current_lap": lap["current_lap_num"],
                "sector": SECTORS.get(lap["sector"], str(lap["sector"])),
                "pit_status": PIT_STATUS.get(lap["pit_status"], str(lap["pit_status"])),
                "driver_status": DRIVER_STATUS.get(
                    lap["driver_status"], str(lap["driver_status"])
                ),
                "result_status": RESULT_STATUS.get(
                    lap["result_status"], str(lap["result_status"])
                ),
                "result_status_code": lap["result_status"],
                "lap_distance": lap["lap_distance"],
                "total_distance": lap["total_distance"],
                "current_lap_time": current_lap_t,
                "last_lap_time": last_lap_t,
                "best_lap_time": round(lap["best_lap_time_s"], 3),
                "sector1_time": sector1,
                "sector2_time": sector2,
                "sector3_time": sector3,
                "penalties_s": lap["penalties"],
                "num_pit_stops": lap["num_pit_stops"],
            }

        player_lap = lap_snapshot.get(player_index, {})
        race_state["driver"].update({
            "position": player_lap.get("position", 0),
            "sector": player_lap.get("sector", "-"),
            "pit_status": player_lap.get("pit_status", "-"),
            "driver_status": player_lap.get("driver_status", "-"),
            "result_status": player_lap.get("result_status", "-"),
        })
        race_state["session"]["current_lap"] = player_lap.get("current_lap", 0)
        race_state["lap"].update({
            "last_lap_s": player_lap.get("last_lap_time", 0),
            "best_lap_s": player_lap.get("best_lap_time", 0),
            "current_lap_s": player_lap.get("current_lap_time", 0),
            "penalties_s": player_lap.get("penalties_s", 0),
        })
        rebuild_live_grid()

    elif canonical_type == CAR_TELEMETRY:
        tel_list = normalize_car_telemetry(game_version, packet)
        for idx, tel in enumerate(tel_list):
            telemetry_snapshot[idx] = {
                "speed_kph": tel["speed"],
                "gear": normalize_gear(tel["gear"]),
                "rpm": tel["engine_rpm"],
                "throttle_pct": round(tel["throttle"] * 100, 1),
                "brake_pct": round(tel["brake"] * 100, 1),
                "steering": round(tel["steer"], 3),
                "drs_on": tel["drs"],
                "rev_lights_pct": tel["rev_lights_percent"],
                "engine_temp_c": tel["engine_temperature"],
                "brake_temps_c": tel["brakes_temperature"],
                "surface_temp_c": tel["tyres_surface_temperature"],
                "inner_temp_c": tel["tyres_inner_temperature"],
                "pressure_psi": tel["tyres_pressure"],
            }

        player_tel = telemetry_snapshot.get(player_index, {})
        race_state["car"].update({
            "speed_kph": player_tel.get("speed_kph", 0),
            "gear": player_tel.get("gear", "N"),
            "rpm": player_tel.get("rpm", 0),
            "throttle_pct": player_tel.get("throttle_pct", 0),
            "brake_pct": player_tel.get("brake_pct", 0),
            "steering": player_tel.get("steering", 0),
            "drs_on": player_tel.get("drs_on", False),
            "rev_lights_pct": player_tel.get("rev_lights_pct", 0),
            "engine_temp_c": player_tel.get("engine_temp_c", 0),
            "brake_temps_c": player_tel.get("brake_temps_c", [0, 0, 0, 0]),
        })
        race_state["tyres"].update({
            "surface_temp_c": player_tel.get("surface_temp_c", [0, 0, 0, 0]),
            "inner_temp_c": player_tel.get("inner_temp_c", [0, 0, 0, 0]),
            "pressure_psi": player_tel.get("pressure_psi", [0, 0, 0, 0]),
        })
        rebuild_live_grid()

    elif canonical_type == CAR_STATUS:
        statuses = normalize_car_status(game_version, packet)
        for idx, st in enumerate(statuses):
            tyres_wear = st["tyres_wear"]
            # For F1 2021, damage comes from a separate packet;
            # merge existing damage_snapshot data if available.
            dmg = damage_snapshot.get(idx, {})
            if game_version == 2021 and dmg:
                tyres_wear = dmg.get("tyres_wear", tyres_wear)

            status_snapshot[idx] = {
                "actual_compound": ACTUAL_TYRE_COMPOUND.get(
                    st["actual_tyre_compound"], str(st["actual_tyre_compound"])
                ),
                "visual_compound": VISUAL_TYRE_COMPOUND.get(
                    st["visual_tyre_compound"], str(st["visual_tyre_compound"])
                ),
                "fuel_in_tank_kg": round(st["fuel_in_tank"], 2),
                "fuel_capacity_kg": round(st["fuel_capacity"], 2),
                "fuel_remaining_laps": round(st["fuel_remaining_laps"], 2),
                "ers_store_j": round(st["ers_store_energy"], 2),
                "ers_store_pct": ers_percent(st["ers_store_energy"]),
                "ers_deployed_this_lap_j": round(st["ers_deployed_this_lap"], 2),
                "ers_mode": ERS_MODE.get(st["ers_deploy_mode"], str(st["ers_deploy_mode"])),
                "drs_allowed": st["drs_allowed"],
                "tyres_wear": tyres_wear,
                "tyres_damage": dmg.get("tyres_damage", st["tyres_damage"]) if game_version == 2021 else st["tyres_damage"],
                "tyre_wear_avg": round(sum(tyres_wear) / 4, 1),
                "front_left_wing_pct": dmg.get("front_left_wing_damage", st["front_left_wing_damage"]) if game_version == 2021 else st["front_left_wing_damage"],
                "front_right_wing_pct": dmg.get("front_right_wing_damage", st["front_right_wing_damage"]) if game_version == 2021 else st["front_right_wing_damage"],
                "rear_wing_pct": dmg.get("rear_wing_damage", st["rear_wing_damage"]) if game_version == 2021 else st["rear_wing_damage"],
                "engine_pct": dmg.get("engine_damage", st["engine_damage"]) if game_version == 2021 else st["engine_damage"],
                "gearbox_pct": dmg.get("gearbox_damage", st["gearbox_damage"]) if game_version == 2021 else st["gearbox_damage"],
                "fia_flag": FIA_FLAGS.get(
                    st["vehicle_fia_flags"], str(st["vehicle_fia_flags"])
                ),
            }

        player_st = status_snapshot.get(player_index, {})
        race_state["car"]["drs_allowed"] = player_st.get("drs_allowed", False)
        race_state["tyres"].update({
            "actual_compound": player_st.get("actual_compound", "-"),
            "visual_compound": player_st.get("visual_compound", "-"),
            "wear_pct": player_st.get("tyres_wear", [0, 0, 0, 0]),
            "damage_pct": player_st.get("tyres_damage", [0, 0, 0, 0]),
        })
        race_state["energy"].update({
            "fuel_in_tank_kg": player_st.get("fuel_in_tank_kg", 0),
            "fuel_capacity_kg": player_st.get("fuel_capacity_kg", 0),
            "fuel_remaining_laps": player_st.get("fuel_remaining_laps", 0),
            "ers_store_j": player_st.get("ers_store_j", 0),
            "ers_deployed_this_lap_j": player_st.get("ers_deployed_this_lap_j", 0),
            "ers_mode": player_st.get("ers_mode", "-"),
        })
        race_state["damage"].update({
            "front_left_wing_pct": player_st.get("front_left_wing_pct", 0),
            "front_right_wing_pct": player_st.get("front_right_wing_pct", 0),
            "rear_wing_pct": player_st.get("rear_wing_pct", 0),
            "engine_pct": player_st.get("engine_pct", 0),
            "gearbox_pct": player_st.get("gearbox_pct", 0),
            "fia_flag": player_st.get("fia_flag", "-"),
        })
        rebuild_live_grid()

    elif canonical_type == CAR_DAMAGE:
        # F1 2021 only: separate damage packet
        damages = normalize_car_damage(game_version, packet)
        for idx, dmg in enumerate(damages):
            damage_snapshot[idx] = dmg
            # If we already have a status_snapshot entry, update its damage fields
            if idx in status_snapshot:
                status_snapshot[idx]["tyres_wear"] = dmg["tyres_wear"]
                status_snapshot[idx]["tyres_damage"] = dmg["tyres_damage"]
                status_snapshot[idx]["tyre_wear_avg"] = round(
                    sum(dmg["tyres_wear"]) / 4, 1
                )
                status_snapshot[idx]["front_left_wing_pct"] = dmg["front_left_wing_damage"]
                status_snapshot[idx]["front_right_wing_pct"] = dmg["front_right_wing_damage"]
                status_snapshot[idx]["rear_wing_pct"] = dmg["rear_wing_damage"]
                status_snapshot[idx]["engine_pct"] = dmg["engine_damage"]
                status_snapshot[idx]["gearbox_pct"] = dmg["gearbox_damage"]

        player_dmg = damage_snapshot.get(player_index, {})
        if player_dmg:
            race_state["tyres"].update({
                "wear_pct": player_dmg.get("tyres_wear", [0, 0, 0, 0]),
                "damage_pct": player_dmg.get("tyres_damage", [0, 0, 0, 0]),
            })
            race_state["damage"].update({
                "front_left_wing_pct": player_dmg.get("front_left_wing_damage", 0),
                "front_right_wing_pct": player_dmg.get("front_right_wing_damage", 0),
                "rear_wing_pct": player_dmg.get("rear_wing_damage", 0),
                "engine_pct": player_dmg.get("engine_damage", 0),
                "gearbox_pct": player_dmg.get("gearbox_damage", 0),
            })
        rebuild_live_grid()

    elif canonical_type == EVENT:
        code = normalize_event(game_version, packet)
        append_event(EVENT_CODES.get(code, code))
        update_race_control()

def telemetry_loop(host="0.0.0.0", port=20777):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((host, port))

    while True:
        raw = udp_socket.recv(2048)
        try:
            version, canonical, packet, pidx = unpack_packet(raw)
            process_packet(version, canonical, packet, pidx)
        except Exception:
            pass

def start_telemetry_thread():
    thread = threading.Thread(target=telemetry_loop, daemon=True)
    thread.start()

def update_race_control():
    safety = race_state["session"].get("safety_car_status", "None")
    fia_flag = race_state["damage"].get("fia_flag", "Clear")
    events = race_state.get("events", [])

    if any("Chequered" in e or "Race winner" in e for e in events):
        race_state["race_control"] = {
            "status": "CHEQUERED",
            "label": "Chequered Flag",
            "css_class": "flag-chequered"
        }
    elif safety == "Full Safety Car":
        race_state["race_control"] = {
            "status": "SAFETY_CAR",
            "label": "Safety Car Deployed",
            "css_class": "flag-safety-car"
        }
    elif safety == "Virtual Safety Car":
        race_state["race_control"] = {
            "status": "VSC",
            "label": "Virtual Safety Car",
            "css_class": "flag-vsc"
        }
    elif fia_flag == "Yellow":
        race_state["race_control"] = {
            "status": "YELLOW",
            "label": "Yellow Flag",
            "css_class": "flag-yellow"
        }
    elif fia_flag == "Red":
        race_state["race_control"] = {
            "status": "RED",
            "label": "Red Flag",
            "css_class": "flag-red"
        }
    else:
        race_state["race_control"] = {
            "status": "GREEN",
            "label": "Green Flag",
            "css_class": "flag-green"
        }

def ers_percent(value_j):
    return round((float(value_j) / 4000000) * 100, 1)
