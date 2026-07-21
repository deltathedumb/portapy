"""Build PortaPy's canonical native interpreter entry.

The historical filename remains the stable CI/release command. Default builds
prepare and compile the generated language-neutral ABI over PortaPy's standalone
portable frontend and full VM. Passing ``--source`` retains focused source-entry
compiler probes and bypasses the final environment adapter.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.build_native import BuildFailure, build_native
from tools.build_native_host_calls import main as build_host_call_entry
from tools.prepare_standalone_native_sources import prepare
from tools.python_surface import PYTHON_MODULE_EXPORTS


def _build_explicit_source(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("linux", "windows"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        metadata = build_native(
            target=args.target,
            output=args.output,
            source=args.source,
            work_dir=args.work_dir,
        )
    except (BuildFailure, ValueError) as error:
        print(f"portapy native build failed: {error}", file=sys.stderr)
        return 1
    metadata["generated_scalar_entry"] = False
    metadata["generated_expression_entry"] = False
    metadata["generated_control_entry"] = False
    metadata["generated_function_entry"] = False
    metadata["generated_host_entry"] = False
    metadata["generated_host_call_entry"] = False
    metadata["python_module_exports"] = list(PYTHON_MODULE_EXPORTS)
    metadata["python_module_entry"] = "portapy"
    metadata_path = args.output.resolve().with_suffix(args.output.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--source" in arguments:
        return _build_explicit_source(arguments)
    try:
        prepare()
    except RuntimeError as error:
        print(f"portapy standalone source preparation failed: {error}", file=sys.stderr)
        return 1
    if "--standalone-vm" not in arguments:
        arguments.insert(0, "--standalone-vm")
    return build_host_call_entry(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
