#include "portapy.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

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
typedef uint32_t (ABI_CALL *abi_version_fn)(void);
typedef portapy_status (ABI_CALL *runtime_create_fn)(const portapy_config *, portapy_runtime *);
typedef portapy_status (ABI_CALL *runtime_destroy_fn)(portapy_runtime);
typedef portapy_status (ABI_CALL *value_from_i64_fn)(portapy_runtime, int64_t, portapy_value *);
typedef portapy_status (ABI_CALL *value_get_kind_fn)(portapy_runtime, portapy_value, portapy_value_kind *);
typedef portapy_status (ABI_CALL *value_as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *value_lifetime_fn)(portapy_runtime, portapy_value);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { \
        fprintf(stderr, "missing symbol: %s\n", name); \
        return 10; \
    }

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: native_handle_host <library>\n");
        return 2;
    }
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) {
        fprintf(stderr, "failed to load %s\n", argv[1]);
        return 3;
    }

    RESOLVE(initialize_fn, initialize, "portapy_library_initialize");
    RESOLVE(abi_version_fn, abi_version, "portapy_abi_version");
    RESOLVE(runtime_create_fn, runtime_create, "portapy_runtime_create");
    RESOLVE(runtime_destroy_fn, runtime_destroy, "portapy_runtime_destroy");
    RESOLVE(value_from_i64_fn, value_from_i64, "portapy_value_from_i64");
    RESOLVE(value_get_kind_fn, value_get_kind, "portapy_value_get_kind");
    RESOLVE(value_as_i64_fn, value_as_i64, "portapy_value_as_i64");
    RESOLVE(value_lifetime_fn, value_retain, "portapy_value_retain");
    RESOLVE(value_lifetime_fn, value_release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    if (abi_version() != PORTAPY_ABI_VERSION) return 12;

    portapy_config bad = {0};
    bad.struct_size = sizeof(bad);
    bad.abi_version = PORTAPY_ABI_VERSION + 1;
    portapy_runtime ignored = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&bad, &ignored) != PORTAPY_ABI_MISMATCH) return 13;

    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime first = PORTAPY_NULL_RUNTIME;
    portapy_runtime second = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &first) != PORTAPY_OK || first == 0) return 14;
    if (runtime_create(&config, &second) != PORTAPY_OK || second == 0 || second == first) return 15;

    portapy_value value = PORTAPY_NULL_VALUE;
    if (value_from_i64(first, -42, &value) != PORTAPY_OK || value == 0) return 16;
    portapy_value_kind kind = PORTAPY_VALUE_OBJECT;
    if (value_get_kind(first, value, &kind) != PORTAPY_OK) return 17;
    if (kind != PORTAPY_VALUE_INT) return 18;
    int64_t number = 0;
    if (value_as_i64(first, value, &number) != PORTAPY_OK || number != -42) return 19;

    if (value_as_i64(second, value, &number) != PORTAPY_INVALID_HANDLE) return 20;
    if (value_retain(first, value) != PORTAPY_OK) return 21;
    if (value_release(first, value) != PORTAPY_OK) return 22;
    if (value_as_i64(first, value, &number) != PORTAPY_OK || number != -42) return 23;
    if (value_release(first, value) != PORTAPY_OK) return 24;
    if (value_as_i64(first, value, &number) != PORTAPY_INVALID_HANDLE) return 25;

    if (runtime_destroy(first) != PORTAPY_OK) return 26;
    if (runtime_destroy(first) != PORTAPY_INVALID_HANDLE) return 27;
    if (runtime_destroy(second) != PORTAPY_OK) return 28;

    printf("opaque-handles: ok\n");
    return 0;
}
