#include "portapy.h"

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern int64_t _portapy_last_status_impl(void);
extern uint64_t _portapy_value_from_data_begin_impl(uint64_t runtime, int64_t kind, int64_t size);
extern int64_t _portapy_value_set_data_byte_impl(uint64_t runtime, uint64_t value, int64_t index, int64_t byte);
extern int64_t _portapy_value_validate_utf8_impl(uint64_t runtime, uint64_t value);
extern int64_t _portapy_value_get_size_impl(uint64_t runtime, uint64_t value);
extern int64_t _portapy_value_get_byte_impl(uint64_t runtime, uint64_t value, int64_t index);
extern int64_t _portapy_value_release_impl(uint64_t runtime, uint64_t value);
extern uint64_t _portapy_value_from_host_object_impl(uint64_t runtime, uint64_t host_id);
extern uint64_t _portapy_value_get_host_id_impl(uint64_t runtime, uint64_t value);
extern int64_t _portapy_set_global_span_impl(uint64_t runtime, const char *name, int64_t name_size, uint64_t value);
extern int64_t _portapy_host_set_attr_span_impl(uint64_t runtime, uint64_t owner, const char *name, int64_t name_size, uint64_t value);
extern uint64_t _portapy_host_get_attr_span_impl(uint64_t runtime, uint64_t owner, const char *name, int64_t name_size);
extern int64_t _portapy_error_status_impl(uint64_t runtime);
extern int64_t _portapy_error_line_impl(uint64_t runtime);
extern int64_t _portapy_error_column_impl(uint64_t runtime);
extern int64_t _portapy_error_type_size_impl(uint64_t runtime);
extern int64_t _portapy_error_type_byte_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_error_message_size_impl(uint64_t runtime);
extern int64_t _portapy_error_message_byte_impl(uint64_t runtime, int64_t index);
extern int64_t _portapy_error_clear_impl(uint64_t runtime);

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
        if (data[index] == 0) {
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

portapy_status PORTAPY_CALL portapy_set_global_utf8(
    portapy_runtime runtime,
    const uint8_t *name,
    size_t name_size,
    portapy_value value
) {
    char *text = NULL;
    portapy_status status = copy_identifier(name, name_size, &text);
    if (status != PORTAPY_OK) {
        return status;
    }
    status = (portapy_status)_portapy_set_global_span_impl(
        runtime,
        text,
        (int64_t)name_size,
        value
    );
    free(text);
    return status;
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

portapy_status PORTAPY_CALL portapy_value_from_host_object(
    portapy_runtime runtime,
    uint64_t host_id,
    portapy_value *out_value
) {
    if (out_value == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_value = PORTAPY_NULL_VALUE;
    portapy_value value = _portapy_value_from_host_object_impl(runtime, host_id);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status == PORTAPY_OK) {
        *out_value = value;
    }
    return status;
}

portapy_status PORTAPY_CALL portapy_value_get_host_id(
    portapy_runtime runtime,
    portapy_value value,
    uint64_t *out_host_id
) {
    if (out_host_id == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_host_id = 0;
    uint64_t host_id = _portapy_value_get_host_id_impl(runtime, value);
    portapy_status status = (portapy_status)_portapy_last_status_impl();
    if (status == PORTAPY_OK) {
        *out_host_id = host_id;
    }
    return status;
}

portapy_status PORTAPY_CALL portapy_host_set_attr_utf8(
    portapy_runtime runtime,
    portapy_value owner,
    const uint8_t *name,
    size_t name_size,
    portapy_value value
) {
    char *text = NULL;
    portapy_status status = copy_identifier(name, name_size, &text);
    if (status != PORTAPY_OK) {
        return status;
    }
    status = (portapy_status)_portapy_host_set_attr_span_impl(
        runtime,
        owner,
        text,
        (int64_t)name_size,
        value
    );
    free(text);
    return status;
}

portapy_status PORTAPY_CALL portapy_host_get_attr_utf8(
    portapy_runtime runtime,
    portapy_value owner,
    const uint8_t *name,
    size_t name_size,
    portapy_value *out_value
) {
    if (out_value == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_value = PORTAPY_NULL_VALUE;
    char *text = NULL;
    portapy_status status = copy_identifier(name, name_size, &text);
    if (status != PORTAPY_OK) {
        return status;
    }
    portapy_value value = _portapy_host_get_attr_span_impl(
        runtime,
        owner,
        text,
        (int64_t)name_size
    );
    status = (portapy_status)_portapy_last_status_impl();
    free(text);
    if (status == PORTAPY_OK) {
        *out_value = value;
    }
    return status;
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
