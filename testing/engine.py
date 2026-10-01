import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

# --- CORE CONFIG STATE ---
config = {
    "current_number": {"value": 0, "on_view": True, "text": "CURRENT NUMBER"},
    "is_running": {"value": False, "on_view": True, "text": "IS RUNNING"},
    "sleeper": {"value": 1 / 60, "on_view": False, "text": None},
    "nuke": {"value": False, "on_view": True, "text": "NUKE"},
}

connected_clients = set()


def get_full_state():
    """Dynamically gathers all entries where on_view is True without hardcoding keys."""
    return {
        k: v
        for k, v in config.items()
        if isinstance(v, dict) and v.get("on_view") is True
    }


async def broadcast_state():
    """Broadcasts dynamic state to all connected browser tabs."""
    state = get_full_state()
    for client in list(connected_clients):
        try:
            await client.send_json(state)
        except Exception:
            pass


# --- THE GENERATOR ENGINE ---
async def num_gen_inf():
    """Runs continuously, ticking at the configured sleeper rate."""
    while True:
        if config["is_running"]["value"] and connected_clients:
            config["current_number"]["value"] += 1
            for client in list(connected_clients):
                try:
                    await client.send_json(
                        {"current_number": config["current_number"]}
                    )
                except Exception:
                    pass
        await asyncio.sleep(config["sleeper"]["value"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(num_gen_inf())
    yield


app = FastAPI(lifespan=lifespan)


# --- ROUTES ---
@app.get("/")
async def serve_view():
    with open("view.html", "r") as f:
        return HTMLResponse(f.read())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)

    # Broadcast initial dynamic state on connection
    await websocket.send_json(get_full_state())

    try:
        while True:
            command = await websocket.receive_text()

            if command in ("is_running", "TOGGLE"):
                config["is_running"]["value"] = not config["is_running"]["value"]
                await broadcast_state()

            elif command in ("nuke", "NUKE"):
                config["current_number"]["value"] = 0
                config["is_running"]["value"] = False
                await broadcast_state()

    except WebSocketDisconnect:
        connected_clients.remove(websocket)