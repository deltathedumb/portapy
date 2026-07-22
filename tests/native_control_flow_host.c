#define _GNU_SOURCE
#include "portapy.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#define LOAD_LIBRARY(path) ((void *)LoadLibraryA(path))
#define LOAD_SYMBOL(lib, name) ((void *)(uintptr_t)GetProcAddress((HMODULE)(lib), (name)))
#define ABI_CALL __cdecl

static LONG WINAPI portapy_control_crash_filter(EXCEPTION_POINTERS *exception) {
    DWORD code = 0;
    void *address = NULL;
    CONTEXT *context = NULL;
    if (exception != NULL) {
        context = exception->ContextRecord;
        if (exception->ExceptionRecord != NULL) {
            code = exception->ExceptionRecord->ExceptionCode;
            address = exception->ExceptionRecord->ExceptionAddress;
        }
    }
    HMODULE module = NULL;
    char module_name[MAX_PATH] = {0};
    unsigned long long offset = 0;
    if (address != NULL && GetModuleHandleExA(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (LPCSTR)address,
            &module
        )) {
        GetModuleFileNameA(module, module_name, (DWORD)sizeof(module_name));
        offset = (unsigned long long)((uintptr_t)address - (uintptr_t)module);
    }
    fprintf(
        stderr,
        "control-crash: code=0x%08lx address=%p module=%s offset=0x%llx\n",
        (unsigned long)code,
        address,
        module_name[0] == '\0' ? "<unknown>" : module_name,
        offset
    );
#if defined(_M_X64) || defined(__x86_64__)
    if (context != NULL) {
        fprintf(
            stderr,
            "control-crash-context: rip=0x%llx rsp=0x%llx rbp=0x%llx\n",
            (unsigned long long)context->Rip,
            (unsigned long long)context->Rsp,
            (unsigned long long)context->Rbp
        );
    }
#endif
    fflush(stderr);
    return EXCEPTION_EXECUTE_HANDLER;
}

#define INSTALL_CRASH_HANDLER() SetUnhandledExceptionFilter(portapy_control_crash_filter)
#else
#include <dlfcn.h>
#include <execinfo.h>
#include <signal.h>
#include <ucontext.h>
#define LOAD_LIBRARY(path) dlopen((path), RTLD_NOW | RTLD_LOCAL)
#define LOAD_SYMBOL(lib, name) dlsym((lib), (name))
#define ABI_CALL

static void portapy_control_signal_handler(
    int signal_number,
    siginfo_t *signal_info,
    void *context_pointer
) {
    uintptr_t instruction = 0;
#if defined(__x86_64__) && defined(REG_RIP)
    ucontext_t *context = (ucontext_t *)context_pointer;
    instruction = (uintptr_t)context->uc_mcontext.gregs[REG_RIP];
#else
    (void)context_pointer;
#endif
    Dl_info module_info = {0};
    const char *module_name = "<unknown>";
    uintptr_t offset = 0;
    if (instruction != 0 && dladdr((void *)instruction, &module_info) != 0) {
        if (module_info.dli_fname != NULL) module_name = module_info.dli_fname;
        if (module_info.dli_fbase != NULL) {
            offset = instruction - (uintptr_t)module_info.dli_fbase;
        }
    }
    fprintf(
        stderr,
        "control-crash: signal=%d fault=%p instruction=%p module=%s offset=0x%llx\n",
        signal_number,
        signal_info == NULL ? NULL : signal_info->si_addr,
        (void *)instruction,
        module_name,
        (unsigned long long)offset
    );
    void *frames[32];
    int frame_count = backtrace(frames, (int)(sizeof(frames) / sizeof(frames[0])));
    backtrace_symbols_fd(frames, frame_count, 2);
    fflush(stderr);
    _Exit(128 + signal_number);
}

static void install_control_crash_handler(void) {
    struct sigaction action;
    memset(&action, 0, sizeof(action));
    action.sa_sigaction = portapy_control_signal_handler;
    action.sa_flags = SA_SIGINFO | SA_RESETHAND;
    sigemptyset(&action.sa_mask);
    sigaction(SIGSEGV, &action, NULL);
    sigaction(SIGBUS, &action, NULL);
    sigaction(SIGABRT, &action, NULL);
}

#define INSTALL_CRASH_HANDLER() install_control_crash_handler()
#endif

#define TRACE_STEP(message) do { \
    fprintf(stderr, "control-step: %s\n", (message)); \
    fflush(stderr); \
} while (0)

typedef portapy_status (ABI_CALL *initialize_fn)(void);
typedef portapy_status (ABI_CALL *runtime_create_fn)(const portapy_config *, portapy_runtime *);
typedef portapy_status (ABI_CALL *runtime_destroy_fn)(portapy_runtime);
typedef portapy_status (ABI_CALL *exec_utf8_fn)(
    portapy_runtime, const uint8_t *, size_t, const uint8_t *, size_t
);
typedef portapy_status (ABI_CALL *get_global_fn)(
    portapy_runtime, const uint8_t *, size_t, portapy_value *
);
typedef portapy_status (ABI_CALL *value_as_bool_fn)(portapy_runtime, portapy_value, int *);
typedef portapy_status (ABI_CALL *value_as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *value_get_size_fn)(portapy_runtime, portapy_value, size_t *);
typedef portapy_status (ABI_CALL *value_copy_data_fn)(
    portapy_runtime, portapy_value, uint8_t *, size_t, size_t *
);
typedef portapy_status (ABI_CALL *value_release_fn)(portapy_runtime, portapy_value);
typedef portapy_status (ABI_CALL *error_get_info_fn)(portapy_runtime, portapy_error_info *);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { \
        fprintf(stderr, "missing symbol: %s\n", name); \
        return 10; \
    }

static int global_value(
    get_global_fn function,
    portapy_runtime runtime,
    const char *name,
    portapy_value *out_value
) {
    return function(runtime, (const uint8_t *)name, strlen(name), out_value) == PORTAPY_OK;
}

static int expect_text(
    value_get_size_fn get_size,
    value_copy_data_fn copy_data,
    portapy_runtime runtime,
    portapy_value value,
    const char *expected
) {
    size_t expected_size = strlen(expected);
    size_t size = 0;
    if (get_size(runtime, value, &size) != PORTAPY_OK || size != expected_size) return 0;
    uint8_t buffer[128] = {0};
    size_t copied = 0;
    if (copy_data(runtime, value, buffer, sizeof(buffer), &copied) != PORTAPY_OK) return 0;
    return copied == expected_size && memcmp(buffer, expected, expected_size) == 0;
}

static portapy_status execute_text(
    exec_utf8_fn execute,
    portapy_runtime runtime,
    const char *source,
    const char *filename
) {
    return execute(
        runtime,
        (const uint8_t *)source,
        strlen(source),
        (const uint8_t *)filename,
        strlen(filename)
    );
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    INSTALL_CRASH_HANDLER();
    TRACE_STEP("load-library");
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) return 3;

    TRACE_STEP("resolve-symbols");
    RESOLVE(initialize_fn, initialize, "portapy_library_initialize");
    RESOLVE(runtime_create_fn, runtime_create, "portapy_runtime_create");
    RESOLVE(runtime_destroy_fn, runtime_destroy, "portapy_runtime_destroy");
    RESOLVE(exec_utf8_fn, exec_utf8, "portapy_exec_utf8");
    RESOLVE(get_global_fn, get_global, "portapy_get_global_utf8");
    RESOLVE(value_as_bool_fn, value_as_bool, "portapy_value_as_bool");
    RESOLVE(value_as_i64_fn, value_as_i64, "portapy_value_as_i64");
    RESOLVE(value_get_size_fn, value_get_size, "portapy_value_get_size");
    RESOLVE(value_copy_data_fn, value_copy_data, "portapy_value_copy_data");
    RESOLVE(value_release_fn, value_release, "portapy_value_release");
    RESOLVE(error_get_info_fn, error_get_info, "portapy_error_get_info");

    TRACE_STEP("initialize");
    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;

    const char *preflight_sources[] = {
        "name = \"Somnia\"\n"
        "choice = \"unset\"\n",
        "name = \"Somnia\"\n"
        "choice = \"unset\"\n"
        "if name == \"Somnia\":\n"
        "    choice = \"matched\"\n"
        "    if 2 < 3:\n"
        "        nested = True\n"
        "else:\n"
        "    choice = \"wrong\"\n",
        "name = \"Somnia\"\n"
        "choice = \"unset\"\n"
        "if name == \"Somnia\":\n"
        "    choice = \"matched\"\n"
        "    if 2 < 3:\n"
        "        nested = True\n"
        "else:\n"
        "    choice = \"wrong\"\n"
        "count = 0\n"
        "total = 0\n"
        "while count < 6:\n"
        "    count = count + 1\n"
        "    if count == 2:\n"
        "        continue\n"
        "    if count == 5:\n"
        "        break\n"
        "    total = total + count\n",
        "name = \"Somnia\"\n"
        "choice = \"unset\"\n"
        "if name == \"Somnia\":\n"
        "    choice = \"matched\"\n"
        "    if 2 < 3:\n"
        "        nested = True\n"
        "else:\n"
        "    choice = \"wrong\"\n"
        "count = 0\n"
        "total = 0\n"
        "while count < 6:\n"
        "    count = count + 1\n"
        "    if count == 2:\n"
        "        continue\n"
        "    if count == 5:\n"
        "        break\n"
        "    total = total + count\n"
        "finished = count == 5 and total == 8\n"
        "42 == 42\n"
        "pass\n"
    };
    const char *preflight_steps[] = {
        "preflight-assignments",
        "preflight-if",
        "preflight-while",
        "preflight-complete"
    };
    const size_t preflight_count = sizeof(preflight_sources) / sizeof(preflight_sources[0]);
    for (size_t index = 0; index < preflight_count; ++index) {
        portapy_runtime probe = PORTAPY_NULL_RUNTIME;
        TRACE_STEP(preflight_steps[index]);
        if (runtime_create(&config, &probe) != PORTAPY_OK || probe == 0) {
            return (int)(40 + index * 2);
        }
        if (execute_text(exec_utf8, probe, preflight_sources[index], "control_preflight.py") != PORTAPY_OK) {
            return (int)(41 + index * 2);
        }
        if (runtime_destroy(probe) != PORTAPY_OK) return (int)(48 + index);
    }

    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    TRACE_STEP("runtime-create");
    if (runtime_create(&config, &runtime) != PORTAPY_OK || runtime == 0) return 12;

    const char source[] =
        "name = \"Somnia\"\n"
        "choice = \"unset\"\n"
        "if name == \"Somnia\":\n"
        "    choice = \"matched\"\n"
        "    if 2 < 3:\n"
        "        nested = True\n"
        "else:\n"
        "    choice = \"wrong\"\n"
        "count = 0\n"
        "total = 0\n"
        "while count < 6:\n"
        "    count = count + 1\n"
        "    if count == 2:\n"
        "        continue\n"
        "    if count == 5:\n"
        "        break\n"
        "    total = total + count\n"
        "finished = count == 5 and total == 8\n"
        "42 == 42\n"
        "pass\n";
    TRACE_STEP("exec-control-block");
    if (execute_text(exec_utf8, runtime, source, "control_flow.py") != PORTAPY_OK) return 13;

    portapy_value value = PORTAPY_NULL_VALUE;
    TRACE_STEP("get-choice");
    if (!global_value(get_global, runtime, "choice", &value)) return 14;
    TRACE_STEP("read-choice");
    if (!expect_text(value_get_size, value_copy_data, runtime, value, "matched")) return 15;
    TRACE_STEP("release-choice");
    if (value_release(runtime, value) != PORTAPY_OK) return 16;

    TRACE_STEP("get-nested");
    if (!global_value(get_global, runtime, "nested", &value)) return 17;
    int boolean = 0;
    TRACE_STEP("read-nested");
    if (value_as_bool(runtime, value, &boolean) != PORTAPY_OK || boolean != 1) return 18;
    TRACE_STEP("release-nested");
    if (value_release(runtime, value) != PORTAPY_OK) return 19;

    TRACE_STEP("get-count");
    if (!global_value(get_global, runtime, "count", &value)) return 20;
    int64_t integer = 0;
    TRACE_STEP("read-count");
    if (value_as_i64(runtime, value, &integer) != PORTAPY_OK || integer != 5) return 21;
    TRACE_STEP("release-count");
    if (value_release(runtime, value) != PORTAPY_OK) return 22;

    TRACE_STEP("get-total");
    if (!global_value(get_global, runtime, "total", &value)) return 23;
    TRACE_STEP("read-total");
    if (value_as_i64(runtime, value, &integer) != PORTAPY_OK || integer != 8) return 24;
    TRACE_STEP("release-total");
    if (value_release(runtime, value) != PORTAPY_OK) return 25;

    TRACE_STEP("get-finished");
    if (!global_value(get_global, runtime, "finished", &value)) return 26;
    TRACE_STEP("read-finished");
    if (value_as_bool(runtime, value, &boolean) != PORTAPY_OK || boolean != 1) return 27;
    TRACE_STEP("release-finished");
    if (value_release(runtime, value) != PORTAPY_OK) return 28;

    const char invalid[] = "value = 1\n  unexpected = 2\n";
    TRACE_STEP("exec-invalid-source");
    if (exec_utf8(
            runtime,
            (const uint8_t *)invalid,
            sizeof(invalid) - 1,
            NULL,
            0
        ) != PORTAPY_COMPILE_ERROR) return 29;
    portapy_error_info info = {0};
    info.struct_size = sizeof(info);
    TRACE_STEP("read-invalid-error");
    if (error_get_info(runtime, &info) != PORTAPY_OK) return 30;
    TRACE_STEP("validate-invalid-error");
    if (info.status != PORTAPY_COMPILE_ERROR || info.line != 2) return 31;

    TRACE_STEP("runtime-destroy");
    if (runtime_destroy(runtime) != PORTAPY_OK) return 32;
    TRACE_STEP("complete");
    puts("control-flow: ok");
    return 0;
}
