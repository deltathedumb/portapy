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
typedef portapy_status (ABI_CALL *from_callable_fn)(portapy_runtime, uint64_t, portapy_value *);
typedef portapy_status (ABI_CALL *set_attr_fn)(portapy_runtime, portapy_value, const uint8_t *, size_t, portapy_value);
typedef portapy_status (ABI_CALL *set_handler_fn)(portapy_runtime, portapy_host_call_handler, void *);
typedef portapy_status (ABI_CALL *as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *from_i64_fn)(portapy_runtime, int64_t, portapy_value *);
typedef portapy_status (ABI_CALL *release_fn)(portapy_runtime, portapy_value);

typedef struct callback_context {
    as_i64_fn as_i64;
    from_i64_fn from_i64;
} callback_context;

static portapy_status ABI_CALL dispatch(
    void *raw_context,
    portapy_runtime runtime,
    uint64_t callable_id,
    const portapy_value *arguments,
    size_t argument_count,
    portapy_value *out_result
) {
    callback_context *context = (callback_context *)raw_context;
    if (callable_id != UINT64_C(9001) || argument_count != 2 || out_result == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    int64_t left = 0;
    int64_t right = 0;
    portapy_status status = context->as_i64(runtime, arguments[0], &left);
    if (status != PORTAPY_OK) return status;
    status = context->as_i64(runtime, arguments[1], &right);
    if (status != PORTAPY_OK) return status;
    return context->from_i64(runtime, left + right, out_result);
}

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
    RESOLVE(from_callable_fn, from_callable, "portapy_value_from_host_callable");
    RESOLVE(set_attr_fn, set_attr, "portapy_host_set_attr_utf8");
    RESOLVE(set_handler_fn, set_handler, "portapy_host_set_call_handler");
    RESOLVE(as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(from_i64_fn, from_i64, "portapy_value_from_i64");
    RESOLVE(release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    callback_context context = {as_i64, from_i64};
    if (set_handler(runtime, dispatch, &context) != PORTAPY_OK) return 13;

    portapy_value math = PORTAPY_NULL_VALUE;
    portapy_value add = PORTAPY_NULL_VALUE;
    if (from_host(runtime, UINT64_C(100), &math) != PORTAPY_OK) return 14;
    if (from_callable(runtime, UINT64_C(9001), &add) != PORTAPY_OK) return 15;
    if (set_attr(runtime, math, (const uint8_t *)"add", 3, add) != PORTAPY_OK) return 16;
    if (set_global(runtime, (const uint8_t *)"math", 4, math) != PORTAPY_OK) return 17;
    if (set_global(runtime, (const uint8_t *)"add", 3, add) != PORTAPY_OK) return 18;

    const char source[] = "answer = math.add(20, 22)\nnested = add(20, add(1, 21))\n";
    if (exec_utf8(runtime, (const uint8_t *)source, strlen(source), NULL, 0) != PORTAPY_OK) return 19;

    portapy_value answer = PORTAPY_NULL_VALUE;
    portapy_value nested = PORTAPY_NULL_VALUE;
    int64_t answer_value = 0;
    int64_t nested_value = 0;
    if (get_global(runtime, (const uint8_t *)"answer", 6, &answer) != PORTAPY_OK) return 20;
    if (get_global(runtime, (const uint8_t *)"nested", 6, &nested) != PORTAPY_OK) return 21;
    if (as_i64(runtime, answer, &answer_value) != PORTAPY_OK || answer_value != 42) return 22;
    if (as_i64(runtime, nested, &nested_value) != PORTAPY_OK || nested_value != 42) return 23;

    if (release(runtime, answer) != PORTAPY_OK) return 24;
    if (release(runtime, nested) != PORTAPY_OK) return 25;
    if (release(runtime, math) != PORTAPY_OK) return 26;
    if (release(runtime, add) != PORTAPY_OK) return 27;
    if (runtime_destroy(runtime) != PORTAPY_OK) return 28;

    puts("native-host-calls: ok");
    return 0;
}
