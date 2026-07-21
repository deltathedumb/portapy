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

typedef portapy_status (ABI_CALL *new_fn)(portapy_environment *);
typedef portapy_status (ABI_CALL *destroy_fn)(portapy_environment);
typedef portapy_status (ABI_CALL *execute_fn)(portapy_environment, const char *);
typedef portapy_status (ABI_CALL *evaluate_fn)(portapy_environment, const char *, portapy_value *);
typedef portapy_status (ABI_CALL *add_fn)(portapy_environment, const portapy_binding *);
typedef portapy_status (ABI_CALL *add_all_fn)(portapy_environment, const portapy_binding *, size_t);
typedef portapy_status (ABI_CALL *from_none_fn)(portapy_runtime, portapy_value *);
typedef portapy_status (ABI_CALL *from_i64_fn)(portapy_runtime, int64_t, portapy_value *);
typedef portapy_status (ABI_CALL *as_i64_fn)(portapy_runtime, portapy_value, int64_t *);
typedef portapy_status (ABI_CALL *release_fn)(portapy_runtime, portapy_value);

typedef struct hello_context {
    from_none_fn from_none;
    int calls;
} hello_context;

static portapy_status ABI_CALL hello_world(
    void *raw_context,
    portapy_environment environment,
    const portapy_value *arguments,
    size_t argument_count,
    portapy_value *out_result
) {
    hello_context *context = (hello_context *)raw_context;
    if (
        context == NULL
        || arguments != NULL
        || argument_count != 0
        || out_result == NULL
    ) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    context->calls += 1;
    puts("Hello, world!");
    return context->from_none(environment, out_result);
}

#define RESOLVE(type, variable, name) \
    type variable = (type)(uintptr_t)LOAD_SYMBOL(library, name); \
    if ((variable) == NULL) { fprintf(stderr, "missing symbol: %s\n", name); return 10; }

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) return 3;

    RESOLVE(new_fn, create_environment, "portapy_new");
    RESOLVE(destroy_fn, destroy_environment, "portapy_destroy");
    RESOLVE(execute_fn, execute, "portapy_execute");
    RESOLVE(evaluate_fn, evaluate, "portapy_evaluate");
    RESOLVE(add_fn, add, "portapy_add");
    RESOLVE(add_all_fn, add_all, "portapy_add_all");
    RESOLVE(from_none_fn, from_none, "portapy_value_from_none");
    RESOLVE(from_i64_fn, from_i64, "portapy_value_from_i64");
    RESOLVE(as_i64_fn, as_i64, "portapy_value_as_i64");
    RESOLVE(release_fn, release, "portapy_value_release");

    portapy_environment environment = PORTAPY_NULL_ENVIRONMENT;
    if (create_environment(&environment) != PORTAPY_OK) return 11;

    hello_context context = {from_none, 0};
    portapy_binding hello = {0};
    hello.struct_size = sizeof(hello);
    hello.kind = PORTAPY_BINDING_CALLABLE;
    hello.name = (const uint8_t *)"helloWorld";
    hello.name_size = strlen("helloWorld");
    hello.callable = hello_world;
    hello.context = &context;
    if (add(environment, &hello) != PORTAPY_OK) return 12;

    portapy_value seed = PORTAPY_NULL_VALUE;
    portapy_value offset = PORTAPY_NULL_VALUE;
    if (from_i64(environment, 40, &seed) != PORTAPY_OK) return 13;
    if (from_i64(environment, 2, &offset) != PORTAPY_OK) return 14;

    portapy_binding module_members[2] = {{0}, {0}};
    module_members[0].struct_size = sizeof(portapy_binding);
    module_members[0].kind = PORTAPY_BINDING_VALUE;
    module_members[0].name = (const uint8_t *)"seed";
    module_members[0].name_size = strlen("seed");
    module_members[0].value = seed;
    module_members[1].struct_size = sizeof(portapy_binding);
    module_members[1].kind = PORTAPY_BINDING_VALUE;
    module_members[1].name = (const uint8_t *)"offset";
    module_members[1].name_size = strlen("offset");
    module_members[1].value = offset;
    if (add_all(environment, module_members, 2) != PORTAPY_OK) return 15;

    if (release(environment, seed) != PORTAPY_OK) return 16;
    if (release(environment, offset) != PORTAPY_OK) return 17;

    if (execute(environment, "helloWorld()\nanswer = seed + offset\n") != PORTAPY_OK) return 18;
    if (context.calls != 1) return 19;

    portapy_value answer = PORTAPY_NULL_VALUE;
    int64_t number = 0;
    if (evaluate(environment, "answer", &answer) != PORTAPY_OK) return 20;
    if (as_i64(environment, answer, &number) != PORTAPY_OK || number != 42) return 21;
    if (release(environment, answer) != PORTAPY_OK) return 22;
    if (destroy_environment(environment) != PORTAPY_OK) return 23;

    puts("universal-environment-api: ok");
    return 0;
}
