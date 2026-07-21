using System.Runtime.InteropServices;
using System.Text;

internal enum PortaPyStatus : int
{
    Ok = 0,
    InvalidArgument = 1,
    CompileError = 2,
    RuntimeError = 3,
    TypeError = 4,
    NotFound = 5,
    Closed = 6,
    InvalidHandle = 7,
    Interrupted = 8,
    AbiMismatch = 9,
}

internal static class PortaPyNative
{
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    internal delegate PortaPyStatus DirectCallback(
        IntPtr context,
        ulong environment,
        IntPtr arguments,
        nuint argumentCount,
        out ulong result);

    [DllImport("portapy.dll", CallingConvention = CallingConvention.Cdecl,
        EntryPoint = "portapy_new")]
    internal static extern PortaPyStatus New(out ulong environment);

    [DllImport("portapy.dll", CallingConvention = CallingConvention.Cdecl,
        EntryPoint = "portapy_add_callable_utf8")]
    internal static extern PortaPyStatus AddCallable(
        ulong environment,
        byte[] name,
        nuint nameSize,
        DirectCallback callback,
        IntPtr context,
        uint flags);

    [DllImport("portapy.dll", CallingConvention = CallingConvention.Cdecl,
        EntryPoint = "portapy_value_from_none")]
    internal static extern PortaPyStatus None(
        ulong environment,
        out ulong value);

    [DllImport("portapy.dll", CallingConvention = CallingConvention.Cdecl,
        EntryPoint = "portapy_execute")]
    internal static extern PortaPyStatus Execute(
        ulong environment,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string source);

    [DllImport("portapy.dll", CallingConvention = CallingConvention.Cdecl,
        EntryPoint = "portapy_destroy")]
    internal static extern PortaPyStatus Destroy(ulong environment);
}

internal static class Program
{
    private static readonly PortaPyNative.DirectCallback HelloWorld = Hello;

    private static PortaPyStatus Hello(
        IntPtr context,
        ulong environment,
        IntPtr arguments,
        nuint argumentCount,
        out ulong result)
    {
        if (argumentCount != 0)
        {
            result = 0;
            return PortaPyStatus.InvalidArgument;
        }

        Console.WriteLine("Hello, world!");
        return PortaPyNative.None(environment, out result);
    }

    private static void Check(PortaPyStatus status, string operation)
    {
        if (status != PortaPyStatus.Ok)
        {
            throw new InvalidOperationException(
                $"PortaPy {operation} failed with status {(int)status}");
        }
    }

    private static void Main()
    {
        Check(PortaPyNative.New(out ulong environment), "new");
        try
        {
            byte[] name = Encoding.UTF8.GetBytes("helloWorld");
            Check(
                PortaPyNative.AddCallable(
                    environment,
                    name,
                    (nuint)name.Length,
                    HelloWorld,
                    IntPtr.Zero,
                    0),
                "add callable");
            Check(
                PortaPyNative.Execute(environment, "helloWorld()"),
                "execute");
        }
        finally
        {
            Check(PortaPyNative.Destroy(environment), "destroy");
        }
    }
}
