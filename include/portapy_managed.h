#ifndef PORTAPY_MANAGED_H
#define PORTAPY_MANAGED_H

#include "portapy.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct portapy_environment portapy_environment;

typedef portapy_status (PORTAPY_CALL *portapy_environment_callback)(
    void *context,
    portapy_runtime runtime,
    const portapy_value *arguments,
    size_t argument_count,
    portapy_value *out_result
);

PORTAPY_API portapy_status PORTAPY_CALL portapy_environment_create(
    portapy_environment **out_environment
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_environment_destroy(
    portapy_environment *environment
);
PORTAPY_API portapy_runtime PORTAPY_CALL portapy_environment_get_runtime(
    const portapy_environment *environment
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_environment_add_callback_utf16(
    portapy_environment *environment,
    const uint16_t *name,
    size_t name_length,
    portapy_environment_callback callback,
    void *context
);
PORTAPY_API portapy_status PORTAPY_CALL portapy_environment_execute_utf16(
    portapy_environment *environment,
    const uint16_t *source,
    size_t source_length
);

#ifdef __cplusplus
}
#endif

#endif
