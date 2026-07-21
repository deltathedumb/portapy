#include "portapy_traceback.h"

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern int64_t _portapy_last_status_impl(void);
extern int64_t _portapy_traceback_set_filename_impl(
    uint64_t runtime,
    const char *filename,
    int64_t filename_size
);
extern int64_t _portapy_traceback_default_filename_impl(uint64_t runtime);
extern int64_t _portapy_traceback_count_impl(uint64_t runtime);
extern int64_t _portapy_traceback_line_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_traceback_column_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_traceback_filename_size_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_traceback_filename_byte_impl(
    uint64_t runtime,
    int64_t index,
    int64_t character_index
);
extern int64_t _portapy_traceback_function_size_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_traceback_function_byte_impl(
    uint64_t runtime,
    int64_t index,
    int64_t character_index
);
extern int64_t _portapy_traceback_source_size_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_traceback_source_byte_impl(
    uint64_t runtime,
    int64_t index,
    int64_t character_index
);

typedef int64_t (*traceback_size_impl)(uint64_t, int64_t);
typedef int64_t (*traceback_codepoint_impl)(uint64_t, int64_t, int64_t);

portapy_status _portapy_traceback_set_filename_utf8_bridge(
    portapy_runtime runtime,
    const uint8_t *filename,
    size_t filename_size
) {
    if (filename_size == 0) {
        (void)_portapy_traceback_default_filename_impl(runtime);
        return (portapy_status)_portapy_last_status_impl();
    }
    if (filename == NULL || filename_size > (size_t)INT64_MAX) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    if (memchr(filename, 0, filename_size) != NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    char *copy = (char *)malloc(filename_size + 1);
    if (copy == NULL) {
        return PORTAPY_RUNTIME_ERROR;
    }
    memcpy(copy, filename, filename_size);
    copy[filename_size] = 0;
    (void)_portapy_traceback_set_filename_impl(
        runtime,
        copy,
        (int64_t)filename_size
    );
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    free(copy);
    return status;
}

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

static portapy_status generated_character_count(
    portapy_runtime runtime,
    int64_t index,
    traceback_size_impl function,
    size_t *out_count
) {
    if (out_count == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_count = 0;
    int64_t raw_count = function(runtime, index);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    if (raw_count < 0) {
        return PORTAPY_RUNTIME_ERROR;
    }
    *out_count = (size_t)raw_count;
    return PORTAPY_OK;
}

static portapy_status generated_codepoint(
    portapy_runtime runtime,
    int64_t index,
    size_t character_index,
    traceback_codepoint_impl function,
    uint32_t *out_codepoint
) {
    if (out_codepoint == NULL || character_index > (size_t)INT64_MAX) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    int64_t raw = function(runtime, index, (int64_t)character_index);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    if (
        raw < 0
        || raw > INT64_C(0x10ffff)
        || (raw >= INT64_C(0xd800) && raw <= INT64_C(0xdfff))
    ) {
        return PORTAPY_TYPE_ERROR;
    }
    *out_codepoint = (uint32_t)raw;
    return PORTAPY_OK;
}

static size_t utf8_width(uint32_t codepoint) {
    if (codepoint <= UINT32_C(0x7f)) return 1;
    if (codepoint <= UINT32_C(0x7ff)) return 2;
    if (codepoint <= UINT32_C(0xffff)) return 3;
    return 4;
}

static portapy_status generated_utf8_size(
    portapy_runtime runtime,
    int64_t index,
    traceback_size_impl size_function,
    traceback_codepoint_impl codepoint_function,
    size_t *out_size
) {
    if (out_size == NULL) return PORTAPY_INVALID_ARGUMENT;
    *out_size = 0;
    size_t characters = 0;
    portapy_status status = generated_character_count(
        runtime, index, size_function, &characters
    );
    if (status != PORTAPY_OK) return status;
    size_t total = 0;
    for (size_t character_index = 0; character_index < characters; ++character_index) {
        uint32_t codepoint = 0;
        status = generated_codepoint(
            runtime,
            index,
            character_index,
            codepoint_function,
            &codepoint
        );
        if (status != PORTAPY_OK) return status;
        size_t width = utf8_width(codepoint);
        if (total > SIZE_MAX - width) return PORTAPY_RUNTIME_ERROR;
        total += width;
    }
    *out_size = total;
    return PORTAPY_OK;
}

static size_t write_utf8(uint8_t *buffer, size_t offset, uint32_t codepoint) {
    if (codepoint <= UINT32_C(0x7f)) {
        buffer[offset] = (uint8_t)codepoint;
        return offset + 1;
    }
    if (codepoint <= UINT32_C(0x7ff)) {
        buffer[offset] = (uint8_t)(UINT32_C(0xc0) | (codepoint >> 6));
        buffer[offset + 1] = (uint8_t)(UINT32_C(0x80) | (codepoint & UINT32_C(0x3f)));
        return offset + 2;
    }
    if (codepoint <= UINT32_C(0xffff)) {
        buffer[offset] = (uint8_t)(UINT32_C(0xe0) | (codepoint >> 12));
        buffer[offset + 1] = (uint8_t)(UINT32_C(0x80) | ((codepoint >> 6) & UINT32_C(0x3f)));
        buffer[offset + 2] = (uint8_t)(UINT32_C(0x80) | (codepoint & UINT32_C(0x3f)));
        return offset + 3;
    }
    buffer[offset] = (uint8_t)(UINT32_C(0xf0) | (codepoint >> 18));
    buffer[offset + 1] = (uint8_t)(UINT32_C(0x80) | ((codepoint >> 12) & UINT32_C(0x3f)));
    buffer[offset + 2] = (uint8_t)(UINT32_C(0x80) | ((codepoint >> 6) & UINT32_C(0x3f)));
    buffer[offset + 3] = (uint8_t)(UINT32_C(0x80) | (codepoint & UINT32_C(0x3f)));
    return offset + 4;
}

static portapy_status copy_generated_text(
    portapy_runtime runtime,
    size_t index,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size,
    traceback_size_impl size_function,
    traceback_codepoint_impl codepoint_function
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
    status = generated_utf8_size(
        runtime,
        raw_index,
        size_function,
        codepoint_function,
        &required
    );
    *out_size = required;
    if (status != PORTAPY_OK) return status;
    if (capacity < required) return PORTAPY_INVALID_ARGUMENT;
    size_t characters = 0;
    status = generated_character_count(
        runtime,
        raw_index,
        size_function,
        &characters
    );
    if (status != PORTAPY_OK) return status;
    size_t offset = 0;
    for (size_t character_index = 0; character_index < characters; ++character_index) {
        uint32_t codepoint = 0;
        status = generated_codepoint(
            runtime,
            raw_index,
            character_index,
            codepoint_function,
            &codepoint
        );
        if (status != PORTAPY_OK) return status;
        offset = write_utf8(buffer, offset, codepoint);
    }
    return offset == required ? PORTAPY_OK : PORTAPY_RUNTIME_ERROR;
}

portapy_status PORTAPY_CALL portapy_error_traceback_count(
    portapy_runtime runtime,
    size_t *out_count
) {
    if (out_count == NULL) return PORTAPY_INVALID_ARGUMENT;
    *out_count = 0;
    int64_t count = _portapy_traceback_count_impl(runtime);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) return status;
    if (count < 0) return PORTAPY_RUNTIME_ERROR;
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
    ) return PORTAPY_INVALID_ARGUMENT;
    int64_t raw_index = 0;
    portapy_status status = checked_frame_index(runtime, index, &raw_index);
    if (status != PORTAPY_OK) return status;
    int64_t line = _portapy_traceback_line_impl(runtime, raw_index);
    status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) return status;
    int64_t column = _portapy_traceback_column_impl(runtime, raw_index);
    status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) return status;
    size_t filename_size = 0;
    size_t function_size = 0;
    size_t source_size = 0;
    status = generated_utf8_size(
        runtime,
        raw_index,
        _portapy_traceback_filename_size_impl,
        _portapy_traceback_filename_byte_impl,
        &filename_size
    );
    if (status != PORTAPY_OK) return status;
    status = generated_utf8_size(
        runtime,
        raw_index,
        _portapy_traceback_function_size_impl,
        _portapy_traceback_function_byte_impl,
        &function_size
    );
    if (status != PORTAPY_OK) return status;
    status = generated_utf8_size(
        runtime,
        raw_index,
        _portapy_traceback_source_size_impl,
        _portapy_traceback_source_byte_impl,
        &source_size
    );
    if (status != PORTAPY_OK) return status;
    out_frame->line = line < 0 ? 0 : (size_t)line;
    out_frame->column = column < 0 ? 0 : (size_t)column;
    out_frame->filename_size = filename_size;
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
    return copy_generated_text(
        runtime,
        index,
        buffer,
        capacity,
        out_size,
        _portapy_traceback_filename_size_impl,
        _portapy_traceback_filename_byte_impl
    );
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
