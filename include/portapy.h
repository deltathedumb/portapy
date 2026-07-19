#ifndef PORTAPY_H
#define PORTAPY_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
# if defined(PORTAPY_BUILD_DLL)
#  define PORTAPY_API __declspec(dllexport)
# elif defined(PORTAPY_USE_DLL)
#  define PORTAPY_API __declspec(dllimport)
# else
#  define PORTAPY_API
# endif
# define PORTAPY_CALL __cdecl
#else
# define PORTAPY_API __attribute__((visibility("default")))
# define PORTAPY_CALL
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define PORTAPY_ABI_VERSION 1u

typedef uint64_t portapy_runtime;
typedef uint64_t portapy_value;

#define PORTAPY_NULL_RUNTIME ((portapy_runtime)0)
#define PORTAPY_NULL_VALUE ((portapy_value)0)

typedef enum portapy_status {
    PORTAPY_OK = 0,
    PORTAPY_INVALID_ARGUMENT = 1,
    PORTAPY_COMPILE_ERROR = 2,
    PORTAPY_RUNTIME_ERROR = 3,
    PORTAPY_TYPE_ERROR = 4,
    PORTAPY_NOT_FOUND = 5,
    PORTAPY_CLOSED = 6,
    PORTAPY_INVALID_HANDLE = 7,
    PORTAPY_INTERRUPTED = 8,
    PORTAPY_ABI_MISMATCH = 9
} portapy_status;

typedef enum portapy_value_kind {
    PORTAPY_VALUE_NONE = 0,
    PORTAPY_VALUE_BOOL = 1,
    PORTAPY_VALUE_INT = 2,
    PORTAPY_VALUE_FLOAT = 3,
    PORTAPY_VALUE_STRING = 4,
    PORTAPY_VALUE_BYTES = 5,
    PORTAPY_VALUE_CALLABLE = 6,
    PORTAPY_VALUE_OBJECT = 7
} portapy_value_kind;

typedef struct portapy_bytes_view {
    const uint8_t *data;
    size_t size;
} portapy_bytes_view;

typedef struct portapy_config {
    size_t struct_size;
    uint32_t abi_version;
    uint32_t flags;
    void *host_context;
} portapy_config;

PORTAPY_API portapy_status PORTAPY_CALL portapy_library_initialize(void);
PORTAPY_API uint32_t PORTAPY_CALL portapy_abi_version(void);

PORTAPY_API portapy_status PORTAPY_CALL portapy_runtime_create(
    const portapy_config *config,
    portapy_runtime *out_runtime
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_runtime_destroy(
    portapy_runtime runtime
);

PORTAPY_API portapy_status PORTAPY_CALL portapy_exec_utf8(
    portapy_runtime runtime,
    const uint8_t *source,
    size_t source_size,
    const uint8_t *filename,
    size_t filename_size
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_eval_utf8(
    portapy_runtime runtime,
    const uint8_t *source,
    size_t source_size,
    const uint8_t *filename,
    size_t filename_size,
    portapy_value *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_get_global_utf8(
    portapy_runtime runtime,
    const uint8_t *name,
    size_t name_size,
    portapy_value *out_value
);

PORTAPY_API portapy_status PORTAPY_CALL portapy_value_from_none(
    portapy_runtime runtime,
    portapy_value *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_from_bool(
    portapy_runtime runtime,
    int value,
    portapy_value *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_from_i64(
    portapy_runtime runtime,
    int64_t value,
    portapy_value *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_from_f64(
    portapy_runtime runtime,
    double value,
    portapy_value *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_get_kind(
    portapy_runtime runtime,
    portapy_value value,
    portapy_value_kind *out_kind
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_as_bool(
    portapy_runtime runtime,
    portapy_value value,
    int *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_as_i64(
    portapy_runtime runtime,
    portapy_value value,
    int64_t *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_as_f64(
    portapy_runtime runtime,
    portapy_value value,
    double *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_retain(
    portapy_runtime runtime,
    portapy_value value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_release(
    portapy_runtime runtime,
    portapy_value value
);

#ifdef __cplusplus
}
#endif
#endif
