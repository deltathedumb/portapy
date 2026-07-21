from __future__ import annotations

import math
from pathlib import Path
import sys

from portapy import ExecutionError, import_binary


class Provider:
    def __init__(self) -> None:
        self.HttpProvider = type("HttpProvider", (), {})


class Game:
    def __init__(self) -> None:
        self.provider = Provider()


def add(left: int, right: int) -> int:
    return left + right


def tuple_roundtrip(value: tuple[object, ...]) -> tuple[object, ...]:
    assert value == (18, (1, 2), "é")
    return (value[-1], value[1], value[0] + 24)


def dict_roundtrip(value: dict[str, object]) -> dict[str, object]:
    assert value == {"left": 18, "right": 24, "nested": {"value": 42}}
    return {
        "total": int(value["left"]) + int(value["right"]),
        "nested": value["nested"],
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_environment_adapter_probe.py <library>")

    module = import_binary(Path(sys.argv[1]))
    with module.new() as environment:
        game = Game()
        environment.add(math)
        environment.add(add)
        environment.add(tuple_roundtrip)
        environment.add(dict_roundtrip)
        environment.add_all({"game": game})
        environment.set("input_value", 41.9)
        environment.set("input_tuple", (18, (1, 2), "é"))
        environment.set(
            "input_mapping",
            {"left": 18, "right": 24, "nested": {"value": 42}},
        )
        environment.set("values", [40, 2])
        environment.execute(
            "import math\n"
            "from math import floor as imported_floor\n"
            "unicode_text = 'π'\n"
            "http_provider = game.provider.HttpProvider\n"
            "floor_value = imported_floor(input_value)\n"
            "answer = floor_value + 1\n"
            "nested = add(20, add(1, 21))\n"
            "tuple_first = input_tuple[0]\n"
            "tuple_size = len(input_tuple)\n"
            "tuple_result = tuple_roundtrip(input_tuple)\n"
            "mapping_total = input_mapping[\"left\"] + input_mapping[\"right\"]\n"
            "mapping_size = len(input_mapping)\n"
            "mapping_result = dict_roundtrip(input_mapping)\n"
            "def total(items):\n"
            "    result = 0\n"
            "    for item in items:\n"
            "        result += item\n"
            "    return result\n"
            "def outer(base):\n"
            "    def inner(value):\n"
            "        return base + value\n"
            "    return inner\n"
            "class Box:\n"
            "    def __init__(self, value):\n"
            "        self.value = value\n"
            "    def get(self):\n"
            "        return self.value\n"
            "fn = outer(base=19)\n"
            "box = Box(value=fn(value=total(items=values) - 19))\n"
            "def fail():\n"
            "    return 1 // 0\n"
            "try:\n"
            "    fail()\n"
            "except Exception as exc:\n"
            "    traced = exc.__traceback__ is not None\n"
            "full_runtime_answer = box.get() if traced else -1\n"
        )

        snapshot = environment.snapshot()
        assert snapshot.var["http_provider"] is game.provider.HttpProvider
        assert snapshot.var["input_value"] == 41.9
        assert snapshot.var["floor_value"] == 41
        assert snapshot.var["answer"] == 42
        assert snapshot.var["nested"] == 42
        assert snapshot.var["math"] is math
        assert snapshot.var["imported_floor"] is math.floor
        assert snapshot.var["unicode_text"] == "π"
        assert snapshot.var["game"] is game
        assert snapshot.var["add"] is add
        assert snapshot.var["tuple_roundtrip"] is tuple_roundtrip
        assert snapshot.var["dict_roundtrip"] is dict_roundtrip
        assert snapshot.var["input_tuple"] == (18, (1, 2), "é")
        assert snapshot.var["tuple_first"] == 18
        assert snapshot.var["tuple_size"] == 3
        assert snapshot.var["tuple_result"] == ("é", (1, 2), 42)
        assert snapshot.var["input_mapping"] == {
            "left": 18,
            "right": 24,
            "nested": {"value": 42},
        }
        assert snapshot.var["mapping_total"] == 42
        assert snapshot.var["mapping_size"] == 3
        assert snapshot.var["mapping_result"] == {
            "total": 42,
            "nested": {"value": 42},
        }
        assert snapshot.var["values"] == [40, 2]
        assert snapshot.var["traced"] is True
        assert snapshot.var["full_runtime_answer"] == 42

        environment.execute(
            "answer = 7\n"
            "input_tuple = (99,)\n"
            "extra = 99\n"
        )
        environment.set("input_mapping", {"changed": 99})
        assert environment.get("answer") == 7
        assert environment.get("input_tuple") == (99,)
        assert environment.get("input_mapping") == {"changed": 99}
        assert environment.get("extra") == 99
        snapshot.restore()
        assert environment.get("answer") == 42
        assert environment.get("input_tuple") == (18, (1, 2), "é")
        assert environment.get("input_mapping") == {
            "left": 18,
            "right": 24,
            "nested": {"value": 42},
        }
        try:
            environment.get("extra")
        except ExecutionError:
            pass
        else:
            raise AssertionError("snapshot restore did not delete extra global")

        environment.remove("answer")
        environment.remove("answer", missing_ok=True)
        try:
            environment.get("answer")
        except ExecutionError:
            pass
        else:
            raise AssertionError("remove did not delete answer")

    print("native-environment-adapter: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
