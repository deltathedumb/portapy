"""Replace the frontend's native dict hint ledger with parallel lists."""
from __future__ import annotations

from pathlib import Path

from tools.normalize_full_core_truthiness_directives import (
    main as normalize_truthiness,
)


FRONTEND_PATH = Path("src/portapy/core/frontend.py")


def _replace(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"native list-backed truth hints {label}: expected 1 match, found {count}"
        )
    return source.replace(old, new, 1)


def main() -> int:
    normalize_truthiness()

    source = FRONTEND_PATH.read_text(encoding="utf-8")
    source = _replace(
        source,
        "    kind_hints: dict[str, int] = field(default_factory=dict)\n",
        "    kind_hint_names: list[str] = field(default_factory=list)\n"
        "    kind_hint_values: list[int] = field(default_factory=list)\n",
        "fields",
    )
    anchor = "    def expression_kind(self, node: ast.expr) -> int:\n"
    methods = '''    def kind_hint(self, name: str) -> int:
        index = 0
        while index < len(self.kind_hint_names):
            if self.kind_hint_names[index] == name:
                return self.kind_hint_values[index]
            index += 1
        return _TRUTH_UNKNOWN

    def set_kind_hint(self, name: str, kind: int) -> None:
        index = 0
        while index < len(self.kind_hint_names):
            if self.kind_hint_names[index] == name:
                self.kind_hint_values[index] = kind
                return
            index += 1
        self.kind_hint_names.append(name)
        self.kind_hint_values.append(kind)

    def copy_kind_hints(self, other: object) -> None:
        index = 0
        while index < len(other.kind_hint_names):
            self.set_kind_hint(
                other.kind_hint_names[index],
                other.kind_hint_values[index],
            )
            index += 1

'''
    source = _replace(source, anchor, methods + anchor, "method insertion")
    source = _replace(
        source,
        "            return self.kind_hints.get(node.id, _TRUTH_UNKNOWN)",
        "            return self.kind_hint(node.id)",
        "name lookup",
    )
    source = _replace(
        source,
        "        nested.kind_hints.update(self.kind_hints)",
        "        nested.copy_kind_hints(self)",
        "nested copy",
    )
    source = _replace(
        source,
        "                self.kind_hints[node.targets[0].id] = self.expression_kind(node.value)",
        "                self.set_kind_hint(node.targets[0].id, self.expression_kind(node.value))",
        "assignment recording",
    )
    source = _replace(
        source,
        "            lowerer.kind_hints[hint_name] = statement.value.value",
        "            lowerer.set_kind_hint(hint_name, statement.value.value)",
        "directive recording",
    )

    if "kind_hints" in source:
        raise RuntimeError("native dict truth-hint ledger survived list normalization")
    FRONTEND_PATH.write_text(source, encoding="utf-8")
    print("NORMALIZED LIST-BACKED NATIVE TRUTH HINTS", 5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
