from portapy import Runtime, Status, ValueKind


def test_exec_eval_and_call() -> None:
    runtime = Runtime()
    assert runtime.exec_utf8("def add(a, b):\n    return a + b\nanswer = 40 + 2\n") == Status.OK
    status, answer = runtime.get_global("answer")
    assert status == Status.OK
    assert runtime.value_kind(answer) == (Status.OK, ValueKind.INT)
    assert runtime.as_int(answer) == (Status.OK, 42)

    status, fn = runtime.get_global("add")
    assert status == Status.OK
    _, a = runtime.box_int(20)
    _, b = runtime.box_int(22)
    status, result = runtime.call(fn, [a, b])
    assert status == Status.OK
    assert runtime.as_int(result) == (Status.OK, 42)


def test_structured_errors_and_lifetime() -> None:
    runtime = Runtime()
    assert runtime.exec_utf8("def broken(:\n") == Status.COMPILE_ERROR
    assert runtime.last_error() is not None
    assert runtime.exec_utf8("1 / 0\n") == Status.RUNTIME_ERROR
    assert runtime.last_error() is not None
    assert runtime.close() == Status.OK
    assert runtime.exec_utf8("x = 1\n") == Status.CLOSED
