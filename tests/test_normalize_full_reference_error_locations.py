from __future__ import annotations

import ast
from pathlib import Path

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as abi_normalizer
from tools import normalize_full_reference_error_locations as location_normalizer
from tools import normalize_full_reference_errors as error_normalizer
from tools import normalize_full_reference_float_bits as float_normalizer


def _locator():
    namespace: dict[str, object] = {}
    source = "def locate(source: str):\n" + "\n".join(
        "    " + line for line in location_normalizer._LOCATION_BODY.splitlines()
    )
    exec(source, namespace)
    return namespace["locate"]


def test_finds_invalid_indentation_and_zero_division() -> None:
    locate = _locator()
    assert locate("value = 1\n  unexpected = 2\n") == (2, 3)
    assert locate("if ready:\n    value = 1\nresult = 2\n") == (1, 1)
    assert locate("safe = 1\nbroken = 5 // 0") == (2, 12)
    assert locate("value = 9 % 0") == (1, 11)
    assert locate("text = '5 // 0'") == (1, 1)


def test_replaces_generated_error_locator(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(abi_normalizer, "PATH", output)
    monkeypatch.setattr(float_normalizer, "PATH", output)
    monkeypatch.setattr(error_normalizer, "PATH", output)
    monkeypatch.setattr(location_normalizer, "PATH", output)

    assert materializer.main() == 0
    assert abi_normalizer.main() == 0
    assert float_normalizer.main() == 0
    assert error_normalizer.main() == 0
    assert location_normalizer.main() == 0

    module = ast.parse(output.read_text(encoding="utf-8"))
    locator = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_native_error_location"
    )
    text = ast.unparse(locator)
    assert "previous_opens_block" in text
    assert "return line_index + 1, indent + 1" in text
    assert "return line_index + 1, column_index + 1" in text
