#include "portapy.h"

#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>


typedef struct managed_callback_entry {
    uint64_t callable_id;
    portapy_environment_callback callback;
    void *context;
} managed_callback_entry;

struct portapy_environment {
    portapy_runtime runtime;
    managed_callback_entry *callbacks;
    size_t callback_count;
    size_t callback_capacity;
    uint64_t next_callable_id;
};


static portapy_status utf16_to_utf8(
    const uint16_t *text,
    size_t length,
    uint8_t **out_data,
    size_t *out_size
) {
    if (out_data == NULL || out_size == NULL || (length != 0 && text == NULL)) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_data = NULL;
    *out_size = 0;
    if (length > (SIZE_MAX - 1) / 3) {
        return PORTAPY_INVALID_ARGUMENT;
    }

    uint8_t *data = (uint8_t *)malloc(length * 3 + 1);
    if (data == NULL) {
        return PORTAPY_RUNTIME_ERROR;
    }

    size_t source_index = 0;
    size_t target_index = 0;
    while (source_index < length) {
        uint32_t codepoint = text[source_index++];
        if (codepoint >= 0xd800 && codepoint <= 0xdbff) {
            if (source_index >= length) {
                free(data);
                return PORTAPY_INVALID_ARGUMENT;
            }
            uint32_t low = text[source_index++];
            if (low < 0xdc00 || low > 0xdfff) {
                free(data);
                return PORTAPY_INVALID_ARGUMENT;
            }
            codepoint = UINT32_C(0x10000)
                + ((codepoint - UINT32_C(0xd800)) << 10)
                + (low - UINT32_C(0xdc00));
        } else if (codepoint >= 0xdc00 && codepoint <= 0xdfff) {
            free(data);
            return PORTAPY_INVALID_ARGUMENT;
        }

        if (codepoint <= UINT32_C(0x7f)) {
            data[target_index++] = (uint8_t)codepoint;
        } else if (codepoint <= UINT32_C(0x7ff)) {
            data[target_index++] = (uint8_t)(UINT32_C(0xc0) | (codepoint >> 6));
            data[target_index++] = (uint8_t)(UINT32_C(0x80) | (codepoint & UINT32_C(0x3f)));
        } else if (codepoint <= UINT32_C(0xffff)) {
            data[target_index++] = (uint8_t)(UINT32_C(0xe0) | (codepoint >> 12));
            data[target_index++] = (uint8_t)(UINT32_C(0x80) | ((codepoint >> 6) & UINT32_C(0x3f)));
            data[target_index++] = (uint8_t)(UINT32_C(0x80) | (codepoint & UINT32_C(0x3f)));
        } else {
            data[target_index++] = (uint8_t)(UINT32_C(0xf0) | (codepoint >> 18));
            data[target_index++] = (uint8_t)(UINT32_C(0x80) | ((codepoint >> 12) & UINT32_C(0x3f)));
            data[target_index++] = (uint8_t)(UINT32_C(0x80) | ((codepoint >> 6) & UINT32_C(0x3f)));
            data[target_index++] = (uint8_t)(UINT32_C(0x80) | (codepoint & UINT32_C(0x3f)));
        }
    }

    data[target_index] = 0;
    *out_data = data;
    *out_size = target_index;
    return PORTAPY_OK;
}


static managed_callback_entry *find_callback(
    portapy_environment *environment,
    uint64_t callable_id
) {
    if (environment == NULL) {
        return NULL;
    }
    for (size_t index = 0; index < environment->callback_count; ++index) {
        if (environment->callbacks[index].callable_id == callable_id) {
            return &environment->callbacks[index];
        }
    }
    return NULL;
}


static portapy_status PORTAPY_CALL dispatch_managed_callback(
    void *context,
    portapy_runtime runtime,
    uint64_t callable_id,
    const portapy_value *arguments,
    size_t argument_count,
    portapy_value *out_result
) {
    portapy_environment *environment = (portapy_environment *)context;
    managed_callback_entry *entry = find_callback(environment, callable_id);
    if (
        environment == NULL
        || environment->runtime != runtime
        || entry == NULL
        || entry->callback == NULL
        || out_result == NULL
    ) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    return entry->callback(
        entry->context,
        runtime,
        arguments,
        argument_count,
        out_result
    );
}


static portapy_status reserve_callback(portapy_environment *environment) {
    if (environment->callback_count < environment->callback_capacity) {
        return PORTAPY_OK;
    }
    size_t next_capacity = environment->callback_capacity == 0
        ? 8
        : environment->callback_capacity * 2;
    if (next_capacity < environment->callback_capacity) {
        return PORTAPY_RUNTIME_ERROR;
    }
    managed_callback_entry *next = (managed_callback_entry *)realloc(
        environment->callbacks,
        next_capacity * sizeof(managed_callback_entry)
    );
    if (next == NULL) {
        return PORTAPY_RUNTIME_ERROR;
    }
    environment->callbacks = next;
    environment->callback_capacity = next_capacity;
    return PORTAPY_OK;
}


portapy_status PORTAPY_CALL portapy_environment_create(
    portapy_environment **out_environment
) {
    if (out_environment == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    *out_environment = NULL;

    portapy_status status = portapy_library_initialize();
    if (status != PORTAPY_OK) {
        return status;
    }

    portapy_environment *environment = (portapy_environment *)calloc(
        1,
        sizeof(portapy_environment)
    );
    if (environment == NULL) {
        return PORTAPY_RUNTIME_ERROR;
    }
    environment->next_callable_id = UINT64_C(1);

    portapy_config config = {0};
    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;
    status = portapy_runtime_create(&config, &environment->runtime);
    if (status != PORTAPY_OK) {
        free(environment);
        return status;
    }

    status = portapy_host_set_call_handler(
        environment->runtime,
        dispatch_managed_callback,
        environment
    );
    if (status != PORTAPY_OK) {
        portapy_runtime_destroy(environment->runtime);
        free(environment);
        return status;
    }

    *out_environment = environment;
    return PORTAPY_OK;
}


portapy_status PORTAPY_CALL portapy_environment_destroy(
    portapy_environment *environment
) {
    if (environment == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    portapy_status handler_status = portapy_host_set_call_handler(
        environment->runtime,
        NULL,
        NULL
    );
    portapy_status destroy_status = portapy_runtime_destroy(environment->runtime);
    free(environment->callbacks);
    free(environment);
    if (destroy_status != PORTAPY_OK) {
        return destroy_status;
    }
    return handler_status;
}


portapy_runtime PORTAPY_CALL portapy_environment_get_runtime(
    const portapy_environment *environment
) {
    return environment == NULL ? PORTAPY_NULL_RUNTIME : environment->runtime;
}


portapy_status PORTAPY_CALL portapy_environment_add_callback_utf16(
    portapy_environment *environment,
    const uint16_t *name,
    size_t name_length,
    portapy_environment_callback callback,
    void *context
) {
    if (environment == NULL || callback == NULL || name_length == 0) {
        return PORTAPY_INVALID_ARGUMENT;
    }

    uint8_t *utf8_name = NULL;
    size_t utf8_name_size = 0;
    portapy_status status = utf16_to_utf8(
        name,
        name_length,
        &utf8_name,
        &utf8_name_size
    );
    if (status != PORTAPY_OK) {
        return status;
    }

    status = reserve_callback(environment);
    if (status != PORTAPY_OK) {
        free(utf8_name);
        return status;
    }

    uint64_t callable_id = environment->next_callable_id++;
    if (callable_id == 0) {
        free(utf8_name);
        return PORTAPY_RUNTIME_ERROR;
    }

    portapy_value callable = PORTAPY_NULL_VALUE;
    status = portapy_value_from_host_callable(
        environment->runtime,
        callable_id,
        &callable
    );
    if (status == PORTAPY_OK) {
        status = portapy_set_global_utf8(
            environment->runtime,
            utf8_name,
            utf8_name_size,
            callable
        );
    }
    if (callable != PORTAPY_NULL_VALUE) {
        portapy_status release_status = portapy_value_release(
            environment->runtime,
            callable
        );
        if (status == PORTAPY_OK && release_status != PORTAPY_OK) {
            status = release_status;
        }
    }
    free(utf8_name);
    if (status != PORTAPY_OK) {
        return status;
    }

    managed_callback_entry *entry = &environment->callbacks[
        environment->callback_count++
    ];
    entry->callable_id = callable_id;
    entry->callback = callback;
    entry->context = context;
    return PORTAPY_OK;
}


portapy_status PORTAPY_CALL portapy_environment_execute_utf16(
    portapy_environment *environment,
    const uint16_t *source,
    size_t source_length
) {
    if (environment == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }

    uint8_t *utf8_source = NULL;
    size_t utf8_source_size = 0;
    portapy_status status = utf16_to_utf8(
        source,
        source_length,
        &utf8_source,
        &utf8_source_size
    );
    if (status != PORTAPY_OK) {
        return status;
    }

    static const uint8_t filename[] = "<managed>";
    status = portapy_exec_utf8(
        environment->runtime,
        utf8_source,
        utf8_source_size,
        filename,
        sizeof(filename) - 1
    );
    free(utf8_source);
    return status;
}
