from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.native_surface import PUBLIC_EXPORTS
from tools.python_surface import PYTHON_MODULE_EXPORTS
from tools.release_gate import main


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_release_gate_validates_both_native_artifacts(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
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
            "source": "src/portapy/native_api_expressions.py",
            "source_sha256": "0" * 64,
            "public_exports": list(PUBLIC_EXPORTS),
            "python_module_exports": list(PYTHON_MODULE_EXPORTS),
            "python_module_entry": "portapy.public_api",
            "python_built_runtime": True,
        }
        artifact.with_suffix(artifact.suffix + ".json").write_text(
            json.dumps(metadata),
            encoding="utf-8",
        )

    status = tmp_path / "status.json"
    status.write_text(
        json.dumps(
            {
                "version_line": "3.14",
                "release_tag": "3.14-dev.1",
                "stage": "developer-preview",
                "prerelease": True,
                "python_built_runtime": True,
                "source_execution_ready": False,
                "completed_surface": ["runtime handles"],
                "release_blockers": ["native parser"],
            }
        ),
        encoding="utf-8",
    )

    assert main([str(dist), "--status", str(status), "--expected-tag", "3.14-dev.1"]) == 0
    assert (dist / "checksums.json").is_file()
    manifest = json.loads((dist / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["release"]["stage"] == "developer-preview"
    assert manifest["public_exports"] == list(PUBLIC_EXPORTS)
    assert manifest["python_module_exports"] == list(PYTHON_MODULE_EXPORTS)
    assert manifest["python_module_entry"] == "portapy.public_api"
    notes = (dist / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert "not the final Python 3.14 interpreter release" in notes
