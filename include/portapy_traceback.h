#ifndef PORTAPY_TRACEBACK_H
#define PORTAPY_TRACEBACK_H

#include "portapy.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct portapy_traceback_frame_info {
    size_t struct_size;
    size_t line;
    size_t column;
    size_t filename_size;
    size_t function_size;
    size_t source_size;
} portapy_traceback_frame_info;

PORTAPY_API portapy_status PORTAPY_CALL portapy_error_traceback_count(
    portapy_runtime runtime,
    size_t *out_count
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_error_traceback_get_frame(
    portapy_runtime runtime,
    size_t index,
    portapy_traceback_frame_info *out_frame
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_error_traceback_copy_filename_utf8(
    portapy_runtime runtime,
    size_t index,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_error_traceback_copy_function_utf8(
    portapy_runtime runtime,
    size_t index,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_error_traceback_copy_source_utf8(
    portapy_runtime runtime,
    size_t index,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
);

#ifdef __cplusplus
}
#endif
#endif
