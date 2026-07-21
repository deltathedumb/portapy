#include "portapy_traceback.h"

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
typedef portapy_status (ABI_CALL *trace_count_fn)(portapy_runtime, size_t *);
typedef portapy_status (ABI_CALL *trace_frame_fn)(portapy_runtime, size_t, portapy_traceback_frame_info *);
typedef portapy_status (ABI_CALL *trace_copy_fn)(portapy_runtime, size_t, uint8_t *, size_t, size_t *);

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { fprintf(stderr, "missing symbol: %s\n", name); return 10; }

static int copy_equals(
    trace_copy_fn copy,
    portapy_runtime runtime,
    size_t index,
    const char *expected
) {
    size_t required = 0;
    portapy_status status = copy(runtime, index, NULL, 0, &required);
    if (required != strlen(expected)) return 0;
    if (required != 0 && status != PORTAPY_INVALID_ARGUMENT) return 0;
    if (required == 0 && status != PORTAPY_OK) return 0;
    uint8_t buffer[128] = {0};
    if (required >= sizeof(buffer)) return 0;
    if (copy(runtime, index, buffer, sizeof(buffer), &required) != PORTAPY_OK) return 0;
    return memcmp(buffer, expected, required) == 0;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) return 3;

    RESOLVE(initialize_fn, initialize, "portapy_library_initialize");
    RESOLVE(runtime_create_fn, runtime_create, "portapy_runtime_create");
    RESOLVE(runtime_destroy_fn, runtime_destroy, "portapy_runtime_destroy");
    RESOLVE(exec_fn, exec_utf8, "portapy_exec_utf8");
    RESOLVE(trace_count_fn, trace_count, "portapy_error_traceback_count");
    RESOLVE(trace_frame_fn, trace_frame, "portapy_error_traceback_get_frame");
    RESOLVE(trace_copy_fn, copy_filename, "portapy_error_traceback_copy_filename_utf8");
    RESOLVE(trace_copy_fn, copy_function, "portapy_error_traceback_copy_function_utf8");
    RESOLVE(trace_copy_fn, copy_source, "portapy_error_traceback_copy_source_utf8");

    if (initialize() != PORTAPY_OK) return 11;
    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    if (runtime_create(&config, &runtime) != PORTAPY_OK) return 12;

    const char source[] =
        "def inner():\n"
        "    return missing\n"
        "def outer():\n"
        "    return inner()\n"
        "result = outer()\n";
    portapy_status execution = exec_utf8(
        runtime,
        (const uint8_t *)source,
        strlen(source),
        (const uint8_t *)"traceback_test.py",
        strlen("traceback_test.py")
    );
    if (execution == PORTAPY_OK) return 13;

    size_t count = 0;
    if (trace_count(runtime, &count) != PORTAPY_OK || count != 3) return 14;

    const char *functions[] = {"<module>", "outer", "inner"};
    for (size_t index = 0; index < count; ++index) {
        portapy_traceback_frame_info frame = {0};
        frame.struct_size = sizeof(frame);
        if (trace_frame(runtime, index, &frame) != PORTAPY_OK) return 15;
        if (frame.line == 0 || frame.column == 0) return 16;
        if (!copy_equals(copy_filename, runtime, index, "traceback_test.py")) return 17;
        if (!copy_equals(copy_function, runtime, index, functions[index])) return 18;
    }
    if (!copy_equals(copy_source, runtime, 1, "def outer():")) return 19;
    if (!copy_equals(copy_source, runtime, 2, "return missing")) return 20;

    if (runtime_destroy(runtime) != PORTAPY_OK) return 21;
    puts("native-traceback-frames: ok");
    return 0;
}
