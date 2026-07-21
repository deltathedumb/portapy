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
typedef portapy_status (ABI_CALL *get_global_fn)(portapy_runtime, const uint8_t *, size_t, portapy_value *);
typedef portapy_status (ABI_CALL *set_global_fn)(portapy_runtime, const uint8_t *, size_t, portapy_value);
typedef portapy_status (ABI_CALL *from_host_fn)(portapy_runtime, uint64_t, portapy_value *);
typedef portapy_status (ABI_CALL *from_i64_fn)(portapy_runtime, int64_t, portapy_value *);
typedef portapy_status (ABI_CALL *as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *set_attr_fn)(portapy_runtime, portapy_value, const uint8_t *, size_t, portapy_value);
typedef portapy_status (ABI_CALL *copy_error_fn)(portapy_runtime, uint8_t *, size_t, size_t *);
typedef portapy_status (ABI_CALL *release_fn)(portapy_runtime, portapy_value);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { fprintf(stderr, "missing symbol: %s\n", name); return 10; }

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) return 3;

    RESOLVE(initialize_fn, initialize, "portapy_library_initialize");
    RESOLVE(runtime_create_fn, runtime_create, "portapy_runtime_create");
    RESOLVE(runtime_destroy_fn, runtime_destroy, "portapy_runtime_destroy");
    RESOLVE(exec_fn, exec_utf8, "portapy_exec_utf8");
    RESOLVE(get_global_fn, get_global, "portapy_get_global_utf8");
    RESOLVE(set_global_fn, set_global, "portapy_set_global_utf8");
    RESOLVE(from_host_fn, from_host, "portapy_value_from_host_object");
    RESOLVE(from_i64_fn, from_i64, "portapy_value_from_i64");
    RESOLVE(as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(set_attr_fn, set_attr, "portapy_host_set_attr_utf8");
    RESOLVE(copy_error_fn, copy_error_type, "portapy_error_copy_type_utf8");
    RESOLVE(release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    portapy_value helpers = PORTAPY_NULL_VALUE;
    portapy_value answer = PORTAPY_NULL_VALUE;
    if (from_host(runtime, UINT64_C(100), &helpers) != PORTAPY_OK) return 13;
    if (from_i64(runtime, 41, &answer) != PORTAPY_OK) return 14;
    if (set_attr(runtime, helpers, (const uint8_t *)"answer", 6, answer) != PORTAPY_OK) return 15;
    if (set_global(runtime, (const uint8_t *)"helpers", 7, helpers) != PORTAPY_OK) return 16;

    const char source[] =
        "import helpers as h\n"
        "aliased = h.answer\n"
        "from helpers import answer as imported\n"
        "result = aliased + imported\n";
    if (exec_utf8(runtime, (const uint8_t *)source, strlen(source), NULL, 0) != PORTAPY_OK) return 17;

    portapy_value result = PORTAPY_NULL_VALUE;
    int64_t number = 0;
    if (get_global(runtime, (const uint8_t *)"result", 6, &result) != PORTAPY_OK) return 18;
    if (as_i64(runtime, result, &number) != PORTAPY_OK || number != 82) return 19;
    if (release(runtime, result) != PORTAPY_OK) return 20;

    const char missing[] = "import missing\n";
    if (exec_utf8(runtime, (const uint8_t *)missing, strlen(missing), NULL, 0) != PORTAPY_NOT_FOUND) return 21;
    size_t required = 0;
    if (copy_error_type(runtime, NULL, 0, &required) != PORTAPY_INVALID_ARGUMENT) return 22;
    if (required != strlen("ModuleNotFoundError")) return 23;
    uint8_t error_type[32] = {0};
    if (copy_error_type(runtime, error_type, sizeof(error_type), &required) != PORTAPY_OK) return 24;
    if (memcmp(error_type, "ModuleNotFoundError", required) != 0) return 25;

    if (release(runtime, helpers) != PORTAPY_OK) return 26;
    if (release(runtime, answer) != PORTAPY_OK) return 27;
    if (runtime_destroy(runtime) != PORTAPY_OK) return 28;

    puts("native-host-imports: ok");
    return 0;
}
