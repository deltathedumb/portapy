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

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { \
        fprintf(stderr, "missing symbol: %s\n", name); \
        return 10; \
    }

static int get_global(
    get_global_fn function,
    portapy_runtime runtime,
    const char *name,
    portapy_value *out_value
) {
    return function(runtime, (const uint8_t *)name, strlen(name), out_value) == PORTAPY_OK;
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
    RESOLVE(get_global_fn, get_global_value, "portapy_get_global_utf8");
    RESOLVE(value_get_kind_fn, value_get_kind, "portapy_value_get_kind");
    RESOLVE(value_as_bool_fn, value_as_bool, "portapy_value_as_bool");
    RESOLVE(value_as_i64_fn, value_as_i64, "portapy_value_as_i64");
    RESOLVE(value_get_size_fn, value_get_size, "portapy_value_get_size");
    RESOLVE(value_copy_data_fn, value_copy_data, "portapy_value_copy_data");
    RESOLVE(value_release_fn, value_release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK || runtime == 0) return 12;

    const char source[] =
        "nothing = None\n"
        "flag = True\n"
        "disabled = False\n"
        "name = \"Somnia\"\n"
        "payload = b\"\\x00\\xffA\"\n"
        "alias = name\n"
        "punctuation = \"a;b#c\"; answer = 40 + 2 # comment\n";
    if (exec_utf8(
            runtime,
            (const uint8_t *)source,
            sizeof(source) - 1,
            (const uint8_t *)"typed_literals.py",
            strlen("typed_literals.py")
        ) != PORTAPY_OK) return 13;

    portapy_value value = PORTAPY_NULL_VALUE;
    portapy_value_kind kind = PORTAPY_VALUE_OBJECT;

    if (!get_global(get_global_value, runtime, "nothing", &value)) return 14;
    if (value_get_kind(runtime, value, &kind) != PORTAPY_OK || kind != PORTAPY_VALUE_NONE) return 15;
    if (value_release(runtime, value) != PORTAPY_OK) return 16;

    if (!get_global(get_global_value, runtime, "flag", &value)) return 17;
    int boolean = 0;
    if (value_as_bool(runtime, value, &boolean) != PORTAPY_OK || boolean != 1) return 18;
    if (value_release(runtime, value) != PORTAPY_OK) return 19;

    if (!get_global(get_global_value, runtime, "disabled", &value)) return 20;
    if (value_as_bool(runtime, value, &boolean) != PORTAPY_OK || boolean != 0) return 21;
    if (value_release(runtime, value) != PORTAPY_OK) return 22;

    static const uint8_t somnia[] = {'S', 'o', 'm', 'n', 'i', 'a'};
    if (!get_global(get_global_value, runtime, "name", &value)) return 23;
    if (value_get_kind(runtime, value, &kind) != PORTAPY_OK || kind != PORTAPY_VALUE_STRING) return 24;
    if (!expect_data(value_get_size, value_copy_data, runtime, value, somnia, sizeof(somnia))) return 25;
    if (value_release(runtime, value) != PORTAPY_OK) return 26;

    if (!get_global(get_global_value, runtime, "alias", &value)) return 27;
    if (!expect_data(value_get_size, value_copy_data, runtime, value, somnia, sizeof(somnia))) return 28;
    if (value_release(runtime, value) != PORTAPY_OK) return 29;

    static const uint8_t payload[] = {0, 255, 'A'};
    if (!get_global(get_global_value, runtime, "payload", &value)) return 30;
    if (value_get_kind(runtime, value, &kind) != PORTAPY_OK || kind != PORTAPY_VALUE_BYTES) return 31;
    if (!expect_data(value_get_size, value_copy_data, runtime, value, payload, sizeof(payload))) return 32;
    if (value_release(runtime, value) != PORTAPY_OK) return 33;

    static const uint8_t punctuation[] = {'a', ';', 'b', '#', 'c'};
    if (!get_global(get_global_value, runtime, "punctuation", &value)) return 34;
    if (!expect_data(value_get_size, value_copy_data, runtime, value, punctuation, sizeof(punctuation))) return 35;
    if (value_release(runtime, value) != PORTAPY_OK) return 36;

    if (!get_global(get_global_value, runtime, "answer", &value)) return 37;
    int64_t integer = 0;
    if (value_as_i64(runtime, value, &integer) != PORTAPY_OK || integer != 42) return 38;
    if (value_release(runtime, value) != PORTAPY_OK) return 39;

    const char expression[] = "name";
    if (eval_utf8(
            runtime,
            (const uint8_t *)expression,
            sizeof(expression) - 1,
            NULL,
            0,
            &value
        ) != PORTAPY_OK) return 40;
    if (!expect_data(value_get_size, value_copy_data, runtime, value, somnia, sizeof(somnia))) return 41;
    if (value_release(runtime, value) != PORTAPY_OK) return 42;

    const char literal[] = "\"native eval\"";
    static const uint8_t literal_expected[] = "native eval";
    if (eval_utf8(
            runtime,
            (const uint8_t *)literal,
            sizeof(literal) - 1,
            NULL,
            0,
            &value
        ) != PORTAPY_OK) return 43;
    if (!expect_data(
            value_get_size,
            value_copy_data,
            runtime,
            value,
            literal_expected,
            sizeof(literal_expected) - 1
        )) return 44;
    if (value_release(runtime, value) != PORTAPY_OK) return 45;

    if (runtime_destroy(runtime) != PORTAPY_OK) return 46;
    puts("typed-literals: ok");
    return 0;
}
