#include "portapy.h"

#include <stddef.h>
#include <stdint.h>

extern int64_t _portapy_last_status_impl(void);
extern uint64_t _portapy_value_from_data_begin_impl(uint64_t runtime, int64_t kind, int64_t size);
extern int64_t _portapy_value_set_data_byte_impl(uint64_t runtime, uint64_t value, int64_t index, int64_t byte);
extern int64_t _portapy_value_validate_utf8_impl(uint64_t runtime, uint64_t value);
extern int64_t _portapy_value_get_size_impl(uint64_t runtime, uint64_t value);
extern int64_t _portapy_value_get_byte_impl(uint64_t runtime, uint64_t value, int64_t index);
extern int64_t _portapy_value_release_impl(uint64_t runtime, uint64_t value);
extern int64_t _portapy_error_status_impl(uint64_t runtime);
extern int64_t _portapy_error_line_impl(uint64_t runtime);
extern int64_t _portapy_error_column_impl(uint64_t runtime);
extern int64_t _portapy_error_type_size_impl(uint64_t runtime);
extern int64_t _portapy_error_type_byte_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_error_message_size_impl(uint64_t runtime);
extern int64_t _portapy_error_message_byte_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_error_clear_impl(uint64_t runtime);

static portapy_status value_from_data(
    portapy_runtime runtime,
    portapy_value_kind kind,
    const uint8_t *data,
    size_t size,
    portapy_value *out_value
) {
    if (out_value == NULL || (size != 0 && data == NULL) || size > (size_t)INT64_MAX) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_value = PORTAPY_NULL_VALUE;
    portapy_value value = _portapy_value_from_data_begin_impl(
        runtime,
        (int64_t)kind,
        (int64_t)size
    );
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    for (size_t index = 0; index < size; ++index) {
        status = (portapy_status)_portapy_value_set_data_byte_impl(
            runtime,
            value,
            (int64_t)index,
            (int64_t)data[index]
        );
        if (status != PORTAPY_OK) {
            (void)_portapy_value_release_impl(runtime, value);
            return status;
        }
    }
    if (kind == PORTAPY_VALUE_STRING) {
        status = (portapy_status)_portapy_value_validate_utf8_impl(runtime, value);
        if (status != PORTAPY_OK) {
            (void)_portapy_value_release_impl(runtime, value);
            return status;
        }
    }
    *out_value = value;
    return PORTAPY_OK;
}

portapy_status PORTAPY_CALL portapy_value_from_utf8(
    portapy_runtime runtime,
    const uint8_t *data,
    size_t size,
    portapy_value *out_value
) {
    return value_from_data(runtime, PORTAPY_VALUE_STRING, data, size, out_value);
}

portapy_status PORTAPY_CALL portapy_value_from_bytes(
    portapy_runtime runtime,
    const uint8_t *data,
    size_t size,
    portapy_value *out_value
) {
    return value_from_data(runtime, PORTAPY_VALUE_BYTES, data, size, out_value);
}

portapy_status PORTAPY_CALL portapy_value_get_size(
    portapy_runtime runtime,
    portapy_value value,
    size_t *out_size
) {
    if (out_size == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_size = 0;
    int64_t result = _portapy_value_get_size_impl(runtime, value);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status == PORTAPY_OK) {
        *out_size = (size_t)result;
    }
    return status;
}

portapy_status PORTAPY_CALL portapy_value_copy_data(
    portapy_runtime runtime,
    portapy_value value,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
) {
    if (out_size == NULL || (capacity != 0 && buffer == NULL)) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_size = 0;
    int64_t result = _portapy_value_get_size_impl(runtime, value);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    size_t required = (size_t)result;
    *out_size = required;
    if (capacity < required) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    for (size_t index = 0; index < required; ++index) {
        int64_t byte = _portapy_value_get_byte_impl(runtime, value, (int64_t)index);
        status = (portapy_status)_portapy_last_status_impl();
        if (status != PORTAPY_OK) {
            return status;
        }
        buffer[index] = (uint8_t)byte;
    }
    return PORTAPY_OK;
}

portapy_status PORTAPY_CALL portapy_error_get_info(
    portapy_runtime runtime,
    portapy_error_info *out_info
) {
    if (out_info == NULL || out_info->struct_size < sizeof(portapy_error_info)) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    out_info->status = (portapy_status)_portapy_error_status_impl(runtime);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    out_info->line = (size_t)_portapy_error_line_impl(runtime);
    out_info->column = (size_t)_portapy_error_column_impl(runtime);
    out_info->type_size = (size_t)_portapy_error_type_size_impl(runtime);
    out_info->message_size = (size_t)_portapy_error_message_size_impl(runtime);
    return PORTAPY_OK;
}

static portapy_status copy_error_text(
    portapy_runtime runtime,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size,
    int type_text
) {
    if (out_size == NULL || (capacity != 0 && buffer == NULL)) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_size = 0;
    int64_t raw_size = type_text
        ? _portapy_error_type_size_impl(runtime)
        : _portapy_error_message_size_impl(runtime);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    size_t required = (size_t)raw_size;
    *out_size = required;
    if (capacity < required) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    for (size_t index = 0; index < required; ++index) {
        int64_t byte = type_text
            ? _portapy_error_type_byte_impl(runtime, (int64_t)index)
            : _portapy_error_message_byte_impl(runtime, (int64_t)index);
        status = (portapy_status)_portapy_last_status_impl();
        if (status != PORTAPY_OK) {
            return status;
        }
        buffer[index] = (uint8_t)byte;
    }
    return PORTAPY_OK;
}

portapy_status PORTAPY_CALL portapy_error_copy_type_utf8(
    portapy_runtime runtime,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
) {
    return copy_error_text(runtime, buffer, capacity, out_size, 1);
}

portapy_status PORTAPY_CALL portapy_error_copy_message_utf8(
    portapy_runtime runtime,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
) {
    return copy_error_text(runtime, buffer, capacity, out_size, 0);
}

portapy_status PORTAPY_CALL portapy_error_clear(portapy_runtime runtime) {
    return (portapy_status)_portapy_error_clear_impl(runtime);
}
