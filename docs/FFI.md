# Universal FFI

PortaPy is embedded through one stable C ABI. Any language that can call C
functions can use the same `portapy.dll`, `libportapy.so`, or
`libportapy.dylib` without a language-specific runtime inside PortaPy.

PortaPy does **not** provide `import_module`. The host language loads or imports
its own modules and then adds selected objects to an environment.

## Two public layers

The friendly environment layer is made of real exported symbols:

- `portapy_new()` / `portapy_new_with_config()`
- `portapy_add()`
- `portapy_add_all()`
- `portapy_add_value_utf8()`
- `portapy_add_callable_utf8()`
- `portapy_execute()`
- `portapy_evaluate()`
- `portapy_destroy()`

`portapy_environment` is an alias of the opaque `portapy_runtime` handle. A host
can therefore use the helpers first and then directly call any fine-grained
API without converting or unwrapping the environment.

The fine-grained layer remains public and includes:

- runtime creation and destruction
- UTF-8 execution and evaluation with explicit lengths and filenames
- global lookup, replacement, enumeration, and deletion
- scalar, string, bytes, tuple, dictionary, list, callable, and object values
- retain/release ownership
- host object attributes and raw callback dispatch
- structured error status, type, message, line, and column

## `add` and `add_all`

`portapy_add()` accepts one `portapy_binding`. A binding is either an existing
PortaPy value or a direct host callback.

`portapy_add_all()` accepts an array of bindings. This is the language-neutral
form of adding all public objects from a module. Each host language enumerates
its own module/object representation and supplies the resulting bindings;
PortaPy intentionally does not attempt to interpret every language's reflection
or module system.

Bindings are borrowed for the duration of the call. Values are retained by the
environment when successfully added. Callback arguments are borrowed, while a
callback returns one owned `portapy_value` through `out_result`.

`PORTAPY_BINDING_REPLACE` permits replacement of an existing global. Without
that flag, a collision fails.

## C example

```c
#include "portapy.h"
#include <stdio.h>
#include <string.h>

static portapy_status PORTAPY_CALL hello_world(
    void *context,
    portapy_environment environment,
    const portapy_value *arguments,
    size_t argument_count,
    portapy_value *out_result
) {
    (void)context;
    (void)arguments;
    if (argument_count != 0 || out_result == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    puts("Hello, world!");
    return portapy_value_from_none(environment, out_result);
}

int main(void) {
    portapy_environment environment = PORTAPY_NULL_ENVIRONMENT;
    if (portapy_new(&environment) != PORTAPY_OK) return 1;

    portapy_binding binding = {0};
    binding.struct_size = sizeof(binding);
    binding.kind = PORTAPY_BINDING_CALLABLE;
    binding.name = (const uint8_t *)"helloWorld";
    binding.name_size = strlen("helloWorld");
    binding.callable = hello_world;

    if (portapy_add(environment, &binding) != PORTAPY_OK) return 2;
    if (portapy_execute(environment, "helloWorld()") != PORTAPY_OK) return 3;
    return portapy_destroy(environment) == PORTAPY_OK ? 0 : 4;
}
```

## C# example

P/Invoke imports functions, not native classes. The opaque environment handle
is represented by `ulong`; a managed class may wrap it, but no wrapper library
is required.

```csharp
using System;
using System.Runtime.InteropServices;
using System.Text;

internal static class PortaPy
{
    internal enum Status : int
    {
        Ok = 0
    }

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    internal delegate Status DirectCallback(
        IntPtr context,
        ulong environment,
        IntPtr arguments,
        nuint argumentCount,
        out ulong result);

    [DllImport("portapy.dll", CallingConvention = CallingConvention.Cdecl,
        EntryPoint = "portapy_new")]
    internal static extern Status New(out ulong environment);

    [DllImport("portapy.dll", CallingConvention = CallingConvention.Cdecl,
        EntryPoint = "portapy_add_callable_utf8")]
    internal static extern Status AddCallable(
        ulong environment,
        byte[] name,
        nuint nameSize,
        DirectCallback callback,
        IntPtr context,
        uint flags);

    [DllImport("portapy.dll", CallingConvention = CallingConvention.Cdecl,
        EntryPoint = "portapy_value_from_none")]
    internal static extern Status None(ulong environment, out ulong value);

    [DllImport("portapy.dll", CallingConvention = CallingConvention.Cdecl,
        EntryPoint = "portapy_execute")]
    internal static extern Status Execute(
        ulong environment,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string source);

    [DllImport("portapy.dll", CallingConvention = CallingConvention.Cdecl,
        EntryPoint = "portapy_destroy")]
    internal static extern Status Destroy(ulong environment);
}

internal static class Program
{
    // Keep the delegate rooted while native code can call it.
    private static readonly PortaPy.DirectCallback HelloWorld = Hello;

    private static PortaPy.Status Hello(
        IntPtr context,
        ulong environment,
        IntPtr arguments,
        nuint argumentCount,
        out ulong result)
    {
        Console.WriteLine("Hello, world!");
        return PortaPy.None(environment, out result);
    }

    private static void Main()
    {
        PortaPy.New(out ulong environment);
        byte[] name = Encoding.UTF8.GetBytes("helloWorld");
        PortaPy.AddCallable(environment, name, (nuint)name.Length,
            HelloWorld, IntPtr.Zero, 0);
        PortaPy.Execute(environment, "helloWorld()");
        PortaPy.Destroy(environment);
    }
}
```

The same mapping works in Rust with `extern "C"`, Go with cgo, Java with its
foreign-function interface, Swift with a bridging header, Zig with `@cImport`,
and scripting languages through their normal FFI facilities.

## Mixing helper and fine-grained callbacks

Direct callbacks registered through `portapy_add()` or
`portapy_add_callable_utf8()` use an internal callable-ID range. Raw callables
created with `portapy_value_from_host_callable()` continue to use the handler
installed by `portapy_host_set_call_handler()`. Both callback styles can coexist
inside the same environment.

## Text and ABI rules

- exported functions use the C calling convention declared by `PORTAPY_CALL`
- text is UTF-8
- explicit-length functions do not require a terminating zero byte
- `portapy_execute()` and `portapy_evaluate()` accept zero-terminated UTF-8
- callers must check every returned `portapy_status`
- owned values must eventually be released with `portapy_value_release()`
- helper-created environments should be closed with `portapy_destroy()`
