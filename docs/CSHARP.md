# Direct C# hosting

`portapy.dll` exposes a managed-host ABI directly. No custom C/C++ shim is
required. Include `bindings/csharp/PortaPy.cs` in the C# project and place
`portapy.dll` beside the built application.

```csharp
using PortaPy;

void helloWorld()
{
    Console.WriteLine("Hello, world!");
}

using var env = new PortaPy.Environment();
env.Add(helloWorld);
env.Execute("helloWorld()\n");
```

`Environment.Add(Action)` uses the managed method name as the Python global
name. An explicit name is also supported:

```csharp
env.Add("hello_world", helloWorld);
env.Execute("hello_world()\n");
```

The environment owns the native runtime and callback registry. The managed
wrapper keeps callback delegates alive until disposal and rethrows exceptions
raised by managed callbacks after native execution returns.

The underlying public exports are:

- `portapy_environment_create`
- `portapy_environment_destroy`
- `portapy_environment_get_runtime`
- `portapy_environment_add_callback_utf16`
- `portapy_environment_execute_utf16`
