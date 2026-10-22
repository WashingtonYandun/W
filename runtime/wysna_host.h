#ifndef W_HOST_H
#define W_HOST_H
/* Internal scalar/opaque ABI for bounded binary I/O. Handles are checked IDs,
 * never exposed allocation addresses; stale handles cannot access freed storage. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <io.h>
#include <direct.h>
#include <wchar.h>
#endif

/* Guard against POSIX unistd.h access() macros colliding with WTag W_OK */
#ifdef W_OK
#undef W_OK
#endif

typedef struct WysnaHostEntry {
    uintptr_t id;
    int kind;
    void* data;
    size_t length;
    size_t capacity;
    struct WysnaHostEntry* next;
} WysnaHostEntry;
static WysnaHostEntry* wysna_host_entries = NULL;
static uintptr_t wysna_host_next_id = 1;
static bool wysna_host_initialized = false;
/* Error codes are captured immediately, before cleanup can overwrite errno. */
static int64_t wysna_host_error_code = 0;
static int64_t wysna_host_error_domain = 0; /* 0 none, 1 errno, 2 Win32 */
static int64_t wysna_host_last_error(void) { return wysna_host_error_code; }
static int64_t wysna_host_last_error_domain(void) { return wysna_host_error_domain; }
static int64_t wysna_host_errno(int code) {
    wysna_host_error_code = code ? code : EIO; wysna_host_error_domain = 1; return -1;
}

static WysnaHostEntry* wysna_host_find(void* handle, int kind) {
    for (WysnaHostEntry* entry = wysna_host_entries; entry; entry = entry->next)
        if (entry->id == (uintptr_t)handle && entry->kind == kind) return entry;
    return NULL;
}
static int64_t wysna_host_close(void* handle) {
    WysnaHostEntry** slot = &wysna_host_entries;
    while (*slot && (*slot)->id != (uintptr_t)handle) slot = &(*slot)->next;
    if (!*slot) return 0;
    WysnaHostEntry* entry = *slot;
    /* fclose consumes the stream even when flushing fails. */
    errno = 0;
    int status = entry->kind == 2 ? fclose((FILE*)entry->data) : 0;
    int close_error = errno;
    if (entry->kind == 1) free(entry->data);
    *slot = entry->next;
    free(entry);
    return status == 0 ? 0 : wysna_host_errno(close_error);
}
static WVal wysna_host_owned_pointer(void* address) {
    return wysna_managed_pointer(address, wysna_host_close);
}
static void* wysna_host_borrow(void* address) { return address; }
static int64_t wysna_host_active_handles(void) {
    int64_t count = 0;
    for (WysnaHostEntry* entry = wysna_host_entries; entry; entry = entry->next) count++;
    return count;
}
static int64_t wysna_host_active_bytes(void) {
    int64_t count = 0;
    for (WysnaHostEntry* entry = wysna_host_entries; entry; entry = entry->next)
        if (entry->kind == 1) count += (int64_t)entry->capacity;
    return count;
}
static void wysna_host_cleanup(void) {
    while (wysna_host_entries) wysna_host_close((void*)wysna_host_entries->id);
}
static void* wysna_host_new(int kind, void* data) {
    if (!wysna_host_initialized) {
        if (atexit(wysna_host_cleanup) != 0) wysna_runtime_fail("W4003", "Cannot register resource cleanup");
        wysna_host_initialized = true;
    }
    if (wysna_host_next_id == UINTPTR_MAX) wysna_runtime_fail("W4003", "Host handle identity exhausted");
    WysnaHostEntry* entry = (WysnaHostEntry*)wysna_alloc_safe(sizeof(WysnaHostEntry));
    entry->id = wysna_host_next_id++;
    entry->kind = kind; entry->data = data; entry->length = 0; entry->capacity = 0;
    entry->next = wysna_host_entries; wysna_host_entries = entry;
    return (void*)entry->id;
}
static void* wysna_host_claim(void* raw) {
    for (WysnaHostEntry* entry = wysna_host_entries; entry; entry = entry->next)
        if (entry->kind == 3 && entry->data == raw) return NULL;
    return wysna_host_new(3, raw);
}
static int64_t wysna_host_claim_valid(void* handle) { return wysna_host_find(handle, 3) != NULL; }
static void* wysna_host_buffer_new(void) { return wysna_host_new(1, NULL); }
static int64_t wysna_host_buffer_size(void* handle) {
    WysnaHostEntry* entry = wysna_host_find(handle, 1);
    return entry ? (int64_t)entry->length : -1;
}
static int64_t wysna_host_buffer_get(void* handle, int64_t index) {
    WysnaHostEntry* entry = wysna_host_find(handle, 1);
    return entry && index >= 0 && (uint64_t)index < entry->length ? ((unsigned char*)entry->data)[index] : -1;
}
static int64_t wysna_host_buffer_append(void* handle, int64_t value) {
    WysnaHostEntry* entry = wysna_host_find(handle, 1);
    if (!entry || value < 0 || value > 255) return -1;
    if (entry->length == entry->capacity) {
        if (entry->capacity > SIZE_MAX / 2 - 1) return -1;
        entry->capacity = entry->capacity ? entry->capacity * 2 : 64;
        entry->data = wysna_realloc_safe(entry->data, entry->capacity);
    }
    ((unsigned char*)entry->data)[entry->length++] = (unsigned char)value;
    return 0;
}
static char* wysna_host_path(void* handle) {
    WysnaHostEntry* entry = wysna_host_find(handle, 1);
    if (!entry || !entry->length || memchr(entry->data, 0, entry->length)) return NULL;
    char* path = (char*)wysna_alloc_safe(entry->length + 1);
    memcpy(path, entry->data, entry->length); path[entry->length] = 0;
    return path;
}
#ifdef _WIN32
static wchar_t* wysna_host_wide(const char* text) {
    if (!text) return NULL;
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, NULL, 0);
    if (!count) {
        count = MultiByteToWideChar(CP_ACP, 0, text, -1, NULL, 0);
        if (!count) return NULL;
        wchar_t* wide = (wchar_t*)wysna_alloc_safe((size_t)count * sizeof(wchar_t));
        if (!MultiByteToWideChar(CP_ACP, 0, text, -1, wide, count)) { free(wide); return NULL; }
        return wide;
    }
    wchar_t* wide = (wchar_t*)wysna_alloc_safe((size_t)count * sizeof(wchar_t));
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, wide, count)) { free(wide); return NULL; }
    return wide;
}
#endif
static void* wysna_host_file_open(void* path_handle, int64_t mode) {
    char* path = wysna_host_path(path_handle);
    if (!path || mode < 0 || mode > 2) { free(path); wysna_host_errno(EINVAL); return NULL; }
    const char* modes[] = { "rb", "wb", "ab" };
#ifdef _WIN32
    wchar_t* wide = wysna_host_wide(path);
    const wchar_t* wide_modes[] = { L"rb", L"wb", L"ab" };
    FILE* file = wide ? _wfopen(wide, wide_modes[mode]) : NULL;
    free(wide);
#else
    FILE* file = fopen(path, modes[mode]);
#endif
    if (!file) wysna_host_errno(errno);
    free(path);
    return file ? wysna_host_new(2, file) : NULL;
}
static int64_t wysna_host_file_read(void* file_handle, void* buffer_handle, int64_t count) {
    WysnaHostEntry* file = wysna_host_find(file_handle, 2);
    WysnaHostEntry* buffer = wysna_host_find(buffer_handle, 1);
    /* An explicit bound prevents an untrusted request from allocating a whole file. */
    if (!file || !buffer) return wysna_host_errno(EBADF);
    if (count <= 0 || count > 16777216) return wysna_host_errno(EINVAL);
    if ((uint64_t)count > buffer->capacity) {
        buffer->capacity = (size_t)count;
        buffer->data = wysna_realloc_safe(buffer->data, buffer->capacity);
    }
    errno = 0;
    buffer->length = fread(buffer->data, 1, (size_t)count, (FILE*)file->data);
    return ferror((FILE*)file->data) ? wysna_host_errno(errno) : (int64_t)buffer->length;
}
static int64_t wysna_host_file_write(void* file_handle, void* buffer_handle) {
    WysnaHostEntry* file = wysna_host_find(file_handle, 2);
    WysnaHostEntry* buffer = wysna_host_find(buffer_handle, 1);
    if (!file || !buffer) return wysna_host_errno(EBADF);
    if (!buffer->length) return 0;
    errno = 0;
    if (fwrite(buffer->data, 1, buffer->length, (FILE*)file->data) != buffer->length) return wysna_host_errno(errno);
    if (fflush((FILE*)file->data) != 0) return wysna_host_errno(errno);
    return 0;
}
static int64_t wysna_host_is_open(void* handle) { return wysna_host_find(handle, 2) != NULL; }
/* Operations: exists, size, mkdir, remove, rename. Failures return -1. */
static int64_t wysna_host_fs(void* first, void* second, int64_t operation) {
    char* path = wysna_host_path(first);
    char* other = operation == 4 ? wysna_host_path(second) : NULL;
    if (!path || (operation == 4 && !other)) { free(path); free(other); return wysna_host_errno(EINVAL); }
    int64_t result = -1;
#ifdef _WIN32
    wchar_t* wide = wysna_host_wide(path);
    wchar_t* wide_other = other ? wysna_host_wide(other) : NULL;
    if (wide) {
        if (operation == 0) {
            DWORD attr = GetFileAttributesW(wide);
            if (attr != INVALID_FILE_ATTRIBUTES) result = 1;
            else {
                DWORD code = GetLastError();
                result = code == ERROR_FILE_NOT_FOUND || code == ERROR_PATH_NOT_FOUND ? 0 : -1;
                if (result < 0) { wysna_host_error_code = code; wysna_host_error_domain = 2; }
            }
        } else if (operation == 1) {
            WIN32_FILE_ATTRIBUTE_DATA data;
            if (GetFileAttributesExW(wide, GetFileExInfoStandard, &data)) {
                result = (int64_t)(((uint64_t)data.nFileSizeHigh << 32) | data.nFileSizeLow);
            } else {
                result = -1;
            }
        } else if (operation == 2) {
            result = CreateDirectoryW(wide, NULL) ? 0 : -1;
        } else if (operation == 3) {
            result = (DeleteFileW(wide) || RemoveDirectoryW(wide)) ? 0 : -1;
        } else if (operation == 4 && wide_other) {
            result = MoveFileExW(wide, wide_other, MOVEFILE_REPLACE_EXISTING) ? 0 : -1;
        }
    }
    if (result < 0 && operation != 0) { wysna_host_error_code = GetLastError(); wysna_host_error_domain = 2; }
    free(wide); free(wide_other);
#else
    struct stat status;
    if (operation <= 1) result = stat(path, &status) == 0 ? (operation == 0 ? 1 : status.st_size) : (operation == 0 && errno == ENOENT ? 0 : -1);
    else if (operation == 2) result = mkdir(path, 0777) == 0 ? 0 : -1;
    else if (operation == 3) result = remove(path) == 0 ? 0 : -1;
    else if (operation == 4) result = rename(path, other) == 0 ? 0 : -1;
#endif
#ifndef _WIN32
    if (result < 0) wysna_host_errno(errno);
#endif
    free(path); free(other); return result;
}
#endif
