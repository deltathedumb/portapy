"""Build PortaPy using the generated general-expression native entry.

The historical filename remains as a compatibility shim for existing CI and
release workflows. The default build statically composes the Python-authored
boolean and scalar parser layers before invoking asmpython.
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
from tools.generate_native_expression_entry import generate_native_expression_entry
from tools.python_surface import PYTHON_MODULE_EXPORTS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("linux", "windows"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    source = args.source
    generated = False
    if source is None:
        source = args.work_dir / "native_api_expressions_generated.py"
        generate_native_expression_entry(source)
        generated = True

    try:
        metadata = build_native(
            target=args.target,
            output=args.output,
            source=source,
            work_dir=args.work_dir,
        )
    except (BuildFailure, ValueError) as error:
        print(f"portapy expression native build failed: {error}", file=sys.stderr)
        return 1

    metadata["generated_expression_entry"] = generated
    metadata["semantic_sources"] = [
        "src/portapy/native_api.py",
        "src/portapy/native_api_typed.py",
        "src/portapy/native_api_scalar.py",
        "src/portapy/native_api_boolean.py",
    ]
    metadata["python_module_exports"] = list(PYTHON_MODULE_EXPORTS)
    metadata["python_module_entry"] = "portapy.public_api"
    metadata_path = args.output.resolve().with_suffix(args.output.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
