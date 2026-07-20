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
typedef portapy_status (ABI_CALL *exec_utf8_fn)(
    portapy_runtime, const uint8_t *, size_t, const uint8_t *, size_t
);
typedef portapy_status (ABI_CALL *value_from_data_fn)(
    portapy_runtime, const uint8_t *, size_t, portapy_value *
);
typedef portapy_status (ABI_CALL *value_get_kind_fn)(
    portapy_runtime, portapy_value, portapy_value_kind *
);
typedef portapy_status (ABI_CALL *value_get_size_fn)(
    portapy_runtime, portapy_value, size_t *
);
typedef portapy_status (ABI_CALL *value_copy_data_fn)(
    portapy_runtime, portapy_value, uint8_t *, size_t, size_t *
);
typedef portapy_status (ABI_CALL *value_release_fn)(portapy_runtime, portapy_value);
typedef portapy_status (ABI_CALL *error_get_info_fn)(portapy_runtime, portapy_error_info *);
typedef portapy_status (ABI_CALL *error_copy_text_fn)(
    portapy_runtime, uint8_t *, size_t, size_t *
);
typedef portapy_status (ABI_CALL *error_clear_fn)(portapy_runtime);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { \
        fprintf(stderr, "missing symbol: %s\n", name); \
        return 10; \
    }

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) return 3;

    RESOLVE(initialize_fn, initialize, "portapy_library_initialize");
    RESOLVE(runtime_create_fn, runtime_create, "portapy_runtime_create");
    RESOLVE(runtime_destroy_fn, runtime_destroy, "portapy_runtime_destroy");
    RESOLVE(exec_utf8_fn, exec_utf8, "portapy_exec_utf8");
    RESOLVE(value_from_data_fn, value_from_utf8, "portapy_value_from_utf8");
    RESOLVE(value_from_data_fn, value_from_bytes, "portapy_value_from_bytes");
    RESOLVE(value_get_kind_fn, value_get_kind, "portapy_value_get_kind");
    RESOLVE(value_get_size_fn, value_get_size, "portapy_value_get_size");
    RESOLVE(value_copy_data_fn, value_copy_data, "portapy_value_copy_data");
    RESOLVE(value_release_fn, value_release, "portapy_value_release");
    RESOLVE(error_get_info_fn, error_get_info, "portapy_error_get_info");
    RESOLVE(error_copy_text_fn, error_copy_type, "portapy_error_copy_type_utf8");
    RESOLVE(error_copy_text_fn, error_copy_message, "portapy_error_copy_message_utf8");
    RESOLVE(error_clear_fn, error_clear, "portapy_error_clear");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK || runtime == 0) return 12;

    const uint8_t utf8[] = {'P', 'o', 'r', 't', 'a', 'P', 'y', ' ', 0xcf, 0x80};
    portapy_value text = PORTAPY_NULL_VALUE;
    if (value_from_utf8(runtime, utf8, sizeof(utf8), &text) != PORTAPY_OK) return 13;
    portapy_value_kind kind = PORTAPY_VALUE_OBJECT;
    if (value_get_kind(runtime, text, &kind) != PORTAPY_OK || kind != PORTAPY_VALUE_STRING) return 14;
    size_t required = 0;
    if (value_get_size(runtime, text, &required) != PORTAPY_OK || required != sizeof(utf8)) return 15;
    uint8_t copied[32] = {0};
    size_t copied_size = 0;
    if (value_copy_data(runtime, text, copied, sizeof(copied), &copied_size) != PORTAPY_OK) return 16;
    if (copied_size != sizeof(utf8) || memcmp(copied, utf8, sizeof(utf8)) != 0) return 17;

    const uint8_t raw[] = {0, 1, 127, 128, 255};
    portapy_value bytes = PORTAPY_NULL_VALUE;
    if (value_from_bytes(runtime, raw, sizeof(raw), &bytes) != PORTAPY_OK) return 18;
    if (value_get_kind(runtime, bytes, &kind) != PORTAPY_OK || kind != PORTAPY_VALUE_BYTES) return 19;
    memset(copied, 0, sizeof(copied));
    if (value_copy_data(runtime, bytes, copied, sizeof(copied), &copied_size) != PORTAPY_OK) return 20;
    if (copied_size != sizeof(raw) || memcmp(copied, raw, sizeof(raw)) != 0) return 21;

    copied_size = 0;
    if (value_copy_data(runtime, bytes, copied, 2, &copied_size) != PORTAPY_INVALID_ARGUMENT) return 22;
    if (copied_size != sizeof(raw)) return 23;

    const uint8_t invalid_utf8[] = {0xf0, 0x28, 0x8c, 0x28};
    portapy_value invalid = 999;
    if (value_from_utf8(runtime, invalid_utf8, sizeof(invalid_utf8), &invalid) != PORTAPY_TYPE_ERROR) return 24;
    if (invalid != PORTAPY_NULL_VALUE) return 25;

    portapy_error_info info = {0};
    info.struct_size = sizeof(info);
    if (error_get_info(runtime, &info) != PORTAPY_OK) return 26;
    if (info.status != PORTAPY_TYPE_ERROR || info.type_size == 0 || info.message_size == 0) return 27;
    uint8_t type_name[64] = {0};
    uint8_t message[128] = {0};
    size_t type_size = 0;
    size_t message_size = 0;
    if (error_copy_type(runtime, type_name, sizeof(type_name), &type_size) != PORTAPY_OK) return 28;
    if (error_copy_message(runtime, message, sizeof(message), &message_size) != PORTAPY_OK) return 29;
    if (type_size != strlen("UnicodeDecodeError")) return 30;
    if (memcmp(type_name, "UnicodeDecodeError", type_size) != 0) return 31;

    const uint8_t source[] = "safe = 1\nbroken = 5 // 0";
    if (exec_utf8(runtime, source, sizeof(source) - 1, NULL, 0) != PORTAPY_RUNTIME_ERROR) return 32;
    info.struct_size = sizeof(info);
    if (error_get_info(runtime, &info) != PORTAPY_OK) return 33;
    if (info.status != PORTAPY_RUNTIME_ERROR || info.line != 2 || info.column == 0) return 34;
    if (error_clear(runtime) != PORTAPY_OK) return 35;
    info.struct_size = sizeof(info);
    if (error_get_info(runtime, &info) != PORTAPY_OK || info.status != PORTAPY_OK) return 36;

    if (value_release(runtime, text) != PORTAPY_OK) return 37;
    if (value_release(runtime, bytes) != PORTAPY_OK) return 38;
    if (runtime_destroy(runtime) != PORTAPY_OK) return 39;

    puts("native-text-errors: ok");
    return 0;
}
