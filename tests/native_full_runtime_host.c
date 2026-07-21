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
typedef portapy_status (ABI_CALL *as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *release_fn)(portapy_runtime, portapy_value);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { fprintf(stderr, "missing symbol: %s\n", name); return 10; }

static int execute(exec_fn function, portapy_runtime runtime, const char *source) {
    return function(runtime, (const uint8_t *)source, strlen(source), NULL, 0) == PORTAPY_OK;
}

static int evaluate_i64(
    eval_fn function,
    as_i64_fn as_i64,
    release_fn release,
    portapy_runtime runtime,
    const char *source,
    int64_t expected
) {
    portapy_value value = PORTAPY_NULL_VALUE;
    int64_t result = 0;
    if (function(runtime, (const uint8_t *)source, strlen(source), NULL, 0, &value) != PORTAPY_OK) return 0;
    if (as_i64(runtime, value, &result) != PORTAPY_OK || result != expected) return 0;
    return release(runtime, value) == PORTAPY_OK;
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
    RESOLVE(as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    const char source[] =
        "class Counter:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "    def step(self):\n"
        "        self.value += 1\n"
        "        return self.value\n"
        "def make_offset(offset):\n"
        "    def apply(value):\n"
        "        return value + offset\n"
        "    return apply\n"
        "counter = Counter(39)\n"
        "offset = make_offset(1)\n"
        "values = [offset(value) for value in [19, 20, 21] if value >= 20]\n"
        "try:\n"
        "    current = counter.step()\n"
        "except ValueError:\n"
        "    current = 0\n"
        "match values:\n"
        "    case [21, 22]:\n"
        "        answer = current + 2\n"
        "    case _:\n"
        "        answer = 0\n";
    if (!execute(exec_utf8, runtime, source)) return 13;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "answer", 42)) return 14;

    if (!execute(exec_utf8, runtime, "answer = counter.step() + 1\n")) return 15;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "answer", 42)) return 16;

    if (runtime_destroy(runtime) != PORTAPY_OK) return 17;
    puts("native-full-runtime: ok");
    return 0;
}
