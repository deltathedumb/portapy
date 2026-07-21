"""Build PortaPy's generated positional-function native entry."""
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
from tools.generate_native_function_entry import (
    generate_native_function_entry,
    rewrite_control_expression_imports,
)
from tools.namespace_generated_module import namespace_generated_module
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
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    package = REPOSITORY_ROOT / "src" / "portapy"
    scalar_module = f"_native_api_scalar_functions_{args.target}"
    expression_module = f"_native_api_expressions_functions_{args.target}"
    control_module = f"_native_api_control_functions_{args.target}"
    function_module = f"_native_api_functions_generated_{args.target}"
    scalar_source = package / f"{scalar_module}.py"
    expression_source = package / f"{expression_module}.py"
    control_source = package / f"{control_module}.py"
    function_source = package / f"{function_module}.py"
    generated_paths = [scalar_source, expression_source, control_source, function_source]

    try:
        generate_namespaced_scalar_entry(scalar_source)
        rewrite_generated_scalar(scalar_source)

        generate_native_expression_entry(
            expression_source,
            scalar_module=scalar_module,
        )
        rewrite_generated_expression(expression_source)
        expression_mapping = namespace_generated_module(expression_source, "_expr_")
        for required in (
            "_parse_boolean_expression",
            "_record_expression_failure",
            "_truthy",
            "_word_at",
        ):
            if required not in expression_mapping:
                raise ValueError(f"generated expression entry is missing {required}")

        generate_native_control_entry(
            control_source,
            expression_module=expression_module,
            scalar_module=scalar_module,
        )
        rewrite_generated_control(control_source)
        rewrite_control_expression_imports(control_source, expression_module)
        control_mapping = namespace_generated_module(control_source, "_ctrl_")
        for required in ("_line_info", "_portapy_exec_span_impl", "_syntax_error"):
            if required not in control_mapping:
                raise ValueError(f"generated control entry is missing {required}")

        generate_native_function_entry(
            function_source,
            scalar_module=scalar_module,
            expression_module=expression_module,
            control_module=control_module,
        )

        metadata = build_native(
            target=args.target,
            output=args.output,
            source=function_source,
            work_dir=args.work_dir,
        )
    except (BuildFailure, ValueError) as error:
        print(f"portapy native function build failed: {error}", file=sys.stderr)
        return 1
    finally:
        for path in generated_paths:
            path.unlink(missing_ok=True)

    metadata["generated_scalar_entry"] = True
    metadata["generated_expression_entry"] = True
    metadata["generated_control_entry"] = True
    metadata["generated_function_entry"] = True
    metadata["namespaced_expression_helpers"] = True
    metadata["namespaced_control_helpers"] = True
    metadata["native_safe_parser_rewrite"] = True
    metadata["semantic_sources"] = [
        "src/portapy/native_api.py",
        "src/portapy/native_api_typed.py",
        "src/portapy/native_api_scalar.py",
        "src/portapy/native_api_boolean.py",
        "src/portapy/native_api_control.py",
        "src/portapy/native_api_functions.py",
    ]
    metadata["python_module_exports"] = list(PYTHON_MODULE_EXPORTS)
    metadata["python_module_entry"] = "portapy"
    metadata_path = args.output.resolve().with_suffix(args.output.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
