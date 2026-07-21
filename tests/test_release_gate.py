from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.native_surface import public_exports
from tools.python_surface import PYTHON_MODULE_EXPORTS
from tools.release_gate import main


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_artifacts(dist: Path, *, full_runtime: bool) -> None:
    expected_exports = list(public_exports(host_bridge=True, host_calls=True))
    for target, name in (("linux", "libportapy.so"), ("windows", "portapy.dll")):
        artifact = dist / name
        artifact.write_bytes((target.encode("ascii") + b"\0") * 1024)
        if artifact.stat().st_size < 4096:
            artifact.write_bytes(artifact.read_bytes() + b"x" * 4096)
        metadata = {
            "schema": 1,
            "target": target,
            "artifact": name,
            "size": artifact.stat().st_size,
            "sha256": _sha256(artifact),
            "source": "src/portapy/native_full_reference_entry.py",
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
            "full_frontend_vm": full_runtime,
            "standalone_parser": full_runtime,
            "reference_runtime_handles": full_runtime,
            "public_tuple_abi": full_runtime,
            "public_dict_abi": full_runtime,
            "public_list_abi": full_runtime,
        }
        artifact.with_suffix(artifact.suffix + ".json").write_text(
            json.dumps(metadata),
            encoding="utf-8",
        )


def _write_status(path: Path, *, source_ready: bool) -> None:
    path.write_text(
        json.dumps(
            {
                "version_line": "3.14",
                "release_tag": "3.14-dev.1",
                "stage": "developer-preview",
                "prerelease": True,
                "python_built_runtime": True,
                "source_execution_ready": source_ready,
                "completed_surface": ["runtime handles"],
                "release_blockers": [] if source_ready else ["native parser"],
            }
        ),
        encoding="utf-8",
    )


def _run_gate(tmp_path: Path, *, source_ready: bool) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_artifacts(dist, full_runtime=source_ready)
    status = tmp_path / "status.json"
    _write_status(status, source_ready=source_ready)
    assert main(
        [str(dist), "--status", str(status), "--expected-tag", "3.14-dev.1"]
    ) == 0
    return dist


def test_release_gate_validates_preview_artifacts(tmp_path: Path) -> None:
    dist = _run_gate(tmp_path, source_ready=False)
    manifest = json.loads(
        (dist / "release-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["release"]["source_execution_ready"] is False
    notes = (dist / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert "incremental native source entry" in notes


def test_release_gate_validates_full_runtime_artifacts(tmp_path: Path) -> None:
    dist = _run_gate(tmp_path, source_ready=True)
    manifest = json.loads(
        (dist / "release-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["release"]["source_execution_ready"] is True
    assert manifest["python_module_exports"] == list(PYTHON_MODULE_EXPORTS)
    notes = (dist / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert "Standalone source execution" in notes
