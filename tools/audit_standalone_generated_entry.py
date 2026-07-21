"""Generate and parse-audit the canonical standalone native entry.

This runs every source-generation and rewrite pass used by
``build_native_host_calls --standalone-vm`` but stops before assembly emission.
It gives source-positioned pinned-asmpython parser failures early and leaves an
optional copy of the generated Python for workflow artifacts.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

from tools.generate_native_control_entry import generate_native_control_entry
from tools.generate_native_expression_entry import (
    generate_namespaced_scalar_entry,
    generate_native_expression_entry,
)
from tools.generate_native_function_entry import (
    generate_native_function_entry,
    rewrite_control_expression_imports,
)
from tools.generate_native_host_call_entry import generate_native_host_call_entry
from tools.generate_native_host_entry import generate_native_host_entry
from tools.namespace_generated_module import namespace_generated_module
from tools.rewrite_generated_full_vm_environment import (
    rewrite_generated_full_vm_environment,
)
from tools.rewrite_generated_function_stack import rewrite_generated_function
from tools.rewrite_generated_host_calls import rewrite_generated_host_calls
from tools.rewrite_generated_parser_safe import (
    rewrite_generated_control,
    rewrite_generated_expression,
    rewrite_generated_scalar,
)
from tools.rewrite_generated_public_dict import rewrite_generated_public_dict
from tools.rewrite_generated_public_list import rewrite_generated_public_list
from tools.rewrite_generated_public_tuple import rewrite_generated_public_tuple


def generate(target: str, directory: Path) -> Path:
    scalar_module = f"_audit_scalar_{target}"
    expression_module = f"_audit_expression_{target}"
    control_module = f"_audit_control_{target}"
    function_module = f"_audit_function_{target}"
    host_module = f"_audit_host_{target}"
    call_module = f"_audit_entry_{target}"

    scalar_source = directory / f"{scalar_module}.py"
    expression_source = directory / f"{expression_module}.py"
    control_source = directory / f"{control_module}.py"
    function_source = directory / f"{function_module}.py"
    host_source = directory / f"{host_module}.py"
    call_source = directory / f"{call_module}.py"

    generate_namespaced_scalar_entry(scalar_source)
    rewrite_generated_scalar(scalar_source)
    generate_native_expression_entry(expression_source, scalar_module=scalar_module)
    rewrite_generated_expression(expression_source)
    namespace_generated_module(expression_source, "_expr_")
    generate_native_control_entry(
        control_source,
        expression_module=expression_module,
        scalar_module=scalar_module,
    )
    rewrite_generated_control(control_source)
    rewrite_control_expression_imports(control_source, expression_module)
    namespace_generated_module(control_source, "_ctrl_")
    generate_native_function_entry(
        function_source,
        scalar_module=scalar_module,
        expression_module=expression_module,
        control_module=control_module,
    )
    rewrite_generated_function(function_source)
    namespace_generated_module(function_source, "_fn_")
    generate_native_host_entry(
        host_source,
        scalar_module=scalar_module,
        function_module=function_module,
    )
    namespace_generated_module(host_source, "_host_")
    generate_native_host_call_entry(
        call_source,
        host_module=host_module,
        scalar_module=scalar_module,
    )
    rewrite_generated_host_calls(call_source)
    rewrite_generated_public_tuple(call_source)
    rewrite_generated_public_dict(call_source)
    rewrite_generated_public_list(call_source)
    rewrite_generated_full_vm_environment(
        call_source,
        host_module=host_module,
        target=target,
    )
    return call_source


def audit(path: Path) -> None:
    from asmpython._compiler.lexer import Lexer
    from asmpython._compiler.parser import Parser

    source = path.read_text(encoding="utf-8")
    try:
        Parser(Lexer(source).tokenize()).parse()
    except Exception as error:
        position = getattr(error, "pos", None)
        line = int(getattr(position, "line", 0))
        column = int(getattr(position, "col", 0))
        print(f"FAIL {path}: {type(error).__name__}: {error}")
        if 0 < line <= len(source.splitlines()):
            text = source.splitlines()[line - 1]
            print(f"  {line}:{column}: {text}")
            print("  " + " " * max(column - 1, 0) + "^")
        raise
    print(f"PASS {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("linux", "windows"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="portapy-standalone-audit-") as raw:
        generated = generate(args.target, Path(raw))
        audit(generated)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(generated.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"WROTE {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
