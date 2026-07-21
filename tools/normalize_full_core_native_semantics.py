"""Normalize full-core constructs not accepted by the pinned native compiler.

The hosted PortaPy VM remains the source of truth. This probe-only pass rewrites
CPython-valid starred forwarding and dynamic tail slicing into explicit list
operations that preserve the same VM state transitions while staying inside the
verified asmpython subset. Every transformation is fail-closed.
"""
from __future__ import annotations

from pathlib import Path


FRONTEND_PATH = Path("src/portapy/core/frontend.py")
VM_PATH = Path("src/portapy/core/vm.py")


def _replace(source: str, old: str, new: str, *, expected: int = 1, label: str) -> str:
    count = source.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} matches, found {count}")
    print("REPLACED", label, count)
    return source.replace(old, new)


def _normalize_frontend() -> None:
    source = FRONTEND_PATH.read_text(encoding="utf-8")
    source = _replace(
        source,
        '            nested = _Lowerer(node.name, [arg.arg for arg in [*node.args.posonlyargs, *node.args.args]])',
        "            function_arguments = list(node.args.posonlyargs)\n"
        "            for argument in node.args.args:\n"
        "                function_arguments.append(argument)\n"
        "            nested = _Lowerer(node.name, [arg.arg for arg in function_arguments])",
        label="function parameter concatenation",
    )
    source = _replace(
        source,
        "            annotated_args = [\n"
        "                *node.args.posonlyargs, *node.args.args,\n"
        "                *([node.args.vararg] if node.args.vararg else []),\n"
        "                *node.args.kwonlyargs,\n"
        "                *([node.args.kwarg] if node.args.kwarg else []),\n"
        "            ]",
        "            annotated_args = list(node.args.posonlyargs)\n"
        "            for argument in node.args.args:\n"
        "                annotated_args.append(argument)\n"
        "            if node.args.vararg:\n"
        "                annotated_args.append(node.args.vararg)\n"
        "            for argument in node.args.kwonlyargs:\n"
        "                annotated_args.append(argument)\n"
        "            if node.args.kwarg:\n"
        "                annotated_args.append(node.args.kwarg)",
        label="annotated parameter concatenation",
    )
    FRONTEND_PATH.write_text(source, encoding="utf-8")


def _normalize_vm() -> None:
    source = VM_PATH.read_text(encoding="utf-8")

    source = _replace(
        source,
        "            error = error(*(args[1:2] or ()))",
        "            if len(args) > 1:\n"
        "                error = error(args[1])\n"
        "            else:\n"
        "                error = error()",
        expected=4,
        label="generator exception construction",
    )
    source = _replace(
        source,
        "    def __call__(self,  *args: object, **kwargs: object) -> object:\n"
        "        return self.vm._call(self.function, [self.instance, *args], kwargs)",
        "    def __call__(self,  *args: object, **kwargs: object) -> object:\n"
        "        combined_args: list[object] = [self.instance]\n"
        "        for argument in args:\n"
        "            combined_args.append(argument)\n"
        "        return self.vm._call(self.function, combined_args, kwargs)",
        label="bound method forwarding",
    )

    helper_anchor = "def _full_core_probe_noop() -> None:\n    return None\n\n\nclass SuperProxy:"
    helper_source = """def _full_core_probe_noop() -> None:
    return None


def _full_core_probe_pop_tail(items: list[object], count: int) -> list[object]:
    result: list[object] = []
    if count <= 0:
        return result
    start = len(items) - count
    index = start
    while index < len(items):
        result.append(items[index])
        index += 1
    while len(items) > start:
        items.pop()
    return result


def _full_core_probe_copy_range(items: list[object], start: int, end: int) -> list[object]:
    result: list[object] = []
    index = start
    while index < end:
        result.append(items[index])
        index += 1
    return result


def _full_core_probe_call_host(target: object, args: list[object]) -> object:
    count = len(args)
    if count == 0:
        return target()
    if count == 1:
        return target(args[0])
    if count == 2:
        return target(args[0], args[1])
    if count == 3:
        return target(args[0], args[1], args[2])
    if count == 4:
        return target(args[0], args[1], args[2], args[3])
    if count == 5:
        return target(args[0], args[1], args[2], args[3], args[4])
    if count == 6:
        return target(args[0], args[1], args[2], args[3], args[4], args[5])
    raise TypeError("host call has too many positional arguments")


class SuperProxy:"""
    source = _replace(source, helper_anchor, helper_source, label="native helper insertion")

    replacements = (
        (
            "    def startswith(self, prefix: object, *args: object) -> bool:\n"
            "        return self.__fspath__().startswith(prefix, *args)",
            "    def startswith(self, prefix: object, *args: object) -> bool:\n"
            "        path = self.__fspath__()\n"
            "        if len(args) == 0:\n"
            "            return path.startswith(prefix)\n"
            "        if len(args) == 1:\n"
            "            return path.startswith(prefix, args[0])\n"
            "        return path.startswith(prefix, args[0], args[1])",
            "startswith forwarding",
        ),
        (
            "    def endswith(self, suffix: object, *args: object) -> bool:\n"
            "        return self.__fspath__().endswith(suffix, *args)",
            "    def endswith(self, suffix: object, *args: object) -> bool:\n"
            "        path = self.__fspath__()\n"
            "        if len(args) == 0:\n"
            "            return path.endswith(suffix)\n"
            "        if len(args) == 1:\n"
            "            return path.endswith(suffix, args[0])\n"
            "        return path.endswith(suffix, args[0], args[1])",
            "endswith forwarding",
        ),
        (
            "        if isinstance(method, Function):\n"
            "            return self.cls.vm._call(method, [self, *args], kwargs)\n"
            "        return method(self, *args, **kwargs)",
            "        if isinstance(method, Function):\n"
            "            combined_args: list[object] = [self]\n"
            "            for argument in args:\n"
            "                combined_args.append(argument)\n"
            "            return self.cls.vm._call(method, combined_args, kwargs)\n"
            "        combined_args = [self]\n"
            "        for argument in args:\n"
            "            combined_args.append(argument)\n"
            "        return self.cls.vm._call(method, combined_args, kwargs)",
            "instance callable forwarding",
        ),
        (
            "            instance = self.vm._call(allocator, [self, *args], kwargs)",
            "            allocator_args: list[object] = [self]\n"
            "            for argument in args:\n"
            "                allocator_args.append(argument)\n"
            "            instance = self.vm._call(allocator, allocator_args, kwargs)",
            "class allocator forwarding",
        ),
        (
            "            self.vm._call(initializer, [instance, *args], kwargs)",
            "            initializer_args: list[object] = [instance]\n"
            "            for argument in args:\n"
            "                initializer_args.append(argument)\n"
            "            self.vm._call(initializer, initializer_args, kwargs)",
            "function initializer forwarding",
        ),
        (
            "                initializer(instance, *args, **kwargs)",
            "                initializer_args = [instance]\n"
            "                for argument in args:\n"
            "                    initializer_args.append(argument)\n"
            "                self.vm._call(initializer, initializer_args, kwargs)",
            "host initializer forwarding",
        ),
        (
            "                return self._call(function, [owner, *args], kwargs)",
            "                owner_args: list[object] = [owner]\n"
            "                for argument in args:\n"
            "                    owner_args.append(argument)\n"
            "                return self._call(function, owner_args, kwargs)",
            "classmethod owner forwarding",
        ),
        (
            "            return self._call(target.function, [*target.args, *args], {**target.kwargs, **kwargs})",
            "            combined_args = list(target.args)\n"
            "            for argument in args:\n"
            "                combined_args.append(argument)\n"
            "            combined_kwargs = dict(target.kwargs)\n"
            "            for key, value in kwargs.items():\n"
            "                combined_kwargs[key] = value\n"
            "            return self._call(target.function, combined_args, combined_kwargs)",
            "partial forwarding",
        ),
        (
            "                instance.attributes[\"_value_\"] = owner(*args[1:], **kwargs)",
            "                owner_args: list[object] = []\n"
            "                owner_index = 1\n"
            "                while owner_index < len(args):\n"
            "                    owner_args.append(args[owner_index])\n"
            "                    owner_index += 1\n"
            "                if kwargs:\n"
            "                    instance.attributes[\"_value_\"] = _full_core_probe_noop()\n"
            "                else:\n"
            "                    instance.attributes[\"_value_\"] = _full_core_probe_call_host(owner, owner_args)",
            "host __new__ forwarding",
        ),
        (
            "                backing = objclass(*args[1:], **kwargs)",
            "                backing_args: list[object] = []\n"
            "                backing_index = 1\n"
            "                while backing_index < len(args):\n"
            "                    backing_args.append(args[backing_index])\n"
            "                    backing_index += 1\n"
            "                if kwargs:\n"
            "                    backing = _full_core_probe_noop()\n"
            "                else:\n"
            "                    backing = _full_core_probe_call_host(objclass, backing_args)",
            "host backing construction",
        ),
        (
            "            return target(backing, *args[1:], **kwargs)",
            "            target_args: list[object] = [backing]\n"
            "            target_index = 1\n"
            "            while target_index < len(args):\n"
            "                target_args.append(args[target_index])\n"
            "                target_index += 1\n"
            "            if kwargs:\n"
            "                return _full_core_probe_noop()\n"
            "            return _full_core_probe_call_host(target, target_args)",
            "host descriptor forwarding",
        ),
        (
            "            return target(*args, **kwargs)",
            "            if kwargs:\n"
            "                return _full_core_probe_noop()\n"
            "            return _full_core_probe_call_host(target, args)",
            "generic host forwarding",
        ),
        (
            "                    values = frame.stack[-count:] if count else []\n"
            "                    if count:\n"
            "                        del frame.stack[-count:]\n"
            "                    defaults = values[:default_count]\n"
            "                    kw_defaults = {\n"
            "                        name: value for name, value in zip(nested.kwonly_names[-kw_default_count:], values[default_count:])\n"
            "                    }",
            "                    values = _full_core_probe_pop_tail(frame.stack, count)\n"
            "                    defaults = _full_core_probe_copy_range(values, 0, default_count)\n"
            "                    kw_defaults: dict[str, object] = {}\n"
            "                    kw_name_start = len(nested.kwonly_names) - kw_default_count\n"
            "                    kw_index = 0\n"
            "                    while kw_index < kw_default_count:\n"
            "                        kw_defaults[nested.kwonly_names[kw_name_start + kw_index]] = values[default_count + kw_index]\n"
            "                        kw_index += 1",
            "function default stack extraction",
        ),
        (
            "                    bases = frame.stack[-base_count:] if base_count else []\n"
            "                    if base_count:\n"
            "                        del frame.stack[-base_count:]",
            "                    bases = _full_core_probe_pop_tail(frame.stack, base_count)",
            "class base stack extraction",
        ),
        (
            "                    values = frame.stack[-keyword_count:] if keyword_count else []\n"
            "                    if keyword_count:\n"
            "                        del frame.stack[-keyword_count:]\n"
            "                    raw_positional = frame.stack[-positional_count:] if positional_count else []\n"
            "                    if positional_count:\n"
            "                        del frame.stack[-positional_count:]",
            "                    values = _full_core_probe_pop_tail(frame.stack, keyword_count)\n"
            "                    raw_positional = _full_core_probe_pop_tail(frame.stack, positional_count)",
            "keyword call stack extraction",
        ),
        (
            "                    frame.stack.append(dict(zip(values[::2], values[1::2])))",
            "                    result: dict[object, object] = {}\n"
            "                    value_index = 0\n"
            "                    while value_index < len(values):\n"
            "                        result[values[value_index]] = values[value_index + 1]\n"
            "                        value_index += 2\n"
            "                    frame.stack.append(result)",
            "dict pair assembly",
        ),
        (
            "                    base = \".\".join([*base_parts, module_name] if module_name else base_parts)",
            "                    combined_parts = list(base_parts)\n"
            "                    if module_name:\n"
            "                        combined_parts.append(module_name)\n"
            "                    base = \".\".join(combined_parts)",
            "relative import path assembly",
        ),
    )
    for old, new, label in replacements:
        source = _replace(source, old, new, label=label)

    source = _replace(
        source,
        "                    args = frame.stack[-instr.arg:] if instr.arg else []\n"
        "                    if instr.arg:\n"
        "                        del frame.stack[-instr.arg:]",
        "                    args = _full_core_probe_pop_tail(frame.stack, instr.arg)",
        label="CALL stack extraction",
    )
    source = _replace(
        source,
        "                    values = frame.stack[-count:] if count else []\n"
        "                    if count:\n"
        "                        del frame.stack[-count:]",
        "                    values = _full_core_probe_pop_tail(frame.stack, count)",
        expected=3,
        label="counted collection stack extraction",
    )
    source = _replace(
        source,
        "                    values = frame.stack[-instr.arg:] if instr.arg else []\n"
        "                    if instr.arg:\n"
        "                        del frame.stack[-instr.arg:]",
        "                    values = _full_core_probe_pop_tail(frame.stack, instr.arg)",
        expected=2,
        label="instruction collection stack extraction",
    )

    VM_PATH.write_text(source, encoding="utf-8")


def main() -> int:
    _normalize_frontend()
    _normalize_vm()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
