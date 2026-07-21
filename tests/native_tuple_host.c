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
typedef portapy_status (ABI_CALL *eval_fn)(portapy_runtime, const uint8_t *, size_t, const uint8_t *, size_t, portapy_value *);
typedef portapy_status (ABI_CALL *from_i64_fn)(portapy_runtime, int64_t, portapy_value *);
typedef portapy_status (ABI_CALL *from_tuple_fn)(portapy_runtime, const portapy_value *, size_t, portapy_value *);
typedef portapy_status (ABI_CALL *get_kind_fn)(portapy_runtime, portapy_value, portapy_value_kind *);
typedef portapy_status (ABI_CALL *as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *tuple_size_fn)(portapy_runtime, portapy_value, size_t *);
typedef portapy_status (ABI_CALL *tuple_item_fn)(portapy_runtime, portapy_value, size_t, portapy_value *);
typedef portapy_status (ABI_CALL *release_fn)(portapy_runtime, portapy_value);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { fprintf(stderr, "missing symbol: %s\n", name); return 10; }

static int expect_i64(
    as_i64_fn as_i64,
    release_fn release,
    portapy_runtime runtime,
    portapy_value value,
    int64_t expected
) {
    int64_t result = 0;
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
    RESOLVE(eval_fn, eval_utf8, "portapy_eval_utf8");
    RESOLVE(from_i64_fn, from_i64, "portapy_value_from_i64");
    RESOLVE(from_tuple_fn, from_tuple, "portapy_value_from_tuple");
    RESOLVE(get_kind_fn, get_kind, "portapy_value_get_kind");
    RESOLVE(as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(tuple_size_fn, tuple_size, "portapy_tuple_get_size");
    RESOLVE(tuple_item_fn, tuple_item, "portapy_tuple_get_item");
    RESOLVE(release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    portapy_value ten = PORTAPY_NULL_VALUE;
    portapy_value twenty = PORTAPY_NULL_VALUE;
    if (from_i64(runtime, 10, &ten) != PORTAPY_OK) return 13;
    if (from_i64(runtime, 20, &twenty) != PORTAPY_OK) return 14;

    portapy_value items[2] = {ten, twenty};
    portapy_value pair = PORTAPY_NULL_VALUE;
    if (from_tuple(runtime, items, 2, &pair) != PORTAPY_OK) return 15;
    if (release(runtime, ten) != PORTAPY_OK) return 16;
    if (release(runtime, twenty) != PORTAPY_OK) return 17;

    portapy_value_kind kind = PORTAPY_VALUE_NONE;
    size_t size = 0;
    if (get_kind(runtime, pair, &kind) != PORTAPY_OK || kind != PORTAPY_VALUE_TUPLE) return 18;
    if (tuple_size(runtime, pair, &size) != PORTAPY_OK || size != 2) return 19;

    portapy_value first = PORTAPY_NULL_VALUE;
    if (tuple_item(runtime, pair, 0, &first) != PORTAPY_OK) return 20;
    if (!expect_i64(as_i64, release, runtime, first, 10)) return 21;
    if (tuple_item(runtime, pair, 2, &first) != PORTAPY_INVALID_ARGUMENT) return 22;
    if (tuple_size(runtime, first, &size) != PORTAPY_INVALID_HANDLE) {
        /* first was released above, proving stale handles do not masquerade as tuples. */
        return 23;
    }

    portapy_value forty_two = PORTAPY_NULL_VALUE;
    if (from_i64(runtime, 42, &forty_two) != PORTAPY_OK) return 24;
    portapy_value nested_items[2] = {pair, forty_two};
    portapy_value nested = PORTAPY_NULL_VALUE;
    if (from_tuple(runtime, nested_items, 2, &nested) != PORTAPY_OK) return 25;
    if (release(runtime, pair) != PORTAPY_OK) return 26;
    if (release(runtime, forty_two) != PORTAPY_OK) return 27;

    portapy_value retained_pair = PORTAPY_NULL_VALUE;
    if (tuple_item(runtime, nested, 0, &retained_pair) != PORTAPY_OK) return 28;
    if (release(runtime, nested) != PORTAPY_OK) return 29;
    if (tuple_size(runtime, retained_pair, &size) != PORTAPY_OK || size != 2) return 30;
    if (tuple_item(runtime, retained_pair, 1, &first) != PORTAPY_OK) return 31;
    if (!expect_i64(as_i64, release, runtime, first, 20)) return 32;
    if (release(runtime, retained_pair) != PORTAPY_OK) return 33;

    portapy_value empty = PORTAPY_NULL_VALUE;
    if (from_tuple(runtime, NULL, 0, &empty) != PORTAPY_OK) return 34;
    if (tuple_size(runtime, empty, &size) != PORTAPY_OK || size != 0) return 35;
    if (release(runtime, empty) != PORTAPY_OK) return 36;

    const char source[] = "(1, (2, 3))";
    portapy_value evaluated = PORTAPY_NULL_VALUE;
    if (eval_utf8(runtime, (const uint8_t *)source, strlen(source), NULL, 0, &evaluated) != PORTAPY_OK) return 37;
    if (tuple_size(runtime, evaluated, &size) != PORTAPY_OK || size != 2) return 38;
    portapy_value evaluated_nested = PORTAPY_NULL_VALUE;
    if (tuple_item(runtime, evaluated, 1, &evaluated_nested) != PORTAPY_OK) return 39;
    if (tuple_item(runtime, evaluated_nested, 0, &first) != PORTAPY_OK) return 40;
    if (!expect_i64(as_i64, release, runtime, first, 2)) return 41;
    if (release(runtime, evaluated_nested) != PORTAPY_OK) return 42;
    if (release(runtime, evaluated) != PORTAPY_OK) return 43;

    if (runtime_destroy(runtime) != PORTAPY_OK) return 44;
    puts("native-tuples: ok");
    return 0;
}
