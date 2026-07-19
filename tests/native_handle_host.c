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
typedef portapy_status (ABI_CALL *exec_utf8_fn)(
    portapy_runtime,
    const uint8_t *,
    size_t,
    const uint8_t *,
    size_t
);
typedef portapy_status (ABI_CALL *eval_utf8_fn)(
    portapy_runtime,
    const uint8_t *,
    size_t,
    const uint8_t *,
    size_t,
    portapy_value *
);
typedef portapy_status (ABI_CALL *get_global_utf8_fn)(
    portapy_runtime,
    const uint8_t *,
    size_t,
    portapy_value *
);
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
    RESOLVE(exec_utf8_fn, exec_utf8, "portapy_exec_utf8");
    RESOLVE(eval_utf8_fn, eval_utf8, "portapy_eval_utf8");
    RESOLVE(get_global_utf8_fn, get_global_utf8, "portapy_get_global_utf8");
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

    const uint8_t expression[] = {'1', ' ', '+', ' ', '2', ' ', '*', ' ', '3'};
    portapy_value evaluated = PORTAPY_NULL_VALUE;
    if (eval_utf8(first, expression, sizeof(expression), NULL, 0, &evaluated) != PORTAPY_OK) return 16;
    if (evaluated == PORTAPY_NULL_VALUE) return 17;
    portapy_value_kind kind = PORTAPY_VALUE_OBJECT;
    if (value_get_kind(first, evaluated, &kind) != PORTAPY_OK || kind != PORTAPY_VALUE_INT) return 18;
    int64_t number = 0;
    if (value_as_i64(first, evaluated, &number) != PORTAPY_OK || number != 7) return 19;
    if (value_as_i64(second, evaluated, &number) != PORTAPY_INVALID_HANDLE) return 20;

    const uint8_t nested[] = {' ', '-', '(', '-', '5', '+', '2', ')', '*', '+', '4', ' '};
    portapy_value nested_value = PORTAPY_NULL_VALUE;
    if (eval_utf8(first, nested, sizeof(nested), (const uint8_t *)"expr.py", 7, &nested_value) != PORTAPY_OK) return 21;
    if (value_as_i64(first, nested_value, &number) != PORTAPY_OK || number != 12) return 22;

    portapy_value failed_eval = 999;
    const uint8_t incomplete[] = {'1', ' ', '+'};
    if (eval_utf8(first, incomplete, sizeof(incomplete), NULL, 0, &failed_eval) != PORTAPY_COMPILE_ERROR) return 23;
    if (failed_eval != PORTAPY_NULL_VALUE) return 24;

    failed_eval = 999;
    const uint8_t embedded_nul[] = {'1', 0, '+', '2'};
    if (eval_utf8(first, embedded_nul, sizeof(embedded_nul), NULL, 0, &failed_eval) != PORTAPY_COMPILE_ERROR) return 25;
    if (failed_eval != PORTAPY_NULL_VALUE) return 26;

    failed_eval = 999;
    const uint8_t divide_zero[] = {'5', '/', '/', '(', '3', '-', '3', ')'};
    if (eval_utf8(first, divide_zero, sizeof(divide_zero), NULL, 0, &failed_eval) != PORTAPY_RUNTIME_ERROR) return 27;
    if (failed_eval != PORTAPY_NULL_VALUE) return 28;

    if (eval_utf8(first, expression, sizeof(expression), NULL, 1, &failed_eval) != PORTAPY_INVALID_ARGUMENT) return 29;
    if (eval_utf8(first, NULL, 0, NULL, 0, &failed_eval) != PORTAPY_INVALID_ARGUMENT) return 30;
    if (eval_utf8(first, expression, sizeof(expression), NULL, 0, NULL) != PORTAPY_INVALID_ARGUMENT) return 31;

    const uint8_t assignment[] = {'a', 'n', 's', 'w', 'e', 'r', ' ', '=', ' ', '6', ' ', '*', ' ', '7'};
    if (exec_utf8(first, assignment, sizeof(assignment), NULL, 0) != PORTAPY_OK) return 32;

    const uint8_t answer_name[] = {'a', 'n', 's', 'w', 'e', 'r'};
    portapy_value old_answer = PORTAPY_NULL_VALUE;
    if (get_global_utf8(first, answer_name, sizeof(answer_name), &old_answer) != PORTAPY_OK) return 33;
    if (old_answer == PORTAPY_NULL_VALUE) return 34;
    if (value_as_i64(first, old_answer, &number) != PORTAPY_OK || number != 42) return 35;

    const uint8_t global_expression[] = {'a', 'n', 's', 'w', 'e', 'r', ' ', '+', ' ', '8'};
    portapy_value global_eval = PORTAPY_NULL_VALUE;
    if (eval_utf8(first, global_expression, sizeof(global_expression), NULL, 0, &global_eval) != PORTAPY_OK) return 36;
    if (value_as_i64(first, global_eval, &number) != PORTAPY_OK || number != 50) return 37;

    portapy_value missing = 999;
    if (get_global_utf8(second, answer_name, sizeof(answer_name), &missing) != PORTAPY_NOT_FOUND) return 38;
    if (missing != PORTAPY_NULL_VALUE) return 39;

    const uint8_t rebind[] = {
        'a', 'n', 's', 'w', 'e', 'r', ' ', '=', ' ',
        'a', 'n', 's', 'w', 'e', 'r', ' ', '+', ' ', '1'
    };
    if (exec_utf8(first, rebind, sizeof(rebind), (const uint8_t *)"state.py", 8) != PORTAPY_OK) return 40;
    portapy_value new_answer = PORTAPY_NULL_VALUE;
    if (get_global_utf8(first, answer_name, sizeof(answer_name), &new_answer) != PORTAPY_OK) return 41;
    if (new_answer == old_answer) return 42;
    if (value_as_i64(first, old_answer, &number) != PORTAPY_OK || number != 42) return 43;
    if (value_as_i64(first, new_answer, &number) != PORTAPY_OK || number != 43) return 44;

    const uint8_t failed_rebind[] = {
        'a', 'n', 's', 'w', 'e', 'r', ' ', '=', ' ', '5', ' ', '/', '/', ' ', '0'
    };
    if (exec_utf8(first, failed_rebind, sizeof(failed_rebind), NULL, 0) != PORTAPY_RUNTIME_ERROR) return 45;
    portapy_value unchanged = PORTAPY_NULL_VALUE;
    if (get_global_utf8(first, answer_name, sizeof(answer_name), &unchanged) != PORTAPY_OK) return 46;
    if (value_as_i64(first, unchanged, &number) != PORTAPY_OK || number != 43) return 47;

    const uint8_t bad_assignment[] = {'a', 'n', 's', 'w', 'e', 'r', 0, '=', '1'};
    if (exec_utf8(first, bad_assignment, sizeof(bad_assignment), NULL, 0) != PORTAPY_COMPILE_ERROR) return 48;
    if (exec_utf8(first, assignment, sizeof(assignment), NULL, 1) != PORTAPY_INVALID_ARGUMENT) return 49;
    if (exec_utf8(first, NULL, 0, NULL, 0) != PORTAPY_INVALID_ARGUMENT) return 50;

    portapy_value bad_global = 999;
    const uint8_t bad_name[] = {'a', 0, 'b'};
    if (get_global_utf8(first, bad_name, sizeof(bad_name), &bad_global) != PORTAPY_INVALID_ARGUMENT) return 51;
    if (bad_global != PORTAPY_NULL_VALUE) return 52;
    if (get_global_utf8(first, answer_name, sizeof(answer_name), NULL) != PORTAPY_INVALID_ARGUMENT) return 53;

    portapy_value failed = 999;
    if (value_from_none(PORTAPY_NULL_RUNTIME, &failed) != PORTAPY_INVALID_HANDLE) return 54;
    if (failed != PORTAPY_NULL_VALUE) return 55;

    portapy_value none_value = PORTAPY_NULL_VALUE;
    if (value_from_none(first, &none_value) != PORTAPY_OK || none_value == 0) return 56;
    if (value_get_kind(first, none_value, &kind) != PORTAPY_OK) return 57;
    if (kind != PORTAPY_VALUE_NONE) return 58;
    int truth = -1;
    if (value_as_bool(first, none_value, &truth) != PORTAPY_TYPE_ERROR) return 59;

    portapy_value true_value = PORTAPY_NULL_VALUE;
    if (value_from_bool(first, 27, &true_value) != PORTAPY_OK || true_value == 0) return 60;
    if (value_get_kind(first, true_value, &kind) != PORTAPY_OK) return 61;
    if (kind != PORTAPY_VALUE_BOOL) return 62;
    truth = 0;
    if (value_as_bool(first, true_value, &truth) != PORTAPY_OK || truth != 1) return 63;

    portapy_value false_value = PORTAPY_NULL_VALUE;
    if (value_from_bool(first, 0, &false_value) != PORTAPY_OK || false_value == 0) return 64;
    truth = 1;
    if (value_as_bool(first, false_value, &truth) != PORTAPY_OK || truth != 0) return 65;
    if (value_as_bool(second, false_value, &truth) != PORTAPY_INVALID_HANDLE) return 66;

    portapy_value integer_value = PORTAPY_NULL_VALUE;
    if (value_from_i64(first, -42, &integer_value) != PORTAPY_OK || integer_value == 0) return 67;
    if (value_get_kind(first, integer_value, &kind) != PORTAPY_OK) return 68;
    if (kind != PORTAPY_VALUE_INT) return 69;
    if (value_as_i64(first, integer_value, &number) != PORTAPY_OK || number != -42) return 70;

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
        if (value_from_f64(first, input.value, &float_values[index]) != PORTAPY_OK) return 71;
        if (float_values[index] == PORTAPY_NULL_VALUE) return 72;
        if (value_get_kind(first, float_values[index], &kind) != PORTAPY_OK) return 73;
        if (kind != PORTAPY_VALUE_FLOAT) return 74;
        if (value_as_f64(first, float_values[index], &output.value) != PORTAPY_OK) return 75;
        if (output.bits != float_patterns[index]) return 76;
    }
    float_bits wrong_type = {0};
    if (value_as_f64(first, integer_value, &wrong_type.value) != PORTAPY_TYPE_ERROR) return 77;

    if (value_as_i64(second, integer_value, &number) != PORTAPY_INVALID_HANDLE) return 78;
    if (value_retain(first, integer_value) != PORTAPY_OK) return 79;
    if (value_release(first, integer_value) != PORTAPY_OK) return 80;
    if (value_as_i64(first, integer_value, &number) != PORTAPY_OK || number != -42) return 81;
    if (value_release(first, integer_value) != PORTAPY_OK) return 82;
    if (value_as_i64(first, integer_value, &number) != PORTAPY_INVALID_HANDLE) return 83;

    if (value_release(first, evaluated) != PORTAPY_OK) return 84;
    if (value_release(first, nested_value) != PORTAPY_OK) return 85;
    if (value_release(first, old_answer) != PORTAPY_OK) return 86;
    if (value_release(first, new_answer) != PORTAPY_OK) return 87;
    if (value_release(first, unchanged) != PORTAPY_OK) return 88;
    if (value_release(first, global_eval) != PORTAPY_OK) return 89;
    if (value_release(first, none_value) != PORTAPY_OK) return 90;
    if (value_release(first, true_value) != PORTAPY_OK) return 91;
    if (value_release(first, false_value) != PORTAPY_OK) return 92;
    for (size_t index = 0; index < 3; ++index) {
        if (value_release(first, float_values[index]) != PORTAPY_OK) return 93;
    }
    if (runtime_destroy(first) != PORTAPY_OK) return 94;
    if (runtime_destroy(first) != PORTAPY_INVALID_HANDLE) return 95;
    if (runtime_destroy(second) != PORTAPY_OK) return 96;

    printf("opaque-floats: ok\n");
    return 0;
}
