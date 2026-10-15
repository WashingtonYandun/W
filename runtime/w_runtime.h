#ifndef W_RUNTIME_H
#define W_RUNTIME_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <inttypes.h>

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
    W_WEAK
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
} WDictBuf;

typedef struct {
    int32_t refcount;
    int32_t len;
    WVal* items;
} WTupleBuf;

typedef struct WWeakControl WWeakControl;

typedef struct {
    int32_t refcount;
    WWeakControl* control;
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

typedef struct {
    const char* enum_name;
    const char* variant;
    WBoxBuf* box;
} WEnumVal;

typedef struct {
    int32_t refcount;
    size_t byte_length;
    char* data;
} WStringBuf;

struct WVal {
    WStringBuf* string_owner;
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
    } as;
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

static inline WVal w_float(double x) {
    WVal v; v.tag = W_FLOAT; v.as.f = x; return v;
}

static inline WVal w_bool(bool x) {
    WVal v; v.tag = W_BOOL; v.as.b = x; return v;
}

static inline WVal w_str(const char* s) {
    WVal v; v.tag = W_STR; v.string_owner = NULL; v.as.s = s ? s : ""; return v;
}

/* Takes ownership of a heap buffer; w_str is for static storage only. */
static inline WVal w_owned_str(char* data) {
    WStringBuf* buffer = (WStringBuf*)w_alloc_safe(sizeof(WStringBuf));
    buffer->refcount = 1;
    buffer->byte_length = strlen(data);
    buffer->data = data;
    w_mem_on_alloc();
    WVal value = w_str(data);
    value.string_owner = buffer;
    return value;
}

static inline WVal w_copy_str(const char* data) {
    size_t length = strlen(data);
    char* copy = (char*)w_alloc_safe(length + 1);
    memcpy(copy, data, length + 1);
    return w_owned_str(copy);
}

static inline WVal w_ok(WVal inner);
static inline WVal w_err(WVal inner);

static inline bool w_builtin_name(const char* name, const char* base) {
    size_t length = strlen(base);
    return strcmp(name, base) == 0 || (strncmp(name, base, length) == 0 &&
        name[length] == '_' && name[length + 1] == '_');
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
    if (v.tag == W_STR && v.string_owner) {
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

static inline void w_release(WVal v) {
    if (v.tag == W_STR && v.string_owner) {
        WStringBuf* buffer = v.string_owner;
        w_check_refcount(buffer->refcount, "release/string");
        w_g_release_count++;
        if (--buffer->refcount == 0) {
            free(buffer->data);
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
            for (int32_t i = 0; i < b->len; i++) {
                w_release(b->data[i]);
            }
            free(b->data);
            free(b);
            w_mem_on_free();
        }
    } else if (v.tag == W_DICT && v.as.dict) {
        WDictBuf* d = v.as.dict;
        w_check_refcount(d->refcount, "release/dict");
        w_g_release_count++;
        d->refcount--;
        if (d->refcount == 0) {
            d->refcount = -1;
            for (int32_t i = 0; i < d->len; i++) {
                w_release(d->keys[i]);
                w_release(d->vals[i]);
            }
            free(d->keys);
            free(d->vals);
            free(d);
            w_mem_on_free();
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
            for (int32_t i = 0; i < object->len; i++) w_release(object->vals[i]);
            free(object->keys);
            free(object->vals);
            free(object);
            w_mem_on_free();
            if (--control->weak == 0) {
                free(control);
                w_mem_on_free();
            }
        }
    } else if (v.tag == W_STRUCT && v.as.st) {
        WStructBuf* st = v.as.st;
        w_check_refcount(st->refcount, "release/struct_or_object");
        w_g_release_count++;
        st->refcount--;
        if (st->refcount == 0) {
            st->refcount = -1;
            for (int32_t i = 0; i < st->len; i++) {
                w_release(st->vals[i]);
            }
            free(st->keys);
            free(st->vals);
            free(st);
            w_mem_on_free();
        }
    } else if (v.tag == W_TUPLE && v.as.tuple) {
        WTupleBuf* t = v.as.tuple;
        w_check_refcount(t->refcount, "release/tuple");
        w_g_release_count++;
        t->refcount--;
        if (t->refcount == 0) {
            t->refcount = -1;
            for (int32_t i = 0; i < t->len; i++) {
                w_release(t->items[i]);
            }
            free(t->items);
            free(t);
            w_mem_on_free();
        }
    } else if ((v.tag == W_OK || v.tag == W_ERR) && v.as.box) {
        WBoxBuf* bx = v.as.box;
        w_check_refcount(bx->refcount, "release/box");
        w_g_release_count++;
        bx->refcount--;
        if (bx->refcount == 0) {
            bx->refcount = -1;
            w_release(bx->val);
            free(bx);
            w_mem_on_free();
        }
    } else if (v.tag == W_ENUM && v.as.en.box) {
        WBoxBuf* bx = v.as.en.box;
        w_check_refcount(bx->refcount, "release/enum_box");
        w_g_release_count++;
        bx->refcount--;
        if (bx->refcount == 0) {
            bx->refcount = -1;
            w_release(bx->val);
            free(bx);
            w_mem_on_free();
        }
    }
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
    w_mem_on_alloc();

    /* B02: CoW detach telemetry */
    w_g_cow_detach_dict++;
    w_g_cow_copied_slots += ((int64_t)old_b->len * 2);
    w_g_cow_copied_bytes += (int64_t)(sizeof(WVal) * old_b->len * 2);
    w_g_cow_allocated_bytes += (int64_t)(sizeof(WDictBuf) + (sizeof(WVal) * new_b->cap * 2));
    w_g_cow_alloc_count += 3;

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
            return strcmp(a.as.s, b.as.s) == 0;
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
                bool found = false;
                for (int32_t j = 0; j < b.as.dict->len; j++) {
                    if (w_eq(k, b.as.dict->keys[j])) {
                        found = w_eq(v, b.as.dict->vals[j]);
                        break;
                    }
                }
                if (!found) return false;
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
    int64_t diff = (e > s) ? (e - s) : 0;
    if (diff > 100000000LL) {
        fprintf(stderr, "[W4003] RuntimeError: Range length %" PRId64 " exceeds maximum list capacity\n", diff);
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
    WDictBuf* d = (WDictBuf*)w_alloc_safe(sizeof(WDictBuf));
    d->refcount = 1;
    d->len = 0;
    d->cap = count > 4 ? count * 2 : 4;
    d->keys = (WVal*)w_alloc_safe(sizeof(WVal) * d->cap);
    d->vals = (WVal*)w_alloc_safe(sizeof(WVal) * d->cap);
    w_mem_on_alloc();
    WVal v; v.tag = W_DICT; v.as.dict = d;
    for (int32_t i = 0; i < count; i++) {
        bool updated = false;
        for (int32_t j = 0; j < d->len; j++) {
            if (w_eq(d->keys[j], keys[i])) {
                w_release(d->vals[j]);
                d->vals[j] = w_clone(vals[i]);
                updated = true;
                break;
            }
        }
        if (!updated) {
            d->keys[d->len] = w_clone(keys[i]);
            d->vals[d->len] = w_clone(vals[i]);
            d->len++;
        }
    }
    return v;
}

static inline WVal w_make_struct(const char* name, int32_t count, const char** keys, const WVal* vals) {
    WStructBuf* st = (WStructBuf*)w_alloc_safe(sizeof(WStructBuf));
    st->refcount = 1;
    st->control = NULL;
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

static inline bool w_utf8_valid_codepoint_at(const char* s, size_t pos, size_t* out_len, int64_t* out_cp) {
    const unsigned char* u = (const unsigned char*)s + pos;
    if (u[0] == '\0') {
        if (out_len) *out_len = 0;
        return false;
    }
    if (u[0] < 0x80) {
        if (out_len) *out_len = 1;
        if (out_cp) *out_cp = u[0];
        return true;
    }
    if ((u[0] & 0xE0) == 0xC0) {
        if ((u[1] & 0xC0) != 0x80) return false;
        int64_t cp = ((u[0] & 0x1F) << 6) | (u[1] & 0x3F);
        if (cp < 0x80) return false;
        if (out_len) *out_len = 2;
        if (out_cp) *out_cp = cp;
        return true;
    }
    if ((u[0] & 0xF0) == 0xE0) {
        if ((u[1] & 0xC0) != 0x80 || (u[2] & 0xC0) != 0x80) return false;
        int64_t cp = ((u[0] & 0x0F) << 12) | ((u[1] & 0x3F) << 6) | (u[2] & 0x3F);
        if (cp < 0x800 || (cp >= 0xD800 && cp <= 0xDFFF)) return false;
        if (out_len) *out_len = 3;
        if (out_cp) *out_cp = cp;
        return true;
    }
    if ((u[0] & 0xF8) == 0xF0) {
        if ((u[1] & 0xC0) != 0x80 || (u[2] & 0xC0) != 0x80 || (u[3] & 0xC0) != 0x80) return false;
        int64_t cp = ((u[0] & 0x07) << 18) | ((u[1] & 0x3F) << 12) | ((u[2] & 0x3F) << 6) | (u[3] & 0x3F);
        if (cp < 0x10000 || cp > 0x10FFFF) return false;
        if (out_len) *out_len = 4;
        if (out_cp) *out_cp = cp;
        return true;
    }
    return false;
}

static inline int64_t w_utf8_cp_len(const char* s) {
    int64_t count = 0;
    size_t pos = 0;
    while (s[pos] != '\0') {
        size_t step = 0;
        if (w_utf8_valid_codepoint_at(s, pos, &step, NULL)) {
            pos += step;
        } else {
            pos++;
        }
        count++;
    }
    return count;
}

static inline bool w_utf8_cp_offset(const char* s, int64_t target_cp, size_t* out_off, size_t* out_len) {
    if (target_cp < 0) return false;
    int64_t idx = 0;
    size_t pos = 0;
    while (s[pos] != '\0') {
        size_t step = 0;
        size_t start = pos;
        if (w_utf8_valid_codepoint_at(s, pos, &step, NULL)) {
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
        if (!w_utf8_cp_offset(obj.as.s, idx.as.i, &off, &blen) || blen == 0) {
            fprintf(stderr, "[W4002] RuntimeError: String index out of bounds\n");
            exit(1);
        }
        char* buf = (char*)w_alloc_safe(blen + 1);
        memcpy(buf, obj.as.s + off, blen);
        buf[blen] = '\0';
        return w_owned_str(buf);
    }
    if (obj.tag == W_DICT) {
        for (int32_t i = 0; i < obj.as.dict->len; i++) {
            if (w_eq(obj.as.dict->keys[i], idx)) {
                return obj.as.dict->vals[i];
            }
        }
        return w_none();
    }
    fprintf(stderr, "[W4003] RuntimeError: Cannot index object of tag %d\n", obj.tag);
    exit(1);
}

static inline WVal w_index_get_owned(WVal object, WVal index) {
    if (object.tag == W_DICT) {
        for (int32_t i = 0; i < object.as.dict->len; i++) {
            if (w_eq(object.as.dict->keys[i], index))
                return w_enum_payload("Option", "Some", w_clone(object.as.dict->vals[i]));
        }
        return w_none();
    }
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
        for (int32_t i = 0; i < d->len; i++) {
            if (w_eq(d->keys[i], idx)) {
                return &d->vals[i];
            }
        }
        if (d->len >= d->cap) {
            d->cap = d->cap > 0 ? d->cap * 2 : 4;
            d->keys = (WVal*)w_realloc_safe(d->keys, sizeof(WVal) * d->cap);
            d->vals = (WVal*)w_realloc_safe(d->vals, sizeof(WVal) * d->cap);
        }
        d->keys[d->len] = w_clone(idx);
        d->vals[d->len] = w_none();
        d->len++;
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
    return w_index_get_owned(dict_val, key);
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
        size_t la = strlen(a.as.s);
        size_t lb = strlen(b.as.s);
        char* res = (char*)w_alloc_safe(la + lb + 1);
        memcpy(res, a.as.s, la);
        memcpy(res + la, b.as.s, lb);
        res[la + lb] = '\0';
        return w_owned_str(res);
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
        case W_FLOAT: {
            buf = (char*)w_alloc_safe(64);
            snprintf(buf, 64, "%g", v.as.f);
            if (!strchr(buf, '.') && !strchr(buf, 'e') && !strchr(buf, 'E')) {
                strcat(buf, ".0");
            }
            return buf;
        }
        case W_BOOL:
            buf = (char*)w_alloc_safe(6);
            strcpy(buf, v.as.b ? "true" : "false");
            return buf;
        case W_STR: {
            size_t len = strlen(v.as.s);
            if (!quote_str) {
                buf = (char*)w_alloc_safe(len + 1);
                strcpy(buf, v.as.s);
                return buf;
            }
            buf = (char*)w_alloc_safe(len + 3);
            buf[0] = '"';
            memcpy(buf + 1, v.as.s, len);
            buf[len + 1] = '"';
            buf[len + 2] = '\0';
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
        char* s = w_to_cstr(argv[i], false);
        fputs(s, stdout);
        free(s);
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
            fputs(s, stderr);
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
    if (v.tag == W_STR) return w_int(w_utf8_cp_len(v.as.s));
    return w_int(0);
}

static inline WVal w_builtin_str(WVal v) {
    if (v.tag == W_STR) return w_clone(v);
    return w_owned_str(w_to_cstr(v, false));
}

static inline WVal w_builtin_int(WVal v) {
    if (v.tag == W_INT) return v;
    if (v.tag == W_FLOAT) return w_int((int64_t)v.as.f);
    if (v.tag == W_STR) return w_int((int64_t)atoll(v.as.s));
    return w_int(0);
}

static inline WVal w_builtin_float(WVal v) {
    if (v.tag == W_FLOAT) return v;
    if (v.tag == W_INT) return w_float((double)v.as.i);
    if (v.tag == W_STR) return w_float(atof(v.as.s));
    return w_float(0.0);
}

static inline WVal w_builtin_ord(WVal v) {
    if (v.tag != W_STR || v.as.s[0] == '\0') {
        fprintf(stderr, "[W4003] RuntimeError: ord() expects non-empty str\n");
        exit(1);
    }
    size_t slen = 0;
    int64_t cp = 0;
    if (!w_utf8_valid_codepoint_at(v.as.s, 0, &slen, &cp)) {
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
    return w_owned_str(buf);
}

static inline WVal w_builtin_slice(WVal s, WVal start, WVal end) {
    int64_t total_cp = w_utf8_cp_len(s.as.s);
    int64_t st = start.as.i < 0 ? 0 : start.as.i;
    int64_t en = end.as.i > total_cp ? total_cp : end.as.i;
    if (en <= st || st >= total_cp) return w_str("");
    size_t st_off = 0, dummy_len = 0, en_off = 0;
    w_utf8_cp_offset(s.as.s, st, &st_off, &dummy_len);
    if (en == total_cp) {
        en_off = strlen(s.as.s);
    } else {
        w_utf8_cp_offset(s.as.s, en, &en_off, &dummy_len);
    }
    size_t blen = en_off - st_off;
    char* buf = (char*)w_alloc_safe(blen + 1);
    memcpy(buf, s.as.s + st_off, blen);
    buf[blen] = '\0';
    return w_owned_str(buf);
}

static inline WVal w_builtin_bytes(WVal s) {
    if (s.tag != W_STR) {
        fprintf(stderr, "[W4003] RuntimeError: bytes() expects str\n");
        exit(1);
    }
    size_t slen = strlen(s.as.s);
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

static inline WVal w_builtin_read_file(WVal path) {
    if (path.tag != W_STR) {
        const char* k[1] = { "message" };
        WVal v[1] = { w_str("Invalid path type") };
        return w_err(w_make_struct("IoError", 1, k, v));
    }
    FILE* f = fopen(path.as.s, "rb");
    if (!f) {
        const char* k[1] = { "message" };
        WVal v[1] = { w_str("Failed to open file") };
        return w_err(w_make_struct("IoError", 1, k, v));
    }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char* buf = (char*)w_alloc_safe((size_t)sz + 1);
    size_t read_bytes = fread(buf, 1, (size_t)sz, f);
    buf[read_bytes] = '\0';
    fclose(f);
    return w_ok(w_owned_str(buf));
}

static inline WVal w_builtin_write_file(WVal path, WVal content) {
    if (path.tag != W_STR || content.tag != W_STR) {
        const char* k[1] = { "message" };
        WVal v[1] = { w_str("Invalid argument type for write_file") };
        return w_err(w_make_struct("IoError", 1, k, v));
    }
    FILE* f = fopen(path.as.s, "wb");
    if (!f) {
        const char* k[1] = { "message" };
        WVal v[1] = { w_str("Failed to write file") };
        return w_err(w_make_struct("IoError", 1, k, v));
    }
    size_t len = strlen(content.as.s);
    fwrite(content.as.s, 1, len, f);
    fclose(f);
    return w_ok(w_unit());
}

static int w_g_argc = 0;
static char** w_g_argv = NULL;

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
