#include "portapy.h"

#include <stddef.h>
#include <stdint.h>

extern int64_t _portapy_cabi_last_status_impl(void);
extern uint64_t _portapy_cabi_tuple_begin_impl(uint64_t runtime, int64_t count);
extern int64_t _portapy_cabi_tuple_set_item_impl(
    uint64_t runtime,
    uint64_t tuple_value,
    int64_t index,
    uint64_t item
);
extern int64_t _portapy_cabi_tuple_finish_impl(
    uint64_t runtime,
    uint64_t tuple_value
);
extern int64_t _portapy_cabi_tuple_get_size_impl(
    uint64_t runtime,
    uint64_t value
);
extern uint64_t _portapy_cabi_tuple_get_item_impl(
    uint64_t runtime,
    uint64_t value,
    int64_t index
);
extern int64_t _portapy_cabi_tuple_release_impl(
    uint64_t runtime,
    uint64_t value
);

portapy_status PORTAPY_CALL portapy_value_from_tuple(
    portapy_runtime runtime,
    const portapy_value *items,
    size_t item_count,
    portapy_value *out_value
) {
    if (
        out_value == NULL
        || item_count > (size_t)INT64_MAX
        || (item_count != 0 && items == NULL)
    ) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_value = PORTAPY_NULL_VALUE;

    portapy_value value = _portapy_cabi_tuple_begin_impl(
        runtime,
        (int64_t)item_count
    );
    portapy_status status = (portapy_status)_portapy_cabi_last_status_impl();
    if (status != PORTAPY_OK) {
        return status;
    }

    for (size_t index = 0; index < item_count; ++index) {
        status = (portapy_status)_portapy_cabi_tuple_set_item_impl(
            runtime,
            value,
            (int64_t)index,
            items[index]
        );
        if (status != PORTAPY_OK) {
            (void)_portapy_cabi_tuple_release_impl(runtime, value);
            return status;
        }
    }

    status = (portapy_status)_portapy_cabi_tuple_finish_impl(runtime, value);
    if (status != PORTAPY_OK) {
        (void)_portapy_cabi_tuple_release_impl(runtime, value);
        return status;
    }
    *out_value = value;
    return PORTAPY_OK;
}

portapy_status PORTAPY_CALL portapy_tuple_get_size(
    portapy_runtime runtime,
    portapy_value value,
    size_t *out_size
) {
    if (out_size == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_size = 0;
    int64_t size = _portapy_cabi_tuple_get_size_impl(runtime, value);
    portapy_status status = (portapy_status)_portapy_cabi_last_status_impl();
    if (status == PORTAPY_OK) {
        *out_size = (size_t)size;
    }
    return status;
}

portapy_status PORTAPY_CALL portapy_tuple_get_item(
    portapy_runtime runtime,
    portapy_value value,
    size_t index,
    portapy_value *out_item
) {
    if (out_item == NULL || index > (size_t)INT64_MAX) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_item = PORTAPY_NULL_VALUE;
    portapy_value item = _portapy_cabi_tuple_get_item_impl(
        runtime,
        value,
        (int64_t)index
    );
    portapy_status status = (portapy_status)_portapy_cabi_last_status_impl();
    if (status == PORTAPY_OK) {
        *out_item = item;
    }
    return status;
}
