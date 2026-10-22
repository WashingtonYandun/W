#ifndef WYSNA_SQLITE_PILOT_H
#define WYSNA_SQLITE_PILOT_H

#include <stdbool.h>
#include <stdint.h>

void *pilot_open(void);
bool pilot_is_open(void *handle);
int32_t pilot_status(void *handle);
int32_t pilot_begin(void *handle);
int32_t pilot_insert(void *handle, int64_t id, int64_t value);
int32_t pilot_commit(void *handle);
int32_t pilot_record_import(void *handle, int64_t rows, int64_t input_bytes);
int64_t pilot_import_count(void *handle);
int32_t pilot_rollback(void *handle);
int64_t pilot_count(void *handle);
int64_t pilot_total(void *handle);
int32_t pilot_close(void *handle);
int32_t pilot_dispose(void *handle);
int32_t pilot_live_resources(void);
int32_t pilot_version(void);
int64_t pilot_rows(void);

#endif
