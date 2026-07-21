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
typedef portapy_status (ABI_CALL *new_fn)(portapy_environment *);
typedef portapy_status (ABI_CALL *destroy_fn)(portapy_environment);
typedef portapy_status (ABI_CALL *execute_fn)(portapy_environment, const char *);
typedef portapy_status (ABI_CALL *evaluate_fn)(portapy_environment, const char *, portapy_value *);
typedef portapy_status (ABI_CALL *add_callable_fn)(
    portapy_environment,
    const uint8_t *,
    size_t,
    portapy_direct_call_handler,
    void *,
    uint32_t
);
typedef portapy_status (ABI_CALL *as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *from_i64_fn)(portapy_runtime, int64_t, portapy_value *);
typedef portapy_status (ABI_CALL *release_fn)(portapy_runtime, portapy_value);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { fprintf(stderr, "missing symbol: %s\n", name); return 10; }

typedef struct callback_context {
    as_i64_fn as_i64;
    from_i64_fn from_i64;
} callback_context;

static portapy_status ABI_CALL host_offset(
    void *opaque,
    portapy_environment environment,
    const portapy_value *arguments,
    size_t argument_count,
    portapy_value *out_result
) {
    callback_context *context = (callback_context *)opaque;
    int64_t value = 0;
    if (context == NULL || out_result == NULL || argument_count != 1) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    portapy_status status = context->as_i64(environment, arguments[0], &value);
    if (status != PORTAPY_OK) return status;
    return context->from_i64(environment, value + 2, out_result);
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) return 3;

    RESOLVE(initialize_fn, initialize, "portapy_library_initialize");
    RESOLVE(new_fn, create_environment, "portapy_new");
    RESOLVE(destroy_fn, destroy_environment, "portapy_destroy");
    RESOLVE(execute_fn, execute, "portapy_execute");
    RESOLVE(evaluate_fn, evaluate, "portapy_evaluate");
    RESOLVE(add_callable_fn, add_callable, "portapy_add_callable_utf8");
    RESOLVE(as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(from_i64_fn, from_i64, "portapy_value_from_i64");
    RESOLVE(release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_environment environment = PORTAPY_NULL_ENVIRONMENT;
    if (create_environment(&environment) != PORTAPY_OK) return 12;

    callback_context context = {as_i64, from_i64};
    const uint8_t callback_name[] = "host_offset";
    if (add_callable(
        environment,
        callback_name,
        sizeof(callback_name) - 1,
        host_offset,
        &context,
        PORTAPY_BINDING_REPLACE
    ) != PORTAPY_OK) return 13;

    const char *source =
        "class Box:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "def make_counter(start):\n"
        "    value = start\n"
        "    def step():\n"
        "        nonlocal value\n"
        "        value = host_offset(value)\n"
        "        return value\n"
        "    return step\n"
        "counter = make_counter(38)\n"
        "boxed = Box(counter())\n";
    if (execute(environment, source) != PORTAPY_OK) return 14;

    portapy_value result = PORTAPY_NULL_VALUE;
    int64_t value = 0;
    if (evaluate(environment, "boxed.value + 2", &result) != PORTAPY_OK) return 15;
    if (as_i64(environment, result, &value) != PORTAPY_OK || value != 42) return 16;
    if (release(environment, result) != PORTAPY_OK) return 17;

    if (execute(environment, "boxed.value = host_offset(boxed.value)\n") != PORTAPY_OK) return 18;
    result = PORTAPY_NULL_VALUE;
    if (evaluate(environment, "boxed.value", &result) != PORTAPY_OK) return 19;
    if (as_i64(environment, result, &value) != PORTAPY_OK || value != 42) return 20;
    if (release(environment, result) != PORTAPY_OK) return 21;

    if (destroy_environment(environment) != PORTAPY_OK) return 22;
    puts("native-full-environment: ok");
    return 0;
}
