#include "portapy.h"

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern int64_t _portapy_last_status_impl(void);
extern uint64_t _portapy_value_from_host_object_impl(uint64_t runtime, uint64_t host_id);
extern uint64_t _portapy_value_get_host_id_impl(uint64_t runtime, uint64_t value);
extern int64_t _portapy_set_global_span_impl(uint64_t runtime, const char *name, int64_t name_size, uint64_t value);
extern int64_t _portapy_host_set_attr_span_impl(uint64_t runtime, uint64_t owner, const char *name, int64_t name_size, uint64_t value);
extern uint64_t _portapy_host_get_attr_span_impl(uint64_t runtime, uint64_t owner, const char *name, int64_t name_size);

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
