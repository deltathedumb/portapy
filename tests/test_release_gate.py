from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.native_surface import public_exports
from tools.python_surface import PYTHON_MODULE_EXPORTS
from tools.release_gate import FULL_RUNTIME_FLAGS, main


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_artifacts(dist: Path, *, full_runtime: bool) -> None:
    expected_exports = list(public_exports(host_bridge=True, host_calls=True))
    for target, name in (("linux", "libportapy.so"), ("windows", "portapy.dll")):
        artifact = dist / name
        artifact.write_bytes((target.encode("ascii") + b"\0") * 1024 + b"x" * 4096)
        metadata: dict[str, object] = {
            "schema": 1,
            "target": target,
            "artifact": name,
            "size": artifact.stat().st_size,
            "sha256": _sha256(artifact),
            "source": (
                "src/portapy/native_full_reference_entry.py"
                if full_runtime
                else "src/portapy/native_api_host_calls.py"
            ),
            "source_sha256": "0" * 64,
            "public_exports": expected_exports,
            "python_module_exports": list(PYTHON_MODULE_EXPORTS),
            "python_module_entry": "portapy",
            "python_built_runtime": True,
            "host_bridge": True,
            "host_calls": True,
            "native_environment_adapter": True,
            "public_environment_api": True,
            "generated_host_call_entry": not full_runtime,
        }
        if full_runtime:
            for flag in FULL_RUNTIME_FLAGS:
                metadata[flag] = True
        artifact.with_suffix(artifact.suffix + ".json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )


def _write_status(path: Path, *, source_ready: bool) -> str:
    tag = "3.14.0" if source_ready else "3.14-dev.1"
    path.write_text(
        json.dumps(
            {
                "version_line": "3.14",
                "release_tag": tag,
                "stage": "stable" if source_ready else "developer-preview",
                "prerelease": not source_ready,
                "python_built_runtime": True,
                "source_execution_ready": source_ready,
                "completed_surface": ["runtime handles"],
                "release_blockers": [] if source_ready else ["native parser"],
            }
        ),
        encoding="utf-8",
    )
    return tag


def _run_gate(tmp_path: Path, *, source_ready: bool) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_artifacts(dist, full_runtime=source_ready)
    status = tmp_path / "status.json"
    tag = _write_status(status, source_ready=source_ready)
    assert main([str(dist), "--status", str(status), "--expected-tag", tag]) == 0
    return dist


def test_release_gate_validates_preview_artifacts(tmp_path: Path) -> None:
    dist = _run_gate(tmp_path, source_ready=False)
    manifest = json.loads((dist / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["release"]["source_execution_ready"] is False
    assert "Not yet included" in (dist / "RELEASE_NOTES.md").read_text(encoding="utf-8")


def test_release_gate_validates_full_runtime_artifacts(tmp_path: Path) -> None:
    dist = _run_gate(tmp_path, source_ready=True)
    manifest = json.loads((dist / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["release"]["source_execution_ready"] is True
    assert manifest["python_module_exports"] == list(PYTHON_MODULE_EXPORTS)
    notes = (dist / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert "Standalone source execution" in notes
