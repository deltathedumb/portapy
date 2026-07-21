"""Generate PortaPy's native control-flow entry over a static expression module."""
from __future__ import annotations

import argparse
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTROL_SOURCE = REPOSITORY_ROOT / "src" / "portapy" / "native_api_control.py"


def generate_native_control_entry(
    output: Path,
    *,
    expression_module: str,
) -> Path:
    if not expression_module.isidentifier():
        raise ValueError(f"invalid generated expression module: {expression_module!r}")
    source = CONTROL_SOURCE.read_text(encoding="utf-8")
    old_import = "from .native_api_expressions import ("
    if old_import not in source:
        raise ValueError("control-flow source has an unexpected expression import")
    source = source.replace(
        old_import,
        f"from .{expression_module} import (",
        1,
    )
    source = source.replace(
        '"""Indented control-flow entry for PortaPy\'s native runtime.',
        '"""Generated control-flow entry for PortaPy\'s native runtime.',
        1,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source, encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expression-module", required=True)
    args = parser.parse_args(argv)
    generate_native_control_entry(
        args.output,
        expression_module=args.expression_module,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
