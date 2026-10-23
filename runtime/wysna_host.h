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
#else
#include <fcntl.h>
#include <signal.h>
#include <sys/select.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
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

static int wysna_host_process_utf8_valid(const unsigned char* data, size_t length) {
    size_t offset = 0;
    while (offset < length) {
        size_t width;
        if (!wysna_utf8_valid_codepoint_at_n((const char*)data, length, offset, &width, NULL)) return 0;
        offset += width;
    }
    return 1;
}

#ifdef _WIN32
static int64_t wysna_host_process_error(int code) {
    wysna_host_error_code = code == E2BIG ? ERROR_BUFFER_OVERFLOW : ERROR_INVALID_PARAMETER;
    wysna_host_error_domain = 2;
    return -1;
}
#else
static int64_t wysna_host_process_error(int code) {
    return wysna_host_errno(code ? code : EIO);
}
#endif

static int wysna_host_process_decode(void* executable_handle, void* arguments_handle,
                                     char** executable_out, char*** argv_out, int* argc_out) {
    WysnaHostEntry* executable_entry = wysna_host_find(executable_handle, 1);
    WysnaHostEntry* arguments_entry = wysna_host_find(arguments_handle, 1);
    if (!executable_entry || !arguments_entry || !executable_entry->length
            || memchr(executable_entry->data, 0, executable_entry->length)
            || !wysna_host_process_utf8_valid((const unsigned char*)executable_entry->data,
                                               executable_entry->length)) {
        wysna_host_process_error(EINVAL); return 0;
    }
    char* executable = (char*)wysna_alloc_safe(executable_entry->length + 1);
    memcpy(executable, executable_entry->data, executable_entry->length);
    executable[executable_entry->length] = 0;

    char** arguments = (char**)wysna_alloc_safe(sizeof(char*) * 258);
    size_t offset = 0;
    int count = 0;
    while (offset < arguments_entry->length) {
        if (count >= 256 || offset + 4 > arguments_entry->length) {
            for (int index = 0; index < count; index++) free(arguments[index]);
            free(executable); free(arguments); wysna_host_process_error(E2BIG); return 0;
        }
        const unsigned char* data = (const unsigned char*)arguments_entry->data;
        uint32_t length = ((uint32_t)data[offset] << 24) | ((uint32_t)data[offset + 1] << 16)
                        | ((uint32_t)data[offset + 2] << 8) | (uint32_t)data[offset + 3];
        offset += 4;
        if (length > 1048576 || offset + length > arguments_entry->length
                || memchr(data + offset, 0, length)
                || !wysna_host_process_utf8_valid(data + offset, length)) {
            for (int index = 0; index < count; index++) free(arguments[index]);
            free(executable); free(arguments); wysna_host_process_error(EINVAL); return 0;
        }
        arguments[count] = (char*)wysna_alloc_safe((size_t)length + 1);
        memcpy(arguments[count], data + offset, length);
        arguments[count][length] = 0;
        count++;
        offset += length;
        if (offset > 16777216) {
            for (int index = 0; index < count; index++) free(arguments[index]);
            free(executable); free(arguments); wysna_host_process_error(E2BIG); return 0;
        }
    }
    arguments[count] = NULL;
    char** argv = (char**)wysna_alloc_safe(sizeof(char*) * (size_t)(count + 2));
    argv[0] = executable;
    for (int index = 0; index < count; index++) argv[index + 1] = arguments[index];
    argv[count + 1] = NULL;
    free(arguments);
    *executable_out = executable;
    *argv_out = argv;
    *argc_out = count + 1;
    return 1;
}

#ifdef _WIN32
static wchar_t* wysna_host_process_wide(const char* value) {
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value, -1, NULL, 0);
    if (!count) return NULL;
    wchar_t* wide = (wchar_t*)wysna_alloc_safe((size_t)count * sizeof(wchar_t));
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value, -1, wide, count)) {
        free(wide); return NULL;
    }
    return wide;
}

static wchar_t* wysna_host_process_quote(const wchar_t* value) {
    size_t length = wcslen(value);
    wchar_t* quoted = (wchar_t*)wysna_alloc_safe((length * 2 + 3) * sizeof(wchar_t));
    size_t output = 0;
    quoted[output++] = L'"';
    size_t slashes = 0;
    for (size_t index = 0; index < length; index++) {
        if (value[index] == L'\\') { slashes++; continue; }
        if (value[index] == L'"') {
            for (size_t count = 0; count < slashes * 2 + 1; count++) quoted[output++] = L'\\';
            quoted[output++] = L'"';
        } else {
            for (size_t count = 0; count < slashes; count++) quoted[output++] = L'\\';
            quoted[output++] = value[index];
        }
        slashes = 0;
    }
    for (size_t count = 0; count < slashes * 2; count++) quoted[output++] = L'\\';
    quoted[output++] = L'"';
    quoted[output] = 0;
    return quoted;
}

static int64_t wysna_host_process_run(void* executable_handle, void* arguments_handle, int64_t timeout_ms) {
    wysna_host_error_code = 0; wysna_host_error_domain = 0;
    if (timeout_ms < 1 || timeout_ms > 600000) return wysna_host_process_error(EINVAL);
    char* executable = NULL; char** argv = NULL; int argc = 0;
    if (!wysna_host_process_decode(executable_handle, arguments_handle, &executable, &argv, &argc)) {
        wysna_host_error_domain = 2; return -1;
    }
    wchar_t** wide_argv = (wchar_t**)wysna_alloc_safe(sizeof(wchar_t*) * (size_t)(argc + 1));
    size_t command_length = 1;
    for (int index = 0; index < argc; index++) {
        wchar_t* wide = wysna_host_process_wide(argv[index]);
        if (!wide) {
            for (int previous = 0; previous < index; previous++) {
                free(wide_argv[previous]);
            }
            for (int argument = 1; argument < argc; argument++) free(argv[argument]);
            free(wide_argv); free(argv); free(executable);
            wysna_host_error_code = GetLastError(); wysna_host_error_domain = 2; return -1;
        }
        wide_argv[index] = wysna_host_process_quote(wide);
        free(wide);
        command_length += wcslen(wide_argv[index]) + 1;
    }
    wide_argv[argc] = NULL;
    wchar_t* application = wysna_host_process_wide(executable);
    wchar_t* command_line = (wchar_t*)wysna_alloc_safe(command_length * sizeof(wchar_t));
    size_t position = 0;
    for (int index = 0; index < argc; index++) {
        if (index) command_line[position++] = L' ';
        size_t length = wcslen(wide_argv[index]);
        memcpy(command_line + position, wide_argv[index], length * sizeof(wchar_t));
        position += length;
        free(wide_argv[index]);
        if (index > 0) free(argv[index]);
    }
    command_line[position] = 0;
    free(wide_argv); free(argv); free(executable);
    HANDLE job = CreateJobObjectW(NULL, NULL);
    if (job) {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
        memset(&limits, 0, sizeof(limits));
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                     &limits, sizeof(limits))) {
            CloseHandle(job); job = NULL;
        }
    }
    if (!application) {
        DWORD error = GetLastError();
        if (job) CloseHandle(job);
        free(command_line); wysna_host_error_code = error; wysna_host_error_domain = 2; return -1;
    }
    STARTUPINFOW startup; PROCESS_INFORMATION process;
    memset(&startup, 0, sizeof(startup)); memset(&process, 0, sizeof(process));
    startup.cb = sizeof(startup); startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    startup.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    startup.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    DWORD creation_flags = CREATE_NEW_PROCESS_GROUP | (job ? CREATE_SUSPENDED : 0);
    BOOL started = CreateProcessW(application, command_line, NULL, NULL, TRUE, creation_flags,
                                  NULL, NULL, &startup, &process);
    DWORD error = started ? 0 : GetLastError();
    free(application); free(command_line);
    if (!started) {
        if (job) CloseHandle(job);
        wysna_host_error_code = error; wysna_host_error_domain = 2; return -1;
    }
    int suspended = job != NULL;
    if (job && !AssignProcessToJobObject(job, process.hProcess)) {
        CloseHandle(job); job = NULL;
    }
    if (suspended && ResumeThread(process.hThread) == (DWORD)-1) {
        error = GetLastError();
        if (job) TerminateJobObject(job, error);
        else TerminateProcess(process.hProcess, error);
        WaitForSingleObject(process.hProcess, INFINITE);
        CloseHandle(process.hThread); CloseHandle(process.hProcess);
        if (job) CloseHandle(job);
        wysna_host_error_code = error; wysna_host_error_domain = 2; return -1;
    }
    DWORD waited = WaitForSingleObject(process.hProcess, (DWORD)timeout_ms);
    if (waited == WAIT_TIMEOUT) {
        if (job) TerminateJobObject(job, ERROR_TIMEOUT);
        else TerminateProcess(process.hProcess, ERROR_TIMEOUT);
        WaitForSingleObject(process.hProcess, INFINITE);
        CloseHandle(process.hThread); CloseHandle(process.hProcess);
        if (job) CloseHandle(job);
        wysna_host_error_code = ERROR_TIMEOUT; wysna_host_error_domain = 2; return -1;
    }
    if (waited != WAIT_OBJECT_0) {
        error = GetLastError();
        if (job) TerminateJobObject(job, error);
        else TerminateProcess(process.hProcess, error);
        WaitForSingleObject(process.hProcess, INFINITE);
        CloseHandle(process.hThread); CloseHandle(process.hProcess);
        if (job) CloseHandle(job);
        wysna_host_error_code = error; wysna_host_error_domain = 2; return -1;
    }
    DWORD exit_code = 0;
    BOOL got_code = GetExitCodeProcess(process.hProcess, &exit_code);
    error = got_code ? 0 : GetLastError();
    CloseHandle(process.hThread); CloseHandle(process.hProcess);
    if (job) CloseHandle(job);
    if (!got_code) { wysna_host_error_code = error; wysna_host_error_domain = 2; return -1; }
    return (int64_t)exit_code;
}
#else
static int64_t wysna_host_process_run(void* executable_handle, void* arguments_handle, int64_t timeout_ms) {
    wysna_host_error_code = 0; wysna_host_error_domain = 0;
    if (timeout_ms < 1 || timeout_ms > 600000) return wysna_host_process_error(EINVAL);
    char* executable = NULL; char** argv = NULL; int argc = 0;
    if (!wysna_host_process_decode(executable_handle, arguments_handle, &executable, &argv, &argc)) return -1;
    argv[0] = executable;
    int error_pipe[2];
    if (pipe(error_pipe) != 0) {
        int error = errno;
        for (int index = 1; index < argc; index++) free(argv[index]);
        free(argv); free(executable); return wysna_host_process_error(error);
    }
    if (fcntl(error_pipe[1], F_SETFD, FD_CLOEXEC) == -1) {
        int error = errno; close(error_pipe[0]); close(error_pipe[1]);
        for (int index = 1; index < argc; index++) free(argv[index]);
        free(argv); free(executable); return wysna_host_process_error(error);
    }
    struct timespec started;
    if (clock_gettime(CLOCK_MONOTONIC, &started) != 0) {
        int error = errno; close(error_pipe[0]); close(error_pipe[1]);
        for (int index = 1; index < argc; index++) free(argv[index]);
        free(argv); free(executable); return wysna_host_process_error(error);
    }
    pid_t child = fork();
    if (child < 0) {
        int error = errno; close(error_pipe[0]); close(error_pipe[1]);
        for (int index = 1; index < argc; index++) free(argv[index]);
        free(argv); free(executable); return wysna_host_process_error(error);
    }
    if (child == 0) {
        close(error_pipe[0]); setpgid(0, 0);
        execvp(executable, argv);
        int error = errno;
        (void)write(error_pipe[1], &error, sizeof(error));
        _exit(127);
    }
    close(error_pipe[1]); (void)setpgid(child, child);
    int exec_error = 0;
    ssize_t received;
    do { received = read(error_pipe[0], &exec_error, sizeof(exec_error)); } while (received < 0 && errno == EINTR);
    close(error_pipe[0]);
    if (received < 0) {
        int error = errno; (void)kill(-child, SIGKILL);
        int status; while (waitpid(child, &status, 0) < 0 && errno == EINTR) { }
        for (int index = 1; index < argc; index++) free(argv[index]);
        free(argv); free(executable); return wysna_host_process_error(error);
    }
    if (received > 0) {
        int status; while (waitpid(child, &status, 0) < 0 && errno == EINTR) { }
        for (int index = 1; index < argc; index++) free(argv[index]);
        free(argv); free(executable); return wysna_host_process_error(exec_error);
    }

    struct timespec current;
    int status = 0;
    for (;;) {
        pid_t waited = waitpid(child, &status, WNOHANG);
        if (waited == child) break;
        if (waited < 0 && errno != EINTR) {
            int error = errno;
            for (int index = 1; index < argc; index++) free(argv[index]);
            free(argv); free(executable); return wysna_host_process_error(error);
        }
        if (clock_gettime(CLOCK_MONOTONIC, &current) != 0) {
            int error = errno; (void)kill(-child, SIGKILL);
            while (waitpid(child, &status, 0) < 0 && errno == EINTR) { }
            for (int index = 1; index < argc; index++) free(argv[index]);
            free(argv); free(executable); return wysna_host_process_error(error);
        }
        int64_t elapsed_ns = ((int64_t)current.tv_sec - started.tv_sec) * 1000000000LL
                           + ((int64_t)current.tv_nsec - started.tv_nsec);
        int64_t elapsed_ms = elapsed_ns / 1000000LL;
        if (elapsed_ms >= timeout_ms) {
            (void)kill(-child, SIGTERM);
            struct timespec grace_start, grace_now;
            if (clock_gettime(CLOCK_MONOTONIC, &grace_start) != 0) {
                int error = errno;
                (void)kill(-child, SIGKILL);
                while (waitpid(child, &status, 0) < 0 && errno == EINTR) { }
                for (int index = 1; index < argc; index++) free(argv[index]);
                free(argv); free(executable); return wysna_host_process_error(error);
            }
            int leader_stopped = 0;
            for (;;) {
                if (!leader_stopped) {
                    pid_t stopped = waitpid(child, &status, WNOHANG);
                    if (stopped == child) leader_stopped = 1;
                    else if (stopped < 0 && errno != EINTR) {
                        int error = errno; (void)kill(-child, SIGKILL);
                        for (int index = 1; index < argc; index++) free(argv[index]);
                        free(argv); free(executable); return wysna_host_process_error(error);
                    }
                }
                if (clock_gettime(CLOCK_MONOTONIC, &grace_now) != 0) {
                    int error = errno;
                    (void)kill(-child, SIGKILL);
                    if (!leader_stopped) while (waitpid(child, &status, 0) < 0 && errno == EINTR) { }
                    for (int index = 1; index < argc; index++) free(argv[index]);
                    free(argv); free(executable); return wysna_host_process_error(error);
                }
                int64_t grace_ns = ((int64_t)grace_now.tv_sec - grace_start.tv_sec) * 1000000000LL
                                 + ((int64_t)grace_now.tv_nsec - grace_start.tv_nsec);
                int64_t grace_ms = grace_ns / 1000000LL;
                if (grace_ms >= 100) {
                    (void)kill(-child, SIGKILL);
                    if (!leader_stopped) while (waitpid(child, &status, 0) < 0 && errno == EINTR) { }
                    break;
                }
                struct timeval delay = {0, 10000}; (void)select(0, NULL, NULL, NULL, &delay);
            }
            for (int index = 1; index < argc; index++) free(argv[index]);
            free(argv); free(executable); return wysna_host_process_error(ETIMEDOUT);
        }
        struct timeval delay = {0, 10000}; (void)select(0, NULL, NULL, NULL, &delay);
    }
    for (int index = 1; index < argc; index++) free(argv[index]);
    free(argv); free(executable);
    if (WIFEXITED(status)) return (int64_t)WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return 128 + WTERMSIG(status);
    return wysna_host_process_error(EIO);
}
#endif
#endif
