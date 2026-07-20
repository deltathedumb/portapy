"""Validate PortaPy release artifacts and generate checksums/manifest files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools.native_surface import PUBLIC_EXPORTS
from tools.python_surface import PYTHON_MODULE_EXPORTS


REQUIRED = {
    "windows": "portapy.dll",
    "linux": "libportapy.so",
}


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument(
        "--status",
        type=Path,
        default=Path("RELEASE_STATUS.json"),
    )
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
    if status.get("source_execution_ready") is not False:
        raise SystemExit(
            "developer preview must state that source execution is not ready; "
            "use a new final-release status when the PortaPy parser lands"
        )

    args.dist.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict[str, object]] = {}
    expected_exports = list(PUBLIC_EXPORTS)
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
        if metadata.get("python_built_runtime") is not True:
            raise SystemExit(f"artifact is not marked Python-built: {metadata_path}")
        if metadata.get("public_exports") != expected_exports:
            raise SystemExit(f"public export surface mismatch in {metadata_path}")
        if metadata.get("python_module_exports") != expected_python_exports:
            raise SystemExit(f"Python module surface mismatch in {metadata_path}")
        if metadata.get("python_module_entry") != "portapy.public_api":
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
        "python_module_entry": "portapy.public_api",
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
            "## High-level Python surface",
            "",
            "The artifact metadata declares the environment-oriented binary-module "
            "surface: `new`, `Environment`, `Snapshot`, and structured public errors.",
            "",
            "## Not yet included",
            "",
            "This is not the final Python 3.14 interpreter release. Native source "
            "execution remains gated on compound statements, function/class "
            "execution, host callbacks, and module imports.",
            "",
        ]
    )
    if isinstance(blockers, list):
        notes.extend(f"- {item}" for item in blockers)
    notes.extend(
        [
            "",
            "The release includes `portapy.dll`, `libportapy.so`, the public "
            "header, build metadata, and SHA-256 checksums.",
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
