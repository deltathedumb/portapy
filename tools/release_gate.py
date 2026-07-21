"""Validate PortaPy release artifacts and generate checksums/manifest files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools.native_surface import public_exports
from tools.python_surface import PYTHON_MODULE_EXPORTS


REQUIRED = {
    "windows": "portapy.dll",
    "linux": "libportapy.so",
}
PYTHON_MODULE_ENTRY = "portapy"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
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


def _require_true(metadata: dict[str, object], key: str, path: Path) -> None:
    if metadata.get(key) is not True:
        raise SystemExit(f"artifact does not assert {key}: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument("--status", type=Path, default=Path("RELEASE_STATUS.json"))
    parser.add_argument("--expected-tag", required=True)
    args = parser.parse_args(argv)

    status = _read_json(args.status)
    if status.get("release_tag") != args.expected_tag:
        raise SystemExit(
            f"release tag mismatch: expected {args.expected_tag!r}, "
            f"status declares {status.get('release_tag')!r}"
        )
    if status.get("stage") != "developer-preview" or status.get("prerelease") is not True:
        raise SystemExit("3.14-dev.1 must remain explicitly marked as a prerelease")
    if status.get("python_built_runtime") is not True:
        raise SystemExit("release status does not assert a Python-built runtime")
    source_ready = status.get("source_execution_ready")
    if not isinstance(source_ready, bool):
        raise SystemExit("release status must declare source_execution_ready as a boolean")

    args.dist.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict[str, object]] = {}
    expected_exports = list(public_exports(host_bridge=True, host_calls=True))
    expected_python_exports = list(PYTHON_MODULE_EXPORTS)
    for target, name in REQUIRED.items():
        path = args.dist / name
        metadata_path = path.with_suffix(path.suffix + ".json")
        if not path.is_file() or path.stat().st_size < 4096:
            raise SystemExit(f"missing or implausibly small native artifact: {path}")
        metadata = _read_json(metadata_path)
        actual_digest = sha256(path)
        if metadata.get("target") != target:
            raise SystemExit(f"target mismatch in {metadata_path}")
        if metadata.get("artifact") != name:
            raise SystemExit(f"artifact-name mismatch in {metadata_path}")
        if metadata.get("size") != path.stat().st_size:
            raise SystemExit(f"artifact-size mismatch in {metadata_path}")
        if metadata.get("sha256") != actual_digest:
            raise SystemExit(f"artifact digest mismatch in {metadata_path}")
        _require_true(metadata, "python_built_runtime", metadata_path)
        _require_true(metadata, "host_bridge", metadata_path)
        _require_true(metadata, "host_calls", metadata_path)
        _require_true(metadata, "native_environment_adapter", metadata_path)
        _require_true(metadata, "public_environment_api", metadata_path)
        if source_ready:
            _require_true(metadata, "full_frontend_vm", metadata_path)
            _require_true(metadata, "standalone_parser", metadata_path)
            _require_true(metadata, "reference_runtime_handles", metadata_path)
            _require_true(metadata, "public_tuple_abi", metadata_path)
            _require_true(metadata, "public_dict_abi", metadata_path)
            _require_true(metadata, "public_list_abi", metadata_path)
        elif metadata.get("generated_host_call_entry") is not True:
            raise SystemExit(
                f"preview artifact is not host-call-entry generated: {metadata_path}"
            )
        if metadata.get("public_exports") != expected_exports:
            raise SystemExit(f"public export surface mismatch in {metadata_path}")
        if metadata.get("python_module_exports") != expected_python_exports:
            raise SystemExit(f"Python module surface mismatch in {metadata_path}")
        if metadata.get("python_module_entry") != PYTHON_MODULE_ENTRY:
            raise SystemExit(f"Python module entry mismatch in {metadata_path}")
        records[name] = {
            "platform": target,
            "sha256": actual_digest,
            "size": path.stat().st_size,
            "metadata": metadata_path.name,
        }

    checksums = args.dist / "checksums.json"
    checksums.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema": 1,
        "release": status,
        "artifacts": records,
        "public_exports": expected_exports,
        "python_module_exports": expected_python_exports,
        "python_module_entry": PYTHON_MODULE_ENTRY,
    }
    (args.dist / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    completed = status.get("completed_surface")
    blockers = status.get("release_blockers")
    notes = [
        "# PortaPy 3.14 Developer Preview 1",
        "",
        "This prerelease contains genuine native libraries generated from "
        "PortaPy's Python-authored runtime state by asmpython.",
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
            "The DLL/SO exports first-class `new`, `add`, `add_all`, `execute`, "
            "`evaluate`, and `destroy` helpers through a language-neutral C ABI. "
            "The same environment handle can be used with the lower-level runtime, "
            "value, global, callback, container, and structured-error functions.",
            "",
        ]
    )
    if source_ready:
        notes.extend(
            [
                "## Standalone source execution",
                "",
                "The release library contains PortaPy's standalone parser, full "
                "frontend, bytecode VM, runtime handles, closures, classes, "
                "configured imports, and traceback propagation.",
                "",
            ]
        )
    else:
        notes.extend(
            [
                "## Not yet included",
                "",
                "This preview still uses the incremental native source entry. "
                "The full standalone parser/VM artifact has not yet been promoted.",
                "",
            ]
        )
    if isinstance(blockers, list) and blockers:
        notes.extend(["## Remaining limitations", ""])
        notes.extend(f"- {item}" for item in blockers)
        notes.append("")
    notes.extend(
        [
            "The release includes `portapy.dll`, `libportapy.so`, the public "
            "header, build metadata, FFI examples, and SHA-256 checksums.",
            "",
        ]
    )
    (args.dist / "RELEASE_NOTES.md").write_text(
        "\n".join(notes),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
