# Testing F1 Telemetry App

## Overview
The F1 telemetry system receives UDP packets from F1 games (2019, 2020, 2021) on port 20777, processes them via a FastAPI backend, and streams live data to HTML/JS frontends via WebSocket.

## Starting the Server
```bash
cd f1_telemetry
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
- HTTP server on port 8000
- UDP listener on port 20777 (started automatically in a background thread)
- Ensure both ports are free before starting: `fuser -k 20777/udp; fuser -k 8000/tcp`

## Frontend Pages
- Dashboard: `http://localhost:8000/dashboard`
- Live Grid: `http://localhost:8000/grid`
- Engineering Grid: `http://localhost:8000/engineering-grid`

## Sending Test Packets (No Real Game Needed)
Since real F1 games may not be available, build valid UDP packets using the libraries' own ctypes structures. This ensures correct struct sizes and field layouts.

**Important**: Do NOT construct raw binary packets manually — the struct sizes must match exactly or the library parser will silently fail. Always use the library's ctypes classes:

```python
from f1_2020_telemetry.packets import PacketParticipantsData_V1, PacketSessionData_V1, PacketLapData_V1
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Build a session packet
sess = PacketSessionData_V1()
sess.header.packetFormat = 2020
sess.header.packetId = 1  # Session
sess.trackId = 0  # Melbourne
sess.weather = 0  # Clear
sess.totalLaps = 58
sock.sendto(bytes(sess), ("127.0.0.1", 20777))
```

### Library class names
- F1 2019: `from f1_2019_telemetry.packets import ...` — classes like `PacketSessionData_V1`
- F1 2020: `from f1_2020_telemetry.packets import ...` — classes like `PacketSessionData_V1`, header is `PacketHeader` (not `PacketHeader_V1`)
- F1 2021: `from telemetry_f1_2021.listener import PacketHeader, HEADER_FIELD_TO_PACKET_TYPE`

### Struct sizes (F1 2020)
- PacketHeader: 24 bytes
- PacketSessionData_V1: 251 bytes
- PacketParticipantsData_V1: 1213 bytes
- PacketLapData_V1: 1190 bytes

## Verifying Data via WebSocket
```python
import asyncio, websockets, json
async def check():
    async with websockets.connect('ws://localhost:8000/ws') as ws:
        data = json.loads(await ws.recv())
        grid = data.get('live_grid', [])
        print(f'Grid rows: {len(grid)}')
        for row in grid:
            print(f'P{row["position"]} {row["name"]} {row["team_name"]}')
asyncio.run(check())
```

## Known Quirks
- F1 2020 sends 22 participant slots but only 20 are real drivers. Empty slots have blank names and team_id=0 (Mercedes). The backend filters these out.
- Team ID mappings might not match between game versions (e.g., team_id=1 is Red Bull in 2019 but might map differently in the lookup table). Verify with real game data.
- The UDP socket binding can fail if a previous server instance is still running. Always kill existing processes first.
- WebSocket disconnects are logged as errors but are harmless (client closed connection).

## Testing Draggable Columns
- Column order is stored in `localStorage` under the key `eng_grid_col_order`
- To reset: click "Reset Columns" button or clear localStorage
- Drag-and-drop uses HTML5 DnD API — test by dragging column headers

## Devin Secrets Needed
No secrets required — the app runs entirely locally with no authentication.
