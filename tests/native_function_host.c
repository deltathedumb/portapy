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
typedef portapy_status (ABI_CALL *get_kind_fn)(portapy_runtime, portapy_value, portapy_value_kind *);
typedef portapy_status (ABI_CALL *as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *release_fn)(portapy_runtime, portapy_value);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { fprintf(stderr, "missing symbol: %s\n", name); return 10; }

static int execute(exec_fn function, portapy_runtime runtime, const char *source) {
    return function(runtime, (const uint8_t *)source, strlen(source), NULL, 0) == PORTAPY_OK;
}

static int execute_status(exec_fn function, portapy_runtime runtime, const char *source, portapy_status expected) {
    return function(runtime, (const uint8_t *)source, strlen(source), NULL, 0) == expected;
}

static int evaluate_i64(eval_fn function, as_i64_fn as_i64, release_fn release, portapy_runtime runtime, const char *source, int64_t expected) {
    portapy_value value = PORTAPY_NULL_VALUE;
    int64_t result = 0;
    if (function(runtime, (const uint8_t *)source, strlen(source), NULL, 0, &value) != PORTAPY_OK) return 0;
    if (as_i64(runtime, value, &result) != PORTAPY_OK || result != expected) return 0;
    return release(runtime, value) == PORTAPY_OK;
}

static int evaluate_status(eval_fn function, portapy_runtime runtime, const char *source, portapy_status expected) {
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
    RESOLVE(get_global_fn, get_global, "portapy_get_global_utf8");
    RESOLVE(get_kind_fn, get_kind, "portapy_value_get_kind");
    RESOLVE(as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    const char first[] =
        "def seven():\n"
        "    return 7\n"
        "def add(left, right):\n"
        "    total = left + right\n"
        "    return total\n"
        "answer = add(20, 22)\n";
    if (!execute(exec_utf8, runtime, first)) return 13;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "seven()", 7)) return 14;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "answer", 42)) return 15;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "add(3, 4)", 7)) return 16;

    portapy_value callable = PORTAPY_NULL_VALUE;
    portapy_value_kind kind = PORTAPY_VALUE_NONE;
    if (get_global(runtime, (const uint8_t *)"add", 3, &callable) != PORTAPY_OK) return 17;
    if (get_kind(runtime, callable, &kind) != PORTAPY_OK || kind != PORTAPY_VALUE_CALLABLE) return 18;
    if (release(runtime, callable) != PORTAPY_OK) return 19;

    const char nested[] =
        "def double(value):\n"
        "    return value * 2\n"
        "nested_answer = add(double(10), double(11))\n";
    if (!execute(exec_utf8, runtime, nested)) return 20;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "nested_answer", 42)) return 21;

    const char control[] =
        "def classify(value):\n"
        "    if value == 0:\n"
        "        return 100\n"
        "    else:\n"
        "        total = 0\n"
        "        current = 0\n"
        "        while current < value:\n"
        "            current += 1\n"
        "            if current == 2:\n"
        "                continue\n"
        "            total += current\n"
        "            if total > 6:\n"
        "                break\n"
        "        return total\n"
        "control_zero = classify(0)\n"
        "control_small = classify(3)\n"
        "control_large = classify(5)\n";
    if (!execute(exec_utf8, runtime, control)) return 22;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "control_zero", 100)) return 23;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "control_small", 4)) return 24;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "control_large", 8)) return 25;

    const char arguments[] =
        "def combine(left, right=2, scale=3):\n"
        "    return (left + right) * scale\n"
        "defaulted = combine(12)\n"
        "mixed = combine(10, scale=4)\n"
        "reordered = combine(scale=2, left=18, right=3)\n"
        "nested_default = combine(combine(1), scale=2)\n";
    if (!execute(exec_utf8, runtime, arguments)) return 26;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "defaulted", 42)) return 27;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "mixed", 48)) return 28;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "reordered", 42)) return 29;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "nested_default", 22)) return 30;
    if (!evaluate_status(eval_utf8, runtime, "combine()", PORTAPY_TYPE_ERROR)) return 31;
    if (!evaluate_status(eval_utf8, runtime, "combine(1, left=2)", PORTAPY_TYPE_ERROR)) return 32;
    if (!evaluate_status(eval_utf8, runtime, "combine(1, unknown=2)", PORTAPY_TYPE_ERROR)) return 33;
    if (!evaluate_status(eval_utf8, runtime, "combine(left=1, 2)", PORTAPY_COMPILE_ERROR)) return 34;

    const char capture[] =
        "seed = 3\n"
        "def captured(value=seed + 2):\n"
        "    return value * 2\n"
        "seed = 20\n"
        "captured_result = captured()\n"
        "explicit_result = captured(7)\n"
        "def stable(value=6):\n"
        "    return value\n";
    if (!execute(exec_utf8, runtime, capture)) return 35;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "captured_result", 10)) return 36;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "explicit_result", 14)) return 37;

    const char redefine[] =
        "seed = 9\n"
        "def captured(value=seed):\n"
        "    return value + 1\n"
        "seed = 100\n";
    if (!execute(exec_utf8, runtime, redefine)) return 38;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "captured()", 10)) return 39;

    const char invalid_redefinition[] =
        "def stable(value=missing_default):\n"
        "    return value + 100\n";
    if (!execute_status(exec_utf8, runtime, invalid_redefinition, PORTAPY_NOT_FOUND)) return 40;
    if (!evaluate_i64(eval_utf8, as_i64, release, runtime, "stable()", 6)) return 41;

    portapy_value missing = PORTAPY_NULL_VALUE;
    if (get_global(runtime, (const uint8_t *)"total", 5, &missing) != PORTAPY_NOT_FOUND) return 42;
    if (get_global(runtime, (const uint8_t *)"current", 7, &missing) != PORTAPY_NOT_FOUND) return 43;
    if (runtime_destroy(runtime) != PORTAPY_OK) return 44;
    puts("native-functions: ok");
    return 0;
}
