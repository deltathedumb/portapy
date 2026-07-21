"""Build PortaPy's current native interpreter entry.

The historical filename remains the stable CI/release command. Default builds
now use the generated host-object entry, which includes scalar expressions,
control flow, positional functions, and opaque host attribute graphs. Passing
``--source`` retains the focused source-entry mode used by compiler probes.
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
from tools.build_native_host import main as build_host_entry
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
    return build_host_entry(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
