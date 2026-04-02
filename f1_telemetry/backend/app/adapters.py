"""
Adapter layer to normalize telemetry packets from F1 2019, 2020, and 2021
into a common format that process_packet() can consume uniformly.

Each game uses a different Python library with different field naming conventions:
  - F1 2019: camelCase (e.g. playerCarIndex, trackId)
  - F1 2020: camelCase (e.g. playerCarIndex, trackId)
  - F1 2021: m_snake_case (e.g. m_player_car_index, m_track_id)

The adapter auto-detects the game version from the UDP header's packetFormat
field and routes to the appropriate library's parser.
"""

import ctypes
import struct

from f1_2019_telemetry.packets import unpack_udp_packet as unpack_2019
from f1_2020_telemetry.packets import unpack_udp_packet as unpack_2020
from telemetry_f1_2021.listener import (
    HEADER_FIELD_TO_PACKET_TYPE as PACKET_TYPES_2021,
    PacketHeader as Header2021,
)


# ---------------------------------------------------------------------------
# Canonical packet type names used by process_packet()
# ---------------------------------------------------------------------------
SESSION = "PacketSessionData"
PARTICIPANTS = "PacketParticipantsData"
LAP_DATA = "PacketLapData"
CAR_TELEMETRY = "PacketCarTelemetryData"
CAR_STATUS = "PacketCarStatusData"
EVENT = "PacketEventData"
CAR_DAMAGE = "PacketCarDamageData"  # F1 2021 only


def detect_game_version(raw: bytes) -> int:
    """Read packetFormat (first 2 bytes, uint16 LE) from raw UDP data."""
    if len(raw) < 2:
        raise ValueError("Packet too short")
    return struct.unpack_from("<H", raw, 0)[0]


def unpack_packet(raw: bytes):
    """Unpack a raw UDP packet using the appropriate library.

    Returns:
        (game_version, canonical_type, packet, player_index)
    """
    version = detect_game_version(raw)

    if version == 2019:
        packet = unpack_2019(raw)
        player_idx = packet.header.playerCarIndex
        canonical = _canonical_type_2019(packet)
        return version, canonical, packet, player_idx

    if version == 2020:
        packet = unpack_2020(raw)
        player_idx = packet.header.playerCarIndex
        canonical = _canonical_type_2020(packet)
        return version, canonical, packet, player_idx

    if version == 2021:
        header = Header2021.from_buffer_copy(raw)
        key = (header.m_packet_format, header.m_packet_version, header.m_packet_id)
        packet_cls = PACKET_TYPES_2021.get(key)
        if packet_cls is None:
            raise ValueError(f"Unknown F1 2021 packet key: {key}")
        packet = packet_cls.from_buffer_copy(raw)
        player_idx = header.m_player_car_index
        canonical = _canonical_type_2021(packet)
        return version, canonical, packet, player_idx

    raise ValueError(f"Unsupported packetFormat: {version}")


# ---------------------------------------------------------------------------
# Map library-specific class names to canonical names
# ---------------------------------------------------------------------------
_MAP_2019 = {
    "PacketSessionData_V1": SESSION,
    "PacketParticipantsData_V1": PARTICIPANTS,
    "PacketLapData_V1": LAP_DATA,
    "PacketCarTelemetryData_V1": CAR_TELEMETRY,
    "PacketCarStatusData_V1": CAR_STATUS,
    "PacketEventData_V1": EVENT,
}

_MAP_2020 = {
    "PacketSessionData_V1": SESSION,
    "PacketParticipantsData_V1": PARTICIPANTS,
    "PacketLapData_V1": LAP_DATA,
    "PacketCarTelemetryData_V1": CAR_TELEMETRY,
    "PacketCarStatusData_V1": CAR_STATUS,
    "PacketEventData_V1": EVENT,
}

_MAP_2021 = {
    "PacketSessionData": SESSION,
    "PacketParticipantsData": PARTICIPANTS,
    "PacketLapData": LAP_DATA,
    "PacketCarTelemetryData": CAR_TELEMETRY,
    "PacketCarStatusData": CAR_STATUS,
    "PacketEventData": EVENT,
    "PacketCarDamageData": CAR_DAMAGE,
}


def _canonical_type_2019(packet) -> str:
    return _MAP_2019.get(type(packet).__name__, type(packet).__name__)


def _canonical_type_2020(packet) -> str:
    return _MAP_2020.get(type(packet).__name__, type(packet).__name__)


def _canonical_type_2021(packet) -> str:
    return _MAP_2021.get(type(packet).__name__, type(packet).__name__)


# ---------------------------------------------------------------------------
# Normalizers — extract data from version-specific packets into plain dicts
# ---------------------------------------------------------------------------

def normalize_session(version: int, packet) -> dict:
    """Extract session info into a common dict."""
    if version in (2019, 2020):
        return {
            "track_id": int(packet.trackId),
            "weather": int(packet.weather),
            "total_laps": int(packet.totalLaps),
            "session_time_left": int(packet.sessionTimeLeft),
            "air_temperature": int(packet.airTemperature),
            "track_temperature": int(packet.trackTemperature),
            "safety_car_status": int(packet.safetyCarStatus),
        }
    # 2021
    return {
        "track_id": int(packet.m_track_id),
        "weather": int(packet.m_weather),
        "total_laps": int(packet.m_total_laps),
        "session_time_left": int(packet.m_session_time_left),
        "air_temperature": int(packet.m_air_temperature),
        "track_temperature": int(packet.m_track_temperature),
        "safety_car_status": int(packet.m_safety_car_status),
    }


def normalize_participants(version: int, packet) -> list:
    """Return list of dicts with name, team_id, race_number."""
    results = []
    if version in (2019, 2020):
        for p in packet.participants:
            results.append({
                "name": p.name,
                "team_id": int(p.teamId),
                "race_number": int(p.raceNumber),
            })
    else:  # 2021
        for p in packet.m_participants:
            results.append({
                "name": p.m_name,
                "team_id": int(p.m_team_id),
                "race_number": int(p.m_race_number),
            })
    return results


def normalize_lap_data(version: int, packet) -> list:
    """Return list of dicts with normalized lap info."""
    results = []
    if version == 2019:
        for lap in packet.lapData:
            results.append({
                "car_position": int(lap.carPosition),
                "current_lap_num": int(lap.currentLapNum),
                "sector": int(lap.sector),
                "pit_status": int(lap.pitStatus),
                "driver_status": int(lap.driverStatus),
                "result_status": int(lap.resultStatus),
                "lap_distance": float(getattr(lap, "lapDistance", 0.0) or 0.0),
                "total_distance": float(getattr(lap, "totalDistance", 0.0) or 0.0),
                "current_lap_time_s": float(getattr(lap, "currentLapTime", 0.0) or 0.0),
                "last_lap_time_s": float(getattr(lap, "lastLapTime", 0.0) or 0.0),
                "best_lap_time_s": float(getattr(lap, "bestLapTime", 0.0) or 0.0),
                "sector1_time_s": float(getattr(lap, "sector1Time", 0.0) or 0.0),
                "sector2_time_s": float(getattr(lap, "sector2Time", 0.0) or 0.0),
                "penalties": int(getattr(lap, "penalties", 0) or 0),
                "num_pit_stops": int(getattr(lap, "numPitStops", 0) or 0),
            })
    elif version == 2020:
        for lap in packet.lapData:
            s1_ms = int(getattr(lap, "sector1TimeInMS", 0) or 0)
            s2_ms = int(getattr(lap, "sector2TimeInMS", 0) or 0)
            results.append({
                "car_position": int(lap.carPosition),
                "current_lap_num": int(lap.currentLapNum),
                "sector": int(lap.sector),
                "pit_status": int(lap.pitStatus),
                "driver_status": int(lap.driverStatus),
                "result_status": int(lap.resultStatus),
                "lap_distance": float(getattr(lap, "lapDistance", 0.0) or 0.0),
                "total_distance": float(getattr(lap, "totalDistance", 0.0) or 0.0),
                "current_lap_time_s": float(getattr(lap, "currentLapTime", 0.0) or 0.0),
                "last_lap_time_s": float(getattr(lap, "lastLapTime", 0.0) or 0.0),
                "best_lap_time_s": float(getattr(lap, "bestLapTime", 0.0) or 0.0),
                "sector1_time_s": s1_ms / 1000.0,
                "sector2_time_s": s2_ms / 1000.0,
                "penalties": int(getattr(lap, "penalties", 0) or 0),
                "num_pit_stops": int(getattr(lap, "numPitStops", 0) or 0),
            })
    else:  # 2021
        for lap in packet.m_lap_data:
            s1_ms = int(getattr(lap, "m_sector1_time_in_ms", 0) or 0)
            s2_ms = int(getattr(lap, "m_sector2_time_in_ms", 0) or 0)
            last_ms = int(getattr(lap, "m_last_lap_time_in_ms", 0) or 0)
            current_ms = int(getattr(lap, "m_current_lap_time_in_ms", 0) or 0)
            results.append({
                "car_position": int(lap.m_car_position),
                "current_lap_num": int(lap.m_current_lap_num),
                "sector": int(lap.m_sector),
                "pit_status": int(lap.m_pit_status),
                "driver_status": int(lap.m_driver_status),
                "result_status": int(lap.m_result_status),
                "lap_distance": float(getattr(lap, "m_lap_distance", 0.0) or 0.0),
                "total_distance": float(getattr(lap, "m_total_distance", 0.0) or 0.0),
                "current_lap_time_s": current_ms / 1000.0,
                "last_lap_time_s": last_ms / 1000.0,
                "best_lap_time_s": 0.0,  # F1 2021 doesn't have bestLapTime in LapData
                "sector1_time_s": s1_ms / 1000.0,
                "sector2_time_s": s2_ms / 1000.0,
                "penalties": int(getattr(lap, "m_penalties", 0) or 0),
                "num_pit_stops": int(getattr(lap, "m_num_pit_stops", 0) or 0),
            })
    return results


def normalize_car_telemetry(version: int, packet) -> list:
    """Return list of dicts with normalized car telemetry."""
    results = []
    if version in (2019, 2020):
        for tel in packet.carTelemetryData:
            results.append({
                "speed": int(tel.speed),
                "throttle": float(tel.throttle),
                "steer": float(tel.steer),
                "brake": float(tel.brake),
                "gear": int(tel.gear),
                "engine_rpm": int(tel.engineRPM),
                "drs": bool(tel.drs),
                "rev_lights_percent": int(tel.revLightsPercent),
                "engine_temperature": int(tel.engineTemperature),
                "brakes_temperature": [int(x) for x in tel.brakesTemperature],
                "tyres_surface_temperature": [int(x) for x in tel.tyresSurfaceTemperature],
                "tyres_inner_temperature": [int(x) for x in tel.tyresInnerTemperature],
                "tyres_pressure": [round(float(x), 1) for x in tel.tyresPressure],
            })
    else:  # 2021
        for tel in packet.m_car_telemetry_data:
            results.append({
                "speed": int(tel.m_speed),
                "throttle": float(tel.m_throttle),
                "steer": float(tel.m_steer),
                "brake": float(tel.m_brake),
                "gear": int(tel.m_gear),
                "engine_rpm": int(tel.m_engine_rpm),
                "drs": bool(tel.m_drs),
                "rev_lights_percent": int(tel.m_rev_lights_percent),
                "engine_temperature": int(tel.m_engine_temperature),
                "brakes_temperature": [int(x) for x in tel.m_brakes_temperature],
                "tyres_surface_temperature": [int(x) for x in tel.m_tyres_surface_temperature],
                "tyres_inner_temperature": [int(x) for x in tel.m_tyres_inner_temperature],
                "tyres_pressure": [round(float(x), 1) for x in tel.m_tyres_pressure],
            })
    return results


def normalize_car_status(version: int, packet) -> list:
    """Return list of dicts with normalized car status.

    Note: In F1 2021, tyre wear/damage and wing damage have moved to
    PacketCarDamageData. Those fields will be filled with defaults here.
    """
    results = []
    if version == 2019:
        for st in packet.carStatusData:
            results.append({
                "actual_tyre_compound": int(st.actualTyreCompound),
                "visual_tyre_compound": int(st.tyreVisualCompound),
                "fuel_in_tank": float(st.fuelInTank),
                "fuel_capacity": float(st.fuelCapacity),
                "fuel_remaining_laps": float(st.fuelRemainingLaps),
                "ers_store_energy": float(st.ersStoreEnergy),
                "ers_deploy_mode": int(st.ersDeployMode),
                "ers_deployed_this_lap": float(st.ersDeployedThisLap),
                "drs_allowed": bool(st.drsAllowed),
                "vehicle_fia_flags": int(st.vehicleFiaFlags),
                # Damage fields (in CarStatus for 2019)
                "tyres_wear": [int(x) for x in st.tyresWear],
                "tyres_damage": [int(x) for x in st.tyresDamage],
                "front_left_wing_damage": int(st.frontLeftWingDamage),
                "front_right_wing_damage": int(st.frontRightWingDamage),
                "rear_wing_damage": int(st.rearWingDamage),
                "engine_damage": int(st.engineDamage),
                "gearbox_damage": int(st.gearBoxDamage),
            })
    elif version == 2020:
        for st in packet.carStatusData:
            results.append({
                "actual_tyre_compound": int(st.actualTyreCompound),
                "visual_tyre_compound": int(st.visualTyreCompound),
                "fuel_in_tank": float(st.fuelInTank),
                "fuel_capacity": float(st.fuelCapacity),
                "fuel_remaining_laps": float(st.fuelRemainingLaps),
                "ers_store_energy": float(st.ersStoreEnergy),
                "ers_deploy_mode": int(st.ersDeployMode),
                "ers_deployed_this_lap": float(st.ersDeployedThisLap),
                "drs_allowed": bool(st.drsAllowed),
                "vehicle_fia_flags": int(st.vehicleFiaFlags),
                # Damage fields (still in CarStatus for 2020)
                "tyres_wear": [int(x) for x in st.tyresWear],
                "tyres_damage": [int(x) for x in st.tyresDamage],
                "front_left_wing_damage": int(st.frontLeftWingDamage),
                "front_right_wing_damage": int(st.frontRightWingDamage),
                "rear_wing_damage": int(st.rearWingDamage),
                "engine_damage": int(st.engineDamage),
                "gearbox_damage": int(st.gearBoxDamage),
            })
    else:  # 2021
        for st in packet.m_car_status_data:
            results.append({
                "actual_tyre_compound": int(st.m_actual_tyre_compound),
                "visual_tyre_compound": int(st.m_visual_tyre_compound),
                "fuel_in_tank": float(st.m_fuel_in_tank),
                "fuel_capacity": float(st.m_fuel_capacity),
                "fuel_remaining_laps": float(st.m_fuel_remaining_laps),
                "ers_store_energy": float(st.m_ers_store_energy),
                "ers_deploy_mode": int(st.m_ers_deploy_mode),
                "ers_deployed_this_lap": float(st.m_ers_deployed_this_lap),
                "drs_allowed": bool(st.m_drs_allowed),
                "vehicle_fia_flags": int(st.m_vehicle_fia_flags),
                # Damage fields default — filled by CarDamageData handler
                "tyres_wear": [0, 0, 0, 0],
                "tyres_damage": [0, 0, 0, 0],
                "front_left_wing_damage": 0,
                "front_right_wing_damage": 0,
                "rear_wing_damage": 0,
                "engine_damage": 0,
                "gearbox_damage": 0,
            })
    return results


def normalize_car_damage(version: int, packet) -> list:
    """Normalize F1 2021 PacketCarDamageData into a list of dicts.

    Only called for F1 2021. Returns damage info per car.
    """
    results = []
    for dmg in packet.m_car_damage_data:
        results.append({
            "tyres_wear": [int(x) for x in dmg.m_tyres_wear],
            "tyres_damage": [int(x) for x in dmg.m_tyres_damage],
            "front_left_wing_damage": int(dmg.m_front_left_wing_damage),
            "front_right_wing_damage": int(dmg.m_front_right_wing_damage),
            "rear_wing_damage": int(dmg.m_rear_wing_damage),
            "engine_damage": int(dmg.m_engine_damage),
            "gearbox_damage": int(dmg.m_gear_box_damage),
        })
    return results


def normalize_event(version: int, packet) -> str:
    """Return the 4-character event code string."""
    if version in (2019, 2020):
        raw = packet.eventStringCode
        if isinstance(raw, (bytes, bytearray)):
            return raw.decode("utf-8", errors="ignore").rstrip("\x00")
        return bytes(raw).decode("utf-8", errors="ignore").rstrip("\x00")
    # 2021
    raw = packet.m_event_string_code
    if isinstance(raw, (bytes, bytearray)):
        return raw.decode("utf-8", errors="ignore").rstrip("\x00")
    return bytes(raw).decode("utf-8", errors="ignore").rstrip("\x00")
