"""Transport keyword arguments through compiler-safe native values.

The pinned native compiler cannot safely pass a freshly built dictionary from
``CALL_KW`` into ``VirtualMachine._call``. It also needs keyword keys to be
statically typed as strings before dictionary mutation. Transport names and
values as lists, encode ``**mapping`` with an impossible empty direct-keyword
sentinel, and construct a typed mapping inside ``_call`` where it is consumed.
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
        keyword_names: list[str] | None = None,
        keyword_values: list[object] | None = None,
    ) -> object:
        if keyword_names is not None and keyword_values is not None:
            transported_kwargs: dict[str, object] = {}
            keyword_index = 0
            while keyword_index < len(keyword_names):
                keyword_name: str = keyword_names[keyword_index]
                keyword_value = keyword_values[keyword_index]
                if keyword_name == "":
                    if not isinstance(keyword_value, dict):
                        _raise_typed("TypeError: ** argument must be a mapping")
                    for raw_mapping_name, mapping_value in keyword_value.items():
                        mapping_name: str = raw_mapping_name
                        transported_kwargs[mapping_name] = mapping_value
                else:
                    transported_kwargs[keyword_name] = keyword_value
                keyword_index += 1
            kwargs = transported_kwargs
        else:
            kwargs = kwargs or {}
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
        '''                    keyword_names: list[str] = []
                    has_effective_keywords = False
                    keyword_index = 0
                    while keyword_index < len(names):
                        name = names[keyword_index]
                        value = values[keyword_index]
                        if name is None:
                            if not isinstance(value, dict):
                                _raise_typed("TypeError: ** argument must be a mapping")
                            keyword_names.append("")
                            if len(value) > 0:
                                has_effective_keywords = True
                        else:
                            keyword_name: str = name
                            keyword_names.append(keyword_name)
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
        "keyword_names: list[str] | None = None",
        "transported_kwargs: dict[str, object] = {}",
        "keyword_name: str = keyword_names[keyword_index]",
        "mapping_name: str = raw_mapping_name",
        "kwargs = transported_kwargs",
        "keyword_names: list[str] = []",
        "has_effective_keywords = False",
        'keyword_names.append("")',
        "and not has_effective_keywords",
        "keyword_name: str = name",
        "self._call(target, positional, None, keyword_names, values)",
    )
    missing = [marker for marker in required if marker not in verified]
    if missing:
        raise RuntimeError(f"native keyword transport validation failed: {missing}")
    forbidden = (
        "keyword_names: list[object]",
    )
    remaining = [marker for marker in forbidden if marker in verified]
    if remaining:
        raise RuntimeError(f"unsafe native keyword transport remains: {remaining}")
    print("NORMALIZED TYPED NATIVE KEYWORD TRANSPORT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
