import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .state import race_state
from .telemetry import start_telemetry_thread


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_telemetry_thread()
    yield


app = FastAPI(lifespan=lifespan)

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
async def home():
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard")
async def dashboard_page():
    return FileResponse(frontend_dir / "dashboard.html")


@app.get("/grid")
async def grid_page():
    return FileResponse(frontend_dir / "grid.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_text(json.dumps(race_state))
        await asyncio.sleep(0.2)

@app.get("/engineering-grid")
async def engineering_grid_page():
    return FileResponse(frontend_dir / "engineering-grid.html")
