import asyncio
import base64
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

# Ensure local packages are importable without installation
REPO_ROOT = Path(__file__).resolve().parent.parent
for package_dir in [
    REPO_ROOT / "libs/python/agent",
    REPO_ROOT / "libs/python/computer",
    REPO_ROOT / "libs/python/core",
]:
    sys.path.insert(0, str(package_dir))


# Stub liteLLM to avoid heavy dependency requirements during tests
def _install_litellm_stub() -> None:
    if "litellm" in sys.modules:
        return

    litellm_module = types.ModuleType("litellm")
    litellm_module.__path__ = []  # mark as package
    litellm_utils = types.ModuleType("litellm.utils")

    def _function_to_dict(func):
        return {
            "name": func.__name__,
            "description": func.__doc__ or "",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    litellm_utils.function_to_dict = _function_to_dict

    class Usage:
        def __init__(self, prompt_tokens=0, completion_tokens=0, total_tokens=0):
            self.prompt_tokens = prompt_tokens
            self.completion_tokens = completion_tokens
            self.total_tokens = total_tokens

    class _ResponseInputParam:  # pragma: no cover - stub
        pass

    class _ResponsesAPIResponse:  # pragma: no cover - stub
        pass

    class _ToolParam:  # pragma: no cover - stub
        pass

    litellm_responses = types.ModuleType("litellm.responses")
    litellm_responses_utils = types.ModuleType("litellm.responses.utils")
    litellm_responses_utils.Usage = Usage

    litellm_types = types.ModuleType("litellm.types")
    litellm_types.__path__ = []
    litellm_types_utils = types.ModuleType("litellm.types.utils")

    class _StreamingChunk:  # pragma: no cover - stub
        pass

    class _ModelResponse:  # pragma: no cover - stub
        pass

    litellm_types_utils.GenericStreamingChunk = _StreamingChunk
    litellm_types_utils.ModelResponse = _ModelResponse

    litellm_module.utils = litellm_utils
    litellm_module.custom_provider_map = []
    litellm_module.suppress_debug_info = False
    litellm_module.completion = lambda *args, **kwargs: None
    litellm_module.ResponseInputParam = _ResponseInputParam
    litellm_module.ResponsesAPIResponse = _ResponsesAPIResponse
    litellm_module.ToolParam = _ToolParam

    async def _acompletion(*args, **kwargs):
        return None

    litellm_module.acompletion = _acompletion

    sys.modules["litellm"] = litellm_module
    sys.modules["litellm.utils"] = litellm_utils
    sys.modules["litellm.types"] = litellm_types
    sys.modules["litellm.types.utils"] = litellm_types_utils
    sys.modules["litellm.responses"] = litellm_responses
    sys.modules["litellm.responses.utils"] = litellm_responses_utils

    litellm_llms = types.ModuleType("litellm.llms")
    litellm_llms.__path__ = []
    litellm_custom_llm = types.ModuleType("litellm.llms.custom_llm")

    class CustomLLM:  # pragma: no cover - stub for adapter import
        pass

    litellm_custom_llm.CustomLLM = CustomLLM

    sys.modules["litellm.llms"] = litellm_llms
    sys.modules["litellm.llms.custom_llm"] = litellm_custom_llm


_install_litellm_stub()

# Prevent importing heavy default loops; tests register their own agent loop
sys.modules.setdefault("agent.loops", types.ModuleType("agent.loops"))

from agent import ComputerAgent  # type: ignore  # noqa: E402
from agent.decorators import _agent_configs, register_agent  # type: ignore  # noqa: E402
from computer.providers.base import BaseVMProvider, VMProviderType  # type: ignore  # noqa: E402
from agent.computers import make_computer_handler  # type: ignore  # noqa: E402


class FakeVMProvider(BaseVMProvider):
    """In-memory VM provider that tracks lifecycle events for validation."""

    def __init__(self) -> None:
        self.vms: dict[str, dict[str, Any]] = {}
        self.actions: list[str] = []

    @property
    def provider_type(self) -> VMProviderType:  # pragma: no cover - trivial
        return VMProviderType.LUMIER

    async def get_vm(self, name: str, storage: str | None = None) -> dict[str, Any]:
        return self.vms.get(name, {"name": name, "status": "missing", "storage": storage})

    async def list_vms(self):
        return {"vms": list(self.vms.values())}

    async def run_vm(self, image: str, name: str, run_opts: dict[str, Any], storage: str | None = None):
        self.actions.append(f"run:{name}")
        vm = {"name": name, "image": image, "status": "running", "opts": run_opts, "storage": storage}
        self.vms[name] = vm
        return vm

    async def stop_vm(self, name: str, storage: str | None = None):
        self.actions.append(f"stop:{name}")
        if name in self.vms:
            self.vms[name]["status"] = "stopped"
        return self.vms.get(name, {"name": name, "status": "stopped"})

    async def restart_vm(self, name: str, storage: str | None = None):
        self.actions.append(f"restart:{name}")
        if name in self.vms:
            self.vms[name]["status"] = "running"
        return self.vms.get(name, {"name": name, "status": "running"})

    async def update_vm(self, name: str, update_opts: dict[str, Any], storage: str | None = None):
        self.actions.append(f"update:{name}")
        if name in self.vms:
            self.vms[name].update(update_opts)
        return self.vms.get(name, {"name": name, **update_opts})

    async def get_ip(self, name: str, storage: str | None = None, retry_delay: int = 2):
        self.actions.append(f"ip:{name}")
        return "127.0.0.1"

    async def __aenter__(self):  # pragma: no cover - trivial
        return self

    async def __aexit__(self, *exc):  # pragma: no cover - trivial
        return False


@dataclass
class AgentTelemetry:
    actions: list[str]
    screenshots: list[str]


@pytest.fixture()
def registered_dummy_agent():
    @register_agent(models="dummy-functional")
    class DummyFunctionalAgent:
        def __init__(self):
            self.step = 0

        def get_capabilities(self):
            return ["step", "click"]

        async def predict_click(self, *_, **__):  # pragma: no cover - not exercised
            return 0, 0

        async def predict_step(self, **_kwargs):
            self.step += 1
            if self.step == 1:
                return {
                    "output": [
                        {"type": "computer_call", "call_id": "click-1", "action": {"type": "click", "x": 10, "y": 15}}
                    ]
                }
            if self.step == 2:
                return {
                    "output": [
                        {"type": "computer_call", "call_id": "type-1", "action": {"type": "type", "text": "hello"}}
                    ]
                }
            return {"output": [{"role": "assistant", "content": [{"text": "done"}]}]}

    yield DummyFunctionalAgent
    _agent_configs[:] = [cfg for cfg in _agent_configs if cfg.agent_class is not DummyFunctionalAgent]


@pytest.mark.asyncio
async def test_vm_provider_and_agent_workflow(registered_dummy_agent):
    provider = FakeVMProvider()

    vm = await provider.run_vm("trycua/cua-ubuntu", "vm-demo", {"memory": "2GB", "cpu": "2"})
    assert vm["status"] == "running"

    restart_status = await provider.restart_vm("vm-demo")
    assert restart_status["status"] == "running"

    ip_addr = await provider.get_ip("vm-demo")
    assert ip_addr == "127.0.0.1"

    listed = await provider.list_vms()
    assert listed["vms"], "VM listing should return at least the running VM"

    stopped = await provider.stop_vm("vm-demo")
    assert stopped["status"] == "stopped"
    assert provider.actions == ["run:vm-demo", "restart:vm-demo", "ip:vm-demo", "stop:vm-demo"]

    telemetry = AgentTelemetry(actions=[], screenshots=[])

    SAMPLE_PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAuMBg9R3KuoAAAAASUVORK5CYII="
    )

    async def record_screenshot():
        telemetry.screenshots.append(base64.b64encode(SAMPLE_PNG).decode("utf-8"))
        return SAMPLE_PNG

    async def record_click(x: int, y: int, button: str = "left"):
        telemetry.actions.append(f"click:{x},{y},{button}")

    async def record_type(text: str):
        telemetry.actions.append(f"type:{text}")

    computer_dict = {"screenshot": record_screenshot, "click": record_click, "type": record_type}
    computer_handler = await make_computer_handler(computer_dict)

    agent = ComputerAgent(
        model="dummy-functional",
        tools=[computer_dict],
        screenshot_delay=0,
        telemetry_enabled=False,
    )
    agent.computer_handler = computer_handler

    results = []
    async for chunk in agent.run([{"role": "user", "content": "start"}]):
        results.append(chunk)

    assert any(
        item.get("type") == "computer_call_output"
        for chunk in results
        for item in chunk.get("output", [])
    )
    assert any(
        item.get("role") == "assistant" and item.get("content", [{}])[0].get("text") == "done"
        for chunk in results
        for item in chunk.get("output", [])
    )

    assert telemetry.actions == ["click:10,15,left", "type:hello"]
    assert len(telemetry.screenshots) >= 2
