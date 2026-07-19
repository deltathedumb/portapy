#include "portapy.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <dlfcn.h>
#endif

typedef uint32_t (PORTAPY_CALL *abi_version_fn)(void);
typedef const char *(PORTAPY_CALL *version_string_fn)(void);
typedef portapy_status (PORTAPY_CALL *runtime_create_fn)(
    const portapy_config *,
    portapy_runtime **
);
typedef portapy_status (PORTAPY_CALL *runtime_destroy_fn)(portapy_runtime *);
typedef portapy_status (PORTAPY_CALL *value_from_i64_fn)(
    portapy_runtime *,
    int64_t,
    portapy_value **
);
typedef portapy_status (PORTAPY_CALL *value_retain_fn)(
    portapy_runtime *,
    portapy_value *
);
typedef portapy_status (PORTAPY_CALL *value_release_fn)(
    portapy_runtime *,
    portapy_value *
);
typedef portapy_status (PORTAPY_CALL *value_get_kind_fn)(
    portapy_runtime *,
    portapy_value *,
    portapy_value_kind *
);
typedef portapy_status (PORTAPY_CALL *value_as_i64_fn)(
    portapy_runtime *,
    portapy_value *,
    int64_t *
);

static void *load_library(const char *path) {
#if defined(_WIN32)
    return (void *)LoadLibraryA(path);
#else
    return dlopen(path, RTLD_NOW | RTLD_LOCAL);
#endif
}

static void *load_symbol(void *library, const char *name) {
#if defined(_WIN32)
    return (void *)(uintptr_t)GetProcAddress((HMODULE)library, name);
#else
    return dlsym(library, name);
#endif
}

#define LOAD_REQUIRED(type, variable, name)                                      \
    type variable = (type)(uintptr_t)load_symbol(library, name);                 \
    if (variable == NULL) {                                                      \
        fprintf(stderr, "missing required export: %s\n", name);                \
        return 4;                                                                \
    }

int main(int argc, char **argv) {
    portapy_config config = {0};
    portapy_config bad_config = {0};
    portapy_runtime *runtime = NULL;
    portapy_runtime *second_runtime = NULL;
    portapy_value *value = NULL;
    portapy_value *owned_until_destroy = NULL;
    portapy_value_kind kind = PORTAPY_VALUE_OBJECT;
    int64_t payload = 0;

    if (argc != 2) {
        fprintf(stderr, "usage: runtime_abi_host <library>\n");
        return 2;
    }

    void *library = load_library(argv[1]);
    if (library == NULL) {
        fprintf(stderr, "failed to load %s\n", argv[1]);
        return 3;
    }

    LOAD_REQUIRED(abi_version_fn, abi_version, "portapy_abi_version");
    LOAD_REQUIRED(version_string_fn, version_string, "portapy_version_string");
    LOAD_REQUIRED(runtime_create_fn, runtime_create, "portapy_runtime_create");
    LOAD_REQUIRED(runtime_destroy_fn, runtime_destroy, "portapy_runtime_destroy");
    LOAD_REQUIRED(value_from_i64_fn, value_from_i64, "portapy_value_from_i64");
    LOAD_REQUIRED(value_retain_fn, value_retain, "portapy_value_retain");
    LOAD_REQUIRED(value_release_fn, value_release, "portapy_value_release");
    LOAD_REQUIRED(value_get_kind_fn, value_get_kind, "portapy_value_get_kind");
    LOAD_REQUIRED(value_as_i64_fn, value_as_i64, "portapy_value_as_i64");

    if (abi_version() != PORTAPY_ABI_VERSION) {
        fprintf(stderr, "unexpected ABI version\n");
        return 5;
    }
    if (strncmp(version_string(), "3.14", 4) != 0) {
        fprintf(stderr, "unexpected implementation version\n");
        return 6;
    }

    bad_config.struct_size = sizeof(bad_config);
    bad_config.abi_version = PORTAPY_ABI_VERSION + 1;
    if (runtime_create(&bad_config, &runtime) != PORTAPY_ABI_MISMATCH) {
        fprintf(stderr, "ABI mismatch was not rejected\n");
        return 7;
    }
    if (runtime != NULL) {
        fprintf(stderr, "failed create wrote an output runtime\n");
        return 8;
    }

    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    if (runtime_create(&config, &runtime) != PORTAPY_OK || runtime == NULL) {
        fprintf(stderr, "runtime creation failed\n");
        return 9;
    }
    if (value_from_i64(runtime, -42, &value) != PORTAPY_OK || value == NULL) {
        fprintf(stderr, "integer value creation failed\n");
        return 10;
    }
    if (value_get_kind(runtime, value, &kind) != PORTAPY_OK ||
        kind != PORTAPY_VALUE_INT) {
        fprintf(stderr, "integer kind mismatch\n");
        return 11;
    }
    if (value_as_i64(runtime, value, &payload) != PORTAPY_OK || payload != -42) {
        fprintf(stderr, "integer conversion mismatch\n");
        return 12;
    }

    if (value_retain(runtime, value) != PORTAPY_OK) {
        fprintf(stderr, "retain failed\n");
        return 13;
    }
    if (value_release(runtime, value) != PORTAPY_OK) {
        fprintf(stderr, "first release failed\n");
        return 14;
    }
    payload = 0;
    if (value_as_i64(runtime, value, &payload) != PORTAPY_OK || payload != -42) {
        fprintf(stderr, "retained value became invalid\n");
        return 15;
    }
    if (value_release(runtime, value) != PORTAPY_OK) {
        fprintf(stderr, "final release failed\n");
        return 16;
    }
    value = NULL;

    if (runtime_destroy(runtime) != PORTAPY_OK) {
        fprintf(stderr, "runtime destruction failed\n");
        return 17;
    }
    runtime = NULL;

    if (runtime_create(NULL, &second_runtime) != PORTAPY_OK ||
        second_runtime == NULL) {
        fprintf(stderr, "default runtime creation failed\n");
        return 18;
    }
    if (value_from_i64(second_runtime, 99, &owned_until_destroy) != PORTAPY_OK ||
        owned_until_destroy == NULL) {
        fprintf(stderr, "owned value creation failed\n");
        return 19;
    }
    if (runtime_destroy(second_runtime) != PORTAPY_OK) {
        fprintf(stderr, "teardown with owned values failed\n");
        return 20;
    }

    printf(
        "abi=%u value=%lld kind=%d\n",
        abi_version(),
        (long long)-42,
        (int)kind
    );
    return 0;
}
