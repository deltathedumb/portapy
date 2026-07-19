#include "portapy.h"

#include <stdint.h>
#include <stdio.h>

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
typedef portapy_status (ABI_CALL *exec_utf8_fn)(portapy_runtime, const uint8_t *, size_t, const uint8_t *, size_t);
typedef portapy_status (ABI_CALL *get_global_utf8_fn)(portapy_runtime, const uint8_t *, size_t, portapy_value *);
typedef portapy_status (ABI_CALL *value_as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *value_release_fn)(portapy_runtime, portapy_value);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) return 10

static int read_global(
    portapy_runtime runtime,
    const char *name,
    size_t name_size,
    get_global_utf8_fn get_global,
    value_as_i64_fn as_i64,
    value_release_fn release,
    int64_t expected
) {
    portapy_value value = PORTAPY_NULL_VALUE;
    int64_t actual = 0;
    if (get_global(runtime, (const uint8_t *)name, name_size, &value) != PORTAPY_OK) return 1;
    if (as_i64(runtime, value, &actual) != PORTAPY_OK) return 2;
    if (release(runtime, value) != PORTAPY_OK) return 3;
    return actual == expected ? 0 : 4;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) return 3;

    RESOLVE(initialize_fn, initialize, "portapy_library_initialize");
    RESOLVE(runtime_create_fn, runtime_create, "portapy_runtime_create");
    RESOLVE(runtime_destroy_fn, runtime_destroy, "portapy_runtime_destroy");
    RESOLVE(exec_utf8_fn, exec_utf8, "portapy_exec_utf8");
    RESOLVE(get_global_utf8_fn, get_global, "portapy_get_global_utf8");
    RESOLVE(value_as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(value_release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    const uint8_t block[] = {
        '#', ' ', 's', 'e', 'e', 'd', '\n',
        'b', 'a', 's', 'e', ' ', '=', ' ', '5', '\n',
        '\n',
        'd', 'o', 'u', 'b', 'l', 'e', ' ', '=', ' ', 'b', 'a', 's', 'e', ' ', '*', ' ', '2', ';',
        ' ', 't', 'o', 't', 'a', 'l', ' ', '=', ' ', 'd', 'o', 'u', 'b', 'l', 'e', ' ', '+', ' ', '3',
        ' ', '#', ' ', 'd', 'o', 'n', 'e', '\n'
    };
    if (exec_utf8(runtime, block, sizeof(block), NULL, 0) != PORTAPY_OK) return 13;
    if (read_global(runtime, "base", 4, get_global, as_i64, release, 5) != 0) return 14;
    if (read_global(runtime, "double", 6, get_global, as_i64, release, 10) != 0) return 15;
    if (read_global(runtime, "total", 5, get_global, as_i64, release, 13) != 0) return 16;

    const uint8_t partial[] = {
        'b', 'e', 'f', 'o', 'r', 'e', ' ', '=', ' ', '1', ';',
        ' ', 'b', 'r', 'o', 'k', 'e', 'n', ' ', '=', ' ', '5', ' ', '/', '/', ' ', '0', ';',
        ' ', 'a', 'f', 't', 'e', 'r', ' ', '=', ' ', '3'
    };
    if (exec_utf8(runtime, partial, sizeof(partial), NULL, 0) != PORTAPY_RUNTIME_ERROR) return 17;
    if (read_global(runtime, "before", 6, get_global, as_i64, release, 1) != 0) return 18;
    portapy_value missing = 99;
    if (get_global(runtime, (const uint8_t *)"after", 5, &missing) != PORTAPY_NOT_FOUND) return 19;
    if (missing != PORTAPY_NULL_VALUE) return 20;

    const uint8_t empty[] = {' ', '\n', ';', ' ', '#', ' ', 'e', 'm', 'p', 't', 'y', '\n'};
    if (exec_utf8(runtime, empty, sizeof(empty), NULL, 0) != PORTAPY_OK) return 21;

    if (runtime_destroy(runtime) != PORTAPY_OK) return 22;
    printf("statement-blocks: ok\n");
    return 0;
}
