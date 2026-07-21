#include "portapy_traceback.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

extern int64_t _portapy_last_status_impl(void);
extern int64_t _portapy_traceback_count_impl(uint64_t runtime);
extern int64_t _portapy_traceback_line_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_traceback_column_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_traceback_function_size_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_traceback_function_byte_impl(
    uint64_t runtime,
    int64_t index,
    int64_t byte_index
);
extern int64_t _portapy_traceback_source_size_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_traceback_source_byte_impl(
    uint64_t runtime,
    int64_t index,
    int64_t byte_index
);

static const uint8_t DEFAULT_FILENAME[] = "<portapy>";

typedef int64_t (*traceback_size_impl)(uint64_t, int64_t);
typedef int64_t (*traceback_byte_impl)(uint64_t, int64_t, int64_t);

static portapy_status checked_index(size_t index, int64_t *out_index) {
    if (out_index == NULL || index > (size_t)INT64_MAX) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_index = (int64_t)index;
    return PORTAPY_OK;
}

static portapy_status checked_frame_index(
    portapy_runtime runtime,
    size_t index,
    int64_t *out_index
) {
    portapy_status status = checked_index(index, out_index);
    if (status != PORTAPY_OK) {
        return status;
    }
    int64_t count = _portapy_traceback_count_impl(runtime);
    status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    if (*out_index < 0 || *out_index >= count) {
        return PORTAPY_NOT_FOUND;
    }
    return PORTAPY_OK;
}

static portapy_status generated_size(
    portapy_runtime runtime,
    int64_t index,
    traceback_size_impl function,
    size_t *out_size
) {
    if (out_size == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_size = 0;
    int64_t raw_size = function(runtime, index);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    if (raw_size < 0) {
        return PORTAPY_RUNTIME_ERROR;
    }
    *out_size = (size_t)raw_size;
    return PORTAPY_OK;
}

static portapy_status copy_generated_text(
    portapy_runtime runtime,
    size_t index,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size,
    traceback_size_impl size_function,
    traceback_byte_impl byte_function
) {
    if (out_size == NULL || (capacity != 0 && buffer == NULL)) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    int64_t raw_index = 0;
    portapy_status status = checked_frame_index(runtime, index, &raw_index);
    if (status != PORTAPY_OK) {
        *out_size = 0;
        return status;
    }
    size_t required = 0;
    status = generated_size(runtime, raw_index, size_function, &required);
    *out_size = required;
    if (status != PORTAPY_OK) {
        return status;
    }
    if (capacity < required) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    for (size_t byte_index = 0; byte_index < required; ++byte_index) {
        int64_t byte = byte_function(runtime, raw_index, (int64_t)byte_index);
        status = (portapy_status)_portapy_last_status_impl();
        if (status != PORTAPY_OK) {
            return status;
        }
        buffer[byte_index] = (uint8_t)byte;
    }
    return PORTAPY_OK;
}

portapy_status PORTAPY_CALL portapy_error_traceback_count(
    portapy_runtime runtime,
    size_t *out_count
) {
    if (out_count == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_count = 0;
    int64_t count = _portapy_traceback_count_impl(runtime);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    if (count < 0) {
        return PORTAPY_RUNTIME_ERROR;
    }
    *out_count = (size_t)count;
    return PORTAPY_OK;
}

portapy_status PORTAPY_CALL portapy_error_traceback_get_frame(
    portapy_runtime runtime,
    size_t index,
    portapy_traceback_frame_info *out_frame
) {
    if (
        out_frame == NULL
        || out_frame->struct_size < sizeof(portapy_traceback_frame_info)
    ) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    int64_t raw_index = 0;
    portapy_status status = checked_frame_index(runtime, index, &raw_index);
    if (status != PORTAPY_OK) {
        return status;
    }
    int64_t line = _portapy_traceback_line_impl(runtime, raw_index);
    status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    int64_t column = _portapy_traceback_column_impl(runtime, raw_index);
    status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    size_t function_size = 0;
    size_t source_size = 0;
    status = generated_size(
        runtime,
        raw_index,
        _portapy_traceback_function_size_impl,
        &function_size
    );
    if (status != PORTAPY_OK) {
        return status;
    }
    status = generated_size(
        runtime,
        raw_index,
        _portapy_traceback_source_size_impl,
        &source_size
    );
    if (status != PORTAPY_OK) {
        return status;
    }
    out_frame->line = line < 0 ? 0 : (size_t)line;
    out_frame->column = column < 0 ? 0 : (size_t)column;
    out_frame->filename_size = sizeof(DEFAULT_FILENAME) - 1;
    out_frame->function_size = function_size;
    out_frame->source_size = source_size;
    return PORTAPY_OK;
}

portapy_status PORTAPY_CALL portapy_error_traceback_copy_filename_utf8(
    portapy_runtime runtime,
    size_t index,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
) {
    if (out_size == NULL || (capacity != 0 && buffer == NULL)) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    int64_t raw_index = 0;
    portapy_status status = checked_frame_index(runtime, index, &raw_index);
    (void)raw_index;
    if (status != PORTAPY_OK) {
        *out_size = 0;
        return status;
    }
    size_t required = sizeof(DEFAULT_FILENAME) - 1;
    *out_size = required;
    if (capacity < required) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    if (required != 0) {
        memcpy(buffer, DEFAULT_FILENAME, required);
    }
    return PORTAPY_OK;
}

portapy_status PORTAPY_CALL portapy_error_traceback_copy_function_utf8(
    portapy_runtime runtime,
    size_t index,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
) {
    return copy_generated_text(
        runtime,
        index,
        buffer,
        capacity,
        out_size,
        _portapy_traceback_function_size_impl,
        _portapy_traceback_function_byte_impl
    );
}

portapy_status PORTAPY_CALL portapy_error_traceback_copy_source_utf8(
    portapy_runtime runtime,
    size_t index,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
) {
    return copy_generated_text(
        runtime,
        index,
        buffer,
        capacity,
        out_size,
        _portapy_traceback_source_size_impl,
        _portapy_traceback_source_byte_impl
    );
}
