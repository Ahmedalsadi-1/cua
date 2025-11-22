# Cua backend demo

Sample FastAPI service that powers the VM control panel with token-protected endpoints for launching/stopping VMs, capturing
snapshots, executing commands through `ComputerAgent`, and streaming telemetry over WebSocket. Start it with:

```bash
pip install "fastapi[all]" pydantic
export CUA_CONTROL_TOKEN=devtoken
export CUA_API_KEY=$YOUR_PROVIDER_KEY
uvicorn examples.backend.cua_backend:app --port 8001 --reload
```
