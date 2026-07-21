#include "portapy.h"

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern int64_t _portapy_cabi_last_status_impl(void);
extern uint64_t _portapy_cabi_dict_begin_impl(uint64_t runtime);
extern int64_t _portapy_cabi_dict_set_span_impl(
    uint64_t runtime,
    uint64_t value,
    const char *key,
    int64_t key_size,
    uint64_t item
);
extern int64_t _portapy_cabi_dict_get_size_impl(uint64_t runtime, uint64_t value);
extern int64_t _portapy_cabi_dict_key_size_impl(
    uint64_t runtime,
    uint64_t value,
    int64_t index
);
extern int64_t _portapy_cabi_dict_key_byte_impl(
    uint64_t runtime,
    uint64_t value,
    int64_t index,
    int64_t offset
);
extern uint64_t _portapy_cabi_dict_get_item_span_impl(
    uint64_t runtime,
    uint64_t value,
    const char *key,
    int64_t key_size
);

static portapy_status copy_key(
    const uint8_t *data,
    size_t size,
    char **out_text
) {
    if (
        out_text == NULL
        || data == NULL
        || size == 0
        || size > (size_t)INT64_MAX
    ) {
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

portapy_status PORTAPY_CALL portapy_value_from_dict(
    portapy_runtime runtime,
    portapy_value *out_value
) {
    if (out_value == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_value = PORTAPY_NULL_VALUE;
    portapy_value value = _portapy_cabi_dict_begin_impl(runtime);
    portapy_status status = (portapy_status)_portapy_cabi_last_status_impl();
    if (status == PORTAPY_OK) {
        *out_value = value;
    }
    return status;
}

portapy_status PORTAPY_CALL portapy_dict_set_utf8(
    portapy_runtime runtime,
    portapy_value value,
    const uint8_t *key,
    size_t key_size,
    portapy_value item
) {
    char *text = NULL;
    portapy_status status = copy_key(key, key_size, &text);
    if (status != PORTAPY_OK) {
        return status;
    }
    status = (portapy_status)_portapy_cabi_dict_set_span_impl(
        runtime,
        value,
        text,
        (int64_t)key_size,
        item
    );
    free(text);
    return status;
}

portapy_status PORTAPY_CALL portapy_dict_get_size(
    portapy_runtime runtime,
    portapy_value value,
    size_t *out_size
) {
    if (out_size == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_size = 0;
    int64_t size = _portapy_cabi_dict_get_size_impl(runtime, value);
    portapy_status status = (portapy_status)_portapy_cabi_last_status_impl();
    if (status == PORTAPY_OK) {
        *out_size = (size_t)size;
    }
    return status;
}

portapy_status PORTAPY_CALL portapy_dict_key_copy_utf8(
    portapy_runtime runtime,
    portapy_value value,
    size_t index,
    uint8_t *buffer,
    size_t capacity,
    size_t *out_size
) {
    if (out_size == NULL || index > (size_t)INT64_MAX) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_size = 0;
    int64_t size = _portapy_cabi_dict_key_size_impl(
        runtime,
        value,
        (int64_t)index
    );
    portapy_status status = (portapy_status)_portapy_cabi_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }
    *out_size = (size_t)size;
    if ((size_t)size > capacity || (size > 0 && buffer == NULL)) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    for (int64_t offset = 0; offset < size; ++offset) {
        int64_t byte = _portapy_cabi_dict_key_byte_impl(
            runtime,
            value,
            (int64_t)index,
            offset
        );
        status = (portapy_status)_portapy_cabi_last_status_impl();
        if (status != PORTAPY_OK) {
            return status;
        }
        buffer[offset] = (uint8_t)byte;
    }
    return PORTAPY_OK;
}

portapy_status PORTAPY_CALL portapy_dict_get_item_utf8(
    portapy_runtime runtime,
    portapy_value value,
    const uint8_t *key,
    size_t key_size,
    portapy_value *out_item
) {
    if (out_item == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_item = PORTAPY_NULL_VALUE;
    char *text = NULL;
    portapy_status status = copy_key(key, key_size, &text);
    if (status != PORTAPY_OK) {
        return status;
    }
    portapy_value item = _portapy_cabi_dict_get_item_span_impl(
        runtime,
        value,
        text,
        (int64_t)key_size
    );
    status = (portapy_status)_portapy_cabi_last_status_impl();
    free(text);
    if (status == PORTAPY_OK) {
        *out_item = item;
    }
    return status;
}
