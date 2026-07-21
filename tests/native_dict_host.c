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
typedef portapy_status (ABI_CALL *from_dict_fn)(portapy_runtime, portapy_value *);
typedef portapy_status (ABI_CALL *dict_set_fn)(portapy_runtime, portapy_value, const uint8_t *, size_t, portapy_value);
typedef portapy_status (ABI_CALL *dict_size_fn)(portapy_runtime, portapy_value, size_t *);
typedef portapy_status (ABI_CALL *dict_key_fn)(portapy_runtime, portapy_value, size_t, uint8_t *, size_t, size_t *);
typedef portapy_status (ABI_CALL *dict_item_fn)(portapy_runtime, portapy_value, const uint8_t *, size_t, portapy_value *);
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

static int expect_key(
    dict_key_fn key_copy,
    portapy_runtime runtime,
    portapy_value value,
    size_t index,
    const char *expected
) {
    size_t required = 0;
    if (key_copy(runtime, value, index, NULL, 0, &required) != PORTAPY_INVALID_ARGUMENT) return 0;
    if (required != strlen(expected)) return 0;
    uint8_t buffer[64] = {0};
    if (required > sizeof(buffer)) return 0;
    if (key_copy(runtime, value, index, buffer, sizeof(buffer), &required) != PORTAPY_OK) return 0;
    return memcmp(buffer, expected, required) == 0;
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
    RESOLVE(from_dict_fn, from_dict, "portapy_value_from_dict");
    RESOLVE(dict_set_fn, dict_set, "portapy_dict_set_utf8");
    RESOLVE(dict_size_fn, dict_size, "portapy_dict_get_size");
    RESOLVE(dict_key_fn, key_copy, "portapy_dict_key_copy_utf8");
    RESOLVE(dict_item_fn, dict_item, "portapy_dict_get_item_utf8");
    RESOLVE(get_kind_fn, get_kind, "portapy_value_get_kind");
    RESOLVE(as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(release_fn, release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    portapy_value mapping = PORTAPY_NULL_VALUE;
    portapy_value left = PORTAPY_NULL_VALUE;
    portapy_value right = PORTAPY_NULL_VALUE;
    if (from_dict(runtime, &mapping) != PORTAPY_OK) return 13;
    if (from_i64(runtime, 18, &left) != PORTAPY_OK) return 14;
    if (from_i64(runtime, 24, &right) != PORTAPY_OK) return 15;
    if (dict_set(runtime, mapping, (const uint8_t *)"left", 4, left) != PORTAPY_OK) return 16;
    if (dict_set(runtime, mapping, (const uint8_t *)"right", 5, right) != PORTAPY_OK) return 17;
    if (release(runtime, left) != PORTAPY_OK) return 18;
    if (release(runtime, right) != PORTAPY_OK) return 19;

    portapy_value_kind kind = PORTAPY_VALUE_NONE;
    size_t size = 0;
    if (get_kind(runtime, mapping, &kind) != PORTAPY_OK || kind != PORTAPY_VALUE_DICT) return 20;
    if (dict_size(runtime, mapping, &size) != PORTAPY_OK || size != 2) return 21;
    if (!expect_key(key_copy, runtime, mapping, 0, "left")) return 22;
    if (!expect_key(key_copy, runtime, mapping, 1, "right")) return 23;

    portapy_value item = PORTAPY_NULL_VALUE;
    if (dict_item(runtime, mapping, (const uint8_t *)"left", 4, &item) != PORTAPY_OK) return 24;
    if (!expect_i64(as_i64, release, runtime, item, 18)) return 25;
    if (dict_item(runtime, mapping, (const uint8_t *)"missing", 7, &item) != PORTAPY_NOT_FOUND) return 26;

    portapy_value replacement = PORTAPY_NULL_VALUE;
    if (from_i64(runtime, 20, &replacement) != PORTAPY_OK) return 27;
    if (dict_set(runtime, mapping, (const uint8_t *)"left", 4, replacement) != PORTAPY_OK) return 28;
    if (release(runtime, replacement) != PORTAPY_OK) return 29;
    if (dict_size(runtime, mapping, &size) != PORTAPY_OK || size != 2) return 30;
    if (dict_item(runtime, mapping, (const uint8_t *)"left", 4, &item) != PORTAPY_OK) return 31;
    if (!expect_i64(as_i64, release, runtime, item, 20)) return 32;

    portapy_value outer = PORTAPY_NULL_VALUE;
    if (from_dict(runtime, &outer) != PORTAPY_OK) return 33;
    if (dict_set(runtime, outer, (const uint8_t *)"inner", 5, mapping) != PORTAPY_OK) return 34;
    if (release(runtime, mapping) != PORTAPY_OK) return 35;
    portapy_value retained = PORTAPY_NULL_VALUE;
    if (dict_item(runtime, outer, (const uint8_t *)"inner", 5, &retained) != PORTAPY_OK) return 36;
    if (release(runtime, outer) != PORTAPY_OK) return 37;
    if (dict_item(runtime, retained, (const uint8_t *)"right", 5, &item) != PORTAPY_OK) return 38;
    if (!expect_i64(as_i64, release, runtime, item, 24)) return 39;
    if (release(runtime, retained) != PORTAPY_OK) return 40;

    const char source[] =
        "def capture(**values):\n"
        "    return values\n"
        "capture(left=18, right=24)";
    portapy_value evaluated = PORTAPY_NULL_VALUE;
    if (eval_utf8(runtime, (const uint8_t *)source, strlen(source), NULL, 0, &evaluated) != PORTAPY_OK) return 41;
    if (dict_size(runtime, evaluated, &size) != PORTAPY_OK || size != 2) return 42;
    if (dict_item(runtime, evaluated, (const uint8_t *)"right", 5, &item) != PORTAPY_OK) return 43;
    if (!expect_i64(as_i64, release, runtime, item, 24)) return 44;
    if (release(runtime, evaluated) != PORTAPY_OK) return 45;

    const uint8_t non_ascii[] = {0xc3, 0xa9};
    portapy_value empty = PORTAPY_NULL_VALUE;
    if (from_dict(runtime, &empty) != PORTAPY_OK) return 46;
    if (from_i64(runtime, 1, &item) != PORTAPY_OK) return 47;
    if (dict_set(runtime, empty, non_ascii, sizeof(non_ascii), item) != PORTAPY_INVALID_ARGUMENT) return 48;
    if (release(runtime, item) != PORTAPY_OK) return 49;
    if (release(runtime, empty) != PORTAPY_OK) return 50;

    if (runtime_destroy(runtime) != PORTAPY_OK) return 51;
    puts("native-dicts: ok");
    return 0;
}
