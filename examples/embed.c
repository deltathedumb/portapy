#include "portapy.h"
#include <stdio.h>

int main(void) {
    portapy_config config = {0};
    portapy_runtime runtime = PORTAPY_NULL_RUNTIME;
    portapy_value value = PORTAPY_NULL_VALUE;
    portapy_value_kind kind = PORTAPY_VALUE_OBJECT;
    int64_t answer = 0;

    config.struct_size = sizeof(config);
    config.abi_version = PORTAPY_ABI_VERSION;

    if (portapy_library_initialize() != PORTAPY_OK) return 1;
    if (portapy_runtime_create(&config, &runtime) != PORTAPY_OK) return 2;
    if (portapy_value_from_i64(runtime, 42, &value) != PORTAPY_OK) return 3;
    if (portapy_value_get_kind(runtime, value, &kind) != PORTAPY_OK) return 4;
    if (kind != PORTAPY_VALUE_INT) return 5;
    if (portapy_value_as_i64(runtime, value, &answer) != PORTAPY_OK) return 6;

    printf("%lld\n", (long long)answer);
    portapy_value_release(runtime, value);
    portapy_runtime_destroy(runtime);
    return answer == 42 ? 0 : 7;
}
