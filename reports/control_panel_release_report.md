# Control panel release QA report

Generated: 2025-11-22T00:55:25.002236+00:00

## Commands
- ✅ `python -m compileall examples/backend/cua_backend.py`
- ✅ `pytest tests/test_functional_agent_stack.py`
  - stdout: ===================================================== test session starts ======================================================
platform linux -- Python 3.12.12, pytest-8.4.2, pluggy-1.6.0
rootdir: /workspace/cua/tests
configfile: pytest.ini
plugins: asyncio-1.3.0, anyio-4.11.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 1 item

tests/test_functional_agent_stack.py .                                                                                   [100%]

====================================================== 1 passed in 10.98s ======================================================

## Artifact
- Path: /workspace/cua/dist/control-panel-snapshot.zip

## Preview simulation
- Mascot: visible
- VM counts: {'running': 0, 'idle': 1, 'error': 0, 'launching': 1}
- Timeline:
  - Initial theme=dark, collapsed=False
  - Initial VM counts={'running': 0, 'idle': 1, 'error': 0, 'launching': 1}
  - Panel toggled -> collapsed=True
  - Panel toggled -> collapsed=False
  - Theme cycled -> carbon
  - Theme cycled -> plasma
  - Theme cycled -> dark
  - Theme cycled -> carbon
- Actions:
  - {'vm': 'vm-01', 'action': 'launch', 'result': 'queued'}
  - {'vm': 'vm-01', 'action': 'screenshot', 'result': 'success'}
  - {'vm': 'vm-01', 'action': 'send-command', 'result': 'error', 'message': 'stubbed'}
  - {'vm': 'vm-02', 'action': 'launch', 'result': 'queued'}
  - {'vm': 'vm-02', 'action': 'screenshot', 'result': 'success'}
  - {'vm': 'vm-02', 'action': 'send-command', 'result': 'error', 'message': 'stubbed'}

## Documentation
- vm_control_panel: present
- backend_api: present
- troubleshooting: present

## Final status
- Ready for Use
