#include "portapy.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#define LOAD_LIBRARY(path) ((void *)LoadLibraryA(path))
#define LOAD_SYMBOL(lib, name) ((void *)(uintptr_t)GetProcAddress((HMODULE)(lib), (name)))
#define ABI_CALL __cdecl

static LONG WINAPI portapy_boolean_crash_filter(EXCEPTION_POINTERS *exception) {
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
        "boolean-crash: code=0x%08lx address=%p module=%s offset=0x%llx\n",
        (unsigned long)code,
        address,
        module_name[0] == '\0' ? "<unknown>" : module_name,
        offset
    );
#if defined(_M_X64) || defined(__x86_64__)
    if (context != NULL) {
        fprintf(
            stderr,
            "boolean-crash-context: rip=0x%llx rsp=0x%llx rbp=0x%llx\n",
            (unsigned long long)context->Rip,
            (unsigned long long)context->Rsp,
            (unsigned long long)context->Rbp
        );
    }
#endif
    fflush(stderr);
    return EXCEPTION_EXECUTE_HANDLER;
}

#define INSTALL_CRASH_HANDLER() SetUnhandledExceptionFilter(portapy_boolean_crash_filter)
#else
#include <dlfcn.h>
#define LOAD_LIBRARY(path) dlopen((path), RTLD_NOW | RTLD_LOCAL)
#define LOAD_SYMBOL(lib, name) dlsym((lib), (name))
#define ABI_CALL
#define INSTALL_CRASH_HANDLER() ((void)0)
#endif

#define TRACE_STEP(message) do { \
    fprintf(stderr, "boolean-step: %s\n", (message)); \
    fflush(stderr); \
} while (0)

typedef portapy_status (ABI_CALL *initialize_fn)(void);
typedef portapy_status (ABI_CALL *runtime_create_fn)(const portapy_config *, portapy_runtime *);
typedef portapy_status (ABI_CALL *runtime_destroy_fn)(portapy_runtime);
typedef portapy_status (ABI_CALL *exec_utf8_fn)(
    portapy_runtime, const uint8_t *, size_t, const uint8_t *, size_t
);
typedef portapy_status (ABI_CALL *eval_utf8_fn)(
    portapy_runtime, const uint8_t *, size_t, const uint8_t *, size_t, portapy_value *
);
typedef portapy_status (ABI_CALL *get_global_fn)(
    portapy_runtime, const uint8_t *, size_t, portapy_value *
);
typedef portapy_status (ABI_CALL *value_get_kind_fn)(
    portapy_runtime, portapy_value, portapy_value_kind *
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

static portapy_status execute(
    exec_utf8_fn function,
    portapy_runtime runtime,
    const char *source,
    const char *filename
) {
    return function(
        runtime,
        (const uint8_t *)source,
        strlen(source),
        (const uint8_t *)filename,
        strlen(filename)
    );
}

static portapy_status evaluate(
    eval_utf8_fn function,
    portapy_runtime runtime,
    const char *source,
    portapy_value *out_value
) {
    return function(
        runtime,
        (const uint8_t *)source,
        strlen(source),
        (const uint8_t *)"boolean_expr.py",
        strlen("boolean_expr.py"),
        out_value
    );
}

static int expect_bool(
    eval_utf8_fn evaluate_fn,
    value_as_bool_fn as_bool,
    value_release_fn release,
    portapy_runtime runtime,
    const char *source,
    int expected
) {
    portapy_value value = PORTAPY_NULL_VALUE;
    if (evaluate(evaluate_fn, runtime, source, &value) != PORTAPY_OK) return 0;
    int actual = -1;
    if (as_bool(runtime, value, &actual) != PORTAPY_OK) return 0;
    if (release(runtime, value) != PORTAPY_OK) return 0;
    return actual == expected;
}

static int expect_data(
    value_get_size_fn get_size,
    value_copy_data_fn copy_data,
    portapy_runtime runtime,
    portapy_value value,
    const uint8_t *expected,
    size_t expected_size
) {
    size_t size = 0;
    if (get_size(runtime, value, &size) != PORTAPY_OK || size != expected_size) return 0;
    uint8_t buffer[128] = {0};
    size_t copied = 0;
    if (copy_data(runtime, value, buffer, sizeof(buffer), &copied) != PORTAPY_OK) return 0;
    return copied == expected_size && memcmp(buffer, expected, expected_size) == 0;
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
    RESOLVE(eval_utf8_fn, eval_utf8, "portapy_eval_utf8");
    RESOLVE(get_global_fn, get_global, "portapy_get_global_utf8");
    RESOLVE(value_get_kind_fn, value_get_kind, "portapy_value_get_kind");
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

    portapy_runtime preflight = PORTAPY_NULL_RUNTIME;
    TRACE_STEP("preflight-runtime-create");
    if (runtime_create(&config, &preflight) != PORTAPY_OK || preflight == 0) return 38;
    const char *preflight_sources[] = {
        "empty = \"\"\n",
        "name = \"Somnia\"\n",
        "alias = name\n",
        "other = \"PortaPy\"\n",
        "zero = 0\n",
        "answer = 42\n",
        "correct = name == \"Somnia\"\n",
        "selected = empty or name\n",
        "guarded = name and answer\n"
    };
    const char *preflight_steps[] = {
        "preflight-empty",
        "preflight-name",
        "preflight-alias",
        "preflight-other",
        "preflight-zero",
        "preflight-answer",
        "preflight-correct",
        "preflight-selected",
        "preflight-guarded"
    };
    const size_t preflight_count = sizeof(preflight_sources) / sizeof(preflight_sources[0]);
    for (size_t index = 0; index < preflight_count; ++index) {
        TRACE_STEP(preflight_steps[index]);
        if (execute(exec_utf8, preflight, preflight_sources[index], "boolean_preflight.py") != PORTAPY_OK) {
            return (int)(39 + index);
        }
    }
    TRACE_STEP("preflight-runtime-destroy");
    if (runtime_destroy(preflight) != PORTAPY_OK) return 48;

    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    TRACE_STEP("runtime-create");
    if (runtime_create(&config, &runtime) != PORTAPY_OK || runtime == 0) return 12;

    const char source[] =
        "empty = \"\"\n"
        "name = \"Somnia\"\n"
        "alias = name\n"
        "other = \"PortaPy\"\n"
        "zero = 0\n"
        "answer = 42\n"
        "correct = name == \"Somnia\"\n"
        "selected = empty or name\n"
        "guarded = name and answer\n";
    TRACE_STEP("exec-boolean-block");
    if (execute(exec_utf8, runtime, source, "boolean_block.py") != PORTAPY_OK) return 13;

    TRACE_STEP("eval-arithmetic-equality");
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "40 + 2 == 42", 1)) return 14;
    TRACE_STEP("eval-bool-int-equality");
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "True == 1", 1)) return 15;
    TRACE_STEP("eval-string-order");
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "\"abc\" < \"abd\"", 1)) return 16;
    TRACE_STEP("eval-none-identity");
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "None is None", 1)) return 17;
    TRACE_STEP("eval-alias-identity");
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "name is alias", 1)) return 18;
    TRACE_STEP("eval-other-nonidentity");
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "name is not other", 1)) return 19;
    TRACE_STEP("eval-not-empty");
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "not empty", 1)) return 20;
    TRACE_STEP("eval-and-expression");
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "answer > 40 and name == \"Somnia\"", 1)) return 21;

    portapy_value value = PORTAPY_NULL_VALUE;
    TRACE_STEP("eval-or-value");
    if (evaluate(eval_utf8, runtime, "empty or name", &value) != PORTAPY_OK) return 22;
    static const uint8_t somnia[] = {'S', 'o', 'm', 'n', 'i', 'a'};
    TRACE_STEP("read-or-value");
    if (!expect_data(value_get_size, value_copy_data, runtime, value, somnia, sizeof(somnia))) return 23;
    TRACE_STEP("release-or-value");
    if (value_release(runtime, value) != PORTAPY_OK) return 24;

    TRACE_STEP("eval-and-value");
    if (evaluate(eval_utf8, runtime, "name and answer", &value) != PORTAPY_OK) return 25;
    int64_t integer = 0;
    TRACE_STEP("read-and-value");
    if (value_as_i64(runtime, value, &integer) != PORTAPY_OK || integer != 42) return 26;
    TRACE_STEP("release-and-value");
    if (value_release(runtime, value) != PORTAPY_OK) return 27;

    const char *global_name = "correct";
    TRACE_STEP("get-correct-global");
    if (get_global(runtime, (const uint8_t *)global_name, strlen(global_name), &value) != PORTAPY_OK) return 28;
    int boolean = 0;
    TRACE_STEP("read-correct-global");
    if (value_as_bool(runtime, value, &boolean) != PORTAPY_OK || boolean != 1) return 29;
    TRACE_STEP("release-correct-global");
    if (value_release(runtime, value) != PORTAPY_OK) return 30;

    global_name = "selected";
    TRACE_STEP("get-selected-global");
    if (get_global(runtime, (const uint8_t *)global_name, strlen(global_name), &value) != PORTAPY_OK) return 31;
    TRACE_STEP("read-selected-global");
    if (!expect_data(value_get_size, value_copy_data, runtime, value, somnia, sizeof(somnia))) return 32;
    TRACE_STEP("release-selected-global");
    if (value_release(runtime, value) != PORTAPY_OK) return 33;

    TRACE_STEP("eval-mixed-type-error");
    if (evaluate(eval_utf8, runtime, "\"text\" < 4", &value) != PORTAPY_TYPE_ERROR) return 34;
    if (value != PORTAPY_NULL_VALUE) return 35;
    portapy_error_info info = {0};
    info.struct_size = sizeof(info);
    TRACE_STEP("read-mixed-type-error");
    if (error_get_info(runtime, &info) != PORTAPY_OK || info.status != PORTAPY_TYPE_ERROR) return 36;

    TRACE_STEP("runtime-destroy");
    if (runtime_destroy(runtime) != PORTAPY_OK) return 37;
    TRACE_STEP("complete");
    puts("boolean-expressions: ok");
    return 0;
}
