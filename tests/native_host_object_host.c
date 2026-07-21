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
typedef portapy_status (ABI_CALL *host_id_fn)(portapy_runtime, portapy_value, uint64_t *);
typedef portapy_status (ABI_CALL *set_attr_fn)(portapy_runtime, portapy_value, const uint8_t *, size_t, portapy_value);
typedef portapy_status (ABI_CALL *get_attr_fn)(portapy_runtime, portapy_value, const uint8_t *, size_t, portapy_value *);
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
    RESOLVE(host_id_fn, get_host_id, "portapy_value_get_host_id");
    RESOLVE(set_attr_fn, set_attr, "portapy_host_set_attr_utf8");
    RESOLVE(get_attr_fn, get_attr, "portapy_host_get_attr_utf8");
    RESOLVE(release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    portapy_value game = PORTAPY_NULL_VALUE;
    portapy_value provider = PORTAPY_NULL_VALUE;
    portapy_value http_provider = PORTAPY_NULL_VALUE;
    if (from_host(runtime, UINT64_C(100), &game) != PORTAPY_OK) return 13;
    if (from_host(runtime, UINT64_C(200), &provider) != PORTAPY_OK) return 14;
    if (from_host(runtime, UINT64_C(300), &http_provider) != PORTAPY_OK) return 15;

    if (set_attr(runtime, game, (const uint8_t *)"provider", 8, provider) != PORTAPY_OK) return 16;
    if (set_attr(runtime, provider, (const uint8_t *)"HttpProvider", 12, http_provider) != PORTAPY_OK) return 17;
    if (set_global(runtime, (const uint8_t *)"game", 4, game) != PORTAPY_OK) return 18;

    portapy_value direct = PORTAPY_NULL_VALUE;
    uint64_t direct_id = 0;
    if (get_attr(runtime, provider, (const uint8_t *)"HttpProvider", 12, &direct) != PORTAPY_OK) return 19;
    if (get_host_id(runtime, direct, &direct_id) != PORTAPY_OK || direct_id != UINT64_C(300)) return 20;
    if (release(runtime, direct) != PORTAPY_OK) return 21;

    const char source[] = "http_provider = game.provider.HttpProvider\n";
    if (exec_utf8(runtime, (const uint8_t *)source, strlen(source), NULL, 0) != PORTAPY_OK) return 22;

    portapy_value captured = PORTAPY_NULL_VALUE;
    uint64_t captured_id = 0;
    if (get_global(runtime, (const uint8_t *)"http_provider", 13, &captured) != PORTAPY_OK) return 23;
    if (get_host_id(runtime, captured, &captured_id) != PORTAPY_OK || captured_id != UINT64_C(300)) return 24;

    if (release(runtime, captured) != PORTAPY_OK) return 25;
    if (release(runtime, game) != PORTAPY_OK) return 26;
    if (release(runtime, provider) != PORTAPY_OK) return 27;
    if (release(runtime, http_provider) != PORTAPY_OK) return 28;
    if (runtime_destroy(runtime) != PORTAPY_OK) return 29;

    puts("native-host-objects: ok");
    return 0;
}
