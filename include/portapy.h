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

typedef struct portapy_error_info {
    size_t struct_size;
    portapy_status status;
    uint32_t reserved;
    size_t line;
    size_t column;
    size_t type_size;
    size_t message_size;
} portapy_error_info;

typedef portapy_status (PORTAPY_CALL *portapy_host_call_handler)(
    void *context,
    portapy_runtime runtime,
    uint64_t callable_id,
    const portapy_value *arguments,
    size_t argument_count,
    portapy_value *out_result
);

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
PORTAPY_API portapy_status PORTAPY_CALL portapy_set_global_utf8(
    portapy_runtime runtime,
    const uint8_t *name,
    size_t name_size,
    portapy_value value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_delete_global_utf8(
    portapy_runtime runtime,
    const uint8_t *name,
    size_t name_size
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_global_count(
    portapy_runtime runtime,
    size_t *out_count
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_global_name_copy_utf8(
    portapy_runtime runtime,
    size_t index,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
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
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_from_utf8(
    portapy_runtime runtime,
    const uint8_t *data,
    size_t size,
    portapy_value *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_from_bytes(
    portapy_runtime runtime,
    const uint8_t *data,
    size_t size,
    portapy_value *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_from_host_object(
    portapy_runtime runtime,
    uint64_t host_id,
    portapy_value *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_from_host_callable(
    portapy_runtime runtime,
    uint64_t callable_id,
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
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_get_host_id(
    portapy_runtime runtime,
    portapy_value value,
    uint64_t *out_host_id
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_get_host_callable_id(
    portapy_runtime runtime,
    portapy_value value,
    uint64_t *out_callable_id
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_get_size(
    portapy_runtime runtime,
    portapy_value value,
    size_t *out_size
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_copy_data(
    portapy_runtime runtime,
    portapy_value value,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_retain(
    portapy_runtime runtime,
    portapy_value value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_value_release(
    portapy_runtime runtime,
    portapy_value value
);

PORTAPY_API portapy_status PORTAPY_CALL portapy_host_set_attr_utf8(
    portapy_runtime runtime,
    portapy_value owner,
    const uint8_t *name,
    size_t name_size,
    portapy_value value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_host_get_attr_utf8(
    portapy_runtime runtime,
    portapy_value owner,
    const uint8_t *name,
    size_t name_size,
    portapy_value *out_value
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_host_set_call_handler(
    portapy_runtime runtime,
    portapy_host_call_handler handler,
    void *context
);

PORTAPY_API portapy_status PORTAPY_CALL portapy_error_get_info(
    portapy_runtime runtime,
    portapy_error_info *out_info
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_error_copy_type_utf8(
    portapy_runtime runtime,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_error_copy_message_utf8(
    portapy_runtime runtime,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_error_clear(
    portapy_runtime runtime
);

#ifdef __cplusplus
}
#endif
#endif
