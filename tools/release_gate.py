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


def _validate_release_status(status: dict[str, object], expected_tag: str) -> None:
    if status.get("release_tag") != expected_tag:
        raise SystemExit(
            f"release tag mismatch: expected {expected_tag!r}, "
            f"status declares {status.get('release_tag')!r}"
        )
    stage = status.get("stage")
    prerelease = status.get("prerelease")
    ready = status.get("source_execution_ready")
    blockers = status.get("release_blockers")
    if stage == "developer-preview":
        if prerelease is not True:
            raise SystemExit("developer preview must be marked as a prerelease")
    elif stage == "final":
        if prerelease is not False:
            raise SystemExit("final release must not be marked as a prerelease")
        if ready is not True:
            raise SystemExit("final release must assert standalone source execution readiness")
        if blockers not in ([], None):
            raise SystemExit("final release status still declares release blockers")
    else:
        raise SystemExit(f"unsupported release stage: {stage!r}")
    if status.get("python_built_runtime") is not True:
        raise SystemExit("release status does not assert a Python-built runtime")


def _require(metadata: dict[str, object], key: str, expected: object, path: Path) -> None:
    if metadata.get(key) != expected:
        raise SystemExit(
            f"artifact metadata mismatch for {key!r} in {path}: "
            f"expected {expected!r}, got {metadata.get(key)!r}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument("--status", type=Path, default=Path("RELEASE_STATUS.json"))
    parser.add_argument("--expected-tag", required=True)
    args = parser.parse_args(argv)

    status = _read_json(args.status)
    _validate_release_status(status, args.expected_tag)

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
        _require(metadata, "target", target, metadata_path)
        _require(metadata, "artifact", name, metadata_path)
        _require(metadata, "size", path.stat().st_size, metadata_path)
        _require(metadata, "sha256", actual_digest, metadata_path)
        _require(metadata, "python_built_runtime", True, metadata_path)
        _require(metadata, "host_bridge", True, metadata_path)
        _require(metadata, "host_calls", True, metadata_path)
        _require(metadata, "native_environment_adapter", True, metadata_path)
        _require(metadata, "public_environment_api", True, metadata_path)
        _require(metadata, "public_traceback_abi", True, metadata_path)
        _require(metadata, "generated_host_call_entry", True, metadata_path)
        _require(metadata, "standalone_frontend", True, metadata_path)
        _require(metadata, "full_virtual_machine", True, metadata_path)
        _require(metadata, "incremental_executor", False, metadata_path)
        _require(metadata, "public_exports", expected_exports, metadata_path)
        _require(metadata, "python_module_exports", expected_python_exports, metadata_path)
        _require(metadata, "python_module_entry", PYTHON_MODULE_ENTRY, metadata_path)
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
    title = status.get("display_name") or f"PortaPy {args.expected_tag}"
    notes = [
        f"# {title}",
        "",
        "This release contains native libraries generated from PortaPy's "
        "Python-authored portable frontend and full virtual machine by asmpython.",
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
            "value, global, callback, container, traceback, and structured-error functions.",
            "",
            "Executed source can use `import` and `from ... import ...` for modules "
            "already added by the host. Host languages still own module loading; "
            "PortaPy does not expose `import_module`.",
            "",
            "Tracebacks are available as indexed filename, function, line, column, "
            "and source-line frames through C and as `NativeTracebackFrame` objects "
            "through the native Python facade.",
            "",
        ]
    )
    if isinstance(blockers, list) and blockers:
        notes.extend(["## Remaining gates", ""])
        notes.extend(f"- {item}" for item in blockers)
        notes.append("")
    notes.extend(
        [
            "The release includes `portapy.dll`, `libportapy.so`, the public "
            "headers, build metadata, FFI examples, and SHA-256 checksums.",
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
