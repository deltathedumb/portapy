from __future__ import annotations

from pathlib import Path
import sys

from portapy import ExecutionError, NativeTracebackFrame, import_binary


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_traceback_adapter_probe.py <library>")

    module = import_binary(Path(sys.argv[1]))
    with module.new() as environment:
        try:
            environment.execute(
                "def inner():\n"
                "    return missing\n"
                "def outer():\n"
                "    return inner()\n"
                "result = outer()\n"
            )
        except ExecutionError as error:
            assert error.error is not None
            assert "Traceback (most recent call last):" in error.error.traceback_text
            assert "in outer" in error.error.traceback_text
            assert "return missing" in error.error.traceback_text
        else:
            raise AssertionError("native execution unexpectedly succeeded")

        frames = environment.traceback_frames
        assert all(isinstance(frame, NativeTracebackFrame) for frame in frames)
        assert [frame.function for frame in frames] == ["<module>", "outer", "inner"]
        assert frames[-1].source_line == "return missing"

        environment.execute("answer = 42\n")
        assert environment.traceback_frames == ()

    print("native-traceback-adapter: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
