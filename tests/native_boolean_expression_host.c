#include "portapy.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#define LOAD_LIBRARY(path) ((void *)LoadLibraryA(path))
#define LOAD_SYMBOL(lib, name) ((void *)(uintptr_t)GetProcAddress((HMODULE)(lib), (name)))
#define ABI_CALL __cdecl
#else
#include <dlfcn.h>
#define LOAD_LIBRARY(path) dlopen((path), RTLD_NOW | RTLD_LOCAL)
#define LOAD_SYMBOL(lib, name) dlsym((lib), (name))
#define ABI_CALL
#endif

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
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) return 3;

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

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
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
    if (exec_utf8(
            runtime,
            (const uint8_t *)source,
            sizeof(source) - 1,
            (const uint8_t *)"boolean_block.py",
            strlen("boolean_block.py")
        ) != PORTAPY_OK) return 13;

    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "40 + 2 == 42", 1)) return 14;
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "True == 1", 1)) return 15;
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "\"abc\" < \"abd\"", 1)) return 16;
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "None is None", 1)) return 17;
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "name is alias", 1)) return 18;
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "name is not other", 1)) return 19;
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "not empty", 1)) return 20;
    if (!expect_bool(eval_utf8, value_as_bool, value_release, runtime, "answer > 40 and name == \"Somnia\"", 1)) return 21;

    portapy_value value = PORTAPY_NULL_VALUE;
    if (evaluate(eval_utf8, runtime, "empty or name", &value) != PORTAPY_OK) return 22;
    static const uint8_t somnia[] = {'S', 'o', 'm', 'n', 'i', 'a'};
    if (!expect_data(value_get_size, value_copy_data, runtime, value, somnia, sizeof(somnia))) return 23;
    if (value_release(runtime, value) != PORTAPY_OK) return 24;

    if (evaluate(eval_utf8, runtime, "name and answer", &value) != PORTAPY_OK) return 25;
    int64_t integer = 0;
    if (value_as_i64(runtime, value, &integer) != PORTAPY_OK || integer != 42) return 26;
    if (value_release(runtime, value) != PORTAPY_OK) return 27;

    const char *global_name = "correct";
    if (get_global(
            runtime,
            (const uint8_t *)global_name,
            strlen(global_name),
            &value
        ) != PORTAPY_OK) return 28;
    int boolean = 0;
    if (value_as_bool(runtime, value, &boolean) != PORTAPY_OK || boolean != 1) return 29;
    if (value_release(runtime, value) != PORTAPY_OK) return 30;

    global_name = "selected";
    if (get_global(
            runtime,
            (const uint8_t *)global_name,
            strlen(global_name),
            &value
        ) != PORTAPY_OK) return 31;
    if (!expect_data(value_get_size, value_copy_data, runtime, value, somnia, sizeof(somnia))) return 32;
    if (value_release(runtime, value) != PORTAPY_OK) return 33;

    if (evaluate(eval_utf8, runtime, "\"text\" < 4", &value) != PORTAPY_TYPE_ERROR) return 34;
    if (value != PORTAPY_NULL_VALUE) return 35;
    portapy_error_info info = {0};
    info.struct_size = sizeof(info);
    if (error_get_info(runtime, &info) != PORTAPY_OK || info.status != PORTAPY_TYPE_ERROR) return 36;

    if (runtime_destroy(runtime) != PORTAPY_OK) return 37;
    puts("boolean-expressions: ok");
    return 0;
}
