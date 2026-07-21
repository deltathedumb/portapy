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
typedef portapy_status (ABI_CALL *as_bool_fn)(portapy_runtime, portapy_value, int *);
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

static int evaluate_bool(
    eval_fn function,
    as_bool_fn as_bool,
    release_fn release,
    portapy_runtime runtime,
    const char *source,
    int expected
) {
    portapy_value value = PORTAPY_NULL_VALUE;
    int result = 0;
    if (function(runtime, (const uint8_t *)source, strlen(source), NULL, 0, &value) != PORTAPY_OK) return 0;
    if (as_bool(runtime, value, &result) != PORTAPY_OK || result != expected) return 0;
    return release(runtime, value) == PORTAPY_OK;
}

static int evaluate_status(
    eval_fn function,
    portapy_runtime runtime,
    const char *source,
    portapy_status expected
) {
    portapy_value value = PORTAPY_NULL_VALUE;
    return function(runtime, (const uint8_t *)source, strlen(source), NULL, 0, &value) == expected;
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
    RESOLVE(as_bool_fn, as_bool, "portapy_value_as_bool");
    RESOLVE(as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    const char source[] =
        "options = 100\n"
        "def summarize(**values):\n"
        "    if values:\n"
        "        return len(values) + values[\"left\"] + values[\"right\"]\n"
        "    return 0\n"
        "def combine(head, /, middle=2, *tail, scale=1, **options):\n"
        "    total = head + middle + len(tail) + len(options)\n"
        "    if tail:\n"
        "        total += tail[0]\n"
        "    if options:\n"
        "        total += options[\"bonus\"]\n"
        "    return total * scale\n"
        "def route(value, /, **options):\n"
        "    return value + options[\"value\"]\n"
        "def capture(**options):\n"
        "    return options\n"
        "empty = summarize()\n"
        "filled = summarize(left=18, right=22)\n"
        "mixed = combine(10, 3, 4, scale=2, bonus=2)\n"
        "positional_name = route(20, value=22)\n"
        "saved = capture(alpha=18, beta=24)\n"
        "saved_again = capture(alpha=18, beta=24)\n"
        "same = saved == saved_again\n"
        "indexed = saved[\"alpha\"] + saved[\"beta\"]\n";
    if (!execute(exec_utf8, runtime, source)) return 13;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "empty", 0)) return 14;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "filled", 42)) return 15;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "mixed", 42)) return 16;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "positional_name", 42)) return 17;
    if (!evaluate_bool(eval_utf8, as_bool, release, runtime, "same", 1)) return 18;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "indexed", 42)) return 19;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "options", 100)) return 20;
    if (!evaluate_status(eval_utf8, runtime, "capture(value=1, value=2)", PORTAPY_TYPE_ERROR)) return 21;

    const char missing[] =
        "def missing(**values):\n"
        "    return values[\"absent\"]\n"
        "missing_result = missing(present=1)\n";
    if (exec_utf8(runtime, (const uint8_t *)missing, strlen(missing), NULL, 0) != PORTAPY_NOT_FOUND) return 22;

    if (runtime_destroy(runtime) != PORTAPY_OK) return 23;
    puts("native-kwargs: ok");
    return 0;
}
