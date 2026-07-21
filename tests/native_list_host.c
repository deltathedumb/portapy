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
typedef portapy_status (ABI_CALL *from_list_fn)(portapy_runtime, const portapy_value *, size_t, portapy_value *);
typedef portapy_status (ABI_CALL *list_size_fn)(portapy_runtime, portapy_value, size_t *);
typedef portapy_status (ABI_CALL *list_item_fn)(portapy_runtime, portapy_value, size_t, portapy_value *);
typedef portapy_status (ABI_CALL *list_set_fn)(portapy_runtime, portapy_value, size_t, portapy_value);
typedef portapy_status (ABI_CALL *list_append_fn)(portapy_runtime, portapy_value, portapy_value);
typedef portapy_status (ABI_CALL *get_kind_fn)(portapy_runtime, portapy_value, portapy_value_kind *);
typedef portapy_status (ABI_CALL *as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
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
    RESOLVE(from_list_fn, from_list, "portapy_value_from_list");
    RESOLVE(list_size_fn, list_size, "portapy_list_get_size");
    RESOLVE(list_item_fn, list_item, "portapy_list_get_item");
    RESOLVE(list_set_fn, list_set, "portapy_list_set_item");
    RESOLVE(list_append_fn, list_append, "portapy_list_append");
    RESOLVE(get_kind_fn, get_kind, "portapy_value_get_kind");
    RESOLVE(as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    portapy_value left = PORTAPY_NULL_VALUE;
    portapy_value right = PORTAPY_NULL_VALUE;
    if (from_i64(runtime, 18, &left) != PORTAPY_OK) return 13;
    if (from_i64(runtime, 24, &right) != PORTAPY_OK) return 14;
    portapy_value items[2] = {left, right};
    portapy_value values = PORTAPY_NULL_VALUE;
    if (from_list(runtime, items, 2, &values) != PORTAPY_OK) return 15;
    if (release(runtime, left) != PORTAPY_OK) return 16;
    if (release(runtime, right) != PORTAPY_OK) return 17;

    portapy_value_kind kind = PORTAPY_VALUE_NONE;
    size_t size = 0;
    if (get_kind(runtime, values, &kind) != PORTAPY_OK || kind != PORTAPY_VALUE_LIST) return 18;
    if (list_size(runtime, values, &size) != PORTAPY_OK || size != 2) return 19;

    portapy_value item = PORTAPY_NULL_VALUE;
    if (list_item(runtime, values, 0, &item) != PORTAPY_OK) return 20;
    if (!expect_i64(as_i64, release, runtime, item, 18)) return 21;

    portapy_value replacement = PORTAPY_NULL_VALUE;
    if (from_i64(runtime, 20, &replacement) != PORTAPY_OK) return 22;
    if (list_set(runtime, values, 0, replacement) != PORTAPY_OK) return 23;
    if (release(runtime, replacement) != PORTAPY_OK) return 24;
    if (list_item(runtime, values, 0, &item) != PORTAPY_OK) return 25;
    if (!expect_i64(as_i64, release, runtime, item, 20)) return 26;

    portapy_value appended = PORTAPY_NULL_VALUE;
    if (from_i64(runtime, 22, &appended) != PORTAPY_OK) return 27;
    if (list_append(runtime, values, appended) != PORTAPY_OK) return 28;
    if (release(runtime, appended) != PORTAPY_OK) return 29;
    if (list_size(runtime, values, &size) != PORTAPY_OK || size != 3) return 30;
    if (list_item(runtime, values, 2, &item) != PORTAPY_OK) return 31;
    if (!expect_i64(as_i64, release, runtime, item, 22)) return 32;

    portapy_value outer = PORTAPY_NULL_VALUE;
    portapy_value nested_items[1] = {values};
    if (from_list(runtime, nested_items, 1, &outer) != PORTAPY_OK) return 33;
    if (release(runtime, values) != PORTAPY_OK) return 34;
    portapy_value retained = PORTAPY_NULL_VALUE;
    if (list_item(runtime, outer, 0, &retained) != PORTAPY_OK) return 35;
    if (release(runtime, outer) != PORTAPY_OK) return 36;
    if (list_item(runtime, retained, 1, &item) != PORTAPY_OK) return 37;
    if (!expect_i64(as_i64, release, runtime, item, 24)) return 38;
    if (release(runtime, retained) != PORTAPY_OK) return 39;

    const char expression[] = "[18, [1, 2], 24]";
    portapy_value evaluated = PORTAPY_NULL_VALUE;
    if (eval_utf8(runtime, (const uint8_t *)expression, strlen(expression), NULL, 0, &evaluated) != PORTAPY_OK) return 40;
    if (list_size(runtime, evaluated, &size) != PORTAPY_OK || size != 3) return 41;
    portapy_value nested = PORTAPY_NULL_VALUE;
    if (list_item(runtime, evaluated, 1, &nested) != PORTAPY_OK) return 42;
    if (list_item(runtime, nested, 1, &item) != PORTAPY_OK) return 43;
    if (!expect_i64(as_i64, release, runtime, item, 2)) return 44;
    if (release(runtime, nested) != PORTAPY_OK) return 45;
    if (release(runtime, evaluated) != PORTAPY_OK) return 46;

    portapy_value empty = PORTAPY_NULL_VALUE;
    if (from_list(runtime, NULL, 0, &empty) != PORTAPY_OK) return 47;
    if (list_size(runtime, empty, &size) != PORTAPY_OK || size != 0) return 48;
    if (list_item(runtime, empty, 0, &item) != PORTAPY_INVALID_ARGUMENT) return 49;
    if (release(runtime, empty) != PORTAPY_OK) return 50;

    if (runtime_destroy(runtime) != PORTAPY_OK) return 51;
    puts("native-lists: ok");
    return 0;
}
