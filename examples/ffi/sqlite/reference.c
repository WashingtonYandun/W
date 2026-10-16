#include "adapter.h"
#include <stdio.h>

static int insert(void *handle, int64_t id, int64_t value) {
    return value < 0 ? -1 : pilot_insert(handle, id, value);
}

int main(void) {
    void *handle = pilot_open();
    int64_t rows = pilot_rows();
    if (!pilot_is_open(handle) || rows < 1) {
        printf("open or input failure %d %lld\n", pilot_status(handle), (long long)rows);
        int disposed = pilot_dispose(handle);
        printf("%d %d\n", disposed, pilot_live_resources());
        return 0;
    }
    int status = pilot_begin(handle);
    for (int64_t id = 0; status == 0 && id < rows; id++) status = insert(handle, id, INT64_C(4294967296) + id * 10);
    if (status == 0) status = pilot_commit(handle);
    if (status != 0) {
        printf("populate failure %d\n", status);
        int disposed = pilot_dispose(handle);
        printf("%d %d\n", disposed, pilot_live_resources());
        return 0;
    }
    printf("%d\n", pilot_version());
    int64_t count = pilot_count(handle);
    int64_t total = pilot_total(handle);
    printf("%lld %lld\n", (long long)count, (long long)total);
    int duplicate = insert(handle, 0, 1);
    int invalid = insert(handle, rows, -1);
    int closed = pilot_close(handle);
    int after_close = insert(handle, rows, 1);
    int closed_again = pilot_close(handle);
    int disposed = pilot_dispose(handle);
    printf("%d %d %d %d %d %d %d\n", duplicate, invalid, after_close,
           closed, closed_again, disposed, pilot_live_resources());
    return 0;
}
