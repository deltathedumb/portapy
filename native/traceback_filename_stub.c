#include "portapy.h"

#include <stddef.h>
#include <stdint.h>

/*
 * Base native probes share the exec/eval ABI wrappers with the full host-call
 * artifact but do not contain generated traceback state. Their bridge is a
 * deliberate no-op. The final host-call relink omits this object and links
 * native/traceback_glue.c, which provides the real implementation.
 */
portapy_status _portapy_traceback_set_filename_utf8_bridge(
    portapy_runtime runtime,
    const uint8_t *filename,
    size_t filename_size
) {
    if (runtime == PORTAPY_NULL_RUNTIME) {
        return PORTAPY_INVALID_HANDLE;
    }
    if (filename_size != 0 && filename == NULL) {
        return PORTAPY_INVALID_ARGUMENT;
    }
    return PORTAPY_OK;
}
