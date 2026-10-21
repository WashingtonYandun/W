#ifndef W_HOST_H
#define W_HOST_H
/* Internal scalar/opaque ABI for bounded binary I/O. Handles are checked IDs,
 * never exposed allocation addresses; stale handles cannot access freed storage. */
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#include <windows.h>
#endif

typedef struct WHostEntry {
    uintptr_t id;
    int kind;
    void* data;
    size_t length;
    size_t capacity;
    struct WHostEntry* next;
} WHostEntry;
static WHostEntry* w_host_entries = NULL;
static uintptr_t w_host_next_id = 1;
static bool w_host_initialized = false;

static WHostEntry* w_host_find(void* handle, int kind) {
    for (WHostEntry* entry = w_host_entries; entry; entry = entry->next)
        if (entry->id == (uintptr_t)handle && entry->kind == kind) return entry;
    return NULL;
}
static int64_t w_host_close(void* handle) {
    WHostEntry** slot = &w_host_entries;
    while (*slot && (*slot)->id != (uintptr_t)handle) slot = &(*slot)->next;
    if (!*slot) return 0;
    WHostEntry* entry = *slot;
    /* fclose consumes the stream even when flushing fails. */
    int status = entry->kind == 2 ? fclose((FILE*)entry->data) : 0;
    if (entry->kind == 1) free(entry->data);
    *slot = entry->next;
    free(entry);
    return status == 0 ? 0 : -1;
}
static void w_host_cleanup(void) {
    while (w_host_entries) w_host_close((void*)w_host_entries->id);
}
static void* w_host_new(int kind, void* data) {
    if (!w_host_initialized) {
        if (atexit(w_host_cleanup) != 0) w_runtime_fail("W4003", "Cannot register resource cleanup");
        w_host_initialized = true;
    }
    if (w_host_next_id == UINTPTR_MAX) w_runtime_fail("W4003", "Host handle identity exhausted");
    WHostEntry* entry = (WHostEntry*)w_alloc_safe(sizeof(WHostEntry));
    entry->id = w_host_next_id++;
    entry->kind = kind; entry->data = data; entry->length = 0; entry->capacity = 0;
    entry->next = w_host_entries; w_host_entries = entry;
    return (void*)entry->id;
}
static void* w_host_claim(void* raw) {
    for (WHostEntry* entry = w_host_entries; entry; entry = entry->next)
        if (entry->kind == 3 && entry->data == raw) return NULL;
    return w_host_new(3, raw);
}
static int64_t w_host_claim_valid(void* handle) { return w_host_find(handle, 3) != NULL; }
static void* w_host_buffer_new(void) { return w_host_new(1, NULL); }
static int64_t w_host_buffer_size(void* handle) {
    WHostEntry* entry = w_host_find(handle, 1);
    return entry ? (int64_t)entry->length : -1;
}
static int64_t w_host_buffer_get(void* handle, int64_t index) {
    WHostEntry* entry = w_host_find(handle, 1);
    return entry && index >= 0 && (uint64_t)index < entry->length ? ((unsigned char*)entry->data)[index] : -1;
}
static int64_t w_host_buffer_append(void* handle, int64_t value) {
    WHostEntry* entry = w_host_find(handle, 1);
    if (!entry || value < 0 || value > 255) return -1;
    if (entry->length == entry->capacity) {
        if (entry->capacity > SIZE_MAX / 2 - 1) return -1;
        entry->capacity = entry->capacity ? entry->capacity * 2 : 64;
        entry->data = w_realloc_safe(entry->data, entry->capacity);
    }
    ((unsigned char*)entry->data)[entry->length++] = (unsigned char)value;
    return 0;
}
static char* w_host_path(void* handle) {
    WHostEntry* entry = w_host_find(handle, 1);
    if (!entry || !entry->length || memchr(entry->data, 0, entry->length)) return NULL;
    char* path = (char*)w_alloc_safe(entry->length + 1);
    memcpy(path, entry->data, entry->length); path[entry->length] = 0;
    return path;
}
#ifdef _WIN32
static wchar_t* w_host_wide(const char* text) {
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, NULL, 0);
    if (!count) return NULL;
    wchar_t* wide = (wchar_t*)w_alloc_safe((size_t)count * sizeof(wchar_t));
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, wide, count)) { free(wide); return NULL; }
    return wide;
}
#endif
static void* w_host_file_open(void* path_handle, int64_t mode) {
    char* path = w_host_path(path_handle);
    if (!path || mode < 0 || mode > 2) { free(path); return NULL; }
    const char* modes[] = { "rb", "wb", "ab" };
#ifdef _WIN32
    wchar_t* wide = w_host_wide(path);
    const wchar_t* wide_modes[] = { L"rb", L"wb", L"ab" };
    FILE* file = wide ? _wfopen(wide, wide_modes[mode]) : NULL;
    free(wide);
#else
    FILE* file = fopen(path, modes[mode]);
#endif
    free(path);
    return file ? w_host_new(2, file) : NULL;
}
static int64_t w_host_file_read(void* file_handle, void* buffer_handle, int64_t count) {
    WHostEntry* file = w_host_find(file_handle, 2);
    WHostEntry* buffer = w_host_find(buffer_handle, 1);
    /* An explicit bound prevents an untrusted request from allocating a whole file. */
    if (!file || !buffer || count <= 0 || count > 16777216) return -1;
    if ((uint64_t)count > buffer->capacity) {
        buffer->capacity = (size_t)count;
        buffer->data = w_realloc_safe(buffer->data, buffer->capacity);
    }
    buffer->length = fread(buffer->data, 1, (size_t)count, (FILE*)file->data);
    return ferror((FILE*)file->data) ? -1 : (int64_t)buffer->length;
}
static int64_t w_host_file_write(void* file_handle, void* buffer_handle) {
    WHostEntry* file = w_host_find(file_handle, 2);
    WHostEntry* buffer = w_host_find(buffer_handle, 1);
    if (!file || !buffer) return -1;
    if (!buffer->length) return 0;
    return fwrite(buffer->data, 1, buffer->length, (FILE*)file->data) == buffer->length ? 0 : -1;
}
static int64_t w_host_is_open(void* handle) { return w_host_find(handle, 2) != NULL; }
/* Operations: exists, size, mkdir, remove, rename. Failures return -1. */
static int64_t w_host_fs(void* first, void* second, int64_t operation) {
    char* path = w_host_path(first);
    char* other = operation == 4 ? w_host_path(second) : NULL;
    if (!path || (operation == 4 && !other)) { free(path); free(other); return -1; }
    int64_t result = -1;
#ifdef _WIN32
    wchar_t* wide = w_host_wide(path);
    wchar_t* wide_other = other ? w_host_wide(other) : NULL;
    struct _stat64 status;
    if (wide) {
        if (operation <= 1) result = _wstat64(wide, &status) == 0 ? (operation == 0 ? 1 : status.st_size) : (operation == 0 && errno == ENOENT ? 0 : -1);
        else if (operation == 2) result = _wmkdir(wide) == 0 ? 0 : -1;
        else if (operation == 3) result = _wremove(wide) == 0 ? 0 : -1;
        else if (operation == 4 && wide_other) result = _wrename(wide, wide_other) == 0 ? 0 : -1;
    }
    free(wide); free(wide_other);
#else
    struct stat status;
    if (operation <= 1) result = stat(path, &status) == 0 ? (operation == 0 ? 1 : status.st_size) : (operation == 0 && errno == ENOENT ? 0 : -1);
    else if (operation == 2) result = mkdir(path, 0777) == 0 ? 0 : -1;
    else if (operation == 3) result = remove(path) == 0 ? 0 : -1;
    else if (operation == 4) result = rename(path, other) == 0 ? 0 : -1;
#endif
    free(path); free(other); return result;
}
#endif
