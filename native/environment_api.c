#include "portapy.h"

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define PORTAPY_DIRECT_CALLABLE_BASE UINT64_C(0x8000000000000000)

typedef struct direct_callable_slot {
    portapy_environment environment;
    uint64_t callable_id;
    portapy_direct_call_handler callable;
    void *context;
} direct_callable_slot;

static direct_callable_slot *direct_slots = NULL;
static size_t direct_slot_count = 0;
static size_t direct_slot_capacity = 0;
static uint64_t next_direct_callable_id = PORTAPY_DIRECT_CALLABLE_BASE;

static direct_callable_slot *find_direct_slot(
    portapy_environment environment,
    uint64_t callable_id
) {
    for (size_t index = 0; index < direct_slot_count; ++index) {
        if (
            direct_slots[index].environment == environment
            && direct_slots[index].callable_id == callable_id
        ) {
            return &direct_slots[index];
        }
    }
    return NULL;
}

static void remove_direct_slot_at(size_t index) {
    if (index >= direct_slot_count) {
        return;
    }
    direct_slots[index] = direct_slots[direct_slot_count - 1];
    direct_slot_count -= 1;
}

static void remove_direct_slot(
    portapy_environment environment,
    uint64_t callable_id
) {
    for (size_t index = 0; index < direct_slot_count; ++index) {
        if (
            direct_slots[index].environment == environment
            && direct_slots[index].callable_id == callable_id
        ) {
            remove_direct_slot_at(index);
            return;
        }
    }
}

static void remove_environment_slots(portapy_environment environment) {
    size_t index = 0;
    while (index < direct_slot_count) {
        if (direct_slots[index].environment == environment) {
            remove_direct_slot_at(index);
        } else {
            index += 1;
        }
    }
}

static portapy_status reserve_direct_slot(
    portapy_environment environment,
    portapy_direct_call_handler callable,
    void *context,
    uint64_t *out_callable_id
) {
    if (callable == NULL || out_callable_id == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    if (direct_slot_count == direct_slot_capacity) {
        size_t next_capacity = direct_slot_capacity == 0 ? 8 : direct_slot_capacity * 2;
        direct_callable_slot *next = (direct_callable_slot *)realloc(
            direct_slots,
            next_capacity * sizeof(direct_callable_slot)
        );
        if (next == NULL) {
            return PORTAPY_RUNTIME_ERROR;
        }
        direct_slots = next;
        direct_slot_capacity = next_capacity;
    }

    uint64_t callable_id = next_direct_callable_id;
    next_direct_callable_id += UINT64_C(1);
    if ((next_direct_callable_id & PORTAPY_DIRECT_CALLABLE_BASE) == 0) {
        next_direct_callable_id = PORTAPY_DIRECT_CALLABLE_BASE;
    }
    direct_callable_slot *slot = &direct_slots[direct_slot_count++];
    slot->environment = environment;
    slot->callable_id = callable_id;
    slot->callable = callable;
    slot->context = context;
    *out_callable_id = callable_id;
    return PORTAPY_OK;
}

int _portapy_environment_is_direct_callable(
    uint64_t runtime,
    uint64_t callable_id
) {
    return find_direct_slot(runtime, callable_id) != NULL;
}

portapy_status _portapy_environment_dispatch_direct(
    uint64_t runtime,
    uint64_t callable_id,
    const portapy_value *arguments,
    size_t argument_count,
    portapy_value *out_result
) {
    direct_callable_slot *slot = find_direct_slot(runtime, callable_id);
    if (slot == NULL) {
        return PORTAPY_NOT_FOUND;
    }
    return slot->callable(
        slot->context,
        runtime,
        arguments,
        argument_count,
        out_result
    );
}

static portapy_status inspect_binding(
    portapy_environment environment,
    const uint8_t *name,
    size_t name_size,
    int *out_exists,
    uint64_t *out_helper_callable_id
) {
    if (out_exists == NULL || out_helper_callable_id == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_exists = 0;
    *out_helper_callable_id = UINT64_C(0);

    portapy_value existing = PORTAPY_NULL_VALUE;
    portapy_status status = portapy_get_global_utf8(
        environment,
        name,
        name_size,
        &existing
    );
    if (status == PORTAPY_NOT_FOUND) {
        (void)portapy_error_clear(environment);
        return PORTAPY_OK;
    }
    if (status != PORTAPY_OK) {
        return status;
    }

    *out_exists = 1;
    uint64_t callable_id = UINT64_C(0);
    status = portapy_value_get_host_callable_id(
        environment,
        existing,
        &callable_id
    );
    if (status == PORTAPY_OK && find_direct_slot(environment, callable_id) != NULL) {
        *out_helper_callable_id = callable_id;
    } else if (status != PORTAPY_OK) {
        (void)portapy_error_clear(environment);
    }

    portapy_status release_status = portapy_value_release(environment, existing);
    if (release_status != PORTAPY_OK) {
        return release_status;
    }
    return PORTAPY_OK;
}

static uint64_t helper_callable_id_for_value(
    portapy_environment environment,
    portapy_value value
) {
    uint64_t callable_id = UINT64_C(0);
    portapy_status status = portapy_value_get_host_callable_id(
        environment,
        value,
        &callable_id
    );
    if (status != PORTAPY_OK) {
        (void)portapy_error_clear(environment);
        return UINT64_C(0);
    }
    if (find_direct_slot(environment, callable_id) == NULL) {
        return UINT64_C(0);
    }
    return callable_id;
}

portapy_status PORTAPY_CALL portapy_new(
    portapy_environment *out_environment
) {
    portapy_config config;
    memset(&config, 0, sizeof(config));
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    return portapy_new_with_config(&config, out_environment);
}

portapy_status PORTAPY_CALL portapy_new_with_config(
    const portapy_config *config,
    portapy_environment *out_environment
) {
    if (config == NULL || out_environment == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_environment = PORTAPY_NULL_ENVIRONMENT;
    portapy_status status = portapy_library_initialize();
    if (status != PORTAPY_OK) {
        return status;
    }
    return portapy_runtime_create(config, out_environment);
}

portapy_status PORTAPY_CALL portapy_destroy(
    portapy_environment environment
) {
    portapy_status status = portapy_runtime_destroy(environment);
    if (
        status == PORTAPY_OK
        || status == PORTAPY_CLOSED
        || status == PORTAPY_INVALID_HANDLE
    ) {
        remove_environment_slots(environment);
    }
    return status;
}

portapy_status PORTAPY_CALL portapy_execute(
    portapy_environment environment,
    const char *source
) {
    static const uint8_t filename[] = "<portapy>";
    if (source == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    return portapy_exec_utf8(
        environment,
        (const uint8_t *)source,
        strlen(source),
        filename,
        sizeof(filename) - 1
    );
}

portapy_status PORTAPY_CALL portapy_evaluate(
    portapy_environment environment,
    const char *expression,
    portapy_value *out_value
) {
    static const uint8_t filename[] = "<portapy-eval>";
    if (expression == NULL || out_value == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    return portapy_eval_utf8(
        environment,
        (const uint8_t *)expression,
        strlen(expression),
        filename,
        sizeof(filename) - 1,
        out_value
    );
}

portapy_status PORTAPY_CALL portapy_add_value_utf8(
    portapy_environment environment,
    const uint8_t *name,
    size_t name_size,
    portapy_value value,
    uint32_t flags
) {
    if (
        environment == PORTAPY_NULL_ENVIRONMENT
        || name == NULL
        || name_size == 0
        || value == PORTAPY_NULL_VALUE
        || (flags & ~PORTAPY_BINDING_REPLACE) != 0
    ) {
        return PORTAPY_INVALID_ARGUMENT;
    }

    int exists = 0;
    uint64_t previous_helper_id = UINT64_C(0);
    portapy_status status = inspect_binding(
        environment,
        name,
        name_size,
        &exists,
        &previous_helper_id
    );
    if (status != PORTAPY_OK) {
        return status;
    }
    if (exists && (flags & PORTAPY_BINDING_REPLACE) == 0) {
        return PORTAPY_INVALID_ARGUMENT;
    }

    uint64_t next_helper_id = helper_callable_id_for_value(environment, value);
    status = portapy_set_global_utf8(environment, name, name_size, value);
    if (
        status == PORTAPY_OK
        && previous_helper_id != UINT64_C(0)
        && previous_helper_id != next_helper_id
    ) {
        remove_direct_slot(environment, previous_helper_id);
    }
    return status;
}

portapy_status PORTAPY_CALL portapy_add_callable_utf8(
    portapy_environment environment,
    const uint8_t *name,
    size_t name_size,
    portapy_direct_call_handler callable,
    void *context,
    uint32_t flags
) {
    if (callable == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }

    uint64_t callable_id = UINT64_C(0);
    portapy_status status = reserve_direct_slot(
        environment,
        callable,
        context,
        &callable_id
    );
    if (status != PORTAPY_OK) {
        return status;
    }

    portapy_value value = PORTAPY_NULL_VALUE;
    status = portapy_value_from_host_callable(
        environment,
        callable_id,
        &value
    );
    if (status != PORTAPY_OK) {
        remove_direct_slot(environment, callable_id);
        return status;
    }

    status = portapy_add_value_utf8(
        environment,
        name,
        name_size,
        value,
        flags
    );
    portapy_status release_status = portapy_value_release(environment, value);
    if (status != PORTAPY_OK) {
        remove_direct_slot(environment, callable_id);
        return status;
    }
    return release_status;
}

portapy_status PORTAPY_CALL portapy_add(
    portapy_environment environment,
    const portapy_binding *binding
) {
    if (
        binding == NULL
        || binding->struct_size < sizeof(portapy_binding)
        || binding->name == NULL
        || binding->name_size == 0
    ) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    if (binding->kind == PORTAPY_BINDING_VALUE) {
        return portapy_add_value_utf8(
            environment,
            binding->name,
            binding->name_size,
            binding->value,
            binding->flags
        );
    }
    if (binding->kind == PORTAPY_BINDING_CALLABLE) {
        return portapy_add_callable_utf8(
            environment,
            binding->name,
            binding->name_size,
            binding->callable,
            binding->context,
            binding->flags
        );
    }
    return PORTAPY_INVALID_ARGUMENT;
}

portapy_status PORTAPY_CALL portapy_add_all(
    portapy_environment environment,
    const portapy_binding *bindings,
    size_t binding_count
) {
    if (binding_count != 0 && bindings == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    for (size_t index = 0; index < binding_count; ++index) {
        portapy_status status = portapy_add(environment, &bindings[index]);
        if (status != PORTAPY_OK) {
            return status;
        }
    }
    return PORTAPY_OK;
}
