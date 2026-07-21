"""Build PortaPy's generated control-flow and expression native entry.

The historical filename remains as a compatibility shim for existing CI and
release workflows. The default build statically composes namespace-safe scalar,
boolean, and control-flow layers before invoking asmpython.
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
from tools.generate_native_control_entry import generate_native_control_entry
from tools.generate_native_expression_entry import (
    generate_namespaced_scalar_entry,
    generate_native_expression_entry,
)
from tools.python_surface import PYTHON_MODULE_EXPORTS
from tools.rewrite_generated_parser_safe import (
    rewrite_generated_control,
    rewrite_generated_expression,
    rewrite_generated_scalar,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("linux", "windows"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    source = args.source
    generated_paths: list[Path] = []
    if source is None:
        package = REPOSITORY_ROOT / "src" / "portapy"
        scalar_module = f"_native_api_scalar_generated_{args.target}"
        expression_module = f"_native_api_expressions_generated_{args.target}"
        scalar_source = package / f"{scalar_module}.py"
        expression_source = package / f"{expression_module}.py"
        control_source = package / f"_native_api_control_generated_{args.target}.py"
        generate_namespaced_scalar_entry(scalar_source)
        rewrite_generated_scalar(scalar_source)
        generate_native_expression_entry(
            expression_source,
            scalar_module=scalar_module,
        )
        rewrite_generated_expression(expression_source)
        generate_native_control_entry(
            control_source,
            expression_module=expression_module,
            scalar_module=scalar_module,
        )
        rewrite_generated_control(control_source)
        generated_paths.extend([scalar_source, expression_source, control_source])
        source = control_source

    try:
        metadata = build_native(
            target=args.target,
            output=args.output,
            source=source,
            work_dir=args.work_dir,
        )
    except (BuildFailure, ValueError) as error:
        print(f"portapy native build failed: {error}", file=sys.stderr)
        return 1
    finally:
        for generated_path in generated_paths:
            generated_path.unlink(missing_ok=True)

    metadata["generated_scalar_entry"] = bool(generated_paths)
    metadata["generated_expression_entry"] = bool(generated_paths)
    metadata["generated_control_entry"] = bool(generated_paths)
    metadata["native_safe_parser_rewrite"] = bool(generated_paths)
    metadata["semantic_sources"] = [
        "src/portapy/native_api.py",
        "src/portapy/native_api_typed.py",
        "src/portapy/native_api_scalar.py",
        "src/portapy/native_api_boolean.py",
        "src/portapy/native_api_control.py",
    ]
    metadata["python_module_exports"] = list(PYTHON_MODULE_EXPORTS)
    metadata["python_module_entry"] = "portapy"
    metadata_path = args.output.resolve().with_suffix(args.output.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
