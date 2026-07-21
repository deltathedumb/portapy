#include "portapy.h"

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

extern int64_t _portapy_cabi_last_status_impl(void);
extern uint64_t _portapy_cabi_value_from_host_callable_impl(
    uint64_t runtime,
    uint64_t callable_id
);
extern uint64_t _portapy_cabi_value_get_host_callable_id_impl(
    uint64_t runtime,
    uint64_t value
);
extern int64_t _portapy_cabi_host_pending_arg_count_impl(uint64_t runtime);
extern uint64_t _portapy_cabi_host_pending_arg_impl(
    uint64_t runtime,
    int64_t index
);
extern uint64_t _portapy_cabi_host_dispatch_complete_impl(
    uint64_t runtime,
    int64_t status,
    uint64_t result
);


typedef struct host_handler_slot {
    portapy_runtime runtime;
    portapy_host_call_handler handler;
    void *context;
} host_handler_slot;

static host_handler_slot *slots = NULL;
static size_t slot_count = 0;
static size_t slot_capacity = 0;

static host_handler_slot *find_slot(portapy_runtime runtime) {
    for (size_t index = 0; index < slot_count; ++index) {
        if (slots[index].runtime == runtime) {
            return &slots[index];
        }
    }
    return NULL;
}

static host_handler_slot *ensure_slot(portapy_runtime runtime) {
    host_handler_slot *slot = find_slot(runtime);
    if (slot != NULL) {
        return slot;
    }
    if (slot_count == slot_capacity) {
        size_t next_capacity = slot_capacity == 0 ? 8 : slot_capacity * 2;
        host_handler_slot *next = (host_handler_slot *)realloc(
            slots,
            next_capacity * sizeof(host_handler_slot)
        );
        if (next == NULL) {
            return NULL;
        }
        slots = next;
        slot_capacity = next_capacity;
    }
    slot = &slots[slot_count++];
    slot->runtime = runtime;
    slot->handler = NULL;
    slot->context = NULL;
    return slot;
}

portapy_status PORTAPY_CALL portapy_host_set_call_handler(
    portapy_runtime runtime,
    portapy_host_call_handler handler,
    void *context
) {
    if (runtime == PORTAPY_NULL_RUNTIME) {
        return PORTAPY_INVALID_HANDLE;
    }
    host_handler_slot *slot = ensure_slot(runtime);
    if (slot == NULL) {
        return PORTAPY_RUNTIME_ERROR;
    }
    slot->handler = handler;
    slot->context = context;
    return PORTAPY_OK;
}

portapy_status PORTAPY_CALL portapy_value_from_host_callable(
    portapy_runtime runtime,
    uint64_t callable_id,
    portapy_value *out_value
) {
    if (out_value == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_value = PORTAPY_NULL_VALUE;
    portapy_value value = _portapy_cabi_value_from_host_callable_impl(
        runtime,
        callable_id
    );
    portapy_status status = (portapy_status)_portapy_cabi_last_status_impl();
    if (status == PORTAPY_OK) {
        *out_value = value;
    }
    return status;
}

portapy_status PORTAPY_CALL portapy_value_get_host_callable_id(
    portapy_runtime runtime,
    portapy_value value,
    uint64_t *out_callable_id
) {
    if (out_callable_id == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_callable_id = 0;
    uint64_t callable_id = _portapy_cabi_value_get_host_callable_id_impl(
        runtime,
        value
    );
    portapy_status status = (portapy_status)_portapy_cabi_last_status_impl();
    if (status == PORTAPY_OK) {
        *out_callable_id = callable_id;
    }
    return status;
}

uint64_t _portapy_host_dispatch_callback(uint64_t runtime, uint64_t callable_id) {
    host_handler_slot *slot = find_slot(runtime);
    if (slot == NULL || slot->handler == NULL) {
        return _portapy_cabi_host_dispatch_complete_impl(
            runtime,
            PORTAPY_INTERRUPTED,
            PORTAPY_NULL_VALUE
        );
    }

    int64_t raw_count = _portapy_cabi_host_pending_arg_count_impl(runtime);
    portapy_status status = (portapy_status)_portapy_cabi_last_status_impl();
    if (status != PORTAPY_OK || raw_count < 0) {
        return _portapy_cabi_host_dispatch_complete_impl(
            runtime,
            status == PORTAPY_OK ? PORTAPY_RUNTIME_ERROR : status,
            PORTAPY_NULL_VALUE
        );
    }
    size_t count = (size_t)raw_count;
    portapy_value *arguments = NULL;
    if (count != 0) {
        arguments = (portapy_value *)malloc(count * sizeof(portapy_value));
        if (arguments == NULL) {
            return _portapy_cabi_host_dispatch_complete_impl(
                runtime,
                PORTAPY_RUNTIME_ERROR,
                PORTAPY_NULL_VALUE
            );
        }
    }
    for (size_t index = 0; index < count; ++index) {
        arguments[index] = _portapy_cabi_host_pending_arg_impl(
            runtime,
            (int64_t)index
        );
        status = (portapy_status)_portapy_cabi_last_status_impl();
        if (status != PORTAPY_OK) {
            free(arguments);
            return _portapy_cabi_host_dispatch_complete_impl(
                runtime,
                status,
                PORTAPY_NULL_VALUE
            );
        }
    }

    portapy_value result = PORTAPY_NULL_VALUE;
    status = slot->handler(
        slot->context,
        runtime,
        callable_id,
        arguments,
        count,
        &result
    );
    free(arguments);
    return _portapy_cabi_host_dispatch_complete_impl(runtime, status, result);
}
