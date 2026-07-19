#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#if defined(_WIN32)
#include <windows.h>
typedef int64_t (__cdecl *probe_fn)(void);
#else
#include <dlfcn.h>
typedef int64_t (*probe_fn)(void);
#endif

static void *load_library(const char *path) {
#if defined(_WIN32)
    return (void *)LoadLibraryA(path);
#else
    return dlopen(path, RTLD_NOW | RTLD_LOCAL);
#endif
}

static probe_fn load_symbol(void *library, const char *name) {
#if defined(_WIN32)
    return (probe_fn)(uintptr_t)GetProcAddress((HMODULE)library, name);
#else
    return (probe_fn)dlsym(library, name);
#endif
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: native_probe_host <library>\n");
        return 2;
    }
    void *library = load_library(argv[1]);
    if (library == NULL) {
        fprintf(stderr, "failed to load %s\n", argv[1]);
        return 3;
    }
    probe_fn abi = load_symbol(library, "portapy_abi_version");
    probe_fn opcode = load_symbol(library, "portapy_opcode_probe");
    if (abi == NULL || opcode == NULL) {
        fprintf(stderr, "required probe exports are missing\n");
        return 4;
    }
    int64_t abi_value = abi();
    int64_t opcode_value = opcode();
    printf("abi=%lld opcode=%lld\n", (long long)abi_value, (long long)opcode_value);
    return abi_value == 1 && opcode_value == 10 ? 0 : 5;
}
