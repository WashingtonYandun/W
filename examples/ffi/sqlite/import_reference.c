/* Independent C99 implementation of the same bounded, two-column CSV contract. */
#include "adapter.h"
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int64_t line; const char *reason; int32_t database; } ImportError;

static bool decimal(const unsigned char *text, size_t length, int64_t *value, ImportError *error) {
    *value = 0;
    if (!length) { error->reason = "empty integer"; return false; }
    for (size_t index = 0; index < length; index++) {
        int digit = text[index] - '0';
        if (digit < 0 || digit > 9) { error->reason = "expected ASCII decimal"; return false; }
        if (*value > (INT64_MAX - digit) / 10) { error->reason = "integer overflow"; return false; }
        *value = *value * 10 + digit;
    }
    return true;
}

static int64_t populate(void *handle, const unsigned char *text, size_t length, ImportError *error, bool commit) {
    error->database = pilot_begin(handle);
    if (error->database) return -1;
    size_t start = 0;
    int64_t rows = 0;
    error->line = 1;
    for (size_t index = 0; index <= length; index++) {
        if (index != length && text[index] != '\n') continue;
        if (index == length && start == index) break;
        size_t end = index;
        if (end > start && text[end - 1] == '\r') end--;
        if (error->line == 1) {
            if (end - start != 8 || memcmp(text + start, "id,value", 8)) {
                error->reason = "expected id,value header"; return -1;
            }
        } else {
            if (rows >= 100000) { error->reason = "row limit exceeded"; return -1; }
            const unsigned char *comma = memchr(text + start, ',', end - start);
            if (!comma || memchr(comma + 1, ',', (size_t)(text + end - comma - 1))) {
                error->reason = "expected two columns"; return -1;
            }
            int64_t id, value;
            if (!decimal(text + start, (size_t)(comma - text - start), &id, error) ||
                !decimal(comma + 1, (size_t)(text + end - comma - 1), &value, error)) return -1;
            error->database = pilot_insert(handle, id, value);
            if (error->database) return -1;
            rows++;
        }
        start = index + 1;
        error->line++;
    }
    if (!rows) { error->reason = "no measurements"; return -1; }
    (void)pilot_total(handle);
    error->database = pilot_status(handle);
    if (error->database) return -1;
    if (!commit) { error->database = pilot_rollback(handle); return error->database ? -1 : rows; }
    error->database = pilot_record_import(handle, rows, (int64_t)length);
    if (error->database) return -1;
    error->database = pilot_commit(handle);
    return error->database ? -1 : rows;
}

int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--version")) { printf("%d\n", pilot_version()); return 0; }
    bool checking = argc == 3 && !strcmp(argv[1], "--check");
    if (argc == 2 && !strcmp(argv[1], "--status")) {
        void *handle = pilot_open();
        if (!pilot_is_open(handle)) { printf("database error %d\n", pilot_status(handle)); pilot_dispose(handle); return 1; }
        int64_t count = pilot_count(handle);
        int32_t status = pilot_status(handle);
        int64_t total = pilot_total(handle);
        int32_t total_status = pilot_status(handle);
        int64_t imports = pilot_import_count(handle);
        if (!status) status = total_status ? total_status : pilot_status(handle);
        int32_t closed = pilot_dispose(handle);
        if (status || closed) { printf("database error %d\n", status ? status : closed); return 1; }
        printf("status %lld %lld %lld\nresources %d\n", (long long)count, (long long)total, (long long)imports, pilot_live_resources());
        return 0;
    }
    if (argc != 2 && !checking) {
        puts("usage: import_csv [--check] measurements.csv | --status (W_SQLITE_DB selects database)"); return 2;
    }
    FILE *input = fopen(argv[checking ? 2 : 1], "rb");
    if (!input) { puts("io error"); return 2; }
    if (fseek(input, 0, SEEK_END)) { fclose(input); puts("io error"); return 2; }
    long size = ftell(input);
    if (size < 0 || fseek(input, 0, SEEK_SET)) { fclose(input); puts("io error"); return 2; }
    unsigned char *text = malloc((size_t)size + 1);
    if (!text) { fclose(input); puts("io error"); return 2; }
    size_t length = fread(text, 1, (size_t)size, input);
    int failed = ferror(input) || length != (size_t)size;
    if (fclose(input)) failed = 1;
    if (failed) { free(text); puts("io error"); return 2; }
    if (length > 8388608) { free(text); puts("csv error 0 input size limit exceeded"); return 2; }
    void *handle = pilot_open();
    if (!pilot_is_open(handle)) {
        printf("database error %d\n", pilot_status(handle));
        pilot_dispose(handle); free(text);
        printf("resources %d\n", pilot_live_resources()); return 1;
    }
    ImportError error = {0, NULL, 0};
    int64_t rows = populate(handle, text, length, &error, !checking);
    free(text);
    if (rows < 0) {
        if (error.database) printf("database error %d\n", error.database);
        else printf("csv error %lld %s\n", (long long)error.line, error.reason);
        int32_t rollback = pilot_rollback(handle);
        if (rollback) printf("rollback error %d\n", rollback);
    } else {
        int64_t count = pilot_count(handle);
        int64_t total = pilot_total(handle);
        if (checking) printf("validated %lld\n", (long long)rows);
        else printf("imported %lld %lld %lld\n", (long long)rows, (long long)count, (long long)total);
    }
    int32_t closed = pilot_dispose(handle);
    printf("resources %d\n", pilot_live_resources());
    return closed || rows < 0 ? 1 : 0;
}
