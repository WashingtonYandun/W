#ifndef W_RUNTIME_H
#define W_RUNTIME_H

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

struct WVal {
    WStringBuf* string_owner;
    size_t string_length;
    WTag tag;
    union {
        int64_t i;
        double f;
        bool b;
        const char* s;
        WListBuf* list;
        WDictBuf* dict;
        WTupleBuf* tuple;
        WStructBuf* st;
        WEnumVal en;
        WBoxBuf* box;
        WWeakControl* weak;
        WFunctionBuf* function;
        void* pointer;
    } as;
};

typedef WVal (*WInvoke)(WVal environment, int32_t argc, const WVal* argv);
struct WClassVTable {
    int32_t count;
    const WInvoke* methods;
};
static inline WVal w_virtual_call(WVal receiver, int32_t slot, int32_t argc, const WVal* argv) {
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
static int64_t w_g_alloc_count = 0;
static int64_t w_g_free_count = 0;
static int64_t w_g_retain_count = 0;
static int64_t w_g_release_count = 0;
static int64_t w_g_live_objects = 0;

/* Copy-on-Write (CoW) Detach Telemetry Counters (B02) */
static int64_t w_g_cow_detach_list = 0;
static int64_t w_g_cow_detach_dict = 0;
static int64_t w_g_cow_detach_struct = 0;
static int64_t w_g_cow_copied_slots = 0;
static int64_t w_g_cow_copied_bytes = 0;
static int64_t w_g_cow_alloc_count = 0;
static int64_t w_g_cow_allocated_bytes = 0;

static inline void w_cow_reset_stats(void) {
    w_g_cow_detach_list = 0;
    w_g_cow_detach_dict = 0;
    w_g_cow_detach_struct = 0;
    w_g_cow_copied_slots = 0;
    w_g_cow_copied_bytes = 0;
    w_g_cow_alloc_count = 0;
    w_g_cow_allocated_bytes = 0;
}

/*
 * Logical container allocation tracking for W runtime.
 * NOTE on W_MEM_CHECK vs ASan/LSan:
 * w_mem_on_alloc() and w_mem_on_free() track high-level container lifecycle
 * (lists, dicts, objects, structs, tuples, strings) as a fast runtime invariant.
 * Comprehensive byte-level leak detection and memory safety are enforced by
 * Clang/GCC AddressSanitizer and LeakSanitizer (ASan/LSan) in CI and test suites.
 */
static inline void w_mem_on_alloc(void) {
    w_g_alloc_count++;
    w_g_live_objects++;
}

static inline void w_mem_on_free(void) {
    w_g_free_count++;
    w_g_live_objects--;
    if (w_g_live_objects < 0) {
        fprintf(stderr, "[W4003] RuntimeError: Memory safety violation (live_object_count underflow: %" PRId64 ")\n", w_g_live_objects);
        exit(1);
    }
}

static inline void w_check_refcount(int32_t rc, const char* op) {
    if (rc <= 0) {
        fprintf(stderr, "[W4003] RuntimeError: Memory safety violation (%s on object with refcount %" PRId32 ")\n", op, rc);
        exit(1);
    }
}

static inline void* w_alloc_safe(size_t size) {
    if (size == 0) return NULL;
    void* ptr = malloc(size);
    if (!ptr) {
        fprintf(stderr, "[W4003] RuntimeError: Out of memory (failed to allocate %zu bytes)\n", size);
        exit(1);
    }
    return ptr;
}

static inline void* w_realloc_safe(void* old_ptr, size_t new_size) {
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

static inline void w_runtime_cleanup(void) {
    const char* stats_env = getenv("W_MEM_STATS");
    if (stats_env && strcmp(stats_env, "1") == 0) {
        fprintf(stderr, "[W_MEM_STATS] alloc=%" PRId64 " free=%" PRId64 " retain=%" PRId64 " release=%" PRId64 " live=%" PRId64 "\n",
                w_g_alloc_count, w_g_free_count, w_g_retain_count, w_g_release_count, w_g_live_objects);
    }
    const char* cow_env = getenv("W_COW_METRICS");
    if (cow_env && strcmp(cow_env, "1") == 0) {
        fprintf(stderr, "[W_COW_METRICS] detach_list=%" PRId64 " detach_dict=%" PRId64 " detach_struct=%" PRId64 " copied_slots=%" PRId64 " copied_bytes=%" PRId64 " allocated_bytes=%" PRId64 " allocs=%" PRId64 "\n",
                w_g_cow_detach_list, w_g_cow_detach_dict, w_g_cow_detach_struct, w_g_cow_copied_slots, w_g_cow_copied_bytes, w_g_cow_allocated_bytes, w_g_cow_alloc_count);
    }
    const char* check_env = getenv("W_MEM_CHECK");
    if (check_env && strcmp(check_env, "1") == 0) {
        if (w_g_live_objects != 0 || w_g_alloc_count != w_g_free_count) {
            fprintf(stderr, "[W4003] RuntimeError: Memory leak detected at exit (alloc=%" PRId64 ", free=%" PRId64 ", retain=%" PRId64 ", release=%" PRId64 ", live=%" PRId64 ")\n",
                    w_g_alloc_count, w_g_free_count, w_g_retain_count, w_g_release_count, w_g_live_objects);
            exit(1);
        }
    }
}

/* Constructors */
static inline WVal w_unit(void) {
    WVal v; v.tag = W_UNIT; v.as.i = 0; return v;
}

static inline WVal w_none(void) {
    WVal v; v.tag = W_NONE; v.as.i = 0; return v;
}

static inline WVal w_int(int64_t x) {
    WVal v; v.tag = W_INT; v.as.i = x; return v;
}

static inline WVal w_pointer(void* pointer) {
    WVal value = w_unit(); value.tag = W_POINTER; value.as.pointer = pointer; return value;
}

static inline int32_t w_ffi_int32(WVal value) {
    if (value.tag != W_INT || value.as.i < INT32_MIN || value.as.i > INT32_MAX) {
        fprintf(stderr, "[W4003] RuntimeError: int32 FFI argument out of range\n"); exit(1);
    }
    return (int32_t)value.as.i;
}

static inline WVal w_float(double x) {
    WVal v; v.tag = W_FLOAT; v.as.f = x; return v;
}

static inline WVal w_bool(bool x) {
    WVal v; v.tag = W_BOOL; v.as.b = x; return v;
}

static inline WVal w_str_n(const char* s, size_t length) {
    WVal v; v.tag = W_STR; v.string_owner = NULL;
    v.as.s = s ? s : ""; v.string_length = s ? length : 0; return v;
}

static inline WVal w_str(const char* s) {
    return w_str_n(s, s ? strlen(s) : 0);
}

/* Takes ownership of a terminated buffer; length includes embedded NUL bytes. */
static inline WVal w_owned_str_n(char* data, size_t length) {
    WStringBuf* buffer = (WStringBuf*)w_alloc_safe(sizeof(WStringBuf));
    buffer->refcount = 1;
    buffer->byte_length = length;
    buffer->codepoint_offsets = NULL;
    buffer->codepoint_count = 0;
    buffer->data = data;
    w_mem_on_alloc();
    WVal value = w_str_n(data, length);
    value.string_owner = buffer;
    return value;
}

static inline WVal w_owned_str(char* data) {
    return w_owned_str_n(data, strlen(data));
}

static inline WVal w_copy_str(const char* data) {
    size_t length = strlen(data);
    char* copy = (char*)w_alloc_safe(length + 1);
    memcpy(copy, data, length + 1);
    return w_owned_str_n(copy, length);
}

static inline WVal w_ok(WVal inner);
static inline WVal w_err(WVal inner);

static inline bool w_builtin_name(const char* name, const char* base) {
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

static inline WVal w_enum(const char* enum_name, const char* variant) {
    if (w_builtin_name(enum_name, "Option") && strcmp(variant, "None") == 0) return w_none();
    WVal v;
    v.tag = W_ENUM;
    v.as.en.enum_name = w_builtin_name(enum_name, "Option") ? "Option" : enum_name;
    v.as.en.variant = variant;
    v.as.en.box = NULL;
    return v;
}

static inline WVal w_enum_payload(const char* enum_name, const char* variant, WVal payload) {
    if (w_builtin_name(enum_name, "Result")) {
        if (strcmp(variant, "Ok") == 0) return w_ok(payload);
        if (strcmp(variant, "Err") == 0) return w_err(payload);
    }
    WBoxBuf* b = (WBoxBuf*)w_alloc_safe(sizeof(WBoxBuf));
    b->refcount = 1;
    b->val = payload;
    w_mem_on_alloc();
    WVal v;
    v.tag = W_ENUM;
    v.as.en.enum_name = w_builtin_name(enum_name, "Option") ? "Option" : enum_name;
    v.as.en.variant = variant;
    v.as.en.box = b;
    return v;
}

static inline WVal w_ok(WVal inner) {
    WBoxBuf* b = (WBoxBuf*)w_alloc_safe(sizeof(WBoxBuf));
    b->refcount = 1;
    b->val = inner;
    w_mem_on_alloc();
    WVal v;
    v.tag = W_OK;
    v.as.box = b;
    return v;
}

static inline WVal w_err(WVal inner) {
    WBoxBuf* b = (WBoxBuf*)w_alloc_safe(sizeof(WBoxBuf));
    b->refcount = 1;
    b->val = inner;
    w_mem_on_alloc();
    WVal v;
    v.tag = W_ERR;
    v.as.box = b;
    return v;
}

static inline WVal w_wrap_result(WVal v, const char* err_type) {
    if (v.tag == W_OK || v.tag == W_ERR) return v;
    (void)err_type;
    return w_ok(v);
}

/* Deterministic RC + Copy-on-Write */
static inline WVal w_clone(WVal v) {
    if (v.tag == W_FUNCTION) {
        w_check_refcount(v.as.function->refcount, "retain/function");
        v.as.function->refcount++;
        w_g_retain_count++;
    } else if (v.tag == W_STR && v.string_owner) {
        w_check_refcount(v.string_owner->refcount, "retain/string");
        v.string_owner->refcount++;
        w_g_retain_count++;
    } else if (v.tag == W_LIST && v.as.list) {
        w_check_refcount(v.as.list->refcount, "retain/list");
        v.as.list->refcount++;
        w_g_retain_count++;
    } else if (v.tag == W_DICT && v.as.dict) {
        w_check_refcount(v.as.dict->refcount, "retain/dict");
        v.as.dict->refcount++;
        w_g_retain_count++;
    } else if (v.tag == W_WEAK && v.as.weak) {
        w_check_refcount(v.as.weak->weak, "retain/weak");
        v.as.weak->weak++;
        w_g_retain_count++;
    } else if (v.tag == W_OBJECT && v.as.st) {
        w_check_refcount(v.as.st->control->strong, "retain/object");
        v.as.st->control->strong++;
        w_g_retain_count++;
    } else if (v.tag == W_STRUCT && v.as.st) {
        w_check_refcount(v.as.st->refcount, "retain/struct_or_object");
        v.as.st->refcount++;
        w_g_retain_count++;
    } else if (v.tag == W_TUPLE && v.as.tuple) {
        w_check_refcount(v.as.tuple->refcount, "retain/tuple");
        v.as.tuple->refcount++;
        w_g_retain_count++;
    } else if ((v.tag == W_OK || v.tag == W_ERR) && v.as.box) {
        w_check_refcount(v.as.box->refcount, "retain/box");
        v.as.box->refcount++;
        w_g_retain_count++;
    } else if (v.tag == W_ENUM && v.as.en.box) {
        w_check_refcount(v.as.en.box->refcount, "retain/enum_box");
        v.as.en.box->refcount++;
        w_g_retain_count++;
    }
    return v;
}

/*
 * Releasing a deeply nested value must not recurse: a 100k-deep list, tuple, enum
 * payload chain or struct overflowed the C stack and died with SIGSEGV while
 * freeing the program's result. `w_release` therefore frees one container and
 * defers its children onto an explicit work list (w_release_deferred), which is
 * drained iteratively in w_release.
 */
static WVal* w_release_deferred(WVal* slot, int32_t* produced);

static inline void w_release(WVal v) {
    WVal stack_work[64];
    WVal* work = stack_work;
    int32_t count = 0;
    int32_t capacity = 64;
    bool heap_work = false;

    work[count++] = v;
    while (count > 0) {
        WVal current = work[--count];
        int32_t produced = 0;
        WVal* children = w_release_deferred(&current, &produced);
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
static WVal* w_release_deferred(WVal* slot, int32_t* produced) {
    /*
     * Frees exactly one container level and returns a malloc'd array of the children
     * that still have to be released, draining nothing itself. Callers append those to
     * their work list, which is what keeps `w_release` off the C stack: without this a
     * 100k-deep list, tuple, enum payload chain or struct overflowed the stack and
     * died with SIGSEGV while freeing the program result.
     *
     * `produced` is the number of entries written to the returned array.
     */
    WVal v = *slot;
    *produced = 0;
    if (v.tag == W_FUNCTION) {
        w_check_refcount(v.as.function->refcount, "release/function");
        w_g_release_count++;
        if (--v.as.function->refcount == 0) {
            WVal environment = v.as.function->environment;
            free(v.as.function);
            w_mem_on_free();
            if (environment.tag != W_UNIT) {
                WVal* out = (WVal*)malloc(sizeof(WVal));
                if (!out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
                out[0] = environment;
                *produced = 1;
                return out;
            }
        }
    } else if (v.tag == W_STR && v.string_owner) {
        WStringBuf* buffer = v.string_owner;
        w_check_refcount(buffer->refcount, "release/string");
        w_g_release_count++;
        if (--buffer->refcount == 0) {
            free(buffer->data);
            free(buffer->codepoint_offsets);
            free(buffer);
            w_mem_on_free();
        }
    } else if (v.tag == W_LIST && v.as.list) {
        WListBuf* b = v.as.list;
        w_check_refcount(b->refcount, "release/list");
        w_g_release_count++;
        b->refcount--;
        if (b->refcount == 0) {
            b->refcount = -1;
            WVal* out = b->len > 0 ? (WVal*)malloc(sizeof(WVal) * (size_t)b->len) : NULL;
            int32_t len = b->len;
            if (len > 0 && !out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
            for (int32_t i = 0; i < len; i++) out[i] = b->data[i];
            free(b->data);
            free(b);
            w_mem_on_free();
            *produced = len;
            return out;
        }
    } else if (v.tag == W_DICT && v.as.dict) {
        WDictBuf* d = v.as.dict;
        w_check_refcount(d->refcount, "release/dict");
        w_g_release_count++;
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
            w_mem_on_free();
            *produced = total;
            return out;
        }
    } else if (v.tag == W_WEAK && v.as.weak) {
        WWeakControl* control = v.as.weak;
        w_check_refcount(control->weak, "release/weak");
        w_g_release_count++;
        if (--control->weak == 0) {
            free(control);
            w_mem_on_free();
        }
    } else if (v.tag == W_OBJECT && v.as.st) {
        WStructBuf* object = v.as.st;
        WWeakControl* control = object->control;
        w_check_refcount(control->strong, "release/object");
        w_g_release_count++;
        if (--control->strong == 0) {
            control->object = NULL;
            int32_t len = object->len;
            WVal* out = len > 0 ? (WVal*)malloc(sizeof(WVal) * (size_t)len) : NULL;
            if (len > 0 && !out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
            for (int32_t i = 0; i < len; i++) out[i] = object->vals[i];
            free(object->keys);
            free(object->vals);
            free(object);
            w_mem_on_free();
            if (--control->weak == 0) {
                free(control);
                w_mem_on_free();
            }
            *produced = len;
            return out;
        }
    } else if (v.tag == W_STRUCT && v.as.st) {
        WStructBuf* st = v.as.st;
        w_check_refcount(st->refcount, "release/struct_or_object");
        w_g_release_count++;
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
            w_mem_on_free();
            *produced = len;
            return out;
        }
    } else if (v.tag == W_TUPLE && v.as.tuple) {
        WTupleBuf* t = v.as.tuple;
        w_check_refcount(t->refcount, "release/tuple");
        w_g_release_count++;
        t->refcount--;
        if (t->refcount == 0) {
            t->refcount = -1;
            int32_t len = t->len;
            WVal* out = len > 0 ? (WVal*)malloc(sizeof(WVal) * (size_t)len) : NULL;
            if (len > 0 && !out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
            for (int32_t i = 0; i < len; i++) out[i] = t->items[i];
            free(t->items);
            free(t);
            w_mem_on_free();
            *produced = len;
            return out;
        }
    } else if ((v.tag == W_OK || v.tag == W_ERR) && v.as.box) {
        WBoxBuf* bx = v.as.box;
        w_check_refcount(bx->refcount, "release/box");
        w_g_release_count++;
        bx->refcount--;
        if (bx->refcount == 0) {
            bx->refcount = -1;
            WVal inner = bx->val;
            free(bx);
            w_mem_on_free();
            WVal* out = (WVal*)malloc(sizeof(WVal));
            if (!out) { fprintf(stderr, "[W4003] RuntimeError: out of memory\n"); exit(1); }
            out[0] = inner;
            *produced = 1;
            return out;
        }
    } else if (v.tag == W_ENUM && v.as.en.box) {
        WBoxBuf* bx = v.as.en.box;
        w_check_refcount(bx->refcount, "release/enum_box");
        w_g_release_count++;
        bx->refcount--;
        if (bx->refcount == 0) {
            bx->refcount = -1;
            WVal inner = bx->val;
            free(bx);
            w_mem_on_free();
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
static inline WVal w_function_new(WInvoke invoke, WVal environment) {
    WFunctionBuf* function = (WFunctionBuf*)w_alloc_safe(sizeof(WFunctionBuf));
    function->refcount = 1; function->invoke = invoke; function->environment = environment;
    w_mem_on_alloc();
    WVal value = w_unit(); value.tag = W_FUNCTION; value.as.function = function; return value;
}

static inline WVal w_call(WVal function, int32_t argc, const WVal* argv) {
    if (function.tag != W_FUNCTION) {
        fprintf(stderr, "[W4003] RuntimeError: Indirect call requires function\n"); exit(1);
    }
    return function.as.function->invoke(function.as.function->environment, argc, argv);
}

static inline void w_release_array(int32_t count, WVal* arr) {
    for (int32_t i = 0; i < count; i++) {
        w_release(arr[i]);
    }
}

static inline WVal w_move(WVal* src) {
    WVal v = *src;
    *src = w_unit();
    return v;
}

static inline WVal w_assign(WVal* dst, WVal owned_src) {
    w_release(*dst);
    *dst = owned_src;
    return *dst;
}

static inline bool w_is_none(WVal value) {
    return value.tag == W_NONE || (value.tag == W_ENUM &&
        strcmp(value.as.en.enum_name, "Option") == 0 && strcmp(value.as.en.variant, "None") == 0);
}

static inline WVal w_peek_optional(WVal value) {
    if (value.tag == W_ENUM && strcmp(value.as.en.enum_name, "Option") == 0 &&
        strcmp(value.as.en.variant, "Some") == 0 && value.as.en.box) return value.as.en.box->val;
    return value;
}

static inline WVal w_unwrap_optional(WVal value) {
    if (value.tag == W_ENUM && strcmp(value.as.en.enum_name, "Option") == 0 &&
        strcmp(value.as.en.variant, "Some") == 0 && value.as.en.box) {
        return w_clone(value.as.en.box->val);
    }
    return w_clone(value);
}

static inline WVal w_unwrap_ok(WVal v) {
    if (v.tag == W_OK && v.as.box) {
        return w_clone(v.as.box->val);
    }
    return w_clone(v);
}

static inline WVal w_unwrap_success(WVal value) {
    if (value.tag == W_ENUM && strcmp(value.as.en.enum_name, "Option") == 0)
        return w_unwrap_optional(value);
    return w_unwrap_ok(value);
}

static inline WVal w_unwrap_err(WVal v) {
    if (v.tag == W_ERR && v.as.box) {
        return w_clone(v.as.box->val);
    }
    return w_none();
}

static inline WVal w_peek_ok(WVal v) {
    if (v.tag == W_OK && v.as.box) {
        return v.as.box->val;
    }
    return v;
}

static inline WVal w_peek_err(WVal v) {
    if (v.tag == W_ERR && v.as.box) {
        return v.as.box->val;
    }
    return w_none();
}

static inline void w_list_detach(WVal* v) {
    if (v->tag != W_LIST || !v->as.list) return;
    WListBuf* old_b = v->as.list;
    w_check_refcount(old_b->refcount, "detach/list");
    if (old_b->refcount <= 1) return;
    old_b->refcount--;
    w_g_release_count++;
    WListBuf* new_b = (WListBuf*)w_alloc_safe(sizeof(WListBuf));
    new_b->refcount = 1;
    new_b->len = old_b->len;
    new_b->cap = old_b->cap > 0 ? old_b->cap : 4;
    new_b->data = (WVal*)w_alloc_safe(sizeof(WVal) * new_b->cap);
    w_mem_on_alloc();

    /* B02: CoW detach telemetry */
    w_g_cow_detach_list++;
    w_g_cow_copied_slots += old_b->len;
    w_g_cow_copied_bytes += (int64_t)(sizeof(WVal) * old_b->len);
    w_g_cow_allocated_bytes += (int64_t)(sizeof(WListBuf) + (sizeof(WVal) * new_b->cap));
    w_g_cow_alloc_count += 2;

    for (int32_t i = 0; i < old_b->len; i++) {
        new_b->data[i] = w_clone(old_b->data[i]);
    }
    v->as.list = new_b;
}

/* Dense insertion-order entries with an open-addressed lookup index. */
static inline bool w_eq(WVal a, WVal b);
static inline uint64_t w_key_hash_bytes(const unsigned char* data, size_t length, uint64_t hash) {
    for (size_t i = 0; i < length; i++) { hash ^= data[i]; hash *= UINT64_C(1099511628211); }
    return hash;
}
static inline uint64_t w_key_hash(WVal value) {
    uint64_t hash = UINT64_C(14695981039346656037) ^ (uint64_t)value.tag;
    if (value.tag == W_STR) return w_key_hash_bytes((const unsigned char*)value.as.s, value.string_length, hash);
    if (value.tag == W_INT || value.tag == W_BOOL) {
        uint64_t number = value.tag == W_INT ? (uint64_t)value.as.i : (uint64_t)value.as.b;
        number ^= number >> 30; number *= UINT64_C(0xbf58476d1ce4e5b9);
        number ^= number >> 27; number *= UINT64_C(0x94d049bb133111eb);
        return hash ^ number ^ (number >> 31);
    }
    if (value.tag == W_ENUM) {
        hash = w_key_hash_bytes((const unsigned char*)value.as.en.enum_name, strlen(value.as.en.enum_name), hash);
        hash = w_key_hash_bytes((const unsigned char*)value.as.en.variant, strlen(value.as.en.variant), hash);
        if (value.as.en.box) {
            WVal payload = value.as.en.box->val;
            if (payload.tag == W_TUPLE) {
                for (int32_t i = 0; i < payload.as.tuple->len; i++) hash = (hash ^ w_key_hash(payload.as.tuple->items[i])) * UINT64_C(1099511628211);
            } else hash ^= w_key_hash(payload);
        }
    }
    return hash;
}
static inline int32_t w_dict_find(WDictBuf* dict, WVal key) {
    uint32_t mask = (uint32_t)dict->bucket_count - 1;
    uint32_t slot = (uint32_t)w_key_hash(key) & mask;
    while (dict->buckets[slot] >= 0) {
        int32_t index = dict->buckets[slot];
        if (w_eq(dict->keys[index], key)) return index;
        slot = (slot + 1) & mask;
    }
    return -1;
}
static inline void w_dict_index_entry(WDictBuf* dict, int32_t index) {
    uint32_t mask = (uint32_t)dict->bucket_count - 1;
    uint32_t slot = (uint32_t)w_key_hash(dict->keys[index]) & mask;
    while (dict->buckets[slot] >= 0) slot = (slot + 1) & mask;
    dict->buckets[slot] = index;
}
static inline void w_dict_reindex(WDictBuf* dict, int32_t capacity) {
    free(dict->buckets);
    dict->bucket_count = capacity;
    dict->buckets = (int32_t*)w_alloc_safe(sizeof(int32_t) * (size_t)capacity);
    for (int32_t i = 0; i < capacity; i++) dict->buckets[i] = -1;
    for (int32_t i = 0; i < dict->len; i++) w_dict_index_entry(dict, i);
}

static inline void w_dict_detach(WVal* v) {
    if (v->tag != W_DICT || !v->as.dict) return;
    WDictBuf* old_b = v->as.dict;
    w_check_refcount(old_b->refcount, "detach/dict");
    if (old_b->refcount <= 1) return;
    old_b->refcount--;
    w_g_release_count++;
    WDictBuf* new_b = (WDictBuf*)w_alloc_safe(sizeof(WDictBuf));
    new_b->refcount = 1;
    new_b->len = old_b->len;
    new_b->cap = old_b->cap > 0 ? old_b->cap : 4;
    new_b->keys = (WVal*)w_alloc_safe(sizeof(WVal) * new_b->cap);
    new_b->vals = (WVal*)w_alloc_safe(sizeof(WVal) * new_b->cap);
    new_b->bucket_count = old_b->bucket_count;
    new_b->buckets = (int32_t*)w_alloc_safe(sizeof(int32_t) * (size_t)new_b->bucket_count);
    memcpy(new_b->buckets, old_b->buckets, sizeof(int32_t) * (size_t)new_b->bucket_count);
    w_mem_on_alloc();

    /* B02: CoW detach telemetry */
    w_g_cow_detach_dict++;
    w_g_cow_copied_slots += ((int64_t)old_b->len * 2);
    w_g_cow_copied_bytes += (int64_t)(sizeof(WVal) * old_b->len * 2 + sizeof(int32_t) * old_b->bucket_count);
    w_g_cow_allocated_bytes += (int64_t)(sizeof(WDictBuf) + (sizeof(WVal) * new_b->cap * 2) + sizeof(int32_t) * new_b->bucket_count);
    w_g_cow_alloc_count += 4;

    for (int32_t i = 0; i < old_b->len; i++) {
        new_b->keys[i] = w_clone(old_b->keys[i]);
        new_b->vals[i] = w_clone(old_b->vals[i]);
    }
    v->as.dict = new_b;
}

static inline void w_struct_detach(WVal* v) {
    if (v->tag != W_STRUCT || !v->as.st) return;
    WStructBuf* old_b = v->as.st;
    w_check_refcount(old_b->refcount, "detach/struct");
    if (old_b->refcount <= 1) return;
    old_b->refcount--;
    w_g_release_count++;
    WStructBuf* new_b = (WStructBuf*)w_alloc_safe(sizeof(WStructBuf));
    new_b->refcount = 1;
    new_b->control = NULL;
    new_b->vtable = NULL;
    new_b->name = old_b->name;
    new_b->len = old_b->len;
    int32_t cap = old_b->len > 0 ? old_b->len : 1;
    new_b->keys = (const char**)w_alloc_safe(sizeof(const char*) * cap);
    new_b->vals = (WVal*)w_alloc_safe(sizeof(WVal) * cap);
    w_mem_on_alloc();

    /* B02: CoW detach telemetry */
    w_g_cow_detach_struct++;
    w_g_cow_copied_slots += old_b->len;
    w_g_cow_copied_bytes += (int64_t)((sizeof(const char*) + sizeof(WVal)) * old_b->len);
    w_g_cow_allocated_bytes += (int64_t)(sizeof(WStructBuf) + (sizeof(const char*) * cap) + (sizeof(WVal) * cap));
    w_g_cow_alloc_count += 3;

    for (int32_t i = 0; i < old_b->len; i++) {
        new_b->keys[i] = old_b->keys[i];
        new_b->vals[i] = w_clone(old_b->vals[i]);
    }
    v->as.st = new_b;
}

/* Structural Equality */
static inline bool w_eq(WVal a, WVal b) {
    bool a_some = a.tag == W_ENUM && strcmp(a.as.en.enum_name, "Option") == 0 && strcmp(a.as.en.variant, "Some") == 0;
    bool b_some = b.tag == W_ENUM && strcmp(b.as.en.enum_name, "Option") == 0 && strcmp(b.as.en.variant, "Some") == 0;
    if (a_some && !b_some && b.tag != W_NONE) return w_eq(a.as.en.box->val, b);
    if (b_some && !a_some && a.tag != W_NONE) return w_eq(a, b.as.en.box->val);
    if (a.tag != b.tag) {
        if ((a.tag == W_NONE && b.tag == W_ENUM && strcmp(b.as.en.enum_name, "Option") == 0 && strcmp(b.as.en.variant, "None") == 0) ||
            (b.tag == W_NONE && a.tag == W_ENUM && strcmp(a.as.en.enum_name, "Option") == 0 && strcmp(a.as.en.variant, "None") == 0)) {
            return true;
        }
        if (a.tag == W_OK && b.tag == W_ENUM && strcmp(b.as.en.enum_name, "Result") == 0 && strcmp(b.as.en.variant, "Ok") == 0) {
            return b.as.en.box ? w_eq(a.as.box->val, b.as.en.box->val) : false;
        }
        if (b.tag == W_OK && a.tag == W_ENUM && strcmp(a.as.en.enum_name, "Result") == 0 && strcmp(a.as.en.variant, "Ok") == 0) {
            return a.as.en.box ? w_eq(a.as.en.box->val, b.as.box->val) : false;
        }
        if (a.tag == W_ERR && b.tag == W_ENUM && strcmp(b.as.en.enum_name, "Result") == 0 && strcmp(b.as.en.variant, "Err") == 0) {
            return b.as.en.box ? w_eq(a.as.box->val, b.as.en.box->val) : false;
        }
        if (b.tag == W_ERR && a.tag == W_ENUM && strcmp(a.as.en.enum_name, "Result") == 0 && strcmp(a.as.en.variant, "Err") == 0) {
            return a.as.en.box ? w_eq(a.as.en.box->val, b.as.box->val) : false;
        }
        return false;
    }
    switch (a.tag) {
        case W_POINTER: return a.as.pointer == b.as.pointer;
        case W_FUNCTION: return a.as.function == b.as.function;
        case W_UNIT:
        case W_NONE:
            return true;
        case W_INT:
            return a.as.i == b.as.i;
        case W_FLOAT:
            return a.as.f == b.as.f;
        case W_BOOL:
            return a.as.b == b.as.b;
        case W_STR:
            return a.string_length == b.string_length && memcmp(a.as.s, b.as.s, a.string_length) == 0;
        case W_ENUM:
            if (strcmp(a.as.en.enum_name, b.as.en.enum_name) != 0 ||
                strcmp(a.as.en.variant, b.as.en.variant) != 0) {
                return false;
            }
            if (!a.as.en.box && !b.as.en.box) return true;
            if (!a.as.en.box || !b.as.en.box) return false;
            return w_eq(a.as.en.box->val, b.as.en.box->val);
        case W_LIST:
            if (a.as.list->len != b.as.list->len) return false;
            for (int32_t i = 0; i < a.as.list->len; i++) {
                if (!w_eq(a.as.list->data[i], b.as.list->data[i])) return false;
            }
            return true;
        case W_TUPLE:
            if (a.as.tuple->len != b.as.tuple->len) return false;
            for (int32_t i = 0; i < a.as.tuple->len; i++) {
                if (!w_eq(a.as.tuple->items[i], b.as.tuple->items[i])) return false;
            }
            return true;
        case W_DICT:
            if (a.as.dict->len != b.as.dict->len) return false;
            for (int32_t i = 0; i < a.as.dict->len; i++) {
                WVal k = a.as.dict->keys[i];
                WVal v = a.as.dict->vals[i];
                int32_t found = w_dict_find(b.as.dict, k);
                if (found < 0 || !w_eq(v, b.as.dict->vals[found])) return false;
            }
            return true;
        case W_STRUCT:
            if (strcmp(a.as.st->name, b.as.st->name) != 0 || a.as.st->len != b.as.st->len) return false;
            for (int32_t i = 0; i < a.as.st->len; i++) {
                if (!w_eq(a.as.st->vals[i], b.as.st->vals[i])) return false;
            }
            return true;
        case W_WEAK:
            return a.as.weak == b.as.weak;
        case W_OBJECT:
            return a.as.st == b.as.st;
        case W_OK:
        case W_ERR:
            return w_eq(a.as.box->val, b.as.box->val);
    }
    return false;
}

/* Containers: List, Dict, Tuple, Struct */
static inline WVal w_make_list(int32_t count, const WVal* elems) {
    WListBuf* b = (WListBuf*)w_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = count;
    b->cap = count > 4 ? count : 4;
    b->data = (WVal*)w_alloc_safe(sizeof(WVal) * b->cap);
    w_mem_on_alloc();
    for (int32_t i = 0; i < count; i++) {
        b->data[i] = w_clone(elems[i]);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal w_make_range(WVal start, WVal end, bool inclusive) {
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
    int32_t count = (int32_t)diff;
    WListBuf* b = (WListBuf*)w_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = count;
    b->cap = count > 4 ? count : 4;
    b->data = (WVal*)w_alloc_safe(sizeof(WVal) * b->cap);
    w_mem_on_alloc();
    for (int32_t i = 0; i < count; i++) {
        b->data[i] = w_int(s + (int64_t)i);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal w_make_tuple(int32_t count, const WVal* elems) {
    WTupleBuf* t = (WTupleBuf*)w_alloc_safe(sizeof(WTupleBuf));
    t->refcount = 1;
    t->len = count;
    t->items = (WVal*)w_alloc_safe(sizeof(WVal) * (count > 0 ? count : 1));
    w_mem_on_alloc();
    for (int32_t i = 0; i < count; i++) {
        t->items[i] = w_clone(elems[i]);
    }
    WVal v; v.tag = W_TUPLE; v.as.tuple = t; return v;
}

static inline WVal w_make_dict(int32_t count, const WVal* keys, const WVal* vals) {
    if (count < 0 || count > INT32_MAX / 4) { fprintf(stderr, "[W4003] RuntimeError: Dictionary too large\n"); exit(1); }
    WDictBuf* d = (WDictBuf*)w_alloc_safe(sizeof(WDictBuf));
    d->refcount = 1;
    d->len = 0;
    d->cap = count > 4 ? count * 2 : 4;
    d->keys = (WVal*)w_alloc_safe(sizeof(WVal) * d->cap);
    d->vals = (WVal*)w_alloc_safe(sizeof(WVal) * d->cap);
    d->buckets = NULL;
    int32_t buckets = 8;
    while (buckets < d->cap) {
        if (buckets > INT32_MAX / 2) { fprintf(stderr, "[W4003] RuntimeError: Dictionary too large\n"); exit(1); }
        buckets *= 2;
    }
    w_dict_reindex(d, buckets);
    w_mem_on_alloc();
    WVal v; v.tag = W_DICT; v.as.dict = d;
    for (int32_t i = 0; i < count; i++) {
        int32_t index = w_dict_find(d, keys[i]);
        if (index >= 0) { w_release(d->vals[index]); d->vals[index] = w_clone(vals[i]); }
        else {
            if ((int64_t)(d->len + 1) * 2 >= d->bucket_count) {
                if (d->bucket_count > INT32_MAX / 2) { fprintf(stderr, "[W4003] RuntimeError: Dictionary too large\n"); exit(1); }
                w_dict_reindex(d, d->bucket_count * 2);
            }
            index = d->len++;
            d->keys[index] = w_clone(keys[i]);
            d->vals[index] = w_clone(vals[i]);
            w_dict_index_entry(d, index);
        }
    }
    return v;
}

static inline WVal w_make_struct(const char* name, int32_t count, const char** keys, const WVal* vals) {
    WStructBuf* st = (WStructBuf*)w_alloc_safe(sizeof(WStructBuf));
    st->refcount = 1;
    st->control = NULL;
    st->vtable = NULL;
    st->name = name;
    st->len = count;
    st->keys = (const char**)w_alloc_safe(sizeof(const char*) * (count > 0 ? count : 1));
    st->vals = (WVal*)w_alloc_safe(sizeof(WVal) * (count > 0 ? count : 1));
    w_mem_on_alloc();
    for (int32_t i = 0; i < count; i++) {
        st->keys[i] = keys[i];
        st->vals[i] = w_clone(vals[i]);
    }
    WVal v; v.tag = W_STRUCT; v.as.st = st; return v;
}

static inline WVal w_make_object(const char* name, int32_t count, const char** keys, const WVal* vals) {
    WStructBuf* st = (WStructBuf*)w_alloc_safe(sizeof(WStructBuf));
    st->refcount = 1;
    st->control = (WWeakControl*)w_alloc_safe(sizeof(WWeakControl));
    st->control->strong = 1;
    st->control->weak = 1;
    st->control->object = st;
    w_mem_on_alloc();
    st->vtable = NULL;
    st->name = name;
    st->len = count;
    st->keys = (const char**)w_alloc_safe(sizeof(const char*) * (count > 0 ? count : 1));
    st->vals = (WVal*)w_alloc_safe(sizeof(WVal) * (count > 0 ? count : 1));
    w_mem_on_alloc();
    for (int32_t i = 0; i < count; i++) {
        st->keys[i] = keys[i];
        st->vals[i] = w_clone(vals[i]);
    }
    WVal v; v.tag = W_OBJECT; v.as.st = st; return v;
}

/* Default non-optional weak fields are independent expired handles. */
static inline WVal w_empty_weak(void) {
    WWeakControl* control = (WWeakControl*)w_alloc_safe(sizeof(WWeakControl));
    control->strong = 0;
    control->weak = 1;
    control->object = NULL;
    w_mem_on_alloc();
    WVal value = w_unit();
    value.tag = W_WEAK;
    value.as.weak = control;
    return value;
}

/* Both helpers borrow their input and return one owned reference. */
static inline WVal w_builtin_weak(WVal object) {
    if (object.tag != W_OBJECT) {
        fprintf(stderr, "[W4003] RuntimeError: weak expects a class object\n");
        exit(1);
    }
    WVal value = w_unit();
    value.tag = W_WEAK;
    value.as.weak = object.as.st->control;
    value.as.weak->weak++;
    w_g_retain_count++;
    return value;
}

/* Language weak calls consume their evaluated argument snapshot immediately. */
static inline WVal w_builtin_weak_owned(WVal object) {
    WVal handle = w_builtin_weak(object);
    w_release(object);
    return handle;
}

static inline WVal w_builtin_upgrade(WVal weak) {
    if (weak.tag != W_WEAK) {
        fprintf(stderr, "[W4003] RuntimeError: upgrade expects a weak reference\n");
        exit(1);
    }
    WWeakControl* control = weak.as.weak;
    if (control->strong == 0 || control->object == NULL) return w_none();
    WVal object = w_unit();
    object.tag = W_OBJECT;
    object.as.st = control->object;
    return w_clone(object);
}

/* UTF-8 Code-Point Helpers (SPEC Section 3.3) */
static inline size_t w_utf8_seq_len(unsigned char c) {
    if (c < 0x80) return 1;
    if ((c & 0xE0) == 0xC0) return 2;
    if ((c & 0xF0) == 0xE0) return 3;
    if ((c & 0xF8) == 0xF0) return 4;
    return 1;
}

static inline bool w_utf8_valid_codepoint_at_n(const char* s, size_t length, size_t pos, size_t* out_len, int64_t* out_cp) {
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

static inline int64_t w_utf8_cp_len_n(const char* s, size_t length) {
    int64_t count = 0;
    size_t pos = 0;
    while (pos < length) {
        size_t step = 0;
        if (w_utf8_valid_codepoint_at_n(s, length, pos, &step, NULL)) {
            pos += step;
        } else {
            pos++;
        }
        count++;
    }
    return count;
}

static inline bool w_utf8_cp_offset_n(const char* s, size_t length, int64_t target_cp, size_t* out_off, size_t* out_len) {
    if (target_cp < 0) return false;
    int64_t idx = 0;
    size_t pos = 0;
    while (pos < length) {
        size_t step = 0;
        size_t start = pos;
        if (w_utf8_valid_codepoint_at_n(s, length, pos, &step, NULL)) {
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

/* Lazily index shared owned strings once; repeated lexer indexing is O(1). */
static inline bool w_string_offset(WVal value, int64_t index, size_t* offset, size_t* length) {
    if (index < 0) return false;
    WStringBuf* owner = value.string_owner;
    if (!owner) return w_utf8_cp_offset_n(value.as.s, value.string_length, index, offset, length);
    if (!owner->codepoint_offsets) {
        if (value.string_length > SIZE_MAX / sizeof(size_t) - 1) {
            fprintf(stderr, "[W4003] RuntimeError: String index too large\n"); exit(1);
        }
        owner->codepoint_offsets = (size_t*)w_alloc_safe((value.string_length + 1) * sizeof(size_t));
        size_t position = 0, count = 0;
        while (position < value.string_length) {
            size_t step = 1;
            owner->codepoint_offsets[count++] = position;
            w_utf8_valid_codepoint_at_n(value.as.s, value.string_length, position, &step, NULL);
            position += step;
        }
        owner->codepoint_offsets[count] = value.string_length;
        owner->codepoint_count = count;
    }
    if ((uint64_t)index > owner->codepoint_count) return false;
    *offset = owner->codepoint_offsets[index];
    *length = (uint64_t)index < owner->codepoint_count ? owner->codepoint_offsets[index + 1] - *offset : 0;
    return *length != 0;
}

/* Indexing & Member Access */
static inline WVal w_index_get(WVal obj, WVal idx) {
    if (obj.tag == W_LIST) {
        int64_t i = idx.as.i;
        if (i < 0 || i >= obj.as.list->len) {
            fprintf(stderr, "[W4002] RuntimeError: List index out of bounds\n");
            exit(1);
        }
        return obj.as.list->data[i];
    }
    if (obj.tag == W_STR) {
        size_t off = 0, blen = 0;
        if (!w_string_offset(obj, idx.as.i, &off, &blen) || blen == 0) {
            fprintf(stderr, "[W4002] RuntimeError: String index out of bounds\n");
            exit(1);
        }
        char* buf = (char*)w_alloc_safe(blen + 1);
        memcpy(buf, obj.as.s + off, blen);
        buf[blen] = '\0';
        return w_owned_str_n(buf, blen);
    }
    if (obj.tag == W_DICT) {
        int32_t index = w_dict_find(obj.as.dict, idx);
        if (index < 0) {
            /* SPEC 10.2: a missing key is W4002. `d.get(k)` is the optional form. */
            fprintf(stderr, "[W4002] RuntimeError: Dictionary key not found\n");
            exit(1);
        }
        return obj.as.dict->vals[index];
    }
    fprintf(stderr, "[W4003] RuntimeError: Cannot index object of tag %d\n", obj.tag);
    exit(1);
}

static inline WVal w_index_get_owned(WVal object, WVal index) {
    WVal value = w_index_get(object, index);
    return object.tag == W_STR ? value : w_clone(value);
}

static inline WVal* w_index_ref(WVal* obj, WVal idx) {
    if (obj->tag == W_LIST) {
        w_list_detach(obj);
        int64_t i = idx.as.i;
        if (i < 0 || i >= obj->as.list->len) {
            fprintf(stderr, "[W4002] RuntimeError: List index out of bounds\n");
            exit(1);
        }
        return &obj->as.list->data[i];
    }
    if (obj->tag == W_DICT) {
        w_dict_detach(obj);
        WDictBuf* d = obj->as.dict;
        int32_t found = w_dict_find(d, idx);
        if (found >= 0) return &d->vals[found];
        if (d->cap > INT32_MAX / 2 || d->bucket_count > INT32_MAX / 2) {
            fprintf(stderr, "[W4003] RuntimeError: Dictionary too large\n"); exit(1);
        }
        if ((int64_t)(d->len + 1) * 2 >= d->bucket_count) w_dict_reindex(d, d->bucket_count * 2);
        if (d->len >= d->cap) {
            d->cap = d->cap > 0 ? d->cap * 2 : 4;
            d->keys = (WVal*)w_realloc_safe(d->keys, sizeof(WVal) * d->cap);
            d->vals = (WVal*)w_realloc_safe(d->vals, sizeof(WVal) * d->cap);
        }
        d->keys[d->len] = w_clone(idx);
        d->vals[d->len] = w_none();
        d->len++;
        w_dict_index_entry(d, d->len - 1);
        return &d->vals[d->len - 1];
    }
    fprintf(stderr, "[W4003] RuntimeError: Cannot index-assign non-collection\n");
    exit(1);
}

static inline WVal w_member_get(WVal obj, const char* prop) {
    if (obj.tag == W_STRUCT || obj.tag == W_OBJECT) {
        for (int32_t i = 0; i < obj.as.st->len; i++) {
            if (strcmp(obj.as.st->keys[i], prop) == 0) {
                return obj.as.st->vals[i];
            }
        }
    }
    return w_none();
}

static inline WVal* w_member_ref(WVal* obj, const char* prop) {
    if (obj->tag == W_STRUCT) {
        w_struct_detach(obj);
        for (int32_t i = 0; i < obj->as.st->len; i++) {
            if (strcmp(obj->as.st->keys[i], prop) == 0) {
                return &obj->as.st->vals[i];
            }
        }
    } else if (obj->tag == W_OBJECT) {
        for (int32_t i = 0; i < obj->as.st->len; i++) {
            if (strcmp(obj->as.st->keys[i], prop) == 0) {
                return &obj->as.st->vals[i];
            }
        }
    }
    fprintf(stderr, "[W4003] RuntimeError: Invalid field '%s'\n", prop);
    exit(1);
}

/* Methods on List / Dict */
static inline WVal w_list_append(WVal* list_val, WVal item) {
    w_list_detach(list_val);
    WListBuf* b = list_val->as.list;
    if (b->len >= b->cap) {
        b->cap = b->cap > 0 ? b->cap * 2 : 4;
        b->data = (WVal*)w_realloc_safe(b->data, sizeof(WVal) * b->cap);
    }
    b->data[b->len++] = w_clone(item);
    return w_unit();
}

static inline WVal w_list_pop(WVal* list_val) {
    w_list_detach(list_val);
    WListBuf* b = list_val->as.list;
    if (b->len == 0) {
        fprintf(stderr, "[W4002] RuntimeError: pop from empty list\n");
        exit(1);
    }
    return b->data[--b->len];
}

static inline WVal w_list_clear(WVal* list_val) {
    w_list_detach(list_val);
    WListBuf* b = list_val->as.list;
    for (int32_t i = 0; i < b->len; i++) {
        w_release(b->data[i]);
    }
    b->len = 0;
    return w_unit();
}

static inline WVal w_dict_get(WVal dict_val, WVal key) {
    /* The optional lookup: unlike `d[k]`, an absent key is `none`, not W4002. */
    if (dict_val.tag != W_DICT) return w_none();
    int32_t found = w_dict_find(dict_val.as.dict, key);
    if (found < 0) return w_none();
    return w_enum_payload("Option", "Some", w_clone(dict_val.as.dict->vals[found]));
}

static inline WVal w_dict_keys(WVal dict_val) {
    WDictBuf* d = dict_val.as.dict;
    return w_make_list(d->len, d->keys);
}

static inline WVal w_dict_values(WVal dict_val) {
    WDictBuf* d = dict_val.as.dict;
    return w_make_list(d->len, d->vals);
}

/* Binary Operations */
static inline WVal w_add(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return w_int((int64_t)((uint64_t)a.as.i + (uint64_t)b.as.i));
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return w_float(a.as.f + b.as.f);
    if (a.tag == W_STR && b.tag == W_STR) {
        size_t la = a.string_length;
        size_t lb = b.string_length;
        char* res = (char*)w_alloc_safe(la + lb + 1);
        memcpy(res, a.as.s, la);
        memcpy(res + la, b.as.s, lb);
        res[la + lb] = '\0';
        return w_owned_str_n(res, la + lb);
    }
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for addition (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal w_sub(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return w_int((int64_t)((uint64_t)a.as.i - (uint64_t)b.as.i));
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return w_float(a.as.f - b.as.f);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for subtraction (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal w_mul(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return w_int((int64_t)((uint64_t)a.as.i * (uint64_t)b.as.i));
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return w_float(a.as.f * b.as.f);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for multiplication (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal w_div(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) {
        if (b.as.i == 0) { fprintf(stderr, "[W4001] RuntimeError: Division by zero\n"); exit(1); }
        if (a.as.i == INT64_MIN && b.as.i == -1) return w_int(INT64_MIN);
        return w_int(a.as.i / b.as.i);
    }
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) {
        if (b.as.f == 0.0) { fprintf(stderr, "[W4001] RuntimeError: Division by zero\n"); exit(1); }
        return w_float(a.as.f / b.as.f);
    }
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for division (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal w_mod(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) {
        if (b.as.i == 0) { fprintf(stderr, "[W4001] RuntimeError: Modulo by zero\n"); exit(1); }
        if (a.as.i == INT64_MIN && b.as.i == -1) return w_int(0);
        return w_int(a.as.i % b.as.i);
    }
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for modulo (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal w_neg(WVal a) {
    if (a.tag == W_INT) return w_int((int64_t)(0ULL - (uint64_t)a.as.i));
    if (a.tag == W_FLOAT) return w_float(-a.as.f);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand type for negation (tag %d)\n", a.tag);
    exit(1);
}

static inline WVal w_lt(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return w_bool(a.as.i < b.as.i);
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return w_bool(a.as.f < b.as.f);
    if (a.tag == W_STR && b.tag == W_STR) return w_bool(strcmp(a.as.s, b.as.s) < 0);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for comparison (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal w_le(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return w_bool(a.as.i <= b.as.i);
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return w_bool(a.as.f <= b.as.f);
    if (a.tag == W_STR && b.tag == W_STR) return w_bool(strcmp(a.as.s, b.as.s) <= 0);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for comparison (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal w_gt(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return w_bool(a.as.i > b.as.i);
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return w_bool(a.as.f > b.as.f);
    if (a.tag == W_STR && b.tag == W_STR) return w_bool(strcmp(a.as.s, b.as.s) > 0);
    fprintf(stderr, "[W4003] RuntimeError: Invalid operand types for comparison (tags %d, %d)\n", a.tag, b.tag);
    exit(1);
}

static inline WVal w_ge(WVal a, WVal b) {
    if (a.tag == W_INT && b.tag == W_INT) return w_bool(a.as.i >= b.as.i);
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return w_bool(a.as.f >= b.as.f);
    if (a.tag == W_STR && b.tag == W_STR) return w_bool(strcmp(a.as.s, b.as.s) >= 0);
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
static inline char* w_format_float(double value) {
    char* buf = (char*)w_alloc_safe(40);
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

/* Formatting & String Conversion (matching W0 Values.__str__ exactly) */
/* Internal module identity is retained for equality/dispatch, not display. */
static inline const char* w_nominal_display_name(const char* name) {
    if (strncmp(name, "__wm_", 5) == 0) {
        const char* boundary = strstr(name + 5, "__");
        if (boundary) return boundary + 2;
    }
    return name;
}

static inline char* w_to_cstr(WVal v, bool quote_str) {
    char* buf;
    switch (v.tag) {
        case W_POINTER:
            buf = (char*)w_alloc_safe(9); memcpy(buf, "<opaque>", 9); return buf;
        case W_FUNCTION:
            buf = (char*)w_alloc_safe(11); memcpy(buf, "<function>", 11); return buf;
        case W_WEAK: {
            const char* text = v.as.weak->object ? "weak(alive)" : "weak(expired)";
            char* result = (char*)w_alloc_safe(strlen(text) + 1);
            strcpy(result, text);
            return result;
        }

        case W_UNIT:
            buf = (char*)w_alloc_safe(5);
            strcpy(buf, "unit");
            return buf;
        case W_NONE:
            buf = (char*)w_alloc_safe(5);
            strcpy(buf, "none");
            return buf;
        case W_INT:
            buf = (char*)w_alloc_safe(32);
            snprintf(buf, 32, "%" PRId64, v.as.i);
            return buf;
        case W_FLOAT:
            return w_format_float(v.as.f);
        case W_BOOL:
            buf = (char*)w_alloc_safe(6);
            strcpy(buf, v.as.b ? "true" : "false");
            return buf;
        case W_STR: {
            size_t len = v.string_length;
            if (!quote_str) {
                buf = (char*)w_alloc_safe(len + 1);
                memcpy(buf, v.as.s, len);
                buf[len] = 0;
                return buf;
            }
            buf = (char*)w_alloc_safe(len * 2 + 3);
            size_t written = 0;
            buf[written++] = '"';
            for (size_t i = 0; i < len; i++) {
                if (v.as.s[i] == 0) { buf[written++] = '\\'; buf[written++] = '0'; }
                else buf[written++] = v.as.s[i];
            }
            buf[written++] = '"';
            buf[written] = 0;
            return buf;
        }
        case W_ENUM: {
            if (strcmp(v.as.en.enum_name, "Option") == 0 && strcmp(v.as.en.variant, "Some") == 0 && v.as.en.box)
                return w_to_cstr(v.as.en.box->val, quote_str);
            if (v.as.en.box) {
                if (v.as.en.box->val.tag == W_TUPLE) {
                    size_t cap = 64;
                    size_t pos = 0;
                    buf = (char*)w_alloc_safe(cap);
                    size_t l1 = strlen(w_nominal_display_name(v.as.en.enum_name));
                    size_t l2 = strlen(v.as.en.variant);
                    while (pos + l1 + l2 + 2 >= cap) { cap *= 2; buf = (char*)w_realloc_safe(buf, cap); }
                    memcpy(buf + pos, w_nominal_display_name(v.as.en.enum_name), l1); pos += l1;
                    buf[pos++] = '.';
                    memcpy(buf + pos, v.as.en.variant, l2); pos += l2;
                    buf[pos++] = '(';
                    for (int32_t i = 0; i < v.as.en.box->val.as.tuple->len; i++) {
                        if (i > 0) {
                            if (pos + 3 >= cap) { cap *= 2; buf = (char*)w_realloc_safe(buf, cap); }
                            buf[pos++] = ','; buf[pos++] = ' ';
                        }
                        char* sub = w_to_cstr(v.as.en.box->val.as.tuple->items[i], true);
                        size_t lsub = strlen(sub);
                        while (pos + lsub + 3 >= cap) { cap *= 2; buf = (char*)w_realloc_safe(buf, cap); }
                        memcpy(buf + pos, sub, lsub); pos += lsub;
                        free(sub);
                    }
                    buf[pos++] = ')';
                    buf[pos] = '\0';
                    return buf;
                } else {
                    char* sub = w_to_cstr(v.as.en.box->val, true);
                    size_t l1 = strlen(w_nominal_display_name(v.as.en.enum_name));
                    size_t l2 = strlen(v.as.en.variant);
                    size_t lsub = strlen(sub);
                    buf = (char*)w_alloc_safe(l1 + l2 + lsub + 4);
                    snprintf(buf, l1 + l2 + lsub + 4, "%s.%s(%s)", w_nominal_display_name(v.as.en.enum_name), v.as.en.variant, sub);
                    free(sub);
                    return buf;
                }
            }
            size_t l1 = strlen(w_nominal_display_name(v.as.en.enum_name));
            size_t l2 = strlen(v.as.en.variant);
            buf = (char*)w_alloc_safe(l1 + l2 + 2);
            snprintf(buf, l1 + l2 + 2, "%s.%s", w_nominal_display_name(v.as.en.enum_name), v.as.en.variant);
            return buf;
        }
        case W_LIST: {
            size_t cap = 64;
            size_t pos = 0;
            buf = (char*)w_alloc_safe(cap);
            buf[pos++] = '[';
            for (int32_t i = 0; i < v.as.list->len; i++) {
                if (i > 0) {
                    if (pos + 3 >= cap) { cap *= 2; buf = (char*)w_realloc_safe(buf, cap); }
                    buf[pos++] = ','; buf[pos++] = ' ';
                }
                char* sub = w_to_cstr(v.as.list->data[i], true);
                size_t sl = strlen(sub);
                while (pos + sl + 4 >= cap) { cap *= 2; buf = (char*)w_realloc_safe(buf, cap); }
                memcpy(buf + pos, sub, sl);
                pos += sl;
                free(sub);
            }
            buf[pos++] = ']';
            buf[pos] = '\0';
            return buf;
        }
        case W_TUPLE: {
            size_t cap = 64;
            size_t pos = 0;
            buf = (char*)w_alloc_safe(cap);
            buf[pos++] = '(';
            for (int32_t i = 0; i < v.as.tuple->len; i++) {
                if (i > 0) {
                    if (pos + 3 >= cap) { cap *= 2; buf = (char*)w_realloc_safe(buf, cap); }
                    buf[pos++] = ','; buf[pos++] = ' ';
                }
                char* sub = w_to_cstr(v.as.tuple->items[i], true);
                size_t sl = strlen(sub);
                while (pos + sl + 4 >= cap) { cap *= 2; buf = (char*)w_realloc_safe(buf, cap); }
                memcpy(buf + pos, sub, sl);
                pos += sl;
                free(sub);
            }
            buf[pos++] = ')';
            buf[pos] = '\0';
            return buf;
        }
        case W_DICT: {
            size_t cap = 64;
            size_t pos = 0;
            buf = (char*)w_alloc_safe(cap);
            buf[pos++] = '{';
            for (int32_t i = 0; i < v.as.dict->len; i++) {
                if (i > 0) {
                    if (pos + 3 >= cap) { cap *= 2; buf = (char*)w_realloc_safe(buf, cap); }
                    buf[pos++] = ','; buf[pos++] = ' ';
                }
                char* ks = w_to_cstr(v.as.dict->keys[i], true);
                char* vs = w_to_cstr(v.as.dict->vals[i], true);
                size_t kl = strlen(ks), vl = strlen(vs);
                while (pos + kl + vl + 6 >= cap) { cap *= 2; buf = (char*)w_realloc_safe(buf, cap); }
                memcpy(buf + pos, ks, kl); pos += kl;
                buf[pos++] = ':'; buf[pos++] = ' ';
                memcpy(buf + pos, vs, vl); pos += vl;
                free(ks); free(vs);
            }
            buf[pos++] = '}';
            buf[pos] = '\0';
            return buf;
        }
        case W_STRUCT:
        case W_OBJECT: {
            size_t cap = 128;
            size_t pos = 0;
            buf = (char*)w_alloc_safe(cap);
            size_t nl = strlen(w_nominal_display_name(v.as.st->name));
            memcpy(buf + pos, w_nominal_display_name(v.as.st->name), nl); pos += nl;
            buf[pos++] = ' '; buf[pos++] = '{'; buf[pos++] = ' ';
            for (int32_t i = 0; i < v.as.st->len; i++) {
                if (i > 0) {
                    if (pos + 3 >= cap) { cap *= 2; buf = (char*)w_realloc_safe(buf, cap); }
                    buf[pos++] = ','; buf[pos++] = ' ';
                }
                const char* fn = v.as.st->keys[i];
                char* vs = w_to_cstr(v.as.st->vals[i], true);
                size_t fl = strlen(fn), vl = strlen(vs);
                while (pos + fl + vl + 8 >= cap) { cap *= 2; buf = (char*)w_realloc_safe(buf, cap); }
                memcpy(buf + pos, fn, fl); pos += fl;
                buf[pos++] = ':'; buf[pos++] = ' ';
                memcpy(buf + pos, vs, vl); pos += vl;
                free(vs);
            }
            buf[pos++] = ' '; buf[pos++] = '}';
            buf[pos] = '\0';
            return buf;
        }
        case W_OK: {
            char* inner = w_to_cstr(v.as.box->val, false);
            size_t il = strlen(inner);
            buf = (char*)w_alloc_safe(il + 5);
            snprintf(buf, il + 5, "Ok(%s)", inner);
            free(inner);
            return buf;
        }
        case W_ERR: {
            char* inner = w_to_cstr(v.as.box->val, false);
            size_t il = strlen(inner);
            buf = (char*)w_alloc_safe(il + 6);
            snprintf(buf, il + 6, "Err(%s)", inner);
            free(inner);
            return buf;
        }
    }
    buf = (char*)w_alloc_safe(1);
    buf[0] = '\0';
    return buf;
}

/* Standard Built-ins */
static inline WVal w_builtin_print(int32_t argc, const WVal* argv) {
    for (int32_t i = 0; i < argc; i++) {
        if (i > 0) fputc(' ', stdout);
        WVal value = argv[i];
        while (value.tag == W_ENUM && strcmp(value.as.en.enum_name, "Option") == 0 &&
               strcmp(value.as.en.variant, "Some") == 0 && value.as.en.box) value = value.as.en.box->val;
        if (value.tag == W_STR) fwrite(value.as.s, 1, value.string_length, stdout);
        else { char* s = w_to_cstr(value, false); fputs(s, stdout); free(s); }
    }
    fputc('\n', stdout);
    fflush(stdout);
    return w_unit();
}

static inline WVal w_builtin_eprint(int32_t argc, const WVal* argv) {
    for (int32_t i = 0; i < argc; i++) {
        if (i > 0) fputc(' ', stderr);
        char* s = w_to_cstr(argv[i], false);
        const char* metrics = getenv("W_COW_METRICS");
        if (metrics && strcmp(metrics, "1") == 0 && argc == 1 && argv[i].tag == W_STR &&
            strncmp(s, "__COW_CHECKPOINT__:", 19) == 0) {
            const char* label = s + 19;
            fprintf(stderr, "[W_COW_CHECKPOINT:%s] detach_list=%" PRId64 " detach_dict=%" PRId64 " detach_struct=%" PRId64 " copied_slots=%" PRId64 " copied_bytes=%" PRId64 " allocated_bytes=%" PRId64 " allocs=%" PRId64,
                    label, w_g_cow_detach_list, w_g_cow_detach_dict, w_g_cow_detach_struct, w_g_cow_copied_slots, w_g_cow_copied_bytes, w_g_cow_allocated_bytes, w_g_cow_alloc_count);
        } else {
            if (argv[i].tag == W_STR) fwrite(argv[i].as.s, 1, argv[i].string_length, stderr);
            else fputs(s, stderr);
        }
        free(s);
    }
    fputc('\n', stderr);
    fflush(stderr);
    return w_unit();
}

static inline WVal w_builtin_exit(WVal code) {
    int c = (code.tag == W_INT) ? (int)code.as.i : 0;
    w_runtime_cleanup();
    exit(c);
    return w_unit();
}

static inline WVal w_builtin_len(WVal v) {
    if (v.tag == W_LIST) return w_int(v.as.list->len);
    if (v.tag == W_DICT) return w_int(v.as.dict->len);
    if (v.tag == W_STR) return w_int(w_utf8_cp_len_n(v.as.s, v.string_length));
    return w_int(0);
}

static inline WVal w_builtin_str(WVal v) {
    if (v.tag == W_STR) return w_clone(v);
    return w_owned_str(w_to_cstr(v, false));
}

static inline void w_conversion_error(const char* kind) {
    fprintf(stderr, "[W4003] RuntimeError: Invalid %s conversion\n", kind);
    exit(1);
}

static inline const char* w_conversion_end(const char* end) {
    while (*end && isspace((unsigned char)*end)) end++;
    return end;
}

static inline WVal w_builtin_int(WVal v) {
    if (v.tag == W_INT) return v;
    if (v.tag == W_FLOAT) {
        if (!isfinite(v.as.f) || v.as.f < -9223372036854775808.0 || v.as.f >= 9223372036854775808.0)
            w_conversion_error("int");
        return w_int((int64_t)v.as.f);
    }
    if (v.tag == W_STR && !memchr(v.as.s, 0, v.string_length)) {
        char* end; errno = 0;
        int64_t value = strtoll(v.as.s, &end, 10);
        if (errno != ERANGE && end != v.as.s && *w_conversion_end(end) == 0) return w_int(value);
    }
    w_conversion_error("int");
    return w_unit();
}

static inline WVal w_builtin_float(WVal v) {
    if (v.tag == W_FLOAT) return v;
    if (v.tag == W_INT) return w_float((double)v.as.i);
    if (v.tag == W_STR && !memchr(v.as.s, 0, v.string_length)) {
        char* end;
        double value = strtod(v.as.s, &end);
        if (end != v.as.s && *w_conversion_end(end) == 0 && !strstr(v.as.s, "0x") && !strstr(v.as.s, "0X"))
            return w_float(value);
    }
    w_conversion_error("float");
    return w_unit();
}

static inline WVal w_builtin_ord(WVal v) {
    if (v.tag != W_STR || v.string_length == 0) {
        fprintf(stderr, "[W4003] RuntimeError: ord() expects non-empty str\n");
        exit(1);
    }
    size_t slen = 0;
    int64_t cp = 0;
    if (!w_utf8_valid_codepoint_at_n(v.as.s, v.string_length, 0, &slen, &cp)) {
        fprintf(stderr, "[W4003] RuntimeError: ord() invalid UTF-8 sequence\n");
        exit(1);
    }
    return w_int(cp);
}

static inline WVal w_builtin_chr(WVal v) {
    if (v.tag != W_INT) {
        fprintf(stderr, "[W4003] RuntimeError: chr() expects int\n");
        exit(1);
    }
    int64_t cp = v.as.i;
    if (cp < 0 || cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) {
        fprintf(stderr, "[W4003] RuntimeError: chr() arg not in valid Unicode scalar range: %" PRId64 "\n", cp);
        exit(1);
    }
    char* buf = (char*)w_alloc_safe(5);
    if (cp < 0x80) {
        buf[0] = (char)cp;
        buf[1] = '\0';
    } else if (cp < 0x800) {
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
    return w_owned_str_n(buf, cp < 0x80 ? 1 : cp < 0x800 ? 2 : cp < 0x10000 ? 3 : 4);
}

static inline WVal w_builtin_slice(WVal s, WVal start, WVal end) {
    if (s.tag == W_LIST) {
        /* SPEC 11.1: slice() is polymorphic over str and list[T]. */
        WListBuf* b = s.as.list;
        int64_t st = start.as.i < 0 ? 0 : start.as.i;
        int64_t en = end.as.i > b->len ? b->len : end.as.i;
        if (en <= st) return w_make_list(0, NULL);
        return w_make_list((int32_t)(en - st), b->data + st);
    }
    if (s.tag != W_STR) {
        fprintf(stderr, "[W4003] RuntimeError: slice() expects str or list\n");
        exit(1);
    }
    int64_t total_cp = w_utf8_cp_len_n(s.as.s, s.string_length);
    int64_t st = start.as.i < 0 ? 0 : start.as.i;
    int64_t en = end.as.i > total_cp ? total_cp : end.as.i;
    if (en <= st || st >= total_cp) return w_str("");
    size_t st_off = 0, dummy_len = 0, en_off = 0;
    w_string_offset(s, st, &st_off, &dummy_len);
    if (en == total_cp) {
        en_off = s.string_length;
    } else {
        w_string_offset(s, en, &en_off, &dummy_len);
    }
    size_t blen = en_off - st_off;
    char* buf = (char*)w_alloc_safe(blen + 1);
    memcpy(buf, s.as.s + st_off, blen);
    buf[blen] = '\0';
    return w_owned_str_n(buf, blen);
}

static inline WVal w_builtin_bytes(WVal s) {
    if (s.tag != W_STR) {
        fprintf(stderr, "[W4003] RuntimeError: bytes() expects str\n");
        exit(1);
    }
    size_t slen = s.string_length;
    WListBuf* b = (WListBuf*)w_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = (int32_t)slen;
    b->cap = slen > 4 ? (int32_t)slen : 4;
    b->data = (WVal*)w_alloc_safe(sizeof(WVal) * b->cap);
    w_mem_on_alloc();
    for (size_t i = 0; i < slen; i++) {
        b->data[i] = w_int((int64_t)(unsigned char)s.as.s[i]);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal w_builtin_enumerate(WVal list_val) {
    if (list_val.tag != W_LIST) {
        fprintf(stderr, "[W4003] RuntimeError: enumerate() expects list\n");
        exit(1);
    }
    WListBuf* src = list_val.as.list;
    WListBuf* b = (WListBuf*)w_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = src->len;
    b->cap = src->len > 4 ? src->len : 4;
    b->data = (WVal*)w_alloc_safe(sizeof(WVal) * b->cap);
    w_mem_on_alloc();
    for (int32_t i = 0; i < src->len; i++) {
        WVal pair[2] = { w_int(i), src->data[i] };
        b->data[i] = w_make_tuple(2, pair);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal w_builtin_dict_items(WVal dict_val) {
    if (dict_val.tag != W_DICT) {
        fprintf(stderr, "[W4003] RuntimeError: dict_items() expects dict\n");
        exit(1);
    }
    WDictBuf* d = dict_val.as.dict;
    WListBuf* b = (WListBuf*)w_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = d->len;
    b->cap = d->len > 4 ? d->len : 4;
    b->data = (WVal*)w_alloc_safe(sizeof(WVal) * b->cap);
    w_mem_on_alloc();
    for (int32_t i = 0; i < d->len; i++) {
        WVal pair[2] = { d->keys[i], d->vals[i] };
        b->data[i] = w_make_tuple(2, pair);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal w_io_error(const char* message) {
    const char* keys[1] = { "message" };
    WVal values[1] = { w_str(message) };
    return w_err(w_make_struct("IoError", 1, keys, values));
}

static inline WVal w_builtin_read_file(WVal path) {
    if (path.tag != W_STR || memchr(path.as.s, 0, path.string_length)) return w_io_error("Invalid path");
    FILE* file = fopen(path.as.s, "rb");
    if (!file) return w_io_error("Failed to open file");
    size_t length = 0, capacity = 4096;
    char* data = (char*)w_alloc_safe(capacity + 1);
    while (1) {
        size_t count = fread(data + length, 1, capacity - length, file);
        length += count;
        if (ferror(file)) { fclose(file); free(data); return w_io_error("Failed to read file"); }
        if (feof(file)) break;
        if (length == capacity) {
            if (capacity > SIZE_MAX / 2 - 1) { fclose(file); free(data); return w_io_error("File too large"); }
            capacity *= 2;
            data = (char*)w_realloc_safe(data, capacity + 1);
        }
    }
    if (fclose(file) != 0) { free(data); return w_io_error("Failed to close file"); }
    data[length] = 0;
    size_t offset = 0;
    while (offset < length) {
        size_t step;
        if (!w_utf8_valid_codepoint_at_n(data, length, offset, &step, NULL)) {
            free(data); return w_io_error("Invalid UTF-8 file");
        }
        offset += step;
    }
    return w_ok(w_owned_str_n(data, length));
}

static inline WVal w_builtin_write_file(WVal path, WVal content) {
    if (path.tag != W_STR || content.tag != W_STR || memchr(path.as.s, 0, path.string_length))
        return w_io_error("Invalid arguments");
    FILE* file = fopen(path.as.s, "wb");
    if (!file) return w_io_error("Failed to write file");
    size_t written = fwrite(content.as.s, 1, content.string_length, file);
    bool failed = written != content.string_length || ferror(file);
    if (fclose(file) != 0) failed = true;
    return failed ? w_io_error("Failed to write file") : w_ok(w_unit());
}

static int w_g_argc = 0;
static char** w_g_argv = NULL;

/*
 * Propagates an unhandled `Err` out of the program entrypoint.
 *
 * W has no stack unwinding, so a fallible `main` returns its error as a value.
 * Discarding that value would make a failed program indistinguishable from a
 * successful one (exit code 0, no output) to make/CI/shell. The entrypoint
 * therefore reports the error on stderr and signals failure to the caller,
 * which terminates with a non-zero status.
 *
 * Error structs that expose a `message: str` field print that field; anything
 * else prints through the ordinary value formatter.
 */
static inline void w_report_entrypoint_error(WVal error) {
    const char* message = NULL;
    if (error.tag == W_STRUCT && strcmp(error.as.st->name, "IoError") == 0) {
        for (int32_t i = 0; i < error.as.st->len; i++) {
            if (strcmp(error.as.st->keys[i], "message") == 0 && error.as.st->vals[i].tag == W_STR) {
                message = error.as.st->vals[i].as.s;
                break;
            }
        }
    }
    if (message) {
        fprintf(stderr, "[W4003] RuntimeError: %s\n", message);
        return;
    }
    char* rendered = w_to_cstr(error, false);
    fprintf(stderr, "[W4003] RuntimeError: unhandled error returned by main: %s\n", rendered);
    free(rendered);
}

static inline void w_init_args(int argc, char** argv) {
    w_g_argc = argc;
    w_g_argv = argv;
}

static inline WVal w_builtin_args(void) {
    WListBuf* b = (WListBuf*)w_alloc_safe(sizeof(WListBuf));
    b->refcount = 1;
    b->len = (int32_t)w_g_argc;
    b->cap = w_g_argc > 4 ? (int32_t)w_g_argc : 4;
    b->data = (WVal*)w_alloc_safe(sizeof(WVal) * b->cap);
    w_mem_on_alloc();
    for (int i = 0; i < w_g_argc; i++) {
        b->data[i] = w_copy_str(w_g_argv[i]);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

#endif /* W_RUNTIME_H */
