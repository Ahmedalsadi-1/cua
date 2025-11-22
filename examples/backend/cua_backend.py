"""
Minimal FastAPI backend that exposes VM + computer endpoints for the Cua control panel.

Features
- Token-based auth with `Authorization: Bearer <token>`
- REST endpoints for start/stop/screenshot/command and log retrieval
- WebSocket channel for live status/log streaming to the UI
- Thin integration hooks to Cua Computer + Agent SDK plus a Lumier/Lume provider facade

Usage
    export CUA_CONTROL_TOKEN=devtoken
    uvicorn examples.backend.cua_backend:app --reload --port 8001
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from agent import ComputerAgent
from computer import Computer

security = HTTPBearer(auto_error=False)

app = FastAPI(title="Cua VM Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class VmSpec(BaseModel):
    id: str
    name: str
    os_type: str = Field(default="linux", description="linux | macos | windows")
    provider: str = Field(default="lumier", description="lumier | lume | docker")
    display: str = Field(default="1280x720")
    model: str = Field(default="anthropic/claude-3-5-sonnet-20241022")
    memory: str = Field(default="8GB")
    cpu: str = Field(default="4")


class CommandRequest(BaseModel):
    command: str = Field(..., description="e.g. click 200 300 or type 'hello'")


class VmSnapshot(BaseModel):
    vm_id: str
    url: Optional[str]
    captured_at: Optional[datetime]


class VmLogLine(BaseModel):
    vm_id: str
    ts: datetime
    level: str
    message: str


class VmState(BaseModel):
    spec: VmSpec
    status: str = "idle"
    busy: bool = False
    last_snapshot: Optional[VmSnapshot] = None
    logs: List[VmLogLine] = Field(default_factory=list)
    last_result: Optional[str] = None


class VmRegistry:
    def __init__(self) -> None:
        self._items: Dict[str, VmState] = {}
        self._listeners: List[WebSocket] = []

    def upsert(self, spec: VmSpec) -> VmState:
        state = self._items.get(spec.id) or VmState(spec=spec)
        self._items[spec.id] = state
        return state

    def get(self, vm_id: str) -> VmState:
        if vm_id not in self._items:
            raise KeyError(vm_id)
        return self._items[vm_id]

    def list(self) -> List[VmState]:
        return list(self._items.values())

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        living: List[WebSocket] = []
        for ws in self._listeners:
            try:
                await ws.send_json(payload)
                living.append(ws)
            except WebSocketDisconnect:
                continue
        self._listeners = living

    async def attach(self, ws: WebSocket) -> None:
        await ws.accept()
        self._listeners.append(ws)
        await ws.send_json({"vms": [state.model_dump() for state in self.list()]})


registry = VmRegistry()


async def require_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    token = os.environ.get("CUA_CONTROL_TOKEN")
    if not token:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server missing CUA_CONTROL_TOKEN")
    if credentials is None or credentials.scheme.lower() != "bearer" or credentials.credentials != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return token


async def _log(vm_id: str, level: str, message: str) -> None:
    state = registry._items.get(vm_id)
    if not state:
        return
    line = VmLogLine(vm_id=vm_id, ts=datetime.utcnow(), level=level, message=message)
    state.logs.append(line)
    await registry.broadcast({"type": "log", **line.model_dump()})


async def _ensure_computer(state: VmState) -> Computer:
    computer = Computer(
        display=state.spec.display,
        memory=state.spec.memory,
        cpu=state.spec.cpu,
        os_type=state.spec.os_type,  # type: ignore[arg-type]
        provider_type=state.spec.provider,
        telemetry_enabled=True,
        api_key=os.environ.get("CUA_API_KEY"),
    )
    await _log(state.spec.id, "info", f"Provisioning VM via {state.spec.provider}")
    await computer.run()
    return computer


async def _ensure_agent(computer: Computer, spec: VmSpec) -> ComputerAgent:
    agent = ComputerAgent(model=spec.model, tools=[computer], only_n_most_recent_images=3)
    await _log(spec.id, "info", f"Agent {spec.model} ready")
    return agent


@app.post("/api/v1/vms", dependencies=[Depends(require_token)])
async def start_vm(spec: VmSpec) -> Dict[str, Any]:
    state = registry.upsert(spec)
    if state.busy:
        raise HTTPException(status_code=409, detail="VM already busy")
    state.busy, state.status = True, "launching"
    await _log(spec.id, "info", "Starting VM")

    async def _launch() -> None:
        try:
            computer = await _ensure_computer(state)
            agent = await _ensure_agent(computer, spec)
            state.status = "running"
            await _log(spec.id, "info", "VM running and agent attached")
            # warm-up action
            async for chunk in agent.run([{"role": "user", "content": "Take a screenshot and describe the desktop"}]):
                state.last_result = str(chunk)
                await registry.broadcast({"type": "agent", "vm_id": spec.id, "chunk": chunk})
            await computer.disconnect()
        except Exception as exc:  # noqa: BLE001
            state.status = "error"
            await _log(spec.id, "error", f"Launch failed: {exc}")
        finally:
            state.busy = False
            await registry.broadcast({"type": "state", "vm_id": spec.id, "status": state.status})

    asyncio.create_task(_launch())
    return {"status": "starting", "vm": state.model_dump()}


@app.post("/api/v1/vms/{vm_id}/stop", dependencies=[Depends(require_token)])
async def stop_vm(vm_id: str) -> Dict[str, Any]:
    try:
        state = registry.get(vm_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="VM not found")
    state.status = "idle"
    await _log(vm_id, "info", "Stop requested")
    await registry.broadcast({"type": "state", "vm_id": vm_id, "status": "idle"})
    return {"status": "stopped"}


@app.post("/api/v1/vms/{vm_id}/snapshot", dependencies=[Depends(require_token)])
async def snapshot_vm(vm_id: str) -> Dict[str, Any]:
    try:
        state = registry.get(vm_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="VM not found")
    state.busy = True

    async def _capture() -> None:
        try:
            computer = await _ensure_computer(state)
            png_bytes = await computer.screenshot()
            url = f"data:image/png;base64,{png_bytes}" if isinstance(png_bytes, str) else None
            state.last_snapshot = VmSnapshot(vm_id=vm_id, url=url, captured_at=datetime.utcnow())
            await _log(vm_id, "info", "Snapshot captured")
            await registry.broadcast({"type": "snapshot", "vm_id": vm_id, "url": url})
        except Exception as exc:  # noqa: BLE001
            await _log(vm_id, "error", f"Snapshot failed: {exc}")
        finally:
            state.busy = False

    asyncio.create_task(_capture())
    return {"status": "capturing"}


@app.post("/api/v1/vms/{vm_id}/command", dependencies=[Depends(require_token)])
async def send_command(vm_id: str, payload: CommandRequest) -> Dict[str, Any]:
    try:
        state = registry.get(vm_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="VM not found")

    async def _execute() -> None:
        try:
            computer = await _ensure_computer(state)
            agent = await _ensure_agent(computer, state.spec)
            async for chunk in agent.run([{"role": "user", "content": payload.command}]):
                state.last_result = str(chunk)
                await registry.broadcast({"type": "agent", "vm_id": vm_id, "chunk": chunk})
            await computer.disconnect()
        except Exception as exc:  # noqa: BLE001
            await _log(vm_id, "error", f"Command failed: {exc}")

    asyncio.create_task(_execute())
    await _log(vm_id, "info", f"Command queued: {payload.command}")
    return {"status": "queued"}


@app.get("/api/v1/vms", dependencies=[Depends(require_token)])
async def list_vms() -> Dict[str, Any]:
    return {"items": [state.model_dump() for state in registry.list()]}


@app.get("/api/v1/vms/{vm_id}/logs", dependencies=[Depends(require_token)])
async def vm_logs(vm_id: str) -> Dict[str, Any]:
    try:
        state = registry.get(vm_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="VM not found")
    return {"logs": [log.model_dump() for log in state.logs]}


@app.websocket("/ws/telemetry")
async def telemetry_socket(ws: WebSocket) -> None:
    await registry.attach(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        return
