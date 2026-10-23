#ifndef WYSNA_RUNTIME_H
#define WYSNA_RUNTIME_H

#ifndef _WIN32
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#endif

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <inttypes.h>
#include <float.h>
#include <math.h>
#include <errno.h>
#include <ctype.h>
#include <time.h>
#include <stdarg.h>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#endif
#ifdef W_OK
#undef W_OK
#endif

typedef enum {
    W_UNIT = 0,
    W_NONE,
    W_INT,
    W_FLOAT,
    W_BOOL,
    W_STR,
    W_LIST,
    W_DICT,
    W_TUPLE,
    W_STRUCT,
    W_OBJECT,
    W_ENUM,
    W_OK,
    W_ERR,
    W_WEAK,
    W_FUNCTION,
    W_POINTER
} WTag;

struct WVal;
typedef struct WVal WVal;

typedef struct {
    int32_t refcount;
    int32_t len;
    int32_t cap;
    WVal* data;
} WListBuf;

typedef struct {
    int32_t refcount;
    int32_t len;
    int32_t cap;
    WVal* keys;
    WVal* vals;
    int32_t* buckets;
    int32_t bucket_count;
} WDictBuf;

typedef struct {
    int32_t refcount;
    int32_t len;
    WVal* items;
} WTupleBuf;

typedef struct WWeakControl WWeakControl;
typedef struct WClassVTable WClassVTable;

typedef struct {
    int32_t refcount;
    WWeakControl* control;
    const WClassVTable* vtable;
    const char* name;
    int32_t len;
    const char** keys;
    WVal* vals;
} WStructBuf;

struct WWeakControl {
    int32_t strong;
    int32_t weak; /* Includes one implicit reference while the object is alive. */
    WStructBuf* object;
};

typedef struct WPointerOwner {
    int32_t refcount;
    int64_t (*close)(void*);
    void* address;
} WPointerOwner;

typedef struct WBoxBuf WBoxBuf;
typedef struct WFunctionBuf WFunctionBuf;

typedef struct {
    const char* enum_name;
    const char* variant;
    WBoxBuf* box;
} WEnumVal;

typedef struct {
    int32_t refcount;
    size_t byte_length;
    size_t* codepoint_offsets;
    size_t codepoint_count;
    char* data;
} WStringBuf;

/* Literal descriptors have static lifetime; only their lazy index is allocated. */
typedef struct WStringLiteral {
    WStringBuf buffer;
    struct WStringLiteral* next;
} WStringLiteral;

/*
 * Every generated program owns one explicit runtime context. For WebAssembly,
 * the context is stored in the module's linear memory and is therefore isolated
 * for each runtime instance. The compatibility macros keep the runtime ABI and
 * the existing internal call sites stable while state moves behind the context.
 */
typedef struct WysnaRuntimeContext {
    WStringLiteral* string_literals;
#ifdef W_STRING_METRICS
    uint64_t string_scan_steps;
#endif
    const char* source_file;
    int32_t source_line;
    int32_t source_col;
    int64_t alloc_count;
    int64_t free_count;
    int64_t retain_count;
    int64_t release_count;
    int64_t live_objects;
    int64_t cow_detach_list;
    int64_t cow_detach_dict;
    int64_t cow_detach_struct;
    int64_t cow_copied_slots;
    int64_t cow_copied_bytes;
    int64_t cow_alloc_count;
    int64_t cow_allocated_bytes;
    int argc;
    char** argv;
#ifdef _WIN32
    bool argv_allocated;
#endif
} WysnaRuntimeContext;

static WysnaRuntimeContext wysna_runtime_context = {0};
#define wysna_g_string_literals (wysna_runtime_context.string_literals)
#ifdef W_STRING_METRICS
#define wysna_g_string_scan_steps (wysna_runtime_context.string_scan_steps)
#define W_STRING_SCAN_STEP() (++wysna_g_string_scan_steps)
#else
#define W_STRING_SCAN_STEP() ((void)0)
#endif

/* ABI v2 keeps string metadata in its variant rather than in every value. */
#define W_RUNTIME_ABI_VERSION 2
struct WVal {
    WTag tag;
    union {
        int64_t i;
        double f;
        bool b;
        struct {
            const char* data;
            WStringBuf* owner;
            size_t length;
        } string;
        WListBuf* list;
        WDictBuf* dict;
        WTupleBuf* tuple;
        WStructBuf* st;
        WEnumVal en;
        WBoxBuf* box;
        WWeakControl* weak;
        WFunctionBuf* function;
        void* pointer;
        struct { void* address; WPointerOwner* owner; } handle;
    } as;
};

static inline bool wysna_value_is_error_type(WVal value, const char* kind, const char* name) {
    if (strcmp(kind, "int") == 0) return value.tag == W_INT;
    if (strcmp(kind, "float") == 0) return value.tag == W_FLOAT;
    if (strcmp(kind, "bool") == 0) return value.tag == W_BOOL;
    if (strcmp(kind, "str") == 0) return value.tag == W_STR;
    if (strcmp(kind, "struct") == 0) {
        return value.tag == W_STRUCT && value.as.st && (value.as.st->name == name || strcmp(value.as.st->name, name) == 0);
    }
    if (strcmp(kind, "enum") == 0) {
        return value.tag == W_ENUM && value.as.en.enum_name && (value.as.en.enum_name == name || strcmp(value.as.en.enum_name, name) == 0);
    }
    return false;
}

typedef WVal (*WInvoke)(WVal environment, int32_t argc, const WVal* argv);

/* Native runtime failures retain the source operation that last entered Wysna. */
#define wysna_g_source_file (wysna_runtime_context.source_file)
#define wysna_g_source_line (wysna_runtime_context.source_line)
#define wysna_g_source_col (wysna_runtime_context.source_col)

static inline void wysna_runtime_set_position(const char* file, int32_t line, int32_t col) {
    wysna_g_source_file = file;
    wysna_g_source_line = line;
    wysna_g_source_col = col;
}

static inline void wysna_runtime_fail(const char* code, const char* format, ...) {
    if (wysna_g_source_file && wysna_g_source_file[0] != '\0' && wysna_g_source_line > 0) {
        fprintf(stderr, "[%s] %s:%" PRId32 ":%" PRId32 " - ",
                code, wysna_g_source_file, wysna_g_source_line, wysna_g_source_col);
    } else {
        fprintf(stderr, "[%s] RuntimeError: ", code);
    }
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);
    fputc('\n', stderr);
    exit(1);
}

struct WClassVTable {
    int32_t count;
    const WInvoke* methods;
};
static inline WVal wysna_virtual_call(WVal receiver, int32_t slot, int32_t argc, const WVal* argv) {
    const WClassVTable* table = receiver.tag == W_OBJECT ? receiver.as.st->vtable : NULL;
    if (!table || slot < 0 || slot >= table->count || !table->methods[slot]) {
        fprintf(stderr, "[W4003] RuntimeError: Invalid virtual method dispatch\n"); exit(1);
    }
    return table->methods[slot](receiver, argc, argv);
}

struct WFunctionBuf {
    int32_t refcount;
    WInvoke invoke;
    WVal environment;
};

struct WBoxBuf {
    int32_t refcount;
    WVal val;
};

/* Deterministic RC & Memory Instrumentation Counters (v0.1.3) */
#define wysna_g_alloc_count (wysna_runtime_context.alloc_count)
#define wysna_g_free_count (wysna_runtime_context.free_count)
#define wysna_g_retain_count (wysna_runtime_context.retain_count)
#define wysna_g_release_count (wysna_runtime_context.release_count)
#define wysna_g_live_objects (wysna_runtime_context.live_objects)

/* Copy-on-Write (CoW) Detach Telemetry Counters (B02) */
#define wysna_g_cow_detach_list (wysna_runtime_context.cow_detach_list)
#define wysna_g_cow_detach_dict (wysna_runtime_context.cow_detach_dict)
#define wysna_g_cow_detach_struct (wysna_runtime_context.cow_detach_struct)
#define wysna_g_cow_copied_slots (wysna_runtime_context.cow_copied_slots)
#define wysna_g_cow_copied_bytes (wysna_runtime_context.cow_copied_bytes)
#define wysna_g_cow_alloc_count (wysna_runtime_context.cow_alloc_count)
#define wysna_g_cow_allocated_bytes (wysna_runtime_context.cow_allocated_bytes)

static inline void wysna_cow_reset_stats(void) {
    wysna_g_cow_detach_list = 0;
    wysna_g_cow_detach_dict = 0;
    wysna_g_cow_detach_struct = 0;
    wysna_g_cow_copied_slots = 0;
    wysna_g_cow_copied_bytes = 0;
    wysna_g_cow_alloc_count = 0;
    wysna_g_cow_allocated_bytes = 0;
}

/*
 * Logical container allocation tracking for Wysna runtime.
 * NOTE on WYSNA_MEM_CHECK vs ASan/LSan:
 * wysna_mem_on_alloc() and wysna_mem_on_free() track high-level container lifecycle
 * (lists, dicts, objects, structs, tuples, strings) as a fast runtime invariant.
 * Comprehensive byte-level leak detection and memory safety are enforced by
 * Clang/GCC AddressSanitizer and LeakSanitizer (ASan/LSan) in CI and test suites.
 */
static inline void wysna_mem_on_alloc(void) {
    wysna_g_alloc_count++;
    wysna_g_live_objects++;
}

static inline void wysna_mem_on_free(void) {
    wysna_g_free_count++;
    wysna_g_live_objects--;
    if (wysna_g_live_objects < 0) {
        fprintf(stderr, "[W4003] RuntimeError: Memory safety violation (live_object_count underflow: %" PRId64 ")\n", wysna_g_live_objects);
        exit(1);
    }
}

static inline void wysna_check_refcount(int32_t rc, const char* op) {
    if (rc <= 0) {
        fprintf(stderr, "[W4003] RuntimeError: Memory safety violation (%s on object with refcount %" PRId32 ")\n", op, rc);
        exit(1);
    }
}

static inline void* wysna_alloc_safe(size_t size) {
    if (size == 0) return NULL;
    void* ptr = malloc(size);
    if (!ptr) {
        fprintf(stderr, "[W4003] RuntimeError: Out of memory (failed to allocate %zu bytes)\n", size);
        exit(1);
    }
    return ptr;
}

static inline void* wysna_realloc_safe(void* old_ptr, size_t new_size) {
    if (new_size == 0) {
        free(old_ptr);
        return NULL;
    }
    void* ptr = realloc(old_ptr, new_size);
    if (!ptr) {
        fprintf(stderr, "[W4003] RuntimeError: Out of memory (failed to reallocate %zu bytes)\n", new_size);
        exit(1);
    }
    return ptr;
}

#define wysna_g_argc (wysna_runtime_context.argc)
#define wysna_g_argv (wysna_runtime_context.argv)
#ifdef _WIN32
#define wysna_g_argv_allocated (wysna_runtime_context.argv_allocated)
#endif

static inline void wysna_runtime_cleanup(void) {
#ifdef _WIN32
    if (wysna_g_argv_allocated && wysna_g_argv) {
        for (int i = 0; i < wysna_g_argc; i++) {
            if (wysna_g_argv[i]) free(wysna_g_argv[i]);
        }
        free(wysna_g_argv);
        wysna_g_argv = NULL;
        wysna_g_argv_allocated = false;
    }
#endif
    while (wysna_g_string_literals) {
        WStringLiteral* literal = wysna_g_string_literals;
        wysna_g_string_literals = literal->next;
        free(literal->buffer.codepoint_offsets);
        memset(&literal->buffer, 0, sizeof(literal->buffer));
        literal->next = NULL;
    }
    const char* stats_env = getenv("WYSNA_MEM_STATS");
    if (stats_env && strcmp(stats_env, "1") == 0) {
        fprintf(stderr, "[WYSNA_MEM_STATS] alloc=%" PRId64 " free=%" PRId64 " retain=%" PRId64 " release=%" PRId64 " live=%" PRId64 "\n",
                wysna_g_alloc_count, wysna_g_free_count, wysna_g_retain_count, wysna_g_release_count, wysna_g_live_objects);
    }
    const char* cow_env = getenv("WYSNA_COW_METRICS");
    if (cow_env && strcmp(cow_env, "1") == 0) {
        fprintf(stderr, "[WYSNA_COW_METRICS] detach_list=%" PRId64 " detach_dict=%" PRId64 " detach_struct=%" PRId64 " copied_slots=%" PRId64 " copied_bytes=%" PRId64 " allocated_bytes=%" PRId64 " allocs=%" PRId64 "\n",
                wysna_g_cow_detach_list, wysna_g_cow_detach_dict, wysna_g_cow_detach_struct, wysna_g_cow_copied_slots, wysna_g_cow_copied_bytes, wysna_g_cow_allocated_bytes, wysna_g_cow_alloc_count);
    }
    const char* check_env = getenv("WYSNA_MEM_CHECK");
    if (check_env && strcmp(check_env, "1") == 0) {
        if (wysna_g_live_objects != 0 || wysna_g_alloc_count != wysna_g_free_count) {
            fprintf(stderr, "[W4003] RuntimeError: Memory leak detected at exit (alloc=%" PRId64 ", free=%" PRId64 ", retain=%" PRId64 ", release=%" PRId64 ", live=%" PRId64 ")\n",
                    wysna_g_alloc_count, wysna_g_free_count, wysna_g_retain_count, wysna_g_release_count, wysna_g_live_objects);
            exit(1);
        }
    }
}

/* Constructors */
static inline WVal wysna_unit(void) {
    WVal v; v.tag = W_UNIT; v.as.i = 0; return v;
}

static inline WVal wysna_none(void) {
    WVal v; v.tag = W_NONE; v.as.i = 0; return v;
}

static inline WVal wysna_int(int64_t x) {
    WVal v; v.tag = W_INT; v.as.i = x; return v;
}

static inline WVal wysna_pointer(void* pointer) {
    WVal value = wysna_unit(); value.tag = W_POINTER;
    value.as.handle.address = pointer; value.as.handle.owner = NULL; return value;
}

static inline int32_t wysna_ffi_int32(WVal value) {
    if (value.tag != W_INT || value.as.i < INT32_MIN || value.as.i > INT32_MAX) {
        fprintf(stderr, "[W4003] RuntimeError: int32 FFI argument out of range\n"); exit(1);
    }
    return (int32_t)value.as.i;
}

static inline WVal wysna_float(double x) {
    WVal v; v.tag = W_FLOAT; v.as.f = x; return v;
}

static inline WVal wysna_bool(bool x) {
    WVal v; v.tag = W_BOOL; v.as.b = x; return v;
}

static inline WVal wysna_str_n(const char* s, size_t length) {
    WVal v; v.tag = W_STR; v.as.string.owner = NULL;
    v.as.string.data = s ? s : ""; v.as.string.length = s ? length : 0; return v;
}

static inline WVal wysna_literal_str_n(WStringLiteral* literal, const char* data, size_t length) {
    if (literal->buffer.refcount == 0) {
        literal->buffer.refcount = -1; /* Immortal data and descriptor. */
        literal->buffer.byte_length = length;
        literal->buffer.codepoint_count = SIZE_MAX;
        literal->buffer.data = (char*)data;
        literal->next = wysna_g_string_literals;
        wysna_g_string_literals = literal;
    }
    WVal value = wysna_str_n(data, length);
    value.as.string.owner = &literal->buffer;
    return value;
}

static inline WVal wysna_str(const char* s) {
    return wysna_str_n(s, s ? strlen(s) : 0);
}

/* Immutable ASCII scalars have static lifetime, including the one-byte NUL string. */
static inline WVal wysna_ascii_string(uint8_t codepoint) {
    static const char scalars[] =
        "\000\000\001\000\002\000\003\000\004\000\005\000\006\000\007\000\010\000\011\000\012\000\013\000\014\000\015\000\016\000\017\000"
        "\020\000\021\000\022\000\023\000\024\000\025\000\026\000\027\000\030\000\031\000\032\000\033\000\034\000\035\000\036\000\037\000"
        "\040\000\041\000\042\000\043\000\044\000\045\000\046\000\047\000\050\000\051\000\052\000\053\000\054\000\055\000\056\000\057\000"
        "\060\000\061\000\062\000\063\000\064\000\065\000\066\000\067\000\070\000\071\000\072\000\073\000\074\000\075\000\076\000\077\000"
        "\100\000\101\000\102\000\103\000\104\000\105\000\106\000\107\000\110\000\111\000\112\000\113\000\114\000\115\000\116\000\117\000"
        "\120\000\121\000\122\000\123\000\124\000\125\000\126\000\127\000\130\000\131\000\132\000\133\000\134\000\135\000\136\000\137\000"
        "\140\000\141\000\142\000\143\000\144\000\145\000\146\000\147\000\150\000\151\000\152\000\153\000\154\000\155\000\156\000\157\000"
        "\160\000\161\000\162\000\163\000\164\000\165\000\166\000\167\000\170\000\171\000\172\000\173\000\174\000\175\000\176\000\177\000";
    if (codepoint >= 128) wysna_runtime_fail("W4003", "ASCII scalar out of bounds");
    return wysna_str_n(scalars + (size_t)codepoint * 2, 1);
}

/* Takes ownership of a terminated buffer; length includes embedded NUL bytes. */
static inline WVal wysna_owned_str_n(char* data, size_t length) {
    WStringBuf* buffer = (WStringBuf*)wysna_alloc_safe(sizeof(WStringBuf));
    buffer->refcount = 1;
    buffer->byte_length = length;
    buffer->codepoint_offsets = NULL;
    buffer->codepoint_count = SIZE_MAX;
    buffer->data = data;
    wysna_mem_on_alloc();
    WVal value = wysna_str_n(data, length);
    value.as.string.owner = buffer;
    return value;
}

static inline WVal wysna_owned_str(char* data) {
    return wysna_owned_str_n(data, strlen(data));
}

static inline WVal wysna_copy_str(const char* data) {
    size_t length = strlen(data);
    char* copy = (char*)wysna_alloc_safe(length + 1);
    memcpy(copy, data, length + 1);
    return wysna_owned_str_n(copy, length);
}

static inline WVal wysna_ok(WVal inner);
static inline WVal wysna_err(WVal inner);

static inline bool wysna_builtin_name(const char* name, const char* base) {
    if (strcmp(name, base) == 0) return true;
    const char* p1 = strstr(name, "__");
    const char* p2 = strstr(base, "__");
    size_t len1 = p1 ? (size_t)(p1 - name) : strlen(name);
    size_t len2 = p2 ? (size_t)(p2 - base) : strlen(base);
    if (len1 == len2 && strncmp(name, base, len1) == 0) return true;
    size_t base_len = strlen(base);
    if (strncmp(name, base, base_len) == 0 && name[base_len] == '_' && name[base_len + 1] == '_') return true;
    size_t name_len = strlen(name);
    if (strncmp(base, name, name_len) == 0 && base[name_len] == '_' && base[name_len + 1] == '_') return true;
    return false;
}

static inline WVal wysna_enum(const char* enum_name, const char* variant) {
    if (wysna_builtin_name(enum_name, "Option") && strcmp(variant, "None") == 0) return wysna_none();
    WVal v;
    v.tag = W_ENUM;
    v.as.en.enum_name = wysna_builtin_name(enum_name, "Option") ? "Option" : enum_name;
    v.as.en.variant = variant;
    v.as.en.box = NULL;
    return v;
}

static inline WVal wysna_enum_payload(const char* enum_name, const char* variant, WVal payload) {
    if (wysna_builtin_name(enum_name, "Result")) {
        if (strcmp(variant, "Ok") == 0) return wysna_ok(payload);
        if (strcmp(variant, "Err") == 0) return wysna_err(payload);
    }
    WBoxBuf* b = (WBoxBuf*)wysna_alloc_safe(sizeof(WBoxBuf));
    b->refcount = 1;
    b->val = payload;
    wysna_mem_on_alloc();
    WVal v;
    v.tag = W_ENUM;
    v.as.en.enum_name = wysna_builtin_name(enum_name, "Option") ? "Option" : enum_name;
    v.as.en.variant = variant;
    v.as.en.box = b;
    return v;
}

static inline WVal wysna_ok(WVal inner) {
    WBoxBuf* b = (WBoxBuf*)wysna_alloc_safe(sizeof(WBoxBuf));
    b->refcount = 1;
    b->val = inner;
    wysna_mem_on_alloc();
    WVal v;
    v.tag = W_OK;
    v.as.box = b;
    return v;
}

static inline WVal wysna_err(WVal inner) {
    WBoxBuf* b = (WBoxBuf*)wysna_alloc_safe(sizeof(WBoxBuf));
    b->refcount = 1;
    b->val = inner;
    wysna_mem_on_alloc();
    WVal v;
    v.tag = W_ERR;
    v.as.box = b;
    return v;
}

static inline WVal wysna_wrap_result(WVal v, const char* err_type) {
    if (v.tag == W_OK || v.tag == W_ERR) return v;
    (void)err_type;
    return wysna_ok(v);
}

static WVal wysna_discard_result_value(WVal value);

/* Internal resource owners carry only a trusted host closer, never user code. */
static WVal wysna_managed_pointer(void* address, int64_t (*close)(void*)) {
    WVal value = wysna_pointer(address);
    if (!address) return value;
    WPointerOwner* owner = (WPointerOwner*)wysna_alloc_safe(sizeof(WPointerOwner));
    owner->refcount = 1; owner->close = close; owner->address = address;
    value.as.handle.owner = owner;
    wysna_mem_on_alloc();
    return value;
}

/* Deterministic RC + Copy-on-Write */
static inline WVal wysna_clone(WVal v) {
    if (v.tag == W_POINTER && v.as.handle.owner) {
        wysna_check_refcount(v.as.handle.owner->refcount, "retain/resource");
        v.as.handle.owner->refcount++;
        wysna_g_retain_count++;
    } else if (v.tag == W_FUNCTION) {
        wysna_check_refcount(v.as.function->refcount, "retain/function");
        v.as.function->refcount++;
        wysna_g_retain_count++;
    } else if (v.tag == W_STR && v.as.string.owner) {
        if (v.as.string.owner->refcount == -1) return v;
        wysna_check_refcount(v.as.string.owner->refcount, "retain/string");
        v.as.string.owner->refcount++;
        wysna_g_retain_count++;
    } else if (v.tag == W_LIST && v.as.list) {
        wysna_check_refcount(v.as.list->refcount, "retain/list");
        v.as.list->refcount++;
        wysna_g_retain_count++;
    } else if (v.tag == W_DICT && v.as.dict) {
        wysna_check_refcount(v.as.dict->refcount, "retain/dict");
        v.as.dict->refcount++;
        wysna_g_retain_count++;
    } else if (v.tag == W_WEAK && v.as.weak) {
        wysna_check_refcount(v.as.weak->weak, "retain/weak");
        v.as.weak->weak++;
        wysna_g_retain_count++;
    } else if (v.tag == W_OBJECT && v.as.st) {
        wysna_check_refcount(v.as.st->control->strong, "retain/object");
        v.as.st->control->strong++;
        wysna_g_retain_count++;
    } else if (v.tag == W_STRUCT && v.as.st) {
        wysna_check_refcount(v.as.st->refcount, "retain/struct_or_object");
        v.as.st->refcount++;
        wysna_g_retain_count++;
    } else if (v.tag == W_TUPLE && v.as.tuple) {
        wysna_check_refcount(v.as.tuple->refcount, "retain/tuple");
        v.as.tuple->refcount++;
        wysna_g_retain_count++;
    } else if ((v.tag == W_OK || v.tag == W_ERR) && v.as.box) {
        wysna_check_refcount(v.as.box->refcount, "retain/box");
        v.as.box->refcount++;
        wysna_g_retain_count++;
    } else if (v.tag == W_ENUM && v.as.en.box) {
        wysna_check_refcount(v.as.en.box->refcount, "retain/enum_box");
        v.as.en.box->refcount++;
        wysna_g_retain_count++;
    }
    return v;
}

/*
 * Releasing a deeply nested value must not recurse: a 100k-deep list, tuple, enum
 * payload chain or struct overflowed the C stack and died with SIGSEGV while
 * freeing the program's result. `wysna_release` therefore frees one container and
 * defers its children onto an explicit work list (wysna_release_deferred), which is
 * drained iteratively in wysna_release.
 */
static WVal* wysna_release_deferred(WVal* slot, int32_t* produced);

#if defined(_MSC_VER)
#define W_RUNTIME_NOINLINE __declspec(noinline)
#elif defined(__GNUC__) || defined(__clang__)
#define W_RUNTIME_NOINLINE __attribute__((noinline))
#else
#define W_RUNTIME_NOINLINE
#endif

/* Keep the graph work list out of leaf callers, even under automatic inlining. */
static W_RUNTIME_NOINLINE void wysna_release_graph(WVal v);

/* Leaf values never need the graph work list, including strings owned by a container. */
static inline void wysna_release_string(WStringBuf* buffer) {
    if (!buffer || buffer->refcount == -1) return;
    wysna_check_refcount(buffer->refcount, "release/string");
    wysna_g_release_count++;
    if (--buffer->refcount == 0) {
        free(buffer->data);
        free(buffer->codepoint_offsets);
        free(buffer);
        wysna_mem_on_free();
    }
}

static inline bool wysna_is_leaf(WVal value) {
    return value.tag <= W_BOOL || value.tag == W_STR || (value.tag == W_POINTER && !value.as.handle.owner);
}

static inline void wysna_release(WVal v) {
    if (wysna_is_leaf(v)) {
        if (v.tag == W_STR) wysna_release_string(v.as.string.owner);
        return;
    }
    if ((v.tag == W_OK || v.tag == W_ERR) && v.as.box) {
        WBoxBuf* box = v.as.box;
        /* Shared boxes and leaf payloads need neither a work list nor child storage. */
        if (box->refcount != 1 || wysna_is_leaf(box->val)) {
            wysna_check_refcount(box->refcount, "release/box");
            wysna_g_release_count++;
            if (--box->refcount == 0) {
                WVal inner = box->val;
                free(box);
                wysna_mem_on_free();
                if (inner.tag == W_STR) wysna_release_string(inner.as.string.owner);
            }
            return;
        }
    }
    wysna_release_graph(v);
}

static void wysna_release_graph(WVal v) {
    WVal stack_work[64];
    WVal* work = stack_work;
    int32_t count = 0;
    int32_t capacity = 64;
    bool heap_work = false;

    work[count++] = v;
    while (count > 0) {
        WVal current = work[--count];
        int32_t produced = 0;
        WVal* children = wysna_release_deferred(&current, &produced);
        if (produced > 0) {
            if (count + produced > capacity) {
                int32_t new_capacity = capacity;
                while (new_capacity < count + produced) new_capacity *= 2;
                WVal* grown = (WVal*)malloc(sizeof(WVal) * (size_t)new_capacity);
                if (!grown) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
                memcpy(grown, work, sizeof(WVal) * (size_t)count);
                if (heap_work) free(work);
                work = grown;
                capacity = new_capacity;
                heap_work = true;
            }
            for (int32_t i = 0; i < produced; i++) work[count + i] = children[i];
            count += produced;
            free(children);
        }
    }
    if (heap_work) free(work);
}

/*
 * Frees one container level and returns a malloc'd array of the children that still
 * need releasing. The array is drained by the caller's work list, so no C stack is
 * consumed per nesting level.
 */
static WVal* wysna_release_deferred(WVal* slot, int32_t* produced) {
    /*
     * Frees exactly one container level and returns a malloc'd array of the children
     * that still have to be released, draining nothing itself. Callers append those to
     * their work list, which is what keeps `wysna_release` off the C stack: without this a
     * 100k-deep list, tuple, enum payload chain or struct overflowed the stack and
     * died with SIGSEGV while freeing the program result.
     *
     * `produced` is the number of entries written to the returned array.
     */
    WVal v = *slot;
    *produced = 0;
    if (v.tag == W_POINTER && v.as.handle.owner) {
        WPointerOwner* owner = v.as.handle.owner;
        wysna_check_refcount(owner->refcount, "release/resource");
        wysna_g_release_count++;
        if (--owner->refcount == 0) {
            owner->close(owner->address);
            free(owner);
            wysna_mem_on_free();
        }
    } else if (v.tag == W_FUNCTION) {
        wysna_check_refcount(v.as.function->refcount, "release/function");
        wysna_g_release_count++;
        if (--v.as.function->refcount == 0) {
            WVal environment = v.as.function->environment;
            free(v.as.function);
            wysna_mem_on_free();
            if (environment.tag != W_UNIT) {
                WVal* out = (WVal*)malloc(sizeof(WVal));
                if (!out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
                out[0] = environment;
                *produced = 1;
                return out;
            }
        }
    } else if (v.tag == W_STR && v.as.string.owner) {
        wysna_release_string(v.as.string.owner);
    } else if (v.tag == W_LIST && v.as.list) {
        WListBuf* b = v.as.list;
        wysna_check_refcount(b->refcount, "release/list");
        wysna_g_release_count++;
        b->refcount--;
        if (b->refcount == 0) {
            b->refcount = -1;
            WVal* out = b->len > 0 ? (WVal*)malloc(sizeof(WVal) * (size_t)b->len) : NULL;
            int32_t len = b->len;
            if (len > 0 && !out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
            for (int32_t i = 0; i < len; i++) out[i] = b->data[i];
            free(b->data);
            free(b);
            wysna_mem_on_free();
            *produced = len;
            return out;
        }
    } else if (v.tag == W_DICT && v.as.dict) {
        WDictBuf* d = v.as.dict;
        wysna_check_refcount(d->refcount, "release/dict");
        wysna_g_release_count++;
        d->refcount--;
        if (d->refcount == 0) {
            d->refcount = -1;
            int32_t total = d->len * 2;
            WVal* out = total > 0 ? (WVal*)malloc(sizeof(WVal) * (size_t)total) : NULL;
            if (total > 0 && !out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
            for (int32_t i = 0; i < d->len; i++) {
                out[i * 2] = d->keys[i];
                out[i * 2 + 1] = d->vals[i];
            }
            free(d->keys);
            free(d->vals);
            free(d->buckets);
            free(d);
            wysna_mem_on_free();
            *produced = total;
            return out;
        }
    } else if (v.tag == W_WEAK && v.as.weak) {
        WWeakControl* control = v.as.weak;
        wysna_check_refcount(control->weak, "release/weak");
        wysna_g_release_count++;
        if (--control->weak == 0) {
            free(control);
            wysna_mem_on_free();
        }
    } else if (v.tag == W_OBJECT && v.as.st) {
        WStructBuf* object = v.as.st;
        WWeakControl* control = object->control;
        wysna_check_refcount(control->strong, "release/object");
        wysna_g_release_count++;
        if (--control->strong == 0) {
            control->object = NULL;
            int32_t len = object->len;
            WVal* out = len > 0 ? (WVal*)malloc(sizeof(WVal) * (size_t)len) : NULL;
            if (len > 0 && !out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
            for (int32_t i = 0; i < len; i++) out[i] = object->vals[i];
            free(object->keys);
            free(object->vals);
            free(object);
            wysna_mem_on_free();
            if (--control->weak == 0) {
                free(control);
                wysna_mem_on_free();
            }
            *produced = len;
            return out;
        }
    } else if (v.tag == W_STRUCT && v.as.st) {
        WStructBuf* st = v.as.st;
        wysna_check_refcount(st->refcount, "release/struct_or_object");
        wysna_g_release_count++;
        st->refcount--;
        if (st->refcount == 0) {
            st->refcount = -1;
            int32_t len = st->len;
            WVal* out = len > 0 ? (WVal*)malloc(sizeof(WVal) * (size_t)len) : NULL;
            if (len > 0 && !out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
            for (int32_t i = 0; i < len; i++) out[i] = st->vals[i];
            free(st->keys);
            free(st->vals);
            free(st);
            wysna_mem_on_free();
            *produced = len;
            return out;
        }
    } else if (v.tag == W_TUPLE && v.as.tuple) {
        WTupleBuf* t = v.as.tuple;
        wysna_check_refcount(t->refcount, "release/tuple");
        wysna_g_release_count++;
        t->refcount--;
        if (t->refcount == 0) {
            t->refcount = -1;
            int32_t len = t->len;
            WVal* out = len > 0 ? (WVal*)malloc(sizeof(WVal) * (size_t)len) : NULL;
            if (len > 0 && !out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
            for (int32_t i = 0; i < len; i++) out[i] = t->items[i];
            free(t->items);
            free(t);
            wysna_mem_on_free();
            *produced = len;
            return out;
        }
    } else if ((v.tag == W_OK || v.tag == W_ERR) && v.as.box) {
        WBoxBuf* bx = v.as.box;
        wysna_check_refcount(bx->refcount, "release/box");
        wysna_g_release_count++;
        bx->refcount--;
        if (bx->refcount == 0) {
            bx->refcount = -1;
            WVal inner = bx->val;
            free(bx);
            wysna_mem_on_free();
            if (wysna_is_leaf(inner)) {
                if (inner.tag == W_STR) wysna_release_string(inner.as.string.owner);
                return NULL;
            }
            WVal* out = (WVal*)malloc(sizeof(WVal));
            if (!out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
            out[0] = inner;
            *produced = 1;
            return out;
        }
    } else if (v.tag == W_ENUM && v.as.en.box) {
        WBoxBuf* bx = v.as.en.box;
        wysna_check_refcount(bx->refcount, "release/enum_box");
        wysna_g_release_count++;
        bx->refcount--;
        if (bx->refcount == 0) {
            bx->refcount = -1;
            WVal inner = bx->val;
            free(bx);
            wysna_mem_on_free();
            WVal* out = (WVal*)malloc(sizeof(WVal));
            if (!out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
            out[0] = inner;
            *produced = 1;
            return out;
        }
    }
    return NULL;
}

/* Consumes the environment; invocation borrows function, environment and arguments. */
static inline WVal wysna_function_new(WInvoke invoke, WVal environment) {
    WFunctionBuf* function = (WFunctionBuf*)wysna_alloc_safe(sizeof(WFunctionBuf));
    function->refcount = 1; function->invoke = invoke; function->environment = environment;
    wysna_mem_on_alloc();
    WVal value = wysna_unit(); value.tag = W_FUNCTION; value.as.function = function; return value;
}

static inline WVal wysna_call(WVal function, int32_t argc, const WVal* argv) {
    if (function.tag != W_FUNCTION) {
        fprintf(stderr, "[W4003] RuntimeError: Indirect call requires function\n"); exit(1);
    }
    return function.as.function->invoke(function.as.function->environment, argc, argv);
}

static WVal wysna_discard_result_value(WVal value) {
    if (value.tag == W_ERR) return value;
    wysna_release(value);
    return wysna_ok(wysna_unit());
}

static inline void wysna_release_array(int32_t count, WVal* arr) {
    for (int32_t i = 0; i < count; i++) {
        wysna_release(arr[i]);
    }
}

static inline WVal wysna_move(WVal* src) {
    WVal v = *src;
    *src = wysna_unit();
    return v;
}

static inline WVal wysna_assign(WVal* dst, WVal owned_src) {
    wysna_release(*dst);
    *dst = owned_src;
    return *dst;
}

static inline bool wysna_is_none(WVal value) {
    return value.tag == W_NONE || (value.tag == W_ENUM &&
        strcmp(value.as.en.enum_name, "Option") == 0 && strcmp(value.as.en.variant, "None") == 0);
}

static inline WVal wysna_peek_optional(WVal value) {
    if (value.tag == W_ENUM && strcmp(value.as.en.enum_name, "Option") == 0 &&
        strcmp(value.as.en.variant, "Some") == 0 && value.as.en.box) return value.as.en.box->val;
    return value;
}

static inline WVal wysna_unwrap_optional(WVal value) {
    if (value.tag == W_ENUM && strcmp(value.as.en.enum_name, "Option") == 0 &&
        strcmp(value.as.en.variant, "Some") == 0 && value.as.en.box) {
        return wysna_clone(value.as.en.box->val);
    }
    return wysna_clone(value);
}

static inline WVal wysna_unwrap_ok(WVal v) {
    if (v.tag == W_OK && v.as.box) {
        return wysna_clone(v.as.box->val);
    }
    return wysna_clone(v);
}

static inline WVal wysna_unwrap_success(WVal value) {
    if (value.tag == W_ENUM && strcmp(value.as.en.enum_name, "Option") == 0)
        return wysna_unwrap_optional(value);
    return wysna_unwrap_ok(value);
}

static inline WVal wysna_unwrap_err(WVal v) {
    if (v.tag == W_ERR && v.as.box) {
        return wysna_clone(v.as.box->val);
    }
    return wysna_none();
}

static inline WVal wysna_peek_ok(WVal v) {
    if (v.tag == W_OK && v.as.box) {
        return v.as.box->val;
    }
    return v;
}

static inline WVal wysna_peek_err(WVal v) {
    if (v.tag == W_ERR && v.as.box) {
        return v.as.box->val;
    }
    return wysna_none();
}

static inline bool wysna_is_enum_variant(WVal value, const char* enum_name, const char* variant) {
    return value.tag == W_ENUM && value.as.en.enum_name && value.as.en.variant &&
        strcmp(value.as.en.enum_name, enum_name) == 0 && strcmp(value.as.en.variant, variant) == 0;
}

static inline WVal wysna_peek_enum_payload(WVal value) {
    if (value.tag == W_ENUM && value.as.en.box) return value.as.en.box->val;
    fprintf(stderr, "[W4003] RuntimeError: enum payload access on invalid value\n");
    exit(1);
}

static inline void wysna_list_detach(WVal* v) {
    if (v->tag != W_LIST || !v->as.list) return;
    WListBuf* old_b = v->as.list;
    wysna_check_refcount(old_b->refcount, "detach/list");
    if (old_b->refcount <= 1) return;
    old_b->refcount--;
    wysna_g_release_count++;
    WListBuf* new_b = (WListBuf*)wysna_alloc_safe(sizeof(WListBuf));
    new_b->refcount = 1;
    new_b->len = old_b->len;
    new_b->cap = old_b->cap > 0 ? old_b->cap : 4;
    new_b->data = (WVal*)wysna_alloc_safe(sizeof(WVal) * new_b->cap);
    wysna_mem_on_alloc();

    /* B02: CoW detach telemetry */
    wysna_g_cow_detach_list++;
    wysna_g_cow_copied_slots += old_b->len;
    wysna_g_cow_copied_bytes += (int64_t)(sizeof(WVal) * old_b->len);
    wysna_g_cow_allocated_bytes += (int64_t)(sizeof(WListBuf) + (sizeof(WVal) * new_b->cap));
    wysna_g_cow_alloc_count += 2;

    for (int32_t i = 0; i < old_b->len; i++) {
        new_b->data[i] = wysna_clone(old_b->data[i]);
    }
    v->as.list = new_b;
}

/* Dense insertion-order entries with an open-addressed lookup index. */
static inline bool wysna_eq(WVal a, WVal b);
static inline uint64_t wysna_key_hash_bytes(const unsigned char* data, size_t length, uint64_t hash) {
    for (size_t i = 0; i < length; i++) { hash ^= data[i]; hash *= UINT64_C(1099511628211); }
    return hash;
}
static inline uint64_t wysna_key_hash(WVal value) {
    uint64_t hash = UINT64_C(14695981039346656037) ^ (uint64_t)value.tag;
    if (value.tag == W_STR) return wysna_key_hash_bytes((const unsigned char*)value.as.string.data, value.as.string.length, hash);
    if (value.tag == W_INT || value.tag == W_BOOL) {
        uint64_t number = value.tag == W_INT ? (uint64_t)value.as.i : (uint64_t)value.as.b;
        number ^= number >> 30; number *= UINT64_C(0xbf58476d1ce4e5b9);
        number ^= number >> 27; number *= UINT64_C(0x94d049bb133111eb);
        return hash ^ number ^ (number >> 31);
    }
    if (value.tag == W_ENUM) {
        hash = wysna_key_hash_bytes((const unsigned char*)value.as.en.enum_name, strlen(value.as.en.enum_name), hash);
        hash = wysna_key_hash_bytes((const unsigned char*)value.as.en.variant, strlen(value.as.en.variant), hash);
        if (value.as.en.box) {
            WVal payload = value.as.en.box->val;
            if (payload.tag == W_TUPLE) {
                for (int32_t i = 0; i < payload.as.tuple->len; i++) hash = (hash ^ wysna_key_hash(payload.as.tuple->items[i])) * UINT64_C(1099511628211);
            } else hash ^= wysna_key_hash(payload);
        }
    }
    return hash;
}
static inline int32_t wysna_dict_find(WDictBuf* dict, WVal key) {
    uint32_t mask = (uint32_t)dict->bucket_count - 1;
    uint32_t slot = (uint32_t)wysna_key_hash(key) & mask;
    while (dict->buckets[slot] >= 0) {
        int32_t index = dict->buckets[slot];
        if (wysna_eq(dict->keys[index], key)) return index;
        slot = (slot + 1) & mask;
    }
    return -1;
}
static inline void wysna_dict_index_entry(WDictBuf* dict, int32_t index) {
    uint32_t mask = (uint32_t)dict->bucket_count - 1;
    uint32_t slot = (uint32_t)wysna_key_hash(dict->keys[index]) & mask;
    while (dict->buckets[slot] >= 0) slot = (slot + 1) & mask;
    dict->buckets[slot] = index;
}
static inline void wysna_dict_reindex(WDictBuf* dict, int32_t capacity) {
    free(dict->buckets);
    dict->bucket_count = capacity;
    dict->buckets = (int32_t*)wysna_alloc_safe(sizeof(int32_t) * (size_t)capacity);
    for (int32_t i = 0; i < capacity; i++) dict->buckets[i] = -1;
    for (int32_t i = 0; i < dict->len; i++) wysna_dict_index_entry(dict, i);
}

static inline void wysna_dict_detach(WVal* v) {
    if (v->tag != W_DICT || !v->as.dict) return;
    WDictBuf* old_b = v->as.dict;
    wysna_check_refcount(old_b->refcount, "detach/dict");
    if (old_b->refcount <= 1) return;
    old_b->refcount--;
    wysna_g_release_count++;
    WDictBuf* new_b = (WDictBuf*)wysna_alloc_safe(sizeof(WDictBuf));
    new_b->refcount = 1;
    new_b->len = old_b->len;
    new_b->cap = old_b->cap > 0 ? old_b->cap : 4;
    new_b->keys = (WVal*)wysna_alloc_safe(sizeof(WVal) * new_b->cap);
    new_b->vals = (WVal*)wysna_alloc_safe(sizeof(WVal) * new_b->cap);
    new_b->bucket_count = old_b->bucket_count;
    new_b->buckets = (int32_t*)wysna_alloc_safe(sizeof(int32_t) * (size_t)new_b->bucket_count);
    memcpy(new_b->buckets, old_b->buckets, sizeof(int32_t) * (size_t)new_b->bucket_count);
    wysna_mem_on_alloc();

    /* B02: CoW detach telemetry */
    wysna_g_cow_detach_dict++;
    wysna_g_cow_copied_slots += ((int64_t)old_b->len * 2);
    wysna_g_cow_copied_bytes += (int64_t)(sizeof(WVal) * old_b->len * 2 + sizeof(int32_t) * old_b->bucket_count);
    wysna_g_cow_allocated_bytes += (int64_t)(sizeof(WDictBuf) + (sizeof(WVal) * new_b->cap * 2) + sizeof(int32_t) * new_b->bucket_count);
    wysna_g_cow_alloc_count += 4;

    for (int32_t i = 0; i < old_b->len; i++) {
        new_b->keys[i] = wysna_clone(old_b->keys[i]);
        new_b->vals[i] = wysna_clone(old_b->vals[i]);
    }
    v->as.dict = new_b;
}

static inline void wysna_struct_detach(WVal* v) {
    if (v->tag != W_STRUCT || !v->as.st) return;
    WStructBuf* old_b = v->as.st;
    wysna_check_refcount(old_b->refcount, "detach/struct");
    if (old_b->refcount <= 1) return;
    old_b->refcount--;
    wysna_g_release_count++;
    WStructBuf* new_b = (WStructBuf*)wysna_alloc_safe(sizeof(WStructBuf));
    new_b->refcount = 1;
    new_b->control = NULL;
    new_b->vtable = NULL;
    new_b->name = old_b->name;
    new_b->len = old_b->len;
    int32_t cap = old_b->len > 0 ? old_b->len : 1;
    new_b->keys = (const char**)wysna_alloc_safe(sizeof(const char*) * cap);
    new_b->vals = (WVal*)wysna_alloc_safe(sizeof(WVal) * cap);
    wysna_mem_on_alloc();

    /* B02: CoW detach telemetry */
    wysna_g_cow_detach_struct++;
    wysna_g_cow_copied_slots += old_b->len;
    wysna_g_cow_copied_bytes += (int64_t)((sizeof(const char*) + sizeof(WVal)) * old_b->len);
    wysna_g_cow_allocated_bytes += (int64_t)(sizeof(WStructBuf) + (sizeof(const char*) * cap) + (sizeof(WVal) * cap));
    wysna_g_cow_alloc_count += 3;

    for (int32_t i = 0; i < old_b->len; i++) {
        new_b->keys[i] = old_b->keys[i];
        new_b->vals[i] = wysna_clone(old_b->vals[i]);
    }
    v->as.st = new_b;
}

/* Structural Equality */
typedef struct {
    WVal left;
    WVal right;
} WEqualityPair;

static inline void wysna_eq_push(WEqualityPair** items, int32_t* count, int32_t* capacity,
                             bool* heap_items, WVal left, WVal right) {
    if (*count == *capacity) {
        if (*capacity > INT32_MAX / 2) {
            fprintf(stderr, "[W4003] RuntimeError: Equality work list is too large\n");
            exit(1);
        }
        int32_t new_capacity = *capacity * 2;
        WEqualityPair* grown = (WEqualityPair*)wysna_alloc_safe(
            sizeof(WEqualityPair) * (size_t)new_capacity);
        memcpy(grown, *items, sizeof(WEqualityPair) * (size_t)*count);
        if (*heap_items) free(*items);
        *items = grown;
        *capacity = new_capacity;
        *heap_items = true;
    }
    (*items)[(*count)++] = (WEqualityPair){left, right};
}

static W_RUNTIME_NOINLINE bool wysna_eq_graph(WVal a, WVal b);

/* Scalar equality must not create the structural comparison work list. */
static inline bool wysna_eq(WVal a, WVal b) {
    if (a.tag == b.tag) {
        switch (a.tag) {
            case W_UNIT:
            case W_NONE: return true;
            case W_INT: return a.as.i == b.as.i;
            case W_FLOAT: return a.as.f == b.as.f;
            case W_BOOL: return a.as.b == b.as.b;
            case W_STR: return a.as.string.length == b.as.string.length &&
                (a.as.string.data == b.as.string.data || memcmp(a.as.string.data, b.as.string.data, a.as.string.length) == 0);
            case W_POINTER: return a.as.pointer == b.as.pointer;
            case W_OBJECT: return a.as.st == b.as.st;
            case W_WEAK: return a.as.weak == b.as.weak;
            default: break;
        }
    }
    return wysna_eq_graph(a, b);
}

static bool wysna_eq_graph(WVal a, WVal b) {
    WEqualityPair local_items[64];
    WEqualityPair* items = local_items;
    int32_t count = 0;
    int32_t capacity = 64;
    bool heap_items = false;
    bool equal = true;
    wysna_eq_push(&items, &count, &capacity, &heap_items, a, b);

    while (count > 0 && equal) {
        WEqualityPair pair = items[--count];
        WVal left = pair.left;
        WVal right = pair.right;
        bool left_some = left.tag == W_ENUM &&
            strcmp(left.as.en.enum_name, "Option") == 0 &&
            strcmp(left.as.en.variant, "Some") == 0;
        bool right_some = right.tag == W_ENUM &&
            strcmp(right.as.en.enum_name, "Option") == 0 &&
            strcmp(right.as.en.variant, "Some") == 0;

        if (left_some && !right_some && right.tag != W_NONE) {
            if (!left.as.en.box) { equal = false; continue; }
            wysna_eq_push(&items, &count, &capacity, &heap_items,
                      left.as.en.box->val, right);
            continue;
        }
        if (right_some && !left_some && left.tag != W_NONE) {
            if (!right.as.en.box) { equal = false; continue; }
            wysna_eq_push(&items, &count, &capacity, &heap_items,
                      left, right.as.en.box->val);
            continue;
        }

        if (left.tag != right.tag) {
            if ((left.tag == W_NONE && right.tag == W_ENUM &&
                 strcmp(right.as.en.enum_name, "Option") == 0 &&
                 strcmp(right.as.en.variant, "None") == 0) ||
                (right.tag == W_NONE && left.tag == W_ENUM &&
                 strcmp(left.as.en.enum_name, "Option") == 0 &&
                 strcmp(left.as.en.variant, "None") == 0)) {
                continue;
            }
            bool left_result = left.tag == W_OK || left.tag == W_ERR;
            bool right_result = right.tag == W_OK || right.tag == W_ERR;
            const char* variant = (left.tag == W_OK || right.tag == W_OK) ? "Ok" : "Err";
            if (left_result && right.tag == W_ENUM &&
                strcmp(right.as.en.enum_name, "Result") == 0 &&
                (right.as.en.variant == variant || strcmp(right.as.en.variant, variant) == 0) &&
                left.as.box && right.as.en.box) {
                wysna_eq_push(&items, &count, &capacity, &heap_items,
                          left.as.box->val, right.as.en.box->val);
                continue;
            }
            if (right_result && left.tag == W_ENUM &&
                strcmp(left.as.en.enum_name, "Result") == 0 &&
                (left.as.en.variant == variant || strcmp(left.as.en.variant, variant) == 0) &&
                left.as.en.box && right.as.box) {
                wysna_eq_push(&items, &count, &capacity, &heap_items,
                          left.as.en.box->val, right.as.box->val);
                continue;
            }
            equal = false;
            continue;
        }

        switch (left.tag) {
            case W_POINTER:
                equal = left.as.pointer == right.as.pointer;
                break;
            case W_FUNCTION:
                equal = left.as.function == right.as.function;
                break;
            case W_UNIT:
            case W_NONE:
                break;
            case W_INT:
                equal = left.as.i == right.as.i;
                break;
            case W_FLOAT:
                equal = left.as.f == right.as.f;
                break;
            case W_BOOL:
                equal = left.as.b == right.as.b;
                break;
            case W_STR:
                equal = left.as.string.length == right.as.string.length &&
                    (left.as.string.data == right.as.string.data || memcmp(left.as.string.data, right.as.string.data, left.as.string.length) == 0);
                break;
            case W_ENUM:
                if ((left.as.en.enum_name != right.as.en.enum_name && strcmp(left.as.en.enum_name, right.as.en.enum_name) != 0) ||
                    (left.as.en.variant != right.as.en.variant && strcmp(left.as.en.variant, right.as.en.variant) != 0) ||
                    (!!left.as.en.box != !!right.as.en.box)) {
                    equal = false;
                } else if (left.as.en.box) {
                    wysna_eq_push(&items, &count, &capacity, &heap_items,
                              left.as.en.box->val, right.as.en.box->val);
                }
                break;
            case W_LIST:
                if (left.as.list->len != right.as.list->len) {
                    equal = false;
                    break;
                }
                for (int32_t i = 0; i < left.as.list->len; i++) {
                    wysna_eq_push(&items, &count, &capacity, &heap_items,
                              left.as.list->data[i], right.as.list->data[i]);
                }
                break;
            case W_TUPLE:
                if (left.as.tuple->len != right.as.tuple->len) {
                    equal = false;
                    break;
                }
                for (int32_t i = 0; i < left.as.tuple->len; i++) {
                    wysna_eq_push(&items, &count, &capacity, &heap_items,
                              left.as.tuple->items[i], right.as.tuple->items[i]);
                }
                break;
            case W_DICT:
                if (left.as.dict->len != right.as.dict->len) {
                    equal = false;
                    break;
                }
                for (int32_t i = 0; i < left.as.dict->len && equal; i++) {
                    int32_t found = wysna_dict_find(right.as.dict, left.as.dict->keys[i]);
                    if (found < 0) {
                        equal = false;
                    } else {
                        wysna_eq_push(&items, &count, &capacity, &heap_items,
                                  left.as.dict->vals[i], right.as.dict->vals[found]);
                    }
                }
                break;
            case W_STRUCT:
                if ((left.as.st->name != right.as.st->name && strcmp(left.as.st->name, right.as.st->name) != 0) ||
                    left.as.st->len != right.as.st->len) {
                    equal = false;
                    break;
                }
                for (int32_t i = 0; i < left.as.st->len && equal; i++) {
                    int32_t found = i;
                    if (left.as.st->keys[i] != right.as.st->keys[i] && strcmp(left.as.st->keys[i], right.as.st->keys[i]) != 0) {
                        found = -1;
                        for (int32_t j = 0; j < right.as.st->len; j++) {
                            if (left.as.st->keys[i] == right.as.st->keys[j] || strcmp(left.as.st->keys[i], right.as.st->keys[j]) == 0) { found = j; break; }
                        }
                    }
                    if (found < 0) equal = false;
                    else wysna_eq_push(&items, &count, &capacity, &heap_items,
                                   left.as.st->vals[i], right.as.st->vals[found]);
                }
                break;
            case W_WEAK:
                equal = left.as.weak == right.as.weak;
                break;
            case W_OBJECT:
                equal = left.as.st == right.as.st;
                break;
            case W_OK:
            case W_ERR:
                if (!left.as.box || !right.as.box) {
                    equal = left.as.box == right.as.box;
                } else {
                    wysna_eq_push(&items, &count, &capacity, &heap_items,
                              left.as.box->val, right.as.box->val);
                }
                break;
        }
    }

    if (heap_items) free(items);
    return equal;
}
/* Containers: List, Dict, Tuple, Struct */
static inline WVal wysna_make_list(int32_t count, const WVal* elems) {
    WListBuf* b = (WListBuf*)wysna_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = count;
    b->cap = count > 4 ? count : 4;
    b->data = (WVal*)wysna_alloc_safe(sizeof(WVal) * b->cap);
    wysna_mem_on_alloc();
    for (int32_t i = 0; i < count; i++) {
        b->data[i] = wysna_clone(elems[i]);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline int32_t wysna_range_count(WVal start, WVal end, bool inclusive) {
    int64_t s = start.as.i;
    int64_t e = end.as.i;
    if (inclusive) {
        if (e == INT64_MAX) {
            fprintf(stderr, "[W4003] RuntimeError: Range bound overflow at INT64_MAX\n");
            exit(1);
        }
        e++;
    }
    uint64_t diff = e > s ? (uint64_t)e - (uint64_t)s : 0;
    if (diff > 100000000ULL) {
        fprintf(stderr, "[W4003] RuntimeError: Range length %" PRIu64 " exceeds maximum list capacity\n", diff);
        exit(1);
    }
    return (int32_t)diff;
}

static inline WVal wysna_make_range(WVal start, WVal end, bool inclusive) {
    int64_t s = start.as.i;
    int32_t count = wysna_range_count(start, end, inclusive);
    WListBuf* b = (WListBuf*)wysna_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = count;
    b->cap = count > 4 ? count : 4;
    b->data = (WVal*)wysna_alloc_safe(sizeof(WVal) * b->cap);
    wysna_mem_on_alloc();
    for (int32_t i = 0; i < count; i++) {
        b->data[i] = wysna_int(s + (int64_t)i);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal wysna_make_tuple(int32_t count, const WVal* elems) {
    WTupleBuf* t = (WTupleBuf*)wysna_alloc_safe(sizeof(WTupleBuf));
    t->refcount = 1;
    t->len = count;
    t->items = (WVal*)wysna_alloc_safe(sizeof(WVal) * (count > 0 ? count : 1));
    wysna_mem_on_alloc();
    for (int32_t i = 0; i < count; i++) {
        t->items[i] = wysna_clone(elems[i]);
    }
    WVal v; v.tag = W_TUPLE; v.as.tuple = t; return v;
}

static inline WVal wysna_make_dict(int32_t count, const WVal* keys, const WVal* vals) {
    if (count < 0 || count > INT32_MAX / 4) { fprintf(stderr, "[W4003] RuntimeError: Dictionary too large\n"); exit(1); }
    WDictBuf* d = (WDictBuf*)wysna_alloc_safe(sizeof(WDictBuf));
    d->refcount = 1;
    d->len = 0;
    d->cap = count > 4 ? count * 2 : 4;
    d->keys = (WVal*)wysna_alloc_safe(sizeof(WVal) * d->cap);
    d->vals = (WVal*)wysna_alloc_safe(sizeof(WVal) * d->cap);
    d->buckets = NULL;
    int32_t buckets = 8;
    while (buckets < d->cap) {
        if (buckets > INT32_MAX / 2) { fprintf(stderr, "[W4003] RuntimeError: Dictionary too large\n"); exit(1); }
        buckets *= 2;
    }
    wysna_dict_reindex(d, buckets);
    wysna_mem_on_alloc();
    WVal v; v.tag = W_DICT; v.as.dict = d;
    for (int32_t i = 0; i < count; i++) {
        int32_t index = wysna_dict_find(d, keys[i]);
        if (index >= 0) { wysna_release(d->vals[index]); d->vals[index] = wysna_clone(vals[i]); }
        else {
            if ((int64_t)(d->len + 1) * 2 >= d->bucket_count) {
                if (d->bucket_count > INT32_MAX / 2) { fprintf(stderr, "[W4003] RuntimeError: Dictionary too large\n"); exit(1); }
                wysna_dict_reindex(d, d->bucket_count * 2);
            }
            index = d->len++;
            d->keys[index] = wysna_clone(keys[i]);
            d->vals[index] = wysna_clone(vals[i]);
            wysna_dict_index_entry(d, index);
        }
    }
    return v;
}

static inline WVal wysna_make_struct(const char* name, int32_t count, const char** keys, const WVal* vals) {
    WStructBuf* st = (WStructBuf*)wysna_alloc_safe(sizeof(WStructBuf));
    st->refcount = 1;
    st->control = NULL;
    st->vtable = NULL;
    st->name = name;
    st->len = count;
    st->keys = (const char**)wysna_alloc_safe(sizeof(const char*) * (count > 0 ? count : 1));
    st->vals = (WVal*)wysna_alloc_safe(sizeof(WVal) * (count > 0 ? count : 1));
    wysna_mem_on_alloc();
    for (int32_t i = 0; i < count; i++) {
        st->keys[i] = keys[i];
        st->vals[i] = wysna_clone(vals[i]);
    }
    WVal v; v.tag = W_STRUCT; v.as.st = st; return v;
}

static inline WVal wysna_make_object(const char* name, int32_t count, const char** keys, const WVal* vals) {
    WStructBuf* st = (WStructBuf*)wysna_alloc_safe(sizeof(WStructBuf));
    st->refcount = 1;
    st->control = (WWeakControl*)wysna_alloc_safe(sizeof(WWeakControl));
    st->control->strong = 1;
    st->control->weak = 1;
    st->control->object = st;
    wysna_mem_on_alloc();
    st->vtable = NULL;
    st->name = name;
    st->len = count;
    st->keys = (const char**)wysna_alloc_safe(sizeof(const char*) * (count > 0 ? count : 1));
    st->vals = (WVal*)wysna_alloc_safe(sizeof(WVal) * (count > 0 ? count : 1));
    wysna_mem_on_alloc();
    for (int32_t i = 0; i < count; i++) {
        st->keys[i] = keys[i];
        st->vals[i] = wysna_clone(vals[i]);
    }
    WVal v; v.tag = W_OBJECT; v.as.st = st; return v;
}

/* Default non-optional weak fields are independent expired handles. */
static inline WVal wysna_empty_weak(void) {
    WWeakControl* control = (WWeakControl*)wysna_alloc_safe(sizeof(WWeakControl));
    control->strong = 0;
    control->weak = 1;
    control->object = NULL;
    wysna_mem_on_alloc();
    WVal value = wysna_unit();
    value.tag = W_WEAK;
    value.as.weak = control;
    return value;
}

/* Both helpers borrow their input and return one owned reference. */
static inline WVal wysna_builtin_weak(WVal object) {
    if (object.tag != W_OBJECT) {
        fprintf(stderr, "[W4003] RuntimeError: weak expects a class object\n");
        exit(1);
    }
    WVal value = wysna_unit();
    value.tag = W_WEAK;
    value.as.weak = object.as.st->control;
    value.as.weak->weak++;
    wysna_g_retain_count++;
    return value;
}

/* Language weak calls consume their evaluated argument snapshot immediately. */
static inline WVal wysna_builtin_weak_owned(WVal object) {
    WVal handle = wysna_builtin_weak(object);
    wysna_release(object);
    return handle;
}

static inline WVal wysna_builtin_upgrade(WVal weak) {
    if (weak.tag != W_WEAK) {
        fprintf(stderr, "[W4003] RuntimeError: upgrade expects a weak reference\n");
        exit(1);
    }
    WWeakControl* control = weak.as.weak;
    if (control->strong == 0 || control->object == NULL) return wysna_none();
    WVal object = wysna_unit();
    object.tag = W_OBJECT;
    object.as.st = control->object;
    return wysna_clone(object);
}

/* UTF-8 Code-Point Helpers (SPEC Section 3.3) */
static inline size_t wysna_utf8_seq_len(unsigned char c) {
    if (c < 0x80) return 1;
    if ((c & 0xE0) == 0xC0) return 2;
    if ((c & 0xF0) == 0xE0) return 3;
    if ((c & 0xF8) == 0xF0) return 4;
    return 1;
}

static inline bool wysna_utf8_valid_codepoint_at_n(const char* s, size_t length, size_t pos, size_t* out_len, int64_t* out_cp) {
    W_STRING_SCAN_STEP();
    const unsigned char* u = (const unsigned char*)s + pos;
    if (pos >= length) {
        if (out_len) *out_len = 0;
        return false;
    }
    if (u[0] < 0x80) {
        if (out_len) *out_len = 1;
        if (out_cp) *out_cp = u[0];
        return true;
    }
    if ((u[0] & 0xE0) == 0xC0) {
        if (length - pos < 2) return false;
        if ((u[1] & 0xC0) != 0x80) return false;
        int64_t cp = ((u[0] & 0x1F) << 6) | (u[1] & 0x3F);
        if (cp < 0x80) return false;
        if (out_len) *out_len = 2;
        if (out_cp) *out_cp = cp;
        return true;
    }
    if ((u[0] & 0xF0) == 0xE0) {
        if (length - pos < 3) return false;
        if ((u[1] & 0xC0) != 0x80 || (u[2] & 0xC0) != 0x80) return false;
        int64_t cp = ((u[0] & 0x0F) << 12) | ((u[1] & 0x3F) << 6) | (u[2] & 0x3F);
        if (cp < 0x800 || (cp >= 0xD800 && cp <= 0xDFFF)) return false;
        if (out_len) *out_len = 3;
        if (out_cp) *out_cp = cp;
        return true;
    }
    if ((u[0] & 0xF8) == 0xF0) {
        if (length - pos < 4) return false;
        if ((u[1] & 0xC0) != 0x80 || (u[2] & 0xC0) != 0x80 || (u[3] & 0xC0) != 0x80) return false;
        int64_t cp = ((u[0] & 0x07) << 18) | ((u[1] & 0x3F) << 12) | ((u[2] & 0x3F) << 6) | (u[3] & 0x3F);
        if (cp < 0x10000 || cp > 0x10FFFF) return false;
        if (out_len) *out_len = 4;
        if (out_cp) *out_cp = cp;
        return true;
    }
    return false;
}

static inline int64_t wysna_utf8_cp_len_n(const char* s, size_t length) {
    int64_t count = 0;
    size_t pos = 0;
    while (pos < length) {
        size_t step = 0;
        if (wysna_utf8_valid_codepoint_at_n(s, length, pos, &step, NULL)) {
            pos += step;
        } else {
            pos++;
        }
        count++;
    }
    return count;
}

static inline bool wysna_utf8_cp_offset_n(const char* s, size_t length, int64_t target_cp, size_t* out_off, size_t* out_len) {
    if (target_cp < 0) return false;
    int64_t idx = 0;
    size_t pos = 0;
    while (pos < length) {
        size_t step = 0;
        size_t start = pos;
        if (wysna_utf8_valid_codepoint_at_n(s, length, pos, &step, NULL)) {
            pos += step;
        } else {
            step = 1;
            pos++;
        }
        if (idx == target_cp) {
            *out_off = start;
            *out_len = step;
            return true;
        }
        idx++;
    }
    if (idx == target_cp) {
        *out_off = pos;
        *out_len = 0;
        return false;
    }
    return false;
}

/* Keep UTF-8 decoding and index construction out of cached index callers. */
static W_RUNTIME_NOINLINE bool wysna_string_offset_slow(WVal value, int64_t index, size_t* offset, size_t* length) {
    WStringBuf* owner = value.as.string.owner;
    if (!owner) return wysna_utf8_cp_offset_n(value.as.string.data, value.as.string.length, index, offset, length);
    if (!owner->codepoint_offsets) {
        size_t ascii_pos = 0;
        const unsigned char* bytes = (const unsigned char*)value.as.string.data;
        while (ascii_pos < value.as.string.length && bytes[ascii_pos] < 0x80) {
            W_STRING_SCAN_STEP();
            ascii_pos++;
        }
        if (ascii_pos == value.as.string.length) {
            owner->codepoint_count = value.as.string.length;
            if ((uint64_t)index > value.as.string.length) return false;
            *offset = (size_t)index;
            *length = (uint64_t)index < value.as.string.length ? 1 : 0;
            return *length != 0;
        }
        if (value.as.string.length > SIZE_MAX / sizeof(size_t) - 1) {
            fprintf(stderr, "[W4003] RuntimeError: String index too large\n"); exit(1);
        }
        size_t count_hint = owner->codepoint_count;
        if (count_hint == SIZE_MAX) count_hint = (size_t)wysna_utf8_cp_len_n(value.as.string.data, value.as.string.length);
        owner->codepoint_offsets = (size_t*)wysna_alloc_safe((count_hint + 1) * sizeof(size_t));
        size_t position = 0, count = 0;
        while (position < value.as.string.length) {
            size_t step = 1;
            owner->codepoint_offsets[count++] = position;
            wysna_utf8_valid_codepoint_at_n(value.as.string.data, value.as.string.length, position, &step, NULL);
            position += step;
        }
        owner->codepoint_offsets[count] = value.as.string.length;
        owner->codepoint_count = count;
    }
    if ((uint64_t)index > owner->codepoint_count) return false;
    *offset = owner->codepoint_offsets[index];
    *length = (uint64_t)index < owner->codepoint_count ? owner->codepoint_offsets[index + 1] - *offset : 0;
    return *length != 0;
}

/* Lazily index shared owned strings once; repeated lexer indexing is O(1). */
static inline bool wysna_string_offset(WVal value, int64_t index, size_t* offset, size_t* length) {
    if (index < 0) return false;
    WStringBuf* owner = value.as.string.owner;
    if (owner && owner->codepoint_count == value.as.string.length) {
        if ((uint64_t)index > value.as.string.length) return false;
        *offset = (size_t)index;
        *length = (uint64_t)index < value.as.string.length ? 1 : 0;
        return *length != 0;
    }
    if (owner && owner->codepoint_offsets) {
        if ((uint64_t)index > owner->codepoint_count) return false;
        *offset = owner->codepoint_offsets[index];
        *length = (uint64_t)index < owner->codepoint_count ? owner->codepoint_offsets[index + 1] - *offset : 0;
        return *length != 0;
    }
    return wysna_string_offset_slow(value, index, offset, length);
}

/* Owned strings cache counts independently of the lazy random-access index. */
static inline int64_t wysna_string_length(WVal value) {
    if (value.as.string.owner && value.as.string.owner->codepoint_count != SIZE_MAX)
        return (int64_t)value.as.string.owner->codepoint_count;
    int64_t count = wysna_utf8_cp_len_n(value.as.string.data, value.as.string.length);
    if (value.as.string.owner) value.as.string.owner->codepoint_count = (size_t)count;
    return count;
}

/* Indexing & Member Access */
static inline WVal wysna_index_get(WVal obj, WVal idx) {
    if (obj.tag == W_LIST) {
        int64_t i = idx.as.i;
        if (i < 0 || i >= obj.as.list->len) {
            wysna_runtime_fail("W4002", "List index out of bounds");
        }
        return obj.as.list->data[i];
    }
    if (obj.tag == W_STR) {
        size_t off = 0, blen = 0;
        if (!wysna_string_offset(obj, idx.as.i, &off, &blen) || blen == 0) {
            wysna_runtime_fail("W4002", "String index out of bounds");
        }
        if (blen == 1 && (unsigned char)obj.as.string.data[off] < 128)
            return wysna_ascii_string((uint8_t)obj.as.string.data[off]);
        char* buf = (char*)wysna_alloc_safe(blen + 1);
        memcpy(buf, obj.as.string.data + off, blen);
        buf[blen] = '\0';
        return wysna_owned_str_n(buf, blen);
    }
    if (obj.tag == W_DICT) {
        int32_t index = wysna_dict_find(obj.as.dict, idx);
        if (index < 0) {
            /* SPEC 10.2: a missing key is W4002. `d.get(k)` is the optional form. */
            wysna_runtime_fail("W4002", "Dictionary key not found");
        }
        return obj.as.dict->vals[index];
    }
    fprintf(stderr, "[W4003] RuntimeError: Cannot index object of tag %d\n", obj.tag);
    exit(1);
}

static inline WVal wysna_index_get_owned(WVal object, WVal index) {
    WVal value = wysna_index_get(object, index);
    return object.tag == W_STR ? value : wysna_clone(value);
}

static inline WVal wysna_index_get_at(WVal object, WVal index, const char* file, int32_t line, int32_t col) {
    wysna_runtime_set_position(file, line, col);
    return wysna_index_get(object, index);
}

static inline WVal wysna_index_get_owned_at(WVal object, WVal index, const char* file, int32_t line, int32_t col) {
    wysna_runtime_set_position(file, line, col);
    return wysna_index_get_owned(object, index);
}

static inline WVal* wysna_index_ref(WVal* obj, WVal idx) {
    if (obj->tag == W_LIST) {
        wysna_list_detach(obj);
        int64_t i = idx.as.i;
        if (i < 0 || i >= obj->as.list->len) {
            wysna_runtime_fail("W4002", "List index out of bounds");
        }
        return &obj->as.list->data[i];
    }
    if (obj->tag == W_DICT) {
        wysna_dict_detach(obj);
        WDictBuf* d = obj->as.dict;
        int32_t found = wysna_dict_find(d, idx);
        if (found >= 0) return &d->vals[found];
        if (d->cap > INT32_MAX / 2 || d->bucket_count > INT32_MAX / 2) {
            fprintf(stderr, "[W4003] RuntimeError: Dictionary too large\n"); exit(1);
        }
        if ((int64_t)(d->len + 1) * 2 >= d->bucket_count) wysna_dict_reindex(d, d->bucket_count * 2);
        if (d->len >= d->cap) {
            d->cap = d->cap > 0 ? d->cap * 2 : 4;
            d->keys = (WVal*)wysna_realloc_safe(d->keys, sizeof(WVal) * d->cap);
            d->vals = (WVal*)wysna_realloc_safe(d->vals, sizeof(WVal) * d->cap);
        }
        d->keys[d->len] = wysna_clone(idx);
        d->vals[d->len] = wysna_none();
        d->len++;
        wysna_dict_index_entry(d, d->len - 1);
        return &d->vals[d->len - 1];
    }
    fprintf(stderr, "[W4003] RuntimeError: Cannot index-assign non-collection\n");
    exit(1);
}

static inline WVal* wysna_index_ref_at(WVal* obj, WVal idx, const char* file, int32_t line, int32_t col) {
    wysna_runtime_set_position(file, line, col);
    return wysna_index_ref(obj, idx);
}

static inline WVal wysna_member_get(WVal obj, const char* prop) {
    if (obj.tag == W_STRUCT || obj.tag == W_OBJECT) {
        for (int32_t i = 0; i < obj.as.st->len; i++) {
            if (obj.as.st->keys[i] == prop || strcmp(obj.as.st->keys[i], prop) == 0) {
                return obj.as.st->vals[i];
            }
        }
    }
    return wysna_none();
}

static inline WVal* wysna_member_ref(WVal* obj, const char* prop) {
    if (obj->tag == W_STRUCT) {
        wysna_struct_detach(obj);
        for (int32_t i = 0; i < obj->as.st->len; i++) {
            if (obj->as.st->keys[i] == prop || strcmp(obj->as.st->keys[i], prop) == 0) {
                return &obj->as.st->vals[i];
            }
        }
    } else if (obj->tag == W_OBJECT) {
        for (int32_t i = 0; i < obj->as.st->len; i++) {
            if (obj->as.st->keys[i] == prop || strcmp(obj->as.st->keys[i], prop) == 0) {
                return &obj->as.st->vals[i];
            }
        }
    }
    fprintf(stderr, "[W4003] RuntimeError: Invalid field '%s'\n", prop);
    exit(1);
}

/* Physical field offsets resolved and checked before MIR reaches the backend. */
static inline WVal wysna_field_get_at(WVal object, int32_t index) {
    if ((object.tag != W_STRUCT && object.tag != W_OBJECT) || index < 0 || index >= object.as.st->len)
        wysna_runtime_fail("W4003", "Invalid physical field read");
    return object.as.st->vals[index];
}

static inline WVal* wysna_field_ref_at(WVal* object, int32_t index) {
    if ((object->tag != W_STRUCT && object->tag != W_OBJECT) || index < 0 || index >= object->as.st->len)
        wysna_runtime_fail("W4003", "Invalid physical field destination");
    if (object->tag == W_STRUCT) wysna_struct_detach(object);
    return &object->as.st->vals[index];
}

static inline WVal wysna_not(WVal value) { return wysna_bool(!value.as.b); }
static inline WVal wysna_equal(WVal left, WVal right) { return wysna_bool(wysna_eq(left, right)); }
static inline WVal wysna_not_equal(WVal left, WVal right) { return wysna_bool(!wysna_eq(left, right)); }
static inline WVal wysna_enum_payload_owned(WVal value) { return wysna_clone(wysna_peek_enum_payload(value)); }

/* Methods on List / Dict */
static inline WVal wysna_list_append(WVal* list_val, WVal item) {
    if (list_val->tag != W_LIST) wysna_runtime_fail("W4003", "List intrinsic requires list receiver");
    wysna_list_detach(list_val);
    WListBuf* b = list_val->as.list;
    if (b->len >= b->cap) {
        b->cap = b->cap > 0 ? b->cap * 2 : 4;
        b->data = (WVal*)wysna_realloc_safe(b->data, sizeof(WVal) * b->cap);
    }
    b->data[b->len++] = wysna_clone(item);
    return wysna_unit();
}

static inline WVal wysna_list_pop(WVal* list_val) {
    if (list_val->tag != W_LIST) wysna_runtime_fail("W4003", "List intrinsic requires list receiver");
    wysna_list_detach(list_val);
    WListBuf* b = list_val->as.list;
    if (b->len == 0) {
        wysna_runtime_fail("W4002", "pop from empty list");
    }
    return b->data[--b->len];
}

static inline WVal wysna_list_pop_at(WVal* list_val, const char* file, int32_t line, int32_t col) {
    wysna_runtime_set_position(file, line, col);
    return wysna_list_pop(list_val);
}

static inline WVal wysna_list_clear(WVal* list_val) {
    if (list_val->tag != W_LIST) wysna_runtime_fail("W4003", "List intrinsic requires list receiver");
    wysna_list_detach(list_val);
    WListBuf* b = list_val->as.list;
    for (int32_t i = 0; i < b->len; i++) {
        wysna_release(b->data[i]);
    }
    b->len = 0;
    return wysna_unit();
}

static inline WVal wysna_dict_get(WVal dict_val, WVal key) {
    /* The optional lookup: unlike `d[k]`, an absent key is `none`, not W4002. */
    if (dict_val.tag != W_DICT) return wysna_none();
    int32_t found = wysna_dict_find(dict_val.as.dict, key);
    if (found < 0) return wysna_none();
    return wysna_enum_payload("Option", "Some", wysna_clone(dict_val.as.dict->vals[found]));
}

static inline WVal wysna_dict_keys(WVal dict_val) {
    if (dict_val.tag != W_DICT) wysna_runtime_fail("W4003", "Dictionary intrinsic requires dict receiver");
    WDictBuf* d = dict_val.as.dict;
    return wysna_make_list(d->len, d->keys);
}

static inline WVal wysna_dict_values(WVal dict_val) {
    if (dict_val.tag != W_DICT) wysna_runtime_fail("W4003", "Dictionary intrinsic requires dict receiver");
    WDictBuf* d = dict_val.as.dict;
    return wysna_make_list(d->len, d->vals);
}

/* Binary Operations */
static inline WVal wysna_add(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return wysna_int((int64_t)((uint64_t)a.as.i + (uint64_t)b.as.i));
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return wysna_float(a.as.f + b.as.f);
    if (a.tag == W_STR && b.tag == W_STR) {
        size_t la = a.as.string.length;
        size_t lb = b.as.string.length;
        char* res = (char*)wysna_alloc_safe(la + lb + 1);
        memcpy(res, a.as.string.data, la);
        memcpy(res + la, b.as.string.data, lb);
        res[la + lb] = '\0';
        return wysna_owned_str_n(res, la + lb);
    }
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for addition (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal wysna_sub(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return wysna_int((int64_t)((uint64_t)a.as.i - (uint64_t)b.as.i));
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return wysna_float(a.as.f - b.as.f);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for subtraction (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal wysna_mul(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return wysna_int((int64_t)((uint64_t)a.as.i * (uint64_t)b.as.i));
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return wysna_float(a.as.f * b.as.f);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for multiplication (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal wysna_div(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) {
        if (b.as.i == 0) wysna_runtime_fail("W4001", "Division by zero");
        if (a.as.i == INT64_MIN && b.as.i == -1) return wysna_int(INT64_MIN);
        return wysna_int(a.as.i / b.as.i);
    }
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) {
        if (b.as.f == 0.0) wysna_runtime_fail("W4001", "Division by zero");
        return wysna_float(a.as.f / b.as.f);
    }
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for division (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal wysna_div_at(WVal a, WVal b, const char* file, int32_t line, int32_t col) {
    wysna_runtime_set_position(file, line, col);
    return wysna_div(a, b);
}

static inline WVal wysna_mod(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) {
        if (b.as.i == 0) wysna_runtime_fail("W4001", "Modulo by zero");
        if (a.as.i == INT64_MIN && b.as.i == -1) return wysna_int(0);
        return wysna_int(a.as.i % b.as.i);
    }
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for modulo (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal wysna_mod_at(WVal a, WVal b, const char* file, int32_t line, int32_t col) {
    wysna_runtime_set_position(file, line, col);
    return wysna_mod(a, b);
}

static inline WVal wysna_neg(WVal a) {
    if (a.tag == W_INT) return wysna_int((int64_t)(0ULL - (uint64_t)a.as.i));
    if (a.tag == W_FLOAT) return wysna_float(-a.as.f);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand type for negation (tag %d)\n", a.tag);
    exit(1);
}

static inline WVal wysna_lt(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return wysna_bool(a.as.i < b.as.i);
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return wysna_bool(a.as.f < b.as.f);
    if (a.tag == W_STR && b.tag == W_STR) return wysna_bool(strcmp(a.as.string.data, b.as.string.data) < 0);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for comparison (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal wysna_le(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return wysna_bool(a.as.i <= b.as.i);
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return wysna_bool(a.as.f <= b.as.f);
    if (a.tag == W_STR && b.tag == W_STR) return wysna_bool(strcmp(a.as.string.data, b.as.string.data) <= 0);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for comparison (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal wysna_gt(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return wysna_bool(a.as.i > b.as.i);
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return wysna_bool(a.as.f > b.as.f);
    if (a.tag == W_STR && b.tag == W_STR) return wysna_bool(strcmp(a.as.string.data, b.as.string.data) > 0);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for comparison (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal wysna_ge(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return wysna_bool(a.as.i >= b.as.i);
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return wysna_bool(a.as.f >= b.as.f);
    if (a.tag == W_STR && b.tag == W_STR) return wysna_bool(strcmp(a.as.string.data, b.as.string.data) >= 0);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for comparison (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

/*
 * Shortest round-trip formatting for binary64, matching Python's `repr(float)`.
 *
 * The previous implementation used "%g" (six significant digits) plus a ".0"
 * heuristic, so `0.1 + 0.2` printed `0.3` and `1.0 / 3.0` printed `0.333333` in
 * compiled programs while the interpreter printed `0.30000000000000004` and
 * `0.3333333333333333`. Two engines disagreeing on how they print a float is a
 * language-level bug, not a cosmetic one.
 *
 * The digits are found by trying precisions 1..17 and keeping the first whose
 * value reads back as the same double; 17 significant digits always suffice.
 * Python's presentation rule is then applied: fixed notation while the decimal
 * exponent is in [-4, 15], scientific notation outside it, and a ".0" suffix for
 * an integral value so that floats stay distinguishable from ints. Infinities and
 * NaN print as `inf`, `-inf` and `nan`.
 */
static inline char* wysna_format_float(double value) {
    char* buf = (char*)wysna_alloc_safe(40);
    if (value != value) { strcpy(buf, "nan"); return buf; }
    if (value > DBL_MAX) { strcpy(buf, "inf"); return buf; }
    if (value < -DBL_MAX) { strcpy(buf, "-inf"); return buf; }
    if (value == 0.0) {
        strcpy(buf, signbit(value) ? "-0.0" : "0.0");
        return buf;
    }

    char digits[32];
    int exponent = 0;
    int length = 0;
    for (int precision = 1; precision <= 17; precision++) {
        char candidate[48];
        snprintf(candidate, sizeof(candidate), "%.*e", precision - 1, value);
        if (strtod(candidate, NULL) == value) {
            const char* mantissa = candidate;
            bool negative = (*mantissa == '-');
            if (negative) mantissa++;
            int written = 0;
            for (const char* p = mantissa; *p && *p != 'e' && *p != 'E'; p++) {
                if (*p == '.') continue;
                if (written < (int)sizeof(digits) - 1) digits[written++] = *p;
            }
            digits[written] = 0;
            const char* e = strchr(mantissa, 'e');
            exponent = e ? (int)strtol(e + 1, NULL, 10) : 0;
            length = written;
            while (length > 1 && digits[length - 1] == '0') length--;
            if (negative) {
                /* Re-attach the sign by shifting the digit buffer. */
                memmove(digits + 1, digits, (size_t)length);
                digits[0] = '-';
                length++;
            }
            break;
        }
    }
    if (length == 0) {
        /* Unreachable: 17 significant digits always round-trip. */
        snprintf(buf, 40, "%.17g", value);
        if (!strchr(buf, '.') && !strchr(buf, 'e')) strcat(buf, ".0");
        return buf;
    }

    bool negative = digits[0] == '-';
    const char* body = negative ? digits + 1 : digits;
    int digit_count = negative ? length - 1 : length;

    if (exponent < -4 || exponent >= 16) {
        char* out = buf;
        if (negative) *out++ = '-';
        *out++ = body[0];
        /* Python does not pad the mantissa: `1e-05`, not `1.0e-05`. */
        if (digit_count > 1) {
            *out++ = '.';
            memcpy(out, body + 1, (size_t)(digit_count - 1));
            out += digit_count - 1;
        }
        *out++ = 'e';
        int written = snprintf(out, 8, "%+03d", exponent);
        (void)written;
        return buf;
    }

    if (exponent >= digit_count - 1) {
        /* Integral value: digits then trailing zeros, then ".0". */
        char* out = buf;
        if (negative) *out++ = '-';
        memcpy(out, body, (size_t)digit_count);
        out += digit_count;
        for (int i = 0; i < exponent - (digit_count - 1); i++) *out++ = '0';
        *out++ = '.';
        *out++ = '0';
        *out = 0;
        return buf;
    }

    if (exponent >= 0) {
        char* out = buf;
        if (negative) *out++ = '-';
        memcpy(out, body, (size_t)(exponent + 1));
        out += exponent + 1;
        *out++ = '.';
        memcpy(out, body + exponent + 1, (size_t)(digit_count - exponent - 1));
        out += digit_count - exponent - 1;
        *out = 0;
        return buf;
    }

    {
        char* out = buf;
        if (negative) *out++ = '-';
        *out++ = '0';
        *out++ = '.';
        for (int i = 0; i < -exponent - 1; i++) *out++ = '0';
        memcpy(out, body, (size_t)digit_count);
        out += digit_count;
        *out = 0;
        return buf;
    }
}

/* Formatting & String Conversion (matching Wysna Seed Values.__str__ exactly) */
/* Internal module identity is retained for equality/dispatch, not display. */
static inline const char* wysna_nominal_display_name(const char* name) {
    static const char module_prefix[] = "__wysna_module_";
    const size_t module_prefix_len = sizeof(module_prefix) - 1;
    if (strncmp(name, module_prefix, module_prefix_len) == 0) {
        const char* boundary = strstr(name + module_prefix_len, "__");
        if (boundary) return boundary + 2;
    }
    return name;
}

typedef struct {
    WVal value;
    const char* text;
    bool is_text;
    bool quote_str;
    bool leave_object;
} WFormatTask;

static inline void wysna_format_push(WFormatTask** tasks, int32_t* count, int32_t* capacity,
                                 bool* heap_tasks, WFormatTask task) {
    if (*count == INT32_MAX) {
        fprintf(stderr, "[W4003] RuntimeError: Formatting work list is too large\n");
        exit(1);
    }
    if (*count == *capacity) {
        if (*capacity > INT32_MAX / 2) {
            fprintf(stderr, "[W4003] RuntimeError: Formatting work list is too large\n");
            exit(1);
        }
        int32_t new_capacity = *capacity * 2;
        WFormatTask* grown = (WFormatTask*)wysna_alloc_safe(
            sizeof(WFormatTask) * (size_t)new_capacity);
        memcpy(grown, *tasks, sizeof(WFormatTask) * (size_t)*count);
        if (*heap_tasks) free(*tasks);
        *tasks = grown;
        *capacity = new_capacity;
        *heap_tasks = true;
    }
    (*tasks)[(*count)++] = task;
}

static inline void wysna_format_push_text(WFormatTask** tasks, int32_t* count, int32_t* capacity,
                                      bool* heap_tasks, const char* text) {
    WVal empty = {0};
    empty.tag = W_UNIT;
    WFormatTask task = {empty, text, true, false, false};
    wysna_format_push(tasks, count, capacity, heap_tasks, task);
}

static inline void wysna_format_push_value(WFormatTask** tasks, int32_t* count, int32_t* capacity,
                                       bool* heap_tasks, WVal value, bool quote_str) {
    WFormatTask task = {value, NULL, false, quote_str, false};
    wysna_format_push(tasks, count, capacity, heap_tasks, task);
}

static inline void wysna_format_append(char** buffer, size_t* length, size_t* capacity,
                                   const char* data, size_t data_length) {
    if (data_length > SIZE_MAX - *length - 1) {
        fprintf(stderr, "[W4003] RuntimeError: Formatted value is too large\n");
        exit(1);
    }
    size_t needed = *length + data_length + 1;
    if (needed > *capacity) {
        size_t new_capacity = *capacity;
        while (new_capacity < needed) {
            if (new_capacity > SIZE_MAX / 2) {
                new_capacity = needed;
                break;
            }
            new_capacity *= 2;
        }
        *buffer = (char*)wysna_realloc_safe(*buffer, new_capacity);
        *capacity = new_capacity;
    }
    if (data_length > 0) memcpy(*buffer + *length, data, data_length);
    *length += data_length;
    (*buffer)[*length] = '\0';
}

static inline void wysna_format_append_text(char** buffer, size_t* length, size_t* capacity,
                                        const char* text) {
    wysna_format_append(buffer, length, capacity, text, strlen(text));
}

/* Active ancestors only: repeated aliases outside the current path render fully. */
typedef struct {
    WStructBuf** entries;
    size_t capacity;
    size_t count;
    size_t used;
} WFormatObjects;
#define W_FORMAT_DELETED ((WStructBuf*)(uintptr_t)1)

static inline size_t wysna_format_object_hash(WStructBuf* object) {
    uintptr_t value = (uintptr_t)object >> 3;
    value ^= value >> 17;
    return (size_t)value;
}

static inline void wysna_format_objects_resize(WFormatObjects* set, size_t capacity) {
    if (capacity > SIZE_MAX / sizeof(WStructBuf*))
        wysna_runtime_fail("W4003", "Formatting ancestor set is too large");
    WStructBuf** entries = (WStructBuf**)wysna_alloc_safe(capacity * sizeof(WStructBuf*));
    memset(entries, 0, capacity * sizeof(WStructBuf*));
    for (size_t index = 0; index < set->capacity; index++) {
        WStructBuf* object = set->entries[index];
        if (!object || object == W_FORMAT_DELETED) continue;
        size_t position = wysna_format_object_hash(object) & (capacity - 1);
        while (entries[position]) position = (position + 1) & (capacity - 1);
        entries[position] = object;
    }
    free(set->entries);
    set->entries = entries;
    set->capacity = capacity;
    set->used = set->count;
}

static inline bool wysna_format_object_enter(WFormatObjects* set, WStructBuf* object) {
    if (!set->capacity) wysna_format_objects_resize(set, 64);
    if (set->used >= set->capacity - set->capacity / 4) {
        size_t capacity = set->capacity;
        if (set->count >= capacity / 4) {
            if (capacity > SIZE_MAX / 2) wysna_runtime_fail("W4003", "Formatting ancestor set is too large");
            capacity *= 2;
        }
        wysna_format_objects_resize(set, capacity);
    }
    size_t position = wysna_format_object_hash(object) & (set->capacity - 1);
    size_t deleted = SIZE_MAX;
    while (set->entries[position]) {
        if (set->entries[position] == object) return false;
        if (set->entries[position] == W_FORMAT_DELETED && deleted == SIZE_MAX) deleted = position;
        position = (position + 1) & (set->capacity - 1);
    }
    if (deleted != SIZE_MAX) position = deleted;
    else set->used++;
    set->entries[position] = object;
    set->count++;
    return true;
}

static inline void wysna_format_object_leave(WFormatObjects* set, WStructBuf* object) {
    size_t position = wysna_format_object_hash(object) & (set->capacity - 1);
    while (set->entries[position] != object) position = (position + 1) & (set->capacity - 1);
    set->entries[position] = W_FORMAT_DELETED;
    set->count--;
}

static inline char* wysna_to_cstr(WVal v, bool quote_str) {
    WFormatObjects active_objects = {0};
    WFormatTask local_tasks[64];
    WFormatTask* tasks = local_tasks;
    int32_t task_count = 0;
    int32_t task_capacity = 64;
    bool heap_tasks = false;
    size_t buffer_capacity = 64;
    size_t buffer_length = 0;
    char* buffer = (char*)wysna_alloc_safe(buffer_capacity);
    buffer[0] = '\0';
    wysna_format_push_value(&tasks, &task_count, &task_capacity, &heap_tasks, v, quote_str);

    while (task_count > 0) {
        WFormatTask task = tasks[--task_count];
        if (task.leave_object) {
            wysna_format_object_leave(&active_objects, task.value.as.st);
            continue;
        }
        if (task.is_text) {
            wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity, task.text);
            continue;
        }

        WVal value = task.value;
        switch (value.tag) {
            case W_POINTER:
                wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity, "<opaque>");
                break;
            case W_FUNCTION:
                wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity, "<function>");
                break;
            case W_WEAK:
                wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity,
                    value.as.weak->object ? "weak(alive)" : "weak(expired)");
                break;
            case W_UNIT:
                wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity, "unit");
                break;
            case W_NONE:
                wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity, "none");
                break;
            case W_INT: {
                char number[32];
                snprintf(number, sizeof(number), "%" PRId64, value.as.i);
                wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity, number);
                break;
            }
            case W_FLOAT: {
                char* number = wysna_format_float(value.as.f);
                wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity, number);
                free(number);
                break;
            }
            case W_BOOL:
                wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity,
                                     value.as.b ? "true" : "false");
                break;
            case W_STR:
                if (!task.quote_str) {
                    wysna_format_append(&buffer, &buffer_length, &buffer_capacity,
                                    value.as.string.data, value.as.string.length);
                } else {
                    wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity, "\"");
                    for (size_t i = 0; i < value.as.string.length; i++) {
                        if (value.as.string.data[i] == 0) {
                            wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity, "\\0");
                        } else {
                            wysna_format_append(&buffer, &buffer_length, &buffer_capacity,
                                            value.as.string.data + i, 1);
                        }
                    }
                    wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity, "\"");
                }
                break;
            case W_ENUM:
                if (strcmp(value.as.en.enum_name, "Option") == 0 &&
                    strcmp(value.as.en.variant, "Some") == 0 && value.as.en.box) {
                    wysna_format_push_value(&tasks, &task_count, &task_capacity, &heap_tasks,
                                        value.as.en.box->val, task.quote_str);
                } else if (value.as.en.box && value.as.en.box->val.tag == W_TUPLE) {
                    WTupleBuf* payload = value.as.en.box->val.as.tuple;
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, ")");
                    for (int32_t i = payload->len - 1; i >= 0; i--) {
                        wysna_format_push_value(&tasks, &task_count, &task_capacity, &heap_tasks,
                                            payload->items[i], true);
                        if (i > 0) wysna_format_push_text(&tasks, &task_count, &task_capacity,
                                                      &heap_tasks, ", ");
                    }
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, "(");
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks,
                                       value.as.en.variant);
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, ".");
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks,
                                       wysna_nominal_display_name(value.as.en.enum_name));
                } else if (value.as.en.box) {
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, ")");
                    wysna_format_push_value(&tasks, &task_count, &task_capacity, &heap_tasks,
                                        value.as.en.box->val, true);
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, "(");
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks,
                                       value.as.en.variant);
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, ".");
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks,
                                       wysna_nominal_display_name(value.as.en.enum_name));
                } else {
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks,
                                       value.as.en.variant);
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, ".");
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks,
                                       wysna_nominal_display_name(value.as.en.enum_name));
                }
                break;
            case W_LIST: {
                WListBuf* list = value.as.list;
                wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, "]");
                for (int32_t i = list->len - 1; i >= 0; i--) {
                    wysna_format_push_value(&tasks, &task_count, &task_capacity, &heap_tasks,
                                        list->data[i], true);
                    if (i > 0) wysna_format_push_text(&tasks, &task_count, &task_capacity,
                                                  &heap_tasks, ", ");
                }
                wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, "[");
                break;
            }
            case W_TUPLE: {
                WTupleBuf* tuple = value.as.tuple;
                wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, ")");
                for (int32_t i = tuple->len - 1; i >= 0; i--) {
                    wysna_format_push_value(&tasks, &task_count, &task_capacity, &heap_tasks,
                                        tuple->items[i], true);
                    if (i > 0) wysna_format_push_text(&tasks, &task_count, &task_capacity,
                                                  &heap_tasks, ", ");
                }
                wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, "(");
                break;
            }
            case W_DICT: {
                WDictBuf* dict = value.as.dict;
                wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, "}");
                for (int32_t i = dict->len - 1; i >= 0; i--) {
                    wysna_format_push_value(&tasks, &task_count, &task_capacity, &heap_tasks,
                                        dict->vals[i], true);
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, ": ");
                    wysna_format_push_value(&tasks, &task_count, &task_capacity, &heap_tasks,
                                        dict->keys[i], true);
                    if (i > 0) wysna_format_push_text(&tasks, &task_count, &task_capacity,
                                                  &heap_tasks, ", ");
                }
                wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, "{");
                break;
            }
            case W_STRUCT:
            case W_OBJECT: {
                WStructBuf* structure = value.as.st;
                if (value.tag == W_OBJECT) {
                    if (!wysna_format_object_enter(&active_objects, structure)) {
                        wysna_format_append_text(&buffer, &buffer_length, &buffer_capacity, "<cycle>");
                        break;
                    }
                    WFormatTask leave = {value, NULL, false, false, true};
                    wysna_format_push(&tasks, &task_count, &task_capacity, &heap_tasks, leave);
                }
                wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, " }");
                for (int32_t i = structure->len - 1; i >= 0; i--) {
                    wysna_format_push_value(&tasks, &task_count, &task_capacity, &heap_tasks,
                                        structure->vals[i], true);
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, ": ");
                    wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks,
                                       structure->keys[i]);
                    if (i > 0) wysna_format_push_text(&tasks, &task_count, &task_capacity,
                                                  &heap_tasks, ", ");
                }
                wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, " { ");
                wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks,
                                   wysna_nominal_display_name(structure->name));
                break;
            }
            case W_OK:
            case W_ERR:
                wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks, ")");
                if (value.as.box) {
                    wysna_format_push_value(&tasks, &task_count, &task_capacity, &heap_tasks,
                                        value.as.box->val, false);
                }
                wysna_format_push_text(&tasks, &task_count, &task_capacity, &heap_tasks,
                                   value.tag == W_OK ? "Ok(" : "Err(");
                break;
        }
    }

    if (heap_tasks) free(tasks);
    free(active_objects.entries);
    return buffer;
}
/* Standard Built-ins */
static inline WVal wysna_builtin_print(int32_t argc, const WVal* argv) {
    for (int32_t i = 0; i < argc; i++) {
        if (i > 0) fputc(' ', stdout);
        WVal value = argv[i];
        while (value.tag == W_ENUM && strcmp(value.as.en.enum_name, "Option") == 0 &&
               strcmp(value.as.en.variant, "Some") == 0 && value.as.en.box) value = value.as.en.box->val;
        if (value.tag == W_STR) fwrite(value.as.string.data, 1, value.as.string.length, stdout);
        else { char* s = wysna_to_cstr(value, false); fputs(s, stdout); free(s); }
    }
    fputc('\n', stdout);
    fflush(stdout);
    return wysna_unit();
}

static inline WVal wysna_builtin_eprint(int32_t argc, const WVal* argv) {
    for (int32_t i = 0; i < argc; i++) {
        if (i > 0) fputc(' ', stderr);
        char* s = wysna_to_cstr(argv[i], false);
        const char* metrics = getenv("WYSNA_COW_METRICS");
        if (metrics && strcmp(metrics, "1") == 0 && argc == 1 && argv[i].tag == W_STR &&
            strncmp(s, "__COW_CHECKPOINT__:", 19) == 0) {
            const char* label = s + 19;
            fprintf(stderr, "[WYSNA_COW_CHECKPOINT:%s] detach_list=%" PRId64 " detach_dict=%" PRId64 " detach_struct=%" PRId64 " copied_slots=%" PRId64 " copied_bytes=%" PRId64 " allocated_bytes=%" PRId64 " allocs=%" PRId64,
                    label, wysna_g_cow_detach_list, wysna_g_cow_detach_dict, wysna_g_cow_detach_struct, wysna_g_cow_copied_slots, wysna_g_cow_copied_bytes, wysna_g_cow_allocated_bytes, wysna_g_cow_alloc_count);
        } else {
            if (argv[i].tag == W_STR) fwrite(argv[i].as.string.data, 1, argv[i].as.string.length, stderr);
            else fputs(s, stderr);
        }
        free(s);
    }
    fputc('\n', stderr);
    fflush(stderr);
    return wysna_unit();
}

static inline WVal wysna_builtin_exit(WVal code) {
    int c = (code.tag == W_INT) ? (int)code.as.i : 0;
    wysna_runtime_cleanup();
    exit(c);
    return wysna_unit();
}

static inline WVal wysna_builtin_len(WVal v) {
    if (v.tag == W_LIST) return wysna_int(v.as.list->len);
    if (v.tag == W_DICT) return wysna_int(v.as.dict->len);
    if (v.tag == W_TUPLE) return wysna_int(v.as.tuple->len);
    if (v.tag == W_STR) return wysna_int(wysna_string_length(v));
    return wysna_int(0);
}

static inline WVal wysna_builtin_str(WVal v) {
    if (v.tag == W_STR) return wysna_clone(v);
    return wysna_owned_str(wysna_to_cstr(v, false));
}

static inline void wysna_conversion_error(const char* kind) {
    fprintf(stderr, "[W4003] RuntimeError: Invalid %s conversion\n", kind);
    exit(1);
}

static inline const char* wysna_conversion_end(const char* end) {
    while (*end && isspace((unsigned char)*end)) end++;
    return end;
}

static inline WVal wysna_builtin_int(WVal v) {
    if (v.tag == W_BOOL) return wysna_int(v.as.b ? 1 : 0);
    if (v.tag == W_INT) return v;
    if (v.tag == W_FLOAT) {
        if (!isfinite(v.as.f) || v.as.f < -9223372036854775808.0 || v.as.f >= 9223372036854775808.0)
            wysna_conversion_error("int");
        return wysna_int((int64_t)v.as.f);
    }
    if (v.tag == W_STR && !memchr(v.as.string.data, 0, v.as.string.length)) {
        char* end; errno = 0;
        int64_t value = strtoll(v.as.string.data, &end, 10);
        if (errno != ERANGE && end != v.as.string.data && *wysna_conversion_end(end) == 0) return wysna_int(value);
    }
    wysna_conversion_error("int");
    return wysna_unit();
}

static inline bool wysna_ascii_space(unsigned char value) {
    return value == ' ' || (value >= 9 && value <= 13);
}

/* Match Python's explicit ASCII grammar, including inf/infinity/nan, before strtod. */
static inline bool wysna_float_text_valid(const char* text, size_t length) {
    size_t begin = 0, end = length;
    while (begin < end && wysna_ascii_space((unsigned char)text[begin])) begin++;
    while (end > begin && wysna_ascii_space((unsigned char)text[end - 1])) end--;
    if (begin < end && (text[begin] == '+' || text[begin] == '-')) begin++;
    const char* words[] = { "inf", "infinity", "nan" };
    for (size_t word = 0; word < 3; word++) {
        if (end - begin != strlen(words[word])) continue;
        bool same = true;
        for (size_t i = begin; i < end; i++) {
            unsigned char ch = (unsigned char)text[i];
            if (ch >= 'A' && ch <= 'Z') ch += 'a' - 'A';
            if (ch != (unsigned char)words[word][i - begin]) same = false;
        }
        if (same) return true;
    }
    size_t position = begin, digits = 0;
    while (position < end && text[position] >= '0' && text[position] <= '9') { position++; digits++; }
    if (position < end && text[position] == '.') {
        position++;
        while (position < end && text[position] >= '0' && text[position] <= '9') { position++; digits++; }
    }
    if (!digits) return false;
    if (position < end && (text[position] == 'e' || text[position] == 'E')) {
        position++;
        if (position < end && (text[position] == '+' || text[position] == '-')) position++;
        size_t exponent = position;
        while (position < end && text[position] >= '0' && text[position] <= '9') position++;
        if (position == exponent) return false;
    }
    return position == end;
}

static inline WVal wysna_builtin_float(WVal v) {
    if (v.tag == W_BOOL) return wysna_float(v.as.b ? 1.0 : 0.0);
    if (v.tag == W_FLOAT) return v;
    if (v.tag == W_INT) return wysna_float((double)v.as.i);
    if (v.tag == W_STR && wysna_float_text_valid(v.as.string.data, v.as.string.length)) {
        char* end;
        double value = strtod(v.as.string.data, &end);
        if (end != v.as.string.data && *wysna_conversion_end(end) == 0 && !strstr(v.as.string.data, "0x") && !strstr(v.as.string.data, "0X"))
            return wysna_float(value);
    }
    wysna_conversion_error("float");
    return wysna_unit();
}

static inline WVal wysna_builtin_ord(WVal v) {
    if (v.tag != W_STR || v.as.string.length == 0) {
        fprintf(stderr, "[W4003] RuntimeError: ord() expects non-empty str\n");
        exit(1);
    }
    size_t slen = 0;
    int64_t cp = 0;
    if (!wysna_utf8_valid_codepoint_at_n(v.as.string.data, v.as.string.length, 0, &slen, &cp)) {
        return wysna_int((unsigned char)v.as.string.data[0]);
    }
    return wysna_int(cp);
}

static inline WVal wysna_builtin_chr(WVal v) {
    if (v.tag != W_INT) {
        fprintf(stderr, "[W4003] RuntimeError: chr() expects int\n");
        exit(1);
    }
    int64_t cp = v.as.i;
    if (cp < 0 || cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) {
        fprintf(stderr, "[W4003] RuntimeError: chr() arg not in valid Unicode scalar range: %" PRId64 "\n", cp);
        exit(1);
    }
    if (cp < 0x80) return wysna_ascii_string((uint8_t)cp);
    char* buf = (char*)wysna_alloc_safe(5);
    if (cp < 0x800) {
        buf[0] = (char)(0xC0 | (cp >> 6));
        buf[1] = (char)(0x80 | (cp & 0x3F));
        buf[2] = '\0';
    } else if (cp < 0x10000) {
        buf[0] = (char)(0xE0 | (cp >> 12));
        buf[1] = (char)(0x80 | ((cp >> 6) & 0x3F));
        buf[2] = (char)(0x80 | (cp & 0x3F));
        buf[3] = '\0';
    } else {
        buf[0] = (char)(0xF0 | (cp >> 18));
        buf[1] = (char)(0x80 | ((cp >> 12) & 0x3F));
        buf[2] = (char)(0x80 | ((cp >> 6) & 0x3F));
        buf[3] = (char)(0x80 | (cp & 0x3F));
        buf[4] = '\0';
    }
    return wysna_owned_str_n(buf, cp < 0x800 ? 2 : cp < 0x10000 ? 3 : 4);
}

static inline WVal wysna_builtin_slice(WVal s, WVal start, WVal end) {
    if (s.tag == W_LIST) {
        /* SPEC 11.1: slice() is polymorphic over str and list[T]. */
        WListBuf* b = s.as.list;
        int64_t st = start.as.i < 0 ? 0 : start.as.i;
        int64_t en = end.as.i > b->len ? b->len : end.as.i;
        if (en <= st) return wysna_make_list(0, NULL);
        return wysna_make_list((int32_t)(en - st), b->data + st);
    }
    if (s.tag != W_STR) {
        fprintf(stderr, "[W4003] RuntimeError: slice() expects str or list\n");
        exit(1);
    }
    int64_t total_cp = wysna_string_length(s);
    int64_t st = start.as.i < 0 ? 0 : start.as.i;
    int64_t en = end.as.i > total_cp ? total_cp : end.as.i;
    if (en <= st || st >= total_cp) return wysna_str("");
    size_t st_off = 0, dummy_len = 0, en_off = 0;
    wysna_string_offset(s, st, &st_off, &dummy_len);
    if (en == total_cp) {
        en_off = s.as.string.length;
    } else {
        wysna_string_offset(s, en, &en_off, &dummy_len);
    }
    size_t blen = en_off - st_off;
    char* buf = (char*)wysna_alloc_safe(blen + 1);
    memcpy(buf, s.as.string.data + st_off, blen);
    buf[blen] = '\0';
    return wysna_owned_str_n(buf, blen);
}

/* A two-pass string builder: one allocation and one copy per input byte. */
static inline WVal wysna_builtin_join_strings(WVal parts, WVal separator) {
    if (parts.tag != W_LIST || separator.tag != W_STR)
        wysna_runtime_fail("W4003", "join_strings requires list[str] and str");
    size_t length = 0;
    for (int32_t i = 0; i < parts.as.list->len; i++) {
        WVal part = parts.as.list->data[i];
        if (part.tag != W_STR) wysna_runtime_fail("W4003", "join_strings requires string elements");
        size_t extra = i ? separator.as.string.length : 0;
        if (part.as.string.length > SIZE_MAX - length - 1 || extra > SIZE_MAX - length - part.as.string.length - 1)
            wysna_runtime_fail("W4003", "Joined string is too large");
        length += extra + part.as.string.length;
    }
    char* data = (char*)wysna_alloc_safe(length + 1);
    size_t offset = 0;
    for (int32_t i = 0; i < parts.as.list->len; i++) {
        if (i) { memcpy(data + offset, separator.as.string.data, separator.as.string.length); offset += separator.as.string.length; }
        WVal part = parts.as.list->data[i];
        memcpy(data + offset, part.as.string.data, part.as.string.length); offset += part.as.string.length;
    }
    data[length] = 0;
    return wysna_owned_str_n(data, length);
}

static inline WVal wysna_builtin_bytes(WVal s) {
    if (s.tag != W_STR) {
        fprintf(stderr, "[W4003] RuntimeError: bytes() expects str\n");
        exit(1);
    }
    size_t slen = s.as.string.length;
    WListBuf* b = (WListBuf*)wysna_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = (int32_t)slen;
    b->cap = slen > 4 ? (int32_t)slen : 4;
    b->data = (WVal*)wysna_alloc_safe(sizeof(WVal) * b->cap);
    wysna_mem_on_alloc();
    for (size_t i = 0; i < slen; i++) {
        b->data[i] = wysna_int((int64_t)(unsigned char)s.as.string.data[i]);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal wysna_builtin_enumerate(WVal list_val) {
    if (list_val.tag != W_LIST) {
        fprintf(stderr, "[W4003] RuntimeError: enumerate() expects list\n");
        exit(1);
    }
    WListBuf* src = list_val.as.list;
    WListBuf* b = (WListBuf*)wysna_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = src->len;
    b->cap = src->len > 4 ? src->len : 4;
    b->data = (WVal*)wysna_alloc_safe(sizeof(WVal) * b->cap);
    wysna_mem_on_alloc();
    for (int32_t i = 0; i < src->len; i++) {
        WVal pair[2] = { wysna_int(i), src->data[i] };
        b->data[i] = wysna_make_tuple(2, pair);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal wysna_builtin_dict_items(WVal dict_val) {
    if (dict_val.tag != W_DICT) {
        fprintf(stderr, "[W4003] RuntimeError: dict_items() expects dict\n");
        exit(1);
    }
    WDictBuf* d = dict_val.as.dict;
    WListBuf* b = (WListBuf*)wysna_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = d->len;
    b->cap = d->len > 4 ? d->len : 4;
    b->data = (WVal*)wysna_alloc_safe(sizeof(WVal) * b->cap);
    wysna_mem_on_alloc();
    for (int32_t i = 0; i < d->len; i++) {
        WVal pair[2] = { d->keys[i], d->vals[i] };
        b->data[i] = wysna_make_tuple(2, pair);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal wysna_io_error(const char* message) {
    const char* keys[1] = { "message" };
    WVal values[1] = { wysna_str(message) };
    return wysna_err(wysna_make_struct("IoError", 1, keys, values));
}

static inline FILE* wysna_builtin_fopen(const char* path, const char* mode) {
#ifdef _WIN32
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, NULL, 0);
    if (!count) count = MultiByteToWideChar(CP_ACP, 0, path, -1, NULL, 0);
    if (!count) return NULL;
    wchar_t* wide = (wchar_t*)wysna_alloc_safe((size_t)count * sizeof(wchar_t));
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, wide, count) &&
        !MultiByteToWideChar(CP_ACP, 0, path, -1, wide, count)) {
        free(wide);
        return NULL;
    }
    wchar_t wide_mode[8];
    MultiByteToWideChar(CP_UTF8, 0, mode, -1, wide_mode, 8);
    FILE* file = _wfopen(wide, wide_mode);
    free(wide);
    return file;
#else
    return fopen(path, mode);
#endif
}

static inline WVal wysna_builtin_read_file(WVal path) {
    if (path.tag != W_STR || memchr(path.as.string.data, 0, path.as.string.length)) return wysna_io_error("Invalid path");
    FILE* file = wysna_builtin_fopen(path.as.string.data, "rb");
    if (!file) return wysna_io_error("Failed to open file");
    size_t length = 0, capacity = 4096;
    char* data = (char*)wysna_alloc_safe(capacity + 1);
    while (1) {
        size_t count = fread(data + length, 1, capacity - length, file);
        length += count;
        if (ferror(file)) { fclose(file); free(data); return wysna_io_error("Failed to read file"); }
        if (feof(file)) break;
        if (length == capacity) {
            if (capacity > SIZE_MAX / 2 - 1) { fclose(file); free(data); return wysna_io_error("File too large"); }
            capacity *= 2;
            data = (char*)wysna_realloc_safe(data, capacity + 1);
        }
    }
    if (fclose(file) != 0) { free(data); return wysna_io_error("Failed to close file"); }
    data[length] = 0;
    size_t offset = 0;
    while (offset < length) {
        size_t step;
        if (!wysna_utf8_valid_codepoint_at_n(data, length, offset, &step, NULL)) {
            free(data); return wysna_io_error("Invalid UTF-8 file");
        }
        offset += step;
    }
    return wysna_ok(wysna_owned_str_n(data, length));
}

static inline WVal wysna_builtin_write_file(WVal path, WVal content) {
    if (path.tag != W_STR || content.tag != W_STR || memchr(path.as.string.data, 0, path.as.string.length))
        return wysna_io_error("Invalid arguments");
    FILE* file = wysna_builtin_fopen(path.as.string.data, "wb");
    if (!file) return wysna_io_error("Failed to write file");
    size_t written = fwrite(content.as.string.data, 1, content.as.string.length, file);
    bool failed = written != content.as.string.length || ferror(file);
    if (fclose(file) != 0) failed = true;
    return failed ? wysna_io_error("Failed to write file") : wysna_ok(wysna_unit());
}

/*
 * Propagates an unhandled `Err` out of the program entrypoint.
 *
 * Wysna has no stack unwinding, so a fallible `main` returns its error as a value.
 * Discarding that value would make a failed program indistinguishable from a
 * successful one (exit code 0, no output) to make/CI/shell. The entrypoint
 * therefore reports the error on stderr and signals failure to the caller,
 * which terminates with a non-zero status.
 *
 * Error structs that expose a `message: str` field print that field; anything
 * else prints through the ordinary value formatter.
 */
static inline void wysna_report_entrypoint_error(WVal error) {
    const char* message = NULL;
    if (error.tag == W_STRUCT && strcmp(error.as.st->name, "IoError") == 0) {
        for (int32_t i = 0; i < error.as.st->len; i++) {
            if (strcmp(error.as.st->keys[i], "message") == 0 && error.as.st->vals[i].tag == W_STR) {
                message = error.as.st->vals[i].as.string.data;
                break;
            }
        }
    }
    if (message) {
        fprintf(stderr, "[W4003] RuntimeError: %s\n", message);
        return;
    }
    char* rendered = wysna_to_cstr(error, false);
    fprintf(stderr, "[W4003] RuntimeError: unhandled error returned by main: %s\n", rendered);
    free(rendered);
}

#ifdef _WIN32
static inline void wysna_init_args(int argc, char** argv) {
    (void)argc; (void)argv;
    typedef LPWSTR* (WINAPI *pfnCommandLineToArgvW)(LPCWSTR, int*);
    HMODULE hShell = LoadLibraryA("shell32.dll");
    pfnCommandLineToArgvW pCmdLineToArgvW = hShell ? (pfnCommandLineToArgvW)GetProcAddress(hShell, "CommandLineToArgvW") : NULL;
    int wysna_argc = 0;
    LPWSTR* wysna_argv = pCmdLineToArgvW ? pCmdLineToArgvW(GetCommandLineW(), &wysna_argc) : NULL;
    if (wysna_argv && wysna_argc > 0) {
        wysna_g_argc = wysna_argc;
        wysna_g_argv = (char**)wysna_alloc_safe(sizeof(char*) * (size_t)(wysna_argc + 1));
        wysna_g_argv_allocated = true;
        for (int i = 0; i < wysna_argc; i++) {
            int len = WideCharToMultiByte(CP_UTF8, 0, wysna_argv[i], -1, NULL, 0, NULL, NULL);
            char* utf8 = (char*)wysna_alloc_safe(len > 0 ? (size_t)len : 1);
            if (len > 0) {
                WideCharToMultiByte(CP_UTF8, 0, wysna_argv[i], -1, utf8, len, NULL, NULL);
            } else {
                utf8[0] = '\0';
            }
            wysna_g_argv[i] = utf8;
        }
        wysna_g_argv[wysna_argc] = NULL;
        LocalFree(wysna_argv);
    } else {
        wysna_g_argc = argc;
        wysna_g_argv = (char**)wysna_alloc_safe(sizeof(char*) * (size_t)(argc + 1));
        wysna_g_argv_allocated = true;
        for (int i = 0; i < argc; i++) {
            int wlen = MultiByteToWideChar(CP_ACP, 0, argv[i], -1, NULL, 0);
            if (wlen > 0) {
                wchar_t* wide = (wchar_t*)wysna_alloc_safe((size_t)wlen * sizeof(wchar_t));
                MultiByteToWideChar(CP_ACP, 0, argv[i], -1, wide, wlen);
                int u8len = WideCharToMultiByte(CP_UTF8, 0, wide, -1, NULL, 0, NULL, NULL);
                char* utf8 = (char*)wysna_alloc_safe(u8len > 0 ? (size_t)u8len : 1);
                if (u8len > 0) {
                    WideCharToMultiByte(CP_UTF8, 0, wide, -1, utf8, u8len, NULL, NULL);
                } else {
                    utf8[0] = '\0';
                }
                wysna_g_argv[i] = utf8;
                free(wide);
            } else {
                size_t blen = strlen(argv[i]);
                char* copy = (char*)wysna_alloc_safe(blen + 1);
                memcpy(copy, argv[i], blen + 1);
                wysna_g_argv[i] = copy;
            }
        }
        wysna_g_argv[argc] = NULL;
    }
}
#else
static inline void wysna_init_args(int argc, char** argv) {
    wysna_g_argc = argc;
    wysna_g_argv = argv;
}
#endif

static inline WVal wysna_builtin_args(void) {
    WListBuf* b = (WListBuf*)wysna_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = (int32_t)wysna_g_argc;
    b->cap = wysna_g_argc > 4 ? (int32_t)wysna_g_argc : 4;
    b->data = (WVal*)wysna_alloc_safe(sizeof(WVal) * b->cap);
    wysna_mem_on_alloc();
    for (int i = 0; i < wysna_g_argc; i++) {
        b->data[i] = wysna_copy_str(wysna_g_argv[i]);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal wysna_builtin_env(WVal name) {
    if (name.tag != W_STR || memchr(name.as.string.data, 0, name.as.string.length))
        wysna_runtime_fail("W4003", "env() expects a valid environment variable name");
    char* key = (char*)wysna_alloc_safe(name.as.string.length + 1);
    memcpy(key, name.as.string.data, name.as.string.length);
    key[name.as.string.length] = 0;
#ifdef _WIN32
    int key_length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, key, -1, NULL, 0);
    if (!key_length) { free(key); wysna_runtime_fail("W4003", "environment variable name is not valid UTF-8"); }
    wchar_t* wide_key = (wchar_t*)wysna_alloc_safe((size_t)key_length * sizeof(wchar_t));
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, key, -1, wide_key, key_length)) {
        free(key); free(wide_key); wysna_runtime_fail("W4003", "environment variable name conversion failed");
    }
    free(key);
    SetLastError(ERROR_SUCCESS);
    DWORD required = GetEnvironmentVariableW(wide_key, NULL, 0);
    DWORD error = GetLastError();
    if (required == 0 && error == ERROR_ENVVAR_NOT_FOUND) { free(wide_key); return wysna_none(); }
    if (required == 0 && error == ERROR_SUCCESS) {
        free(wide_key);
        return wysna_enum_payload("Option", "Some", wysna_str(""));
    }
    if (required == 0 && error != ERROR_SUCCESS) {
        free(wide_key); wysna_runtime_fail("W4003", "unable to read environment variable");
    }
    wchar_t* wide_value = (wchar_t*)wysna_alloc_safe((size_t)(required ? required : 1) * sizeof(wchar_t));
    DWORD copied = required ? GetEnvironmentVariableW(wide_key, wide_value, required) : 0;
    free(wide_key);
    if (required && copied >= required) {
        free(wide_value); wysna_runtime_fail("W4003", "environment variable changed while reading");
    }
    int value_length = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide_value, -1, NULL, 0, NULL, NULL);
    if (!value_length) { free(wide_value); wysna_runtime_fail("W4003", "environment variable is not valid Unicode"); }
    char* copy = (char*)wysna_alloc_safe((size_t)value_length);
    if (!WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide_value, -1, copy, value_length, NULL, NULL)) {
        free(wide_value); free(copy); wysna_runtime_fail("W4003", "environment variable conversion failed");
    }
    free(wide_value);
    return wysna_enum_payload("Option", "Some", wysna_owned_str_n(copy, (size_t)value_length - 1));
#else
    const char* value = getenv(key);
    free(key);
    if (!value) return wysna_none();
    size_t length = strlen(value);
    size_t offset = 0;
    while (offset < length) {
        size_t width;
        if (!wysna_utf8_valid_codepoint_at_n(value, length, offset, &width, NULL))
            wysna_runtime_fail("W4003", "environment variable is not valid UTF-8");
        offset += width;
    }
    char* copy = (char*)wysna_alloc_safe(length + 1);
    memcpy(copy, value, length + 1);
    return wysna_enum_payload("Option", "Some", wysna_owned_str_n(copy, length));
#endif
}

static inline WVal wysna_builtin_unix_time(void) {
    time_t current = time(NULL);
    if (current == (time_t)-1) wysna_runtime_fail("W4003", "unable to read the system clock");
    return wysna_int((int64_t)current);
}

#if defined(__has_include)
#if __has_include("runtime/wysna_host.h")
#include "runtime/wysna_host.h"
#else
#include "wysna_host.h"
#endif
#else
#include "wysna_host.h"
#endif

#endif /* WYSNA_RUNTIME_H */
