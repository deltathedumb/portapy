"""Build PortaPy using the general scalar-expression native source entry.

The historical filename remains as a compatibility shim for existing CI and
release workflows. Its default source advances with the native interpreter.
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
from tools.python_surface import PYTHON_MODULE_EXPORTS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("linux", "windows"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--source",
        type=Path,
        default=REPOSITORY_ROOT / "src" / "portapy" / "native_api_expressions.py",
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        metadata = build_native(
            target=args.target,
            output=args.output,
            source=args.source,
            work_dir=args.work_dir,
        )
    except BuildFailure as error:
        print(f"portapy expression native build failed: {error}", file=sys.stderr)
        return 1

    metadata["python_module_exports"] = list(PYTHON_MODULE_EXPORTS)
    metadata["python_module_entry"] = "portapy.public_api"
    metadata_path = args.output.resolve().with_suffix(args.output.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
