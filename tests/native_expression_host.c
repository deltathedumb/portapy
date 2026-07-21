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
typedef portapy_status (ABI_CALL *exec_fn)(portapy_runtime, const uint8_t *, size_t, const uint8_t *, size_t);
typedef portapy_status (ABI_CALL *eval_fn)(portapy_runtime, const uint8_t *, size_t, const uint8_t *, size_t, portapy_value *);
typedef portapy_status (ABI_CALL *get_global_fn)(portapy_runtime, const uint8_t *, size_t, portapy_value *);
typedef portapy_status (ABI_CALL *as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *as_bool_fn)(portapy_runtime, portapy_value, int *);
typedef portapy_status (ABI_CALL *get_size_fn)(portapy_runtime, portapy_value, size_t *);
typedef portapy_status (ABI_CALL *copy_data_fn)(portapy_runtime, portapy_value, uint8_t *, size_t, size_t *);
typedef portapy_status (ABI_CALL *release_fn)(portapy_runtime, portapy_value);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { fprintf(stderr, "missing symbol: %s\n", name); return 10; }

static int eval_value(eval_fn function, portapy_runtime runtime, const char *source, portapy_value *value) {
    return function(runtime, (const uint8_t *)source, strlen(source), NULL, 0, value) == PORTAPY_OK;
}

static int expect_text(get_size_fn get_size, copy_data_fn copy_data, portapy_runtime runtime, portapy_value value, const char *expected) {
    size_t size = 0;
    size_t copied = 0;
    uint8_t buffer[128] = {0};
    size_t expected_size = strlen(expected);
    if (get_size(runtime, value, &size) != PORTAPY_OK || size != expected_size) return 0;
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
    RESOLVE(exec_fn, exec_utf8, "portapy_exec_utf8");
    RESOLVE(eval_fn, eval_utf8, "portapy_eval_utf8");
    RESOLVE(get_global_fn, get_global, "portapy_get_global_utf8");
    RESOLVE(as_i64_fn, value_as_i64, "portapy_value_as_i64");
    RESOLVE(as_bool_fn, value_as_bool, "portapy_value_as_bool");
    RESOLVE(get_size_fn, value_get_size, "portapy_value_get_size");
    RESOLVE(copy_data_fn, value_copy_data, "portapy_value_copy_data");
    RESOLVE(release_fn, value_release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    portapy_value value = PORTAPY_NULL_VALUE;
    int64_t integer = 0;
    int boolean = 0;

    if (!eval_value(eval_utf8, runtime, "2 + 3 * 4", &value)) return 13;
    if (value_as_i64(runtime, value, &integer) != PORTAPY_OK || integer != 14) return 14;
    if (value_release(runtime, value) != PORTAPY_OK) return 15;

    if (!eval_value(eval_utf8, runtime, "2 ** 3 ** 2", &value)) return 16;
    if (value_as_i64(runtime, value, &integer) != PORTAPY_OK || integer != 512) return 17;
    if (value_release(runtime, value) != PORTAPY_OK) return 18;

    if (!eval_value(eval_utf8, runtime, "\"Som\" + \"nia\"", &value)) return 19;
    if (!expect_text(value_get_size, value_copy_data, runtime, value, "Somnia")) return 20;
    if (value_release(runtime, value) != PORTAPY_OK) return 21;

    if (!eval_value(eval_utf8, runtime, "3 * 4 == 12", &value)) return 22;
    if (value_as_bool(runtime, value, &boolean) != PORTAPY_OK || boolean != 1) return 23;
    if (value_release(runtime, value) != PORTAPY_OK) return 24;

    const char source[] =
        "counter = 5\n"
        "counter *= 3\n"
        "counter += 2\n"
        "name = \"Som\" + \"nia\"\n"
        "counter == 17\n"
        "pass\n";
    if (exec_utf8(runtime, (const uint8_t *)source, sizeof(source) - 1, NULL, 0) != PORTAPY_OK) return 25;

    if (get_global(runtime, (const uint8_t *)"counter", 7, &value) != PORTAPY_OK) return 26;
    if (value_as_i64(runtime, value, &integer) != PORTAPY_OK || integer != 17) return 27;
    if (value_release(runtime, value) != PORTAPY_OK) return 28;

    if (get_global(runtime, (const uint8_t *)"name", 4, &value) != PORTAPY_OK) return 29;
    if (!expect_text(value_get_size, value_copy_data, runtime, value, "Somnia")) return 30;
    if (value_release(runtime, value) != PORTAPY_OK) return 31;

    if (runtime_destroy(runtime) != PORTAPY_OK) return 32;
    puts("general-expressions: ok");
    return 0;
}
