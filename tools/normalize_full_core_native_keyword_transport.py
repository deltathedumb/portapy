"""Avoid passing freshly-built keyword dictionaries across the native call ABI.

The pinned native compiler can materialize dictionaries locally, but a keyword
mapping created in the CALL_KW opcode path may arrive at ``VirtualMachine._call``
as a null raw dictionary pointer. Positional calls are unaffected. Transport
keyword names and values as lists instead, then build the mapping inside
``_call`` where it is consumed.
"""
from __future__ import annotations

from pathlib import Path


VM_PATH = Path("src/portapy/core/vm.py")


def _replace(source: str, old: str, new: str, *, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return source.replace(old, new, 1)


def main() -> int:
    source = VM_PATH.read_text(encoding="utf-8")
    source = _replace(
        source,
        '''    def _call(self, target: object, args: list[object], kwargs: dict[str, object] | None = None) -> object:
        kwargs = kwargs or {}
''',
        '''    def _call(
        self,
        target: object,
        args: list[object],
        kwargs: dict[str, object] | None = None,
        keyword_names: list[object] | None = None,
        keyword_values: list[object] | None = None,
    ) -> object:
        kwargs = kwargs or {}
        if keyword_names is not None and keyword_values is not None:
            keyword_index = 0
            while keyword_index < len(keyword_names):
                keyword_name = keyword_names[keyword_index]
                keyword_value = keyword_values[keyword_index]
                if keyword_name is None:
                    if not isinstance(keyword_value, dict):
                        _raise_typed("TypeError: ** argument must be a mapping")
                    for mapping_name, mapping_value in keyword_value.items():
                        kwargs[mapping_name] = mapping_value
                else:
                    kwargs[keyword_name] = keyword_value
                keyword_index += 1
''',
        label="native keyword receiver",
    )
    source = _replace(
        source,
        '''                    kwargs: dict[str, object] = {}
                    for name, value in zip(names, values):
                        if name is None:
                            if not isinstance(value, dict): _raise_typed("TypeError: ** argument must be a mapping")
                            kwargs.update(value)
                        else:
                            kwargs[name] = value
                    if getattr(target, "__pyinbin_super__", False) and not positional and not kwargs:
                        instance = frame.locals.get("self")
                        cls = self._lexical_super_class(frame, instance)
                        frame.stack.append(SuperProxy(self, cls, instance))
                    else:
                        frame.stack.append(self._call(target, positional, kwargs))
''',
        '''                    keyword_names: list[object] = []
                    has_effective_keywords = False
                    keyword_index = 0
                    while keyword_index < len(names):
                        name = names[keyword_index]
                        value = values[keyword_index]
                        keyword_names.append(name)
                        if name is None:
                            if not isinstance(value, dict):
                                _raise_typed("TypeError: ** argument must be a mapping")
                            if len(value) > 0:
                                has_effective_keywords = True
                        else:
                            has_effective_keywords = True
                        keyword_index += 1
                    if (
                        getattr(target, "__pyinbin_super__", False)
                        and not positional
                        and not has_effective_keywords
                    ):
                        instance = frame.locals.get("self")
                        cls = self._lexical_super_class(frame, instance)
                        frame.stack.append(SuperProxy(self, cls, instance))
                    else:
                        frame.stack.append(
                            self._call(target, positional, None, keyword_names, values)
                        )
''',
        label="native keyword sender",
    )
    VM_PATH.write_text(source, encoding="utf-8")
    verified = VM_PATH.read_text(encoding="utf-8")
    required = (
        "keyword_names: list[object] | None = None",
        "keyword_values: list[object] | None = None",
        "has_effective_keywords = False",
        "if len(value) > 0:",
        "and not has_effective_keywords",
        "self._call(target, positional, None, keyword_names, values)",
    )
    missing = [marker for marker in required if marker not in verified]
    if missing:
        raise RuntimeError(f"native keyword transport validation failed: {missing}")
    print("NORMALIZED NATIVE KEYWORD TRANSPORT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
