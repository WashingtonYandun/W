#include <stdint.h>
#include <stdlib.h>
#ifdef _WIN32
#define AUDIT_EXPORT __declspec(dllexport)
#else
#define AUDIT_EXPORT
#endif
static int32_t live;
static int32_t fail_close;
AUDIT_EXPORT void audit_fail_close(void) { fail_close = 1; }
AUDIT_EXPORT void *audit_open(void) {
    void *handle = malloc(1);
    if (!handle) abort();
    live++;
    return handle;
}
AUDIT_EXPORT int32_t audit_dispose(void *handle) {
    if (fail_close) { fail_close = 0; return 5; }
    free(handle);
    live--;
    return 0;
}
AUDIT_EXPORT int32_t audit_live(void) { return live; }
