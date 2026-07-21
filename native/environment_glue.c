#include "portapy.h"

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern int64_t _portapy_last_status_impl(void);
extern int64_t _portapy_delete_global_span_impl(
    uint64_t runtime,
    const char *name,
    int64_t name_size
);
extern int64_t _portapy_global_count_impl(uint64_t runtime);
extern int64_t _portapy_global_name_size_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_global_name_byte_impl(
    uint64_t runtime,
    int64_t index,
    int64_t byte_index
);

static portapy_status copy_identifier(
    const uint8_t *data,
    size_t size,
    char **out_text
) {
    if (out_text == NULL || data == NULL || size == 0 || size > (size_t)INT64_MAX) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_text = NULL;
    for (size_t index = 0; index < size; ++index) {
        if (data[index] == 0 || data[index] > 0x7f) {
            return PORTAPY_INVALID_ARGUMENT;
        }
    }
    char *text = (char *)malloc(size + 1);
    if (text == NULL) {
        return PORTAPY_RUNTIME_ERROR;
    }
    memcpy(text, data, size);
    text[size] = '\0';
    *out_text = text;
    return PORTAPY_OK;
}

portapy_status PORTAPY_CALL portapy_delete_global_utf8(
    portapy_runtime runtime,
    const uint8_t *name,
    size_t name_size
) {
    char *text = NULL;
    portapy_status status = copy_identifier(name, name_size, &text);
    if (status != PORTAPY_OK) {
        return status;
    }
    status = (portapy_status)_portapy_delete_global_span_impl(
        runtime,
        text,
        (int64_t)name_size
    );
    free(text);
    return status;
}

portapy_status PORTAPY_CALL portapy_global_count(
    portapy_runtime runtime,
    size_t *out_count
) {
    if (out_count == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_count = 0;
    int64_t count = _portapy_global_count_impl(runtime);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status == PORTAPY_OK) {
        *out_count = (size_t)count;
    }
    return status;
}

portapy_status PORTAPY_CALL portapy_global_name_copy_utf8(
    portapy_runtime runtime,
    size_t index,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
) {
    if (
        out_size == NULL
        || index > (size_t)INT64_MAX
        || (capacity != 0 && buffer == NULL)
    ) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_size = 0;
    int64_t raw_size = _portapy_global_name_size_impl(runtime, (int64_t)index);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    size_t required = (size_t)raw_size;
    *out_size = required;
    if (capacity < required) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    for (size_t offset = 0; offset < required; ++offset) {
        int64_t byte = _portapy_global_name_byte_impl(
            runtime,
            (int64_t)index,
            (int64_t)offset
        );
        status = (portapy_status)_portapy_last_status_impl();
        if (status != PORTAPY_OK) {
            return status;
        }
        buffer[offset] = (uint8_t)byte;
    }
    return PORTAPY_OK;
}
