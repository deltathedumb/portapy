"""Indexed traceback-frame support for PortaPy's native Python facade."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass

from . import native_binary as _native
from .reference_api import ErrorInfo, Status


_installed = False


class _TracebackFrameInfo(ctypes.Structure):
    _fields_ = [
        ("struct_size", _native._SIZE),
        ("line", _native._SIZE),
        ("column", _native._SIZE),
        ("filename_size", _native._SIZE),
        ("function_size", _native._SIZE),
        ("source_size", _native._SIZE),
    ]


@dataclass(frozen=True)
class NativeTracebackFrame:
    """One frame from the most recent failed native evaluation or execution."""

    filename: str
    function: str
    line: int
    column: int
    source_line: str


def _copy_frame_text(
    environment: _native.NativeEnvironment,
    function: object,
    index: int,
) -> str:
    required = _native._SIZE(0)
    status = int(
        function(
            environment._runtime,
            index,
            None,
            0,
            ctypes.byref(required),
        )
    )
    if required.value == 0:
        environment._check(status, "inspect traceback text")
        return ""
    if status != int(Status.INVALID_ARGUMENT):
        environment._check(status, "inspect traceback text size")
    buffer = (_native._BYTE * required.value)()
    environment._check(
        int(
            function(
                environment._runtime,
                index,
                buffer,
                required.value,
                ctypes.byref(required),
            )
        ),
        "copy traceback text",
    )
    return bytes(buffer).decode("utf-8", errors="replace")


def _read_frames(
    environment: _native.NativeEnvironment,
) -> tuple[NativeTracebackFrame, ...]:
    count = _native._SIZE(0)
    environment._check(
        int(
            environment._api.portapy_error_traceback_count(
                environment._runtime,
                ctypes.byref(count),
            )
        ),
        "inspect traceback frame count",
    )
    frames: list[NativeTracebackFrame] = []
    for index in range(count.value):
        info = _TracebackFrameInfo()
        info.struct_size = ctypes.sizeof(_TracebackFrameInfo)
        environment._check(
            int(
                environment._api.portapy_error_traceback_get_frame(
                    environment._runtime,
                    index,
                    ctypes.byref(info),
                )
            ),
            "inspect traceback frame",
        )
        frames.append(
            NativeTracebackFrame(
                filename=_copy_frame_text(
                    environment,
                    environment._api.portapy_error_traceback_copy_filename_utf8,
                    index,
                ),
                function=_copy_frame_text(
                    environment,
                    environment._api.portapy_error_traceback_copy_function_utf8,
                    index,
                ),
                line=int(info.line),
                column=int(info.column),
                source_line=_copy_frame_text(
                    environment,
                    environment._api.portapy_error_traceback_copy_source_utf8,
                    index,
                ),
            )
        )
    return tuple(frames)


def _format_frames(frames: tuple[NativeTracebackFrame, ...]) -> str:
    if not frames:
        return ""
    lines = ["Traceback (most recent call last):"]
    for frame in frames:
        lines.append(
            f'  File "{frame.filename}", line {frame.line}, in {frame.function}'
        )
        if frame.source_line:
            lines.append(f"    {frame.source_line}")
    return "\n".join(lines) + "\n"


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    original_bind = _native._NativeLibrary._bind
    original_last_error = _native.NativeEnvironment._last_error

    def bind(library: _native._NativeLibrary) -> None:
        original_bind(library)
        library._function(
            "portapy_error_traceback_count",
            [_native._U64, ctypes.POINTER(_native._SIZE)],
        )
        library._function(
            "portapy_error_traceback_get_frame",
            [_native._U64, _native._SIZE, ctypes.POINTER(_TracebackFrameInfo)],
        )
        for name in (
            "portapy_error_traceback_copy_filename_utf8",
            "portapy_error_traceback_copy_function_utf8",
            "portapy_error_traceback_copy_source_utf8",
        ):
            library._function(
                name,
                [
                    _native._U64,
                    _native._SIZE,
                    ctypes.POINTER(_native._BYTE),
                    _native._SIZE,
                    ctypes.POINTER(_native._SIZE),
                ],
            )

    def traceback_frames(
        environment: _native.NativeEnvironment,
    ) -> tuple[NativeTracebackFrame, ...]:
        environment._ensure_open()
        return _read_frames(environment)

    def last_error(environment: _native.NativeEnvironment) -> ErrorInfo | None:
        error = original_last_error(environment)
        if error is None:
            return None
        try:
            traceback_text = _format_frames(_read_frames(environment))
        except BaseException:
            traceback_text = error.traceback_text
        return ErrorInfo(
            error.status,
            error.type_name,
            error.message,
            traceback_text or error.traceback_text,
        )

    _native._NativeLibrary._bind = bind
    _native.NativeEnvironment.traceback_frames = property(traceback_frames)
    _native.NativeEnvironment._last_error = last_error


install()


__all__ = ["NativeTracebackFrame", "install"]
