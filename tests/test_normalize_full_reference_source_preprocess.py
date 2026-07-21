from __future__ import annotations

import ast
from pathlib import Path

from tools import materialize_full_reference_entry as materializer
from tools import normalize_full_reference_abi_helpers as abi_normalizer
from tools import normalize_full_reference_errors as error_normalizer
from tools import normalize_full_reference_float_bits as float_normalizer
from tools import normalize_full_reference_source_preprocess as source_normalizer
from tools import normalize_full_reference_value_kinds as kind_normalizer


def _expand(source: str) -> str:
    namespace: dict[str, object] = {}
    exec(source_normalizer._HELPER_SOURCE, namespace)
    return namespace["_native_expand_runtime_source"](source)


def test_expands_top_level_semicolons_without_touching_literals_or_comments() -> None:
    assert _expand("first = 1; second = 2") == "first = 1\nsecond = 2"
    assert _expand("text = 'a;b#c'; answer = 42 # ; ignored") == (
        "text = 'a;b#c'\nanswer = 42 # ; ignored"
    )
    assert _expand("items = [1; 2]") == "items = [1; 2]"


def test_indents_compact_compound_suites() -> None:
    assert _expand("if flag: first = 1; second = 2") == (
        "if flag: first = 1\n    second = 2"
    )
    assert _expand("while ready: tick(); stop()") == (
        "while ready: tick()\n    stop()"
    )


def test_consumes_tabs_and_spaces_after_separator() -> None:
    assert _expand("first = 1;\t  second = 2") == "first = 1\nsecond = 2"
    assert _expand("if flag: first = 1;\t second = 2") == (
        "if flag: first = 1\n    second = 2"
    )


def test_installs_preprocessing_into_exec_and_eval(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "native_full_reference_entry.py"
    monkeypatch.setattr(materializer, "OUTPUT", output)
    monkeypatch.setattr(abi_normalizer, "PATH", output)
    monkeypatch.setattr(float_normalizer, "PATH", output)
    monkeypatch.setattr(error_normalizer, "PATH", output)
    monkeypatch.setattr(kind_normalizer, "PATH", output)
    monkeypatch.setattr(source_normalizer, "PATH", output)

    assert materializer.main() == 0
    assert abi_normalizer.main() == 0
    assert float_normalizer.main() == 0
    assert error_normalizer.main() == 0
    assert kind_normalizer.main() == 0
    assert source_normalizer.main() == 0

    module = ast.parse(output.read_text(encoding="utf-8"))
    text = ast.unparse(module)
    assert text.count("_native_expand_runtime_source(source[0:source_size])") == 2
