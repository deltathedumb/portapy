#include "portapy_managed.h"

#include <stdint.h>
#include <stdio.h>

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

typedef portapy_status (ABI_CALL *environment_create_fn)(portapy_environment **);
typedef portapy_status (ABI_CALL *environment_destroy_fn)(portapy_environment *);
typedef portapy_status (ABI_CALL *environment_add_fn)(
    portapy_environment *,
    const uint16_t *,
    size_t,
    portapy_environment_callback,
    void *
);
typedef portapy_status (ABI_CALL *environment_execute_fn)(
    portapy_environment *,
    const uint16_t *,
    size_t
);
typedef portapy_status (ABI_CALL *from_none_fn)(
    portapy_runtime,
    portapy_value *
);

typedef struct callback_context {
    from_none_fn from_none;
    int calls;
} callback_context;

static portapy_status ABI_CALL hello_world(
    void *raw_context,
    portapy_runtime runtime,
    const portapy_value *arguments,
    size_t argument_count,
    portapy_value *out_result
) {
    callback_context *context = (callback_context *)raw_context;
    if (
        context == NULL
        || arguments != NULL
        || argument_count != 0
        || out_result == NULL
    ) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    context->calls += 1;
    return context->from_none(runtime, out_result);
}

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

    RESOLVE(environment_create_fn, environment_create, "portapy_environment_create");
    RESOLVE(environment_destroy_fn, environment_destroy, "portapy_environment_destroy");
    RESOLVE(environment_add_fn, environment_add, "portapy_environment_add_callback_utf16");
    RESOLVE(environment_execute_fn, environment_execute, "portapy_environment_execute_utf16");
    RESOLVE(from_none_fn, from_none, "portapy_value_from_none");

    portapy_environment *environment = NULL;
    if (environment_create(&environment) != PORTAPY_OK || environment == NULL) {
        return 11;
    }

    callback_context context = {from_none, 0};
    const uint16_t name[] = {
        'h', 'e', 'l', 'l', 'o', 'W', 'o', 'r', 'l', 'd'
    };
    if (
        environment_add(
            environment,
            name,
            sizeof(name) / sizeof(name[0]),
            hello_world,
            &context
        ) != PORTAPY_OK
    ) {
        return 12;
    }

    const uint16_t source[] = {
        'h', 'e', 'l', 'l', 'o', 'W', 'o', 'r', 'l', 'd', '(', ')', '\n'
    };
    if (
        environment_execute(
            environment,
            source,
            sizeof(source) / sizeof(source[0])
        ) != PORTAPY_OK
    ) {
        return 13;
    }
    if (context.calls != 1) return 14;
    if (environment_destroy(environment) != PORTAPY_OK) return 15;

    puts("managed-environment: ok");
    return 0;
}
