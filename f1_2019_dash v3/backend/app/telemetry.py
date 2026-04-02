import socket
import threading
from datetime import datetime

from f1_2019_telemetry.packets import unpack_udp_packet

from .state import race_state
from .mappings import (
    TRACKS, TEAMS, WEATHER, SECTORS, PIT_STATUS, DRIVER_STATUS,
    RESULT_STATUS, SAFETY_CAR, ERS_MODE, FIA_FLAGS,
    ACTUAL_TYRE_COMPOUND, VISUAL_TYRE_COMPOUND, EVENT_CODES
)

player_index = 0
participants_snapshot = {}
lap_snapshot = {}
telemetry_snapshot = {}
status_snapshot = {}

def decode_name(raw_name):
    if isinstance(raw_name, bytes):
        return raw_name.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
    return str(raw_name)

def append_event(text):
    race_state["events"] = ([text] + race_state["events"])[:12]

def set_meta(packet_type):
    race_state["meta"]["connected"] = True
    race_state["meta"]["packet_type"] = packet_type
    race_state["meta"]["updated_at"] = datetime.utcnow().isoformat() + "Z"

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

def process_packet(packet):
    global player_index

    header = getattr(packet, "header", None)
    if header:
        player_index = getattr(header, "playerCarIndex", player_index)

    packet_type = packet.__class__.__name__
    set_meta(packet_type)

    if packet_type == "PacketSessionData_V1":
        race_state["session"].update({
            "track_name": TRACKS.get(packet.trackId, f"Track {packet.trackId}"),
            "weather_label": WEATHER.get(packet.weather, f"Weather {packet.weather}"),
            "total_laps": int(packet.totalLaps),
            "session_time_left_s": int(packet.sessionTimeLeft),
            "air_temp_c": int(packet.airTemperature),
            "track_temp_c": int(packet.trackTemperature),
            "safety_car_status": SAFETY_CAR.get(packet.safetyCarStatus, str(packet.safetyCarStatus)),
        })

    elif packet_type == "PacketParticipantsData_V1":
        for idx, p in enumerate(packet.participants):
            participants_snapshot[idx] = {
                "name": decode_name(p.name),
                "team_name": TEAMS.get(p.teamId, f"Team {p.teamId}"),
                "race_number": int(p.raceNumber),
            }

        participant = participants_snapshot.get(player_index, {})
        race_state["driver"].update({
            "name": participant.get("name", "-"),
            "team_name": participant.get("team_name", "-"),
            "race_number": participant.get("race_number", 0),
        })
        rebuild_live_grid()

    elif packet_type == "PacketLapData_V1":
        for idx, lap in enumerate(packet.lapData):
            sector1 = round(float(getattr(lap, "sector1Time", 0.0) or 0.0), 3)
            sector2 = round(float(getattr(lap, "sector2Time", 0.0) or 0.0), 3)
            current_lap = round(float(getattr(lap, "currentLapTime", 0.0) or 0.0), 3)
            last_lap = round(float(getattr(lap, "lastLapTime", 0.0) or 0.0), 3)

            sector3 = 0.0
            if last_lap > 0 and sector1 > 0 and sector2 > 0:
                sector3 = round(max(last_lap - sector1 - sector2, 0.0), 3)

            lap_snapshot[idx] = {
                "position": int(lap.carPosition),
                "current_lap": int(lap.currentLapNum),
                "sector": SECTORS.get(lap.sector, str(lap.sector)),
                "pit_status": PIT_STATUS.get(lap.pitStatus, str(lap.pitStatus)),
                "driver_status": DRIVER_STATUS.get(lap.driverStatus, str(lap.driverStatus)),
                "result_status": RESULT_STATUS.get(lap.resultStatus, str(lap.resultStatus)),
                "lap_distance": float(getattr(lap, "lapDistance", 0.0) or 0.0),
                "total_distance": float(getattr(lap, "totalDistance", 0.0) or 0.0),
                "current_lap_time": current_lap,
                "last_lap_time": last_lap,
                "best_lap_time": round(float(getattr(lap, "bestLapTime", 0.0) or 0.0), 3),
                "sector1_time": sector1,
                "sector2_time": sector2,
                "sector3_time": sector3,
                "penalties_s": int(getattr(lap, "penalties", 0) or 0),
                "num_pit_stops": int(getattr(lap, "numPitStops", 0) or 0),
            }

        lap = lap_snapshot.get(player_index, {})
        race_state["driver"].update({
            "position": lap.get("position", 0),
            "sector": lap.get("sector", "-"),
            "pit_status": lap.get("pit_status", "-"),
            "driver_status": lap.get("driver_status", "-"),
            "result_status": lap.get("result_status", "-"),
        })
        race_state["session"]["current_lap"] = lap.get("current_lap", 0)
        race_state["lap"].update({
            "last_lap_s": lap.get("last_lap_time", 0),
            "best_lap_s": lap.get("best_lap_time", 0),
            "current_lap_s": lap.get("current_lap_time", 0),
            "penalties_s": lap.get("penalties_s", 0),
        })
        rebuild_live_grid()

    elif packet_type == "PacketCarTelemetryData_V1":
        for idx, tel in enumerate(packet.carTelemetryData):
            telemetry_snapshot[idx] = {
                "speed_kph": int(tel.speed),
                "gear": normalize_gear(int(tel.gear)),
                "rpm": int(tel.engineRPM),
                "throttle_pct": round(float(tel.throttle) * 100, 1),
                "brake_pct": round(float(tel.brake) * 100, 1),
                "steering": round(float(tel.steer), 3),
                "drs_on": bool(tel.drs),
                "rev_lights_pct": int(tel.revLightsPercent),
                "engine_temp_c": int(tel.engineTemperature),
                "brake_temps_c": [int(x) for x in tel.brakesTemperature],
                "surface_temp_c": [int(x) for x in tel.tyresSurfaceTemperature],
                "inner_temp_c": [int(x) for x in tel.tyresInnerTemperature],
                "pressure_psi": [round(float(x), 1) for x in tel.tyresPressure],
            }

        tel = telemetry_snapshot.get(player_index, {})
        race_state["car"].update({
            "speed_kph": tel.get("speed_kph", 0),
            "gear": tel.get("gear", "N"),
            "rpm": tel.get("rpm", 0),
            "throttle_pct": tel.get("throttle_pct", 0),
            "brake_pct": tel.get("brake_pct", 0),
            "steering": tel.get("steering", 0),
            "drs_on": tel.get("drs_on", False),
            "rev_lights_pct": tel.get("rev_lights_pct", 0),
            "engine_temp_c": tel.get("engine_temp_c", 0),
            "brake_temps_c": tel.get("brake_temps_c", [0, 0, 0, 0]),
        })
        race_state["tyres"].update({
            "surface_temp_c": tel.get("surface_temp_c", [0, 0, 0, 0]),
            "inner_temp_c": tel.get("inner_temp_c", [0, 0, 0, 0]),
            "pressure_psi": tel.get("pressure_psi", [0, 0, 0, 0]),
        })
        rebuild_live_grid()

    elif packet_type == "PacketCarStatusData_V1":
        for idx, st in enumerate(packet.carStatusData):
            tyres_wear = [int(x) for x in st.tyresWear]
            status_snapshot[idx] = {
                "actual_compound": ACTUAL_TYRE_COMPOUND.get(st.actualTyreCompound, str(st.actualTyreCompound)),
                "visual_compound": VISUAL_TYRE_COMPOUND.get(st.tyreVisualCompound, str(st.tyreVisualCompound)),
                "fuel_in_tank_kg": round(float(st.fuelInTank), 2),
                "fuel_capacity_kg": round(float(st.fuelCapacity), 2),
                "fuel_remaining_laps": round(float(st.fuelRemainingLaps), 2),
                "ers_store_j": round(float(st.ersStoreEnergy), 2),
                "ers_store_pct": ers_percent(st.ersStoreEnergy),
                "ers_deployed_this_lap_j": round(float(st.ersDeployedThisLap), 2),
                "ers_mode": ERS_MODE.get(st.ersDeployMode, str(st.ersDeployMode)),
                "drs_allowed": bool(st.drsAllowed),
                "tyres_wear": tyres_wear,
                "tyres_damage": [int(x) for x in st.tyresDamage],
                "tyre_wear_avg": round(sum(tyres_wear) / 4, 1),
                "front_left_wing_pct": int(st.frontLeftWingDamage),
                "front_right_wing_pct": int(st.frontRightWingDamage),
                "rear_wing_pct": int(st.rearWingDamage),
                "engine_pct": int(st.engineDamage),
                "gearbox_pct": int(st.gearBoxDamage),
                "fia_flag": FIA_FLAGS.get(st.vehicleFiaFlags, str(st.vehicleFiaFlags)),
            }

        st = status_snapshot.get(player_index, {})
        race_state["car"]["drs_allowed"] = st.get("drs_allowed", False)
        race_state["tyres"].update({
            "actual_compound": st.get("actual_compound", "-"),
            "visual_compound": st.get("visual_compound", "-"),
            "wear_pct": st.get("tyres_wear", [0, 0, 0, 0]),
            "damage_pct": st.get("tyres_damage", [0, 0, 0, 0]),
        })
        race_state["energy"].update({
            "fuel_in_tank_kg": st.get("fuel_in_tank_kg", 0),
            "fuel_capacity_kg": st.get("fuel_capacity_kg", 0),
            "fuel_remaining_laps": st.get("fuel_remaining_laps", 0),
            "ers_store_j": st.get("ers_store_j", 0),
            "ers_deployed_this_lap_j": st.get("ers_deployed_this_lap_j", 0),
            "ers_mode": st.get("ers_mode", "-"),
        })
        race_state["damage"].update({
            "front_left_wing_pct": st.get("front_left_wing_pct", 0),
            "front_right_wing_pct": st.get("front_right_wing_pct", 0),
            "rear_wing_pct": st.get("rear_wing_pct", 0),
            "engine_pct": st.get("engine_pct", 0),
            "gearbox_pct": st.get("gearbox_pct", 0),
            "fia_flag": st.get("fia_flag", "-"),
        })
        rebuild_live_grid()

    elif packet_type == "PacketEventData_V1":
        code = bytes(packet.eventStringCode).decode("utf-8", errors="ignore")
        append_event(EVENT_CODES.get(code, code))
        update_race_control()

def telemetry_loop(host="0.0.0.0", port=20777):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((host, port))

    while True:
        udp_packet = udp_socket.recv(2048)
        try:
            packet = unpack_udp_packet(udp_packet)
            process_packet(packet)
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
