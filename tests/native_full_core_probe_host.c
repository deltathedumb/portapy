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

typedef int64_t (ABI_CALL *probe_fn)(void);

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    void *library = LOAD_LIBRARY(argv[1]);
    if (library == NULL) return 3;

    probe_fn parse_probe = (probe_fn)(uintptr_t)LOAD_SYMBOL(
        library,
        "portapy_full_core_parse_probe"
    );
    if (parse_probe == NULL) return 4;

    probe_fn probe = (probe_fn)(uintptr_t)LOAD_SYMBOL(
        library,
        "portapy_full_core_probe"
    );
    if (probe == NULL) return 5;

    int64_t parsed_instructions = parse_probe();
    fprintf(stderr, "full-core-parse=%lld\n", (long long)parsed_instructions);
    if (parsed_instructions <= 0) return 6;

    int64_t result = probe();
    printf("full-core=%lld\n", (long long)result);
    return result == 42 ? 0 : 7;
}
