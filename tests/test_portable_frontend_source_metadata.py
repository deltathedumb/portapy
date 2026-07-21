from __future__ import annotations

import pytest

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import Frame, VirtualMachine


class TracingVM(VirtualMachine):
    def __init__(self) -> None:
        super().__init__()
        self.frames: list[tuple[str, int, int, str, str]] = []

    def _run_frame(self, frame: Frame) -> object:
        try:
            return super()._run_frame(frame)
        except BaseException:
            offset = max(frame.ip - 1, 0)
            lines = getattr(frame.code, "instruction_lines", [])
            columns = getattr(frame.code, "instruction_columns", [])
            line = lines[offset] if offset < len(lines) else getattr(frame.code, "first_line", 1)
            column = columns[offset] if offset < len(columns) else 1
            source_lines = getattr(frame.code, "source_lines", [])
            source = source_lines[line - 1].strip() if 0 < line <= len(source_lines) else ""
            self.frames.append((
                getattr(frame.code, "filename", "<portapy>"),
                line,
                column,
                frame.code.name,
                source,
            ))
            raise


def test_portable_code_objects_keep_source_metadata_across_frames() -> None:
    source = (
        "def inner():\n"
        "    return missing\n"
        "def outer():\n"
        "    return inner()\n"
        "outer()\n"
    )
    machine = TracingVM()
    with pytest.raises(NameError):
        machine.run(compile_portable_source(source, "traceback_test.py"), {})

    frames = list(reversed(machine.frames))
    assert [frame[3] for frame in frames] == ["traceback_test.py", "outer", "inner"]
    assert all(frame[0] == "traceback_test.py" for frame in frames)
    assert all(frame[1] > 0 and frame[2] > 0 for frame in frames)
    assert frames[-1][4] == "return missing"
