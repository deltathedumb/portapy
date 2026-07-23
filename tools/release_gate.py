"""Validate PortaPy release artifacts and generate checksums/manifest files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools.native_surface import public_exports
from tools.python_surface import PYTHON_MODULE_EXPORTS


REQUIRED = {"windows": "portapy.dll", "linux": "libportapy.so"}
PYTHON_MODULE_ENTRY = "portapy"
FULL_RUNTIME_FLAGS = (
    "full_frontend_vm",
    "standalone_parser",
    "reference_runtime_handles",
    "public_tuple_abi",
    "public_dict_abi",
    "public_list_abi",
    "direct_float_abi",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"invalid release metadata {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"release metadata must be a JSON object: {path}")
    return value


def _validate_status(status: dict[str, object], expected_tag: str) -> bool:
    if status.get("release_tag") != expected_tag:
        raise SystemExit(
            f"release tag mismatch: expected {expected_tag!r}, "
            f"status declares {status.get('release_tag')!r}"
        )
    if status.get("python_built_runtime") is not True:
        raise SystemExit("release status does not assert a Python-built runtime")

    source_ready = status.get("source_execution_ready") is True
    if source_ready:
        if status.get("stage") != "stable" or status.get("prerelease") is not False:
            raise SystemExit("source-ready PortaPy must be marked as a stable release")
        blockers = status.get("release_blockers")
        if blockers not in ([], None):
            raise SystemExit("stable source-ready release still declares blockers")
    else:
        if status.get("stage") != "developer-preview" or status.get("prerelease") is not True:
            raise SystemExit("non-source-ready PortaPy must remain a developer preview")
    return source_ready


def _validate_artifact(
    path: Path,
    *,
    target: str,
    source_ready: bool,
    expected_exports: list[str],
    expected_python_exports: list[str],
) -> dict[str, object]:
    metadata_path = path.with_suffix(path.suffix + ".json")
    if not path.is_file() or path.stat().st_size < 4096:
        raise SystemExit(f"missing or implausibly small native artifact: {path}")
    metadata = _read_json(metadata_path)
    actual_digest = sha256(path)

    expected = {
        "target": target,
        "artifact": path.name,
        "size": path.stat().st_size,
        "sha256": actual_digest,
        "python_built_runtime": True,
        "host_bridge": True,
        "host_calls": True,
        "native_environment_adapter": True,
        "public_environment_api": True,
        "public_exports": expected_exports,
        "python_module_exports": expected_python_exports,
        "python_module_entry": PYTHON_MODULE_ENTRY,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise SystemExit(f"{key} mismatch in {metadata_path}")

    if source_ready:
        for flag in FULL_RUNTIME_FLAGS:
            if metadata.get(flag) is not True:
                raise SystemExit(f"full Runtime flag {flag!r} missing in {metadata_path}")
    elif metadata.get("generated_host_call_entry") is not True:
        raise SystemExit(f"preview artifact is not host-call-entry generated: {metadata_path}")

    return {
        "platform": target,
        "sha256": actual_digest,
        "size": path.stat().st_size,
        "metadata": metadata_path.name,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument("--status", type=Path, default=Path("RELEASE_STATUS.json"))
    parser.add_argument("--expected-tag", required=True)
    args = parser.parse_args(argv)

    status = _read_json(args.status)
    source_ready = _validate_status(status, args.expected_tag)
    args.dist.mkdir(parents=True, exist_ok=True)

    expected_exports = list(public_exports(host_bridge=True, host_calls=True))
    expected_python_exports = list(PYTHON_MODULE_EXPORTS)
    records: dict[str, dict[str, object]] = {}
    for target, name in REQUIRED.items():
        records[name] = _validate_artifact(
            args.dist / name,
            target=target,
            source_ready=source_ready,
            expected_exports=expected_exports,
            expected_python_exports=expected_python_exports,
        )

    (args.dist / "checksums.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema": 1,
        "release": status,
        "artifacts": records,
        "public_exports": expected_exports,
        "python_module_exports": expected_python_exports,
        "python_module_entry": PYTHON_MODULE_ENTRY,
    }
    (args.dist / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    completed = status.get("completed_surface")
    blockers = status.get("release_blockers")
    title = "# PortaPy 3.14.0" if source_ready else "# PortaPy 3.14 Developer Preview 1"
    notes = [
        title,
        "",
        "PortaPy is a Python-built embeddable runtime compiled into native Linux and Windows libraries.",
        "",
        "## Implemented native surface",
        "",
    ]
    if isinstance(completed, list):
        notes.extend(f"- {item}" for item in completed)
    notes.extend(
        [
            "",
            "## Universal embedding surface",
            "",
            "The DLL/SO exports language-neutral `new`, `add`, `add_all`, `execute`, `evaluate`, and `destroy` helpers alongside the complete low-level runtime, value, callback, container, snapshot, and error ABI.",
            "",
        ]
    )
    if source_ready:
        notes.extend(
            [
                "## Standalone source execution",
                "",
                "The canonical artifacts include PortaPy's standalone parser, full frontend, bytecode VM, closures, classes, configured imports, and synthetic traceback frames.",
                "",
            ]
        )
    else:
        notes.extend(["## Not yet included", ""])
        if isinstance(blockers, list):
            notes.extend(f"- {item}" for item in blockers)
        notes.append("")
    notes.extend(
        [
            "The release includes `portapy.dll`, `libportapy.so`, the public header, build metadata, FFI examples, and SHA-256 checksums.",
            "",
        ]
    )
    (args.dist / "RELEASE_NOTES.md").write_text("\n".join(notes), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
