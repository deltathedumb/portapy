#include "portapy.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

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

typedef union float_bits {
    double value;
    uint64_t bits;
} float_bits;

typedef portapy_status (ABI_CALL *initialize_fn)(void);
typedef uint32_t (ABI_CALL *abi_version_fn)(void);
typedef portapy_status (ABI_CALL *runtime_create_fn)(const portapy_config *, portapy_runtime *);
typedef portapy_status (ABI_CALL *runtime_destroy_fn)(portapy_runtime);
typedef portapy_status (ABI_CALL *value_from_none_fn)(portapy_runtime, portapy_value *);
typedef portapy_status (ABI_CALL *value_from_bool_fn)(portapy_runtime, int, portapy_value *);
typedef portapy_status (ABI_CALL *value_from_i64_fn)(portapy_runtime, int64_t, portapy_value *);
typedef portapy_status (ABI_CALL *value_from_f64_fn)(portapy_runtime, double, portapy_value *);
typedef portapy_status (ABI_CALL *value_get_kind_fn)(portapy_runtime, portapy_value, portapy_value_kind *);
typedef portapy_status (ABI_CALL *value_as_bool_fn)(portapy_runtime, portapy_value, int *);
typedef portapy_status (ABI_CALL *value_as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *value_as_f64_fn)(portapy_runtime, portapy_value, double *);
typedef portapy_status (ABI_CALL *value_lifetime_fn)(portapy_runtime, portapy_value);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { \
        fprintf(stderr, "missing symbol: %s\n", name); \
        return 10; \
    }

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: native_handle_host <library>\n");
        return 2;
    }
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) {
        fprintf(stderr, "failed to load %s\n", argv[1]);
        return 3;
    }

    RESOLVE(initialize_fn, initialize, "portapy_library_initialize");
    RESOLVE(abi_version_fn, abi_version, "portapy_abi_version");
    RESOLVE(runtime_create_fn, runtime_create, "portapy_runtime_create");
    RESOLVE(runtime_destroy_fn, runtime_destroy, "portapy_runtime_destroy");
    RESOLVE(value_from_none_fn, value_from_none, "portapy_value_from_none");
    RESOLVE(value_from_bool_fn, value_from_bool, "portapy_value_from_bool");
    RESOLVE(value_from_i64_fn, value_from_i64, "portapy_value_from_i64");
    RESOLVE(value_from_f64_fn, value_from_f64, "portapy_value_from_f64");
    RESOLVE(value_get_kind_fn, value_get_kind, "portapy_value_get_kind");
    RESOLVE(value_as_bool_fn, value_as_bool, "portapy_value_as_bool");
    RESOLVE(value_as_i64_fn, value_as_i64, "portapy_value_as_i64");
    RESOLVE(value_as_f64_fn, value_as_f64, "portapy_value_as_f64");
    RESOLVE(value_lifetime_fn, value_retain, "portapy_value_retain");
    RESOLVE(value_lifetime_fn, value_release, "portapy_value_release");

    if (initialize() != PORTAPY_OK) return 11;
    if (abi_version() != PORTAPY_ABI_VERSION) return 12;

    portapy_config bad = {0};
    bad.struct_size = sizeof(bad);
    bad.abi_version = PORTAPY_ABI_VERSION + 1;
    portapy_runtime ignored = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&bad, &ignored) != PORTAPY_ABI_MISMATCH) return 13;

    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime first = PORTAPY_NULL_RUNTIME;
    portapy_runtime second = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &first) != PORTAPY_OK || first == 0) return 14;
    if (runtime_create(&config, &second) != PORTAPY_OK || second == 0 || second == first) return 15;

    portapy_value failed = 999;
    if (value_from_none(PORTAPY_NULL_RUNTIME, &failed) != PORTAPY_INVALID_HANDLE) return 16;
    if (failed != PORTAPY_NULL_VALUE) return 17;

    portapy_value none_value = PORTAPY_NULL_VALUE;
    if (value_from_none(first, &none_value) != PORTAPY_OK || none_value == 0) return 18;
    portapy_value_kind kind = PORTAPY_VALUE_OBJECT;
    if (value_get_kind(first, none_value, &kind) != PORTAPY_OK) return 19;
    if (kind != PORTAPY_VALUE_NONE) return 20;
    int truth = -1;
    if (value_as_bool(first, none_value, &truth) != PORTAPY_TYPE_ERROR) return 21;

    portapy_value true_value = PORTAPY_NULL_VALUE;
    if (value_from_bool(first, 27, &true_value) != PORTAPY_OK || true_value == 0) return 22;
    if (value_get_kind(first, true_value, &kind) != PORTAPY_OK) return 23;
    if (kind != PORTAPY_VALUE_BOOL) return 24;
    truth = 0;
    if (value_as_bool(first, true_value, &truth) != PORTAPY_OK || truth != 1) return 25;

    portapy_value false_value = PORTAPY_NULL_VALUE;
    if (value_from_bool(first, 0, &false_value) != PORTAPY_OK || false_value == 0) return 26;
    truth = 1;
    if (value_as_bool(first, false_value, &truth) != PORTAPY_OK || truth != 0) return 27;
    if (value_as_bool(second, false_value, &truth) != PORTAPY_INVALID_HANDLE) return 28;

    portapy_value integer_value = PORTAPY_NULL_VALUE;
    if (value_from_i64(first, -42, &integer_value) != PORTAPY_OK || integer_value == 0) return 29;
    if (value_get_kind(first, integer_value, &kind) != PORTAPY_OK) return 30;
    if (kind != PORTAPY_VALUE_INT) return 31;
    int64_t number = 0;
    if (value_as_i64(first, integer_value, &number) != PORTAPY_OK || number != -42) return 32;

    const uint64_t float_patterns[] = {
        UINT64_C(0x3ff8000000000000),
        UINT64_C(0x8000000000000000),
        UINT64_C(0x7ff8000000001234)
    };
    portapy_value float_values[3] = {
        PORTAPY_NULL_VALUE,
        PORTAPY_NULL_VALUE,
        PORTAPY_NULL_VALUE
    };
    for (size_t index = 0; index < 3; ++index) {
        float_bits input = {0};
        float_bits output = {0};
        input.bits = float_patterns[index];
        if (value_from_f64(first, input.value, &float_values[index]) != PORTAPY_OK) return 33;
        if (float_values[index] == PORTAPY_NULL_VALUE) return 34;
        if (value_get_kind(first, float_values[index], &kind) != PORTAPY_OK) return 35;
        if (kind != PORTAPY_VALUE_FLOAT) return 36;
        if (value_as_f64(first, float_values[index], &output.value) != PORTAPY_OK) return 37;
        if (output.bits != float_patterns[index]) return 38;
    }
    float_bits wrong_type = {0};
    if (value_as_f64(first, integer_value, &wrong_type.value) != PORTAPY_TYPE_ERROR) return 39;

    if (value_as_i64(second, integer_value, &number) != PORTAPY_INVALID_HANDLE) return 40;
    if (value_retain(first, integer_value) != PORTAPY_OK) return 41;
    if (value_release(first, integer_value) != PORTAPY_OK) return 42;
    if (value_as_i64(first, integer_value, &number) != PORTAPY_OK || number != -42) return 43;
    if (value_release(first, integer_value) != PORTAPY_OK) return 44;
    if (value_as_i64(first, integer_value, &number) != PORTAPY_INVALID_HANDLE) return 45;

    if (value_release(first, none_value) != PORTAPY_OK) return 46;
    if (value_release(first, true_value) != PORTAPY_OK) return 47;
    if (value_release(first, false_value) != PORTAPY_OK) return 48;
    for (size_t index = 0; index < 3; ++index) {
        if (value_release(first, float_values[index]) != PORTAPY_OK) return 49;
    }
    if (runtime_destroy(first) != PORTAPY_OK) return 50;
    if (runtime_destroy(first) != PORTAPY_INVALID_HANDLE) return 51;
    if (runtime_destroy(second) != PORTAPY_OK) return 52;

    printf("opaque-floats: ok\n");
    return 0;
}
