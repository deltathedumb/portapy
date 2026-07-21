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
typedef portapy_status (ABI_CALL *as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *release_fn)(portapy_runtime, portapy_value);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { fprintf(stderr, "missing symbol: %s\n", name); return 10; }

static int read_i64(
    portapy_runtime runtime,
    const char *name,
    get_global_fn get_global,
    as_i64_fn as_i64,
    release_fn release,
    int64_t *out_value
) {
    portapy_value value = PORTAPY_NULL_VALUE;
    if (
        get_global(
            runtime,
            (const uint8_t *)name,
            strlen(name),
            &value
        ) != PORTAPY_OK
    ) {
        return 0;
    }
    int ok = as_i64(runtime, value, out_value) == PORTAPY_OK;
    if (release(runtime, value) != PORTAPY_OK) {
        return 0;
    }
    return ok;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) return 3;

    RESOLVE(initialize_fn, initialize, "portapy_library_initialize");
    RESOLVE(runtime_create_fn, runtime_create, "portapy_runtime_create");
    RESOLVE(runtime_destroy_fn, runtime_destroy, "portapy_runtime_destroy");
    RESOLVE(exec_fn, exec_utf8, "portapy_exec_utf8");
    RESOLVE(get_global_fn, get_global, "portapy_get_global_utf8");
    RESOLVE(as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    const char source[] =
        "def make_reader(start):\n"
        "    value = start\n"
        "    def read():\n"
        "        return value\n"
        "    value = value + 1\n"
        "    return read\n"
        "first = make_reader(40)\n"
        "second = make_reader(90)\n"
        "first_result = first()\n"
        "second_result = second()\n"
        "first_again = first()\n";

    portapy_status status = exec_utf8(
        runtime,
        (const uint8_t *)source,
        strlen(source),
        (const uint8_t *)"closure_test.py",
        strlen("closure_test.py")
    );
    if (status != PORTAPY_OK) return 13;

    int64_t first = 0;
    int64_t second = 0;
    int64_t again = 0;
    if (!read_i64(runtime, "first_result", get_global, as_i64, release, &first)) return 14;
    if (!read_i64(runtime, "second_result", get_global, as_i64, release, &second)) return 15;
    if (!read_i64(runtime, "first_again", get_global, as_i64, release, &again)) return 16;
    if (first != 41 || second != 91 || again != 41) return 17;

    if (runtime_destroy(runtime) != PORTAPY_OK) return 18;
    puts("native-closures: ok");
    return 0;
}
