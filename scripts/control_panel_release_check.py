import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
REPORTS_DIR = ROOT / "reports"
DEFAULT_REPORT = REPORTS_DIR / "control_panel_release_report.md"

COMMANDS: List[Tuple[str, List[str]]] = [
    ("compile_backend", ["python", "-m", "compileall", "examples/backend/cua_backend.py"]),
    ("functional_tests", ["pytest", "tests/test_functional_agent_stack.py"]),
]

PREVIEW_FIXTURES = {
    "instances": [
        {
            "id": "vm-01",
            "name": "Workspace",
            "status": "idle",
            "resource": {"cpu": 7, "memoryMb": 512},
            "snapshotUrl": None,
        },
        {
            "id": "vm-02",
            "name": "Browser sand-box",
            "status": "launching",
            "resource": {"cpu": 21, "memoryMb": 1024},
            "snapshotUrl": "https://placehold.co/240x140/0f172a/67e8f9?text=VM+02",
        },
    ]
}


def run_command(label: str, cmd: List[str]) -> Dict[str, object]:
    """Run a command and capture stdout/stderr plus a success flag."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "label": label,
        "cmd": cmd,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "success": proc.returncode == 0,
        "returncode": proc.returncode,
    }


def package_artifact(artifact_name: str = "control-panel-snapshot.zip") -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target = DIST_DIR / artifact_name
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in [
            Path("examples/ui/vm-control-panel/ControlPanel.tsx"),
            Path("examples/ui/vm-control-panel/ControlPanelApp.tsx"),
            Path("examples/ui/vm-control-panel/control-panel.css"),
            Path("examples/ui/vm-control-panel/electron/main.ts"),
            Path("examples/ui/vm-control-panel/electron/preload.ts"),
            Path("examples/backend/cua_backend.py"),
            Path("examples/backend/README.md"),
        ]:
            zf.write(ROOT / rel, arcname=rel.as_posix())
    return target


def simulate_preview() -> Dict[str, object]:
    """Simulate panel toggles, theme cycling, and action feedback without a browser."""
    log: List[str] = []
    collapsed = False
    themes = ["dark", "carbon", "plasma"]
    theme_index = 0
    instances = PREVIEW_FIXTURES["instances"].copy()

    def snapshot_counts(state: List[Dict[str, object]]):
        counts = {"running": 0, "idle": 0, "error": 0, "launching": 0}
        for vm in state:
            counts[vm.get("status", "idle")] += 1
        return counts

    log.append(f"Initial theme={themes[theme_index]}, collapsed={collapsed}")
    log.append(f"Initial VM counts={snapshot_counts(instances)}")

    # Toggle collapse/expand
    collapsed = not collapsed
    log.append(f"Panel toggled -> collapsed={collapsed}")
    collapsed = not collapsed
    log.append(f"Panel toggled -> collapsed={collapsed}")

    # Cycle themes
    for _ in range(4):
        theme_index = (theme_index + 1) % len(themes)
        log.append(f"Theme cycled -> {themes[theme_index]}")

    # Simulate actions
    actions_log: List[Dict[str, object]] = []
    for vm in instances:
        actions_log.append({"vm": vm["id"], "action": "launch", "result": "queued"})
        actions_log.append({"vm": vm["id"], "action": "screenshot", "result": "success"})
        actions_log.append({"vm": vm["id"], "action": "send-command", "result": "error", "message": "stubbed"})

    mascot_state = "visible" if not collapsed else "hidden"

    return {
        "timeline": log,
        "actions": actions_log,
        "counts": snapshot_counts(instances),
        "mascot": mascot_state,
    }


def check_docs() -> Dict[str, bool]:
    docs = {
        "vm_control_panel": ROOT / "docs/content/docs/get-started/vm-control-panel.mdx",
        "backend_api": ROOT / "docs/content/docs/get-started/backend-api.mdx",
        "troubleshooting": ROOT / "docs/content/docs/get-started/troubleshooting.mdx",
    }
    return {name: path.exists() for name, path in docs.items()}


def build_report(results: Dict[str, object], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    lines = ["# Control panel release QA report", "", f"Generated: {timestamp}", ""]

    lines.append("## Commands")
    for item in results.get("commands", []):
        status = "✅" if item.get("success") else "❌"
        lines.append(f"- {status} `{ ' '.join(item.get('cmd', [])) }`")
        if item.get("stdout"):
            lines.append(f"  - stdout: {item['stdout']}")
        if item.get("stderr"):
            lines.append(f"  - stderr: {item['stderr']}")

    lines.append("\n## Artifact")
    artifact = results.get("artifact")
    lines.append(f"- Path: {artifact if artifact else 'not created'}")

    lines.append("\n## Preview simulation")
    preview = results.get("preview", {})
    if preview:
        lines.append(f"- Mascot: {preview.get('mascot')}")
        lines.append(f"- VM counts: {preview.get('counts')}")
        lines.append("- Timeline:")
        for entry in preview.get("timeline", []):
            lines.append(f"  - {entry}")
        lines.append("- Actions:")
        for action in preview.get("actions", []):
            lines.append(f"  - {action}")

    lines.append("\n## Documentation")
    for name, ok in results.get("docs", {}).items():
        lines.append(f"- {name}: {'present' if ok else 'missing'}")

    lines.append("\n## Final status")
    lines.append(f"- {results.get('final_status', 'unknown')}")

    report_path.write_text("\n".join(lines) + "\n")


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Release QA for the control panel")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Where to write the QA report")
    parser.add_argument(
        "--skip-tests", action="store_true", help="Skip test commands (not recommended for release)"
    )
    parser.add_argument("--package", action="store_true", help="Package the panel into dist/ for download checks")
    args = parser.parse_args(argv)

    results: Dict[str, object] = {}

    commands_results = []
    if not args.skip_tests:
        for label, cmd in COMMANDS:
            commands_results.append(run_command(label, cmd))
    results["commands"] = commands_results

    preview = simulate_preview()
    results["preview"] = preview

    artifact_path: Path | None = None
    if args.package:
        artifact_path = package_artifact()
    results["artifact"] = str(artifact_path) if artifact_path else None

    doc_state = check_docs()
    results["docs"] = doc_state

    ready = all(item.get("success", False) for item in commands_results) and all(doc_state.values())
    final_status = "Ready for Use" if ready else "Needs investigation"
    results["final_status"] = final_status

    build_report(results, args.report)

    print(json.dumps(results, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
