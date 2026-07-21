using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.ExceptionServices;
using System.Runtime.InteropServices;

namespace PortaPy;

public enum Status : int
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

public sealed class PortaPyException : Exception
{
    public Status Status { get; }

    public PortaPyException(Status status)
        : base($"PortaPy failed with status {status} ({(int)status}).")
    {
        Status = status;
    }
}

public sealed class Environment : IDisposable
{
    private const string LibraryName = "portapy";

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate Status NativeCallback(
        IntPtr context,
        ulong runtime,
        IntPtr arguments,
        nuint argumentCount,
        out ulong result
    );

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern Status portapy_environment_create(out IntPtr environment);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern Status portapy_environment_destroy(IntPtr environment);

    [DllImport(
        LibraryName,
        CallingConvention = CallingConvention.Cdecl,
        CharSet = CharSet.Unicode
    )]
    private static extern Status portapy_environment_add_callback_utf16(
        IntPtr environment,
        [MarshalAs(UnmanagedType.LPWStr)] string name,
        nuint nameLength,
        NativeCallback callback,
        IntPtr context
    );

    [DllImport(
        LibraryName,
        CallingConvention = CallingConvention.Cdecl,
        CharSet = CharSet.Unicode
    )]
    private static extern Status portapy_environment_execute_utf16(
        IntPtr environment,
        [MarshalAs(UnmanagedType.LPWStr)] string source,
        nuint sourceLength
    );

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern Status portapy_value_from_none(
        ulong runtime,
        out ulong value
    );

    private readonly List<NativeCallback> callbackRoots = new();
    private readonly object callbackLock = new();
    private IntPtr handle;
    private ExceptionDispatchInfo? pendingManagedException;
    private bool disposed;

    public Environment()
    {
        ThrowIfError(portapy_environment_create(out handle));
        if (handle == IntPtr.Zero)
        {
            throw new PortaPyException(Status.RuntimeError);
        }
    }

    ~Environment()
    {
        Dispose(false);
    }

    public void Add(Action callback)
    {
        ArgumentNullException.ThrowIfNull(callback);
        Add(callback.Method.Name, callback);
    }

    public void Add(string name, Action callback)
    {
        ObjectDisposedException.ThrowIf(disposed, this);
        ArgumentException.ThrowIfNullOrWhiteSpace(name);
        ArgumentNullException.ThrowIfNull(callback);

        NativeCallback nativeCallback = (
            IntPtr context,
            ulong runtime,
            IntPtr arguments,
            nuint argumentCount,
            out ulong result
        ) =>
        {
            result = 0;
            if (argumentCount != 0)
            {
                return Status.InvalidArgument;
            }

            try
            {
                callback();
                return portapy_value_from_none(runtime, out result);
            }
            catch (Exception error)
            {
                lock (callbackLock)
                {
                    pendingManagedException = ExceptionDispatchInfo.Capture(error);
                }
                return Status.RuntimeError;
            }
        };

        ThrowIfError(
            portapy_environment_add_callback_utf16(
                handle,
                name,
                (nuint)name.Length,
                nativeCallback,
                IntPtr.Zero
            )
        );

        // Native code stores the function pointer, not the managed delegate.
        // Root it for at least as long as the environment can call it.
        callbackRoots.Add(nativeCallback);
    }

    public void Execute(string source)
    {
        ObjectDisposedException.ThrowIf(disposed, this);
        ArgumentNullException.ThrowIfNull(source);

        Status status = portapy_environment_execute_utf16(
            handle,
            source,
            (nuint)source.Length
        );

        ExceptionDispatchInfo? callbackError = null;
        lock (callbackLock)
        {
            if (pendingManagedException is not null)
            {
                callbackError = pendingManagedException;
                pendingManagedException = null;
            }
        }
        callbackError?.Throw();
        ThrowIfError(status);
    }

    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }

    private void Dispose(bool disposing)
    {
        if (disposed)
        {
            return;
        }
        disposed = true;

        IntPtr current = handle;
        handle = IntPtr.Zero;
        if (current != IntPtr.Zero)
        {
            Status status = portapy_environment_destroy(current);
            if (disposing)
            {
                ThrowIfError(status);
            }
        }

        callbackRoots.Clear();
    }

    private static void ThrowIfError(Status status)
    {
        if (status != Status.Ok)
        {
            throw new PortaPyException(status);
        }
    }
}
