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


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_environment_adapter_probe.py <library>")

    module = import_binary(Path(sys.argv[1]))
    with module.new() as environment:
        game = Game()
        environment.add_modules(math)
        environment.expose(
            {
                "game": game,
                "add": add,
                "tuple_roundtrip": tuple_roundtrip,
            }
        )
        environment.set("input_value", 41.9)
        environment.set("input_tuple", (18, (1, 2), "é"))
        environment.execute(
            "http_provider = game.provider.HttpProvider\n"
            "floor_value = math.floor(input_value)\n"
            "answer = floor_value + 1\n"
            "nested = add(20, add(1, 21))\n"
            "tuple_first = input_tuple[0]\n"
            "tuple_size = len(input_tuple)\n"
            "tuple_result = tuple_roundtrip(input_tuple)\n"
        )

        snapshot = environment.snapshot()
        assert snapshot.var["http_provider"] is game.provider.HttpProvider
        assert snapshot.var["input_value"] == 41.9
        assert snapshot.var["floor_value"] == 41
        assert snapshot.var["answer"] == 42
        assert snapshot.var["nested"] == 42
        assert snapshot.var["math"] is math
        assert snapshot.var["game"] is game
        assert snapshot.var["add"] is add
        assert snapshot.var["tuple_roundtrip"] is tuple_roundtrip
        assert snapshot.var["input_tuple"] == (18, (1, 2), "é")
        assert snapshot.var["tuple_first"] == 18
        assert snapshot.var["tuple_size"] == 3
        assert snapshot.var["tuple_result"] == ("é", (1, 2), 42)

        environment.execute(
            "answer = 7\n"
            "input_tuple = (99,)\n"
            "extra = 99\n"
        )
        assert environment.get("answer") == 7
        assert environment.get("input_tuple") == (99,)
        assert environment.get("extra") == 99
        snapshot.restore()
        assert environment.get("answer") == 42
        assert environment.get("input_tuple") == (18, (1, 2), "é")
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
