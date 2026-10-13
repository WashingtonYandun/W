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
    W_ERR
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
    int32_t len;
    WVal* items;
} WTupleBuf;

typedef struct {
    int32_t refcount;
    const char* name;
    int32_t len;
    const char** keys;
    WVal* vals;
} WStructBuf;

typedef struct {
    const char* enum_name;
    const char* variant;
} WEnumVal;

struct WVal {
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
        WVal* box;
    } as;
};

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
    WVal v; v.tag = W_STR; v.as.s = s ? s : ""; return v;
}

static inline WVal w_enum(const char* enum_name, const char* variant) {
    WVal v;
    v.tag = W_ENUM;
    v.as.en.enum_name = enum_name;
    v.as.en.variant = variant;
    return v;
}

static inline WVal w_ok(WVal inner) {
    if (inner.tag == W_OK || inner.tag == W_ERR) return inner;
    WVal v;
    v.tag = W_OK;
    v.as.box = (WVal*)malloc(sizeof(WVal));
    *v.as.box = inner;
    return v;
}

static inline WVal w_err(WVal inner) {
    WVal v;
    v.tag = W_ERR;
    v.as.box = (WVal*)malloc(sizeof(WVal));
    *v.as.box = inner;
    return v;
}

/* ARC + Copy-on-Write */
static inline WVal w_clone(WVal v) {
    if (v.tag == W_LIST && v.as.list) {
        v.as.list->refcount++;
    } else if (v.tag == W_DICT && v.as.dict) {
        v.as.dict->refcount++;
    } else if ((v.tag == W_STRUCT || v.tag == W_OBJECT) && v.as.st) {
        v.as.st->refcount++;
    } else if (v.tag == W_TUPLE && v.as.tuple) {
        WTupleBuf* old_t = v.as.tuple;
        WTupleBuf* new_t = (WTupleBuf*)malloc(sizeof(WTupleBuf));
        new_t->len = old_t->len;
        new_t->items = (WVal*)malloc(sizeof(WVal) * (old_t->len > 0 ? old_t->len : 1));
        for (int32_t i = 0; i < old_t->len; i++) {
            new_t->items[i] = w_clone(old_t->items[i]);
        }
        v.as.tuple = new_t;
    }
    return v;
}

static inline void w_list_detach(WVal* v) {
    if (v->tag != W_LIST || !v->as.list) return;
    WListBuf* old_b = v->as.list;
    if (old_b->refcount <= 1) return;
    old_b->refcount--;
    WListBuf* new_b = (WListBuf*)malloc(sizeof(WListBuf));
    new_b->refcount = 1;
    new_b->len = old_b->len;
    new_b->cap = old_b->cap > 0 ? old_b->cap : 4;
    new_b->data = (WVal*)malloc(sizeof(WVal) * new_b->cap);
    for (int32_t i = 0; i < old_b->len; i++) {
        new_b->data[i] = w_clone(old_b->data[i]);
    }
    v->as.list = new_b;
}

static inline void w_dict_detach(WVal* v) {
    if (v->tag != W_DICT || !v->as.dict) return;
    WDictBuf* old_b = v->as.dict;
    if (old_b->refcount <= 1) return;
    old_b->refcount--;
    WDictBuf* new_b = (WDictBuf*)malloc(sizeof(WDictBuf));
    new_b->refcount = 1;
    new_b->len = old_b->len;
    new_b->cap = old_b->cap > 0 ? old_b->cap : 4;
    new_b->keys = (WVal*)malloc(sizeof(WVal) * new_b->cap);
    new_b->vals = (WVal*)malloc(sizeof(WVal) * new_b->cap);
    for (int32_t i = 0; i < old_b->len; i++) {
        new_b->keys[i] = w_clone(old_b->keys[i]);
        new_b->vals[i] = w_clone(old_b->vals[i]);
    }
    v->as.dict = new_b;
}

static inline void w_struct_detach(WVal* v) {
    if (v->tag != W_STRUCT || !v->as.st) return;
    WStructBuf* old_b = v->as.st;
    if (old_b->refcount <= 1) return;
    old_b->refcount--;
    WStructBuf* new_b = (WStructBuf*)malloc(sizeof(WStructBuf));
    new_b->refcount = 1;
    new_b->name = old_b->name;
    new_b->len = old_b->len;
    new_b->keys = (const char**)malloc(sizeof(const char*) * (old_b->len > 0 ? old_b->len : 1));
    new_b->vals = (WVal*)malloc(sizeof(WVal) * (old_b->len > 0 ? old_b->len : 1));
    for (int32_t i = 0; i < old_b->len; i++) {
        new_b->keys[i] = old_b->keys[i];
        new_b->vals[i] = w_clone(old_b->vals[i]);
    }
    v->as.st = new_b;
}

/* Structural Equality */
static inline bool w_eq(WVal a, WVal b) {
    if (a.tag != b.tag) return false;
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
            return strcmp(a.as.en.enum_name, b.as.en.enum_name) == 0 &&
                   strcmp(a.as.en.variant, b.as.en.variant) == 0;
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
        case W_OBJECT:
            return a.as.st == b.as.st;
        case W_OK:
        case W_ERR:
            return w_eq(*a.as.box, *b.as.box);
    }
    return false;
}

/* Containers: List, Dict, Tuple, Struct */
static inline WVal w_make_list(int32_t count, const WVal* elems) {
    WListBuf* b = (WListBuf*)malloc(sizeof(WListBuf));
    b->refcount = 1;
    b->len = count;
    b->cap = count > 4 ? count : 4;
    b->data = (WVal*)malloc(sizeof(WVal) * b->cap);
    for (int32_t i = 0; i < count; i++) {
        b->data[i] = w_clone(elems[i]);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal w_make_range(WVal start, WVal end, bool inclusive) {
    int64_t s = start.as.i;
    int64_t e = inclusive ? (end.as.i + 1) : end.as.i;
    int32_t count = (e > s) ? (int32_t)(e - s) : 0;
    WListBuf* b = (WListBuf*)malloc(sizeof(WListBuf));
    b->refcount = 1;
    b->len = count;
    b->cap = count > 4 ? count : 4;
    b->data = (WVal*)malloc(sizeof(WVal) * b->cap);
    for (int32_t i = 0; i < count; i++) {
        b->data[i] = w_int(s + i);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal w_make_tuple(int32_t count, const WVal* elems) {
    WTupleBuf* t = (WTupleBuf*)malloc(sizeof(WTupleBuf));
    t->len = count;
    t->items = (WVal*)malloc(sizeof(WVal) * (count > 0 ? count : 1));
    for (int32_t i = 0; i < count; i++) {
        t->items[i] = w_clone(elems[i]);
    }
    WVal v; v.tag = W_TUPLE; v.as.tuple = t; return v;
}

static inline WVal w_make_dict(int32_t count, const WVal* keys, const WVal* vals) {
    WDictBuf* d = (WDictBuf*)malloc(sizeof(WDictBuf));
    d->refcount = 1;
    d->len = 0;
    d->cap = count > 4 ? count * 2 : 4;
    d->keys = (WVal*)malloc(sizeof(WVal) * d->cap);
    d->vals = (WVal*)malloc(sizeof(WVal) * d->cap);
    WVal v; v.tag = W_DICT; v.as.dict = d;
    for (int32_t i = 0; i < count; i++) {
        bool updated = false;
        for (int32_t j = 0; j < d->len; j++) {
            if (w_eq(d->keys[j], keys[i])) {
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
    WStructBuf* st = (WStructBuf*)malloc(sizeof(WStructBuf));
    st->refcount = 1;
    st->name = name;
    st->len = count;
    st->keys = (const char**)malloc(sizeof(const char*) * (count > 0 ? count : 1));
    st->vals = (WVal*)malloc(sizeof(WVal) * (count > 0 ? count : 1));
    for (int32_t i = 0; i < count; i++) {
        st->keys[i] = keys[i];
        st->vals[i] = w_clone(vals[i]);
    }
    WVal v; v.tag = W_STRUCT; v.as.st = st; return v;
}

static inline WVal w_make_object(const char* name, int32_t count, const char** keys, const WVal* vals) {
    WStructBuf* st = (WStructBuf*)malloc(sizeof(WStructBuf));
    st->refcount = 1;
    st->name = name;
    st->len = count;
    st->keys = (const char**)malloc(sizeof(const char*) * (count > 0 ? count : 1));
    st->vals = (WVal*)malloc(sizeof(WVal) * (count > 0 ? count : 1));
    for (int32_t i = 0; i < count; i++) {
        st->keys[i] = keys[i];
        st->vals[i] = w_clone(vals[i]);
    }
    WVal v; v.tag = W_OBJECT; v.as.st = st; return v;
}

/* UTF-8 Code-Point Helpers (SPEC Section 3.3) */
static inline size_t w_utf8_seq_len(unsigned char c) {
    if (c < 0x80) return 1;
    if ((c & 0xE0) == 0xC0) return 2;
    if ((c & 0xF0) == 0xE0) return 3;
    if ((c & 0xF8) == 0xF0) return 4;
    return 1;
}

static inline int64_t w_utf8_cp_len(const char* s) {
    int64_t count = 0;
    size_t pos = 0;
    while (s[pos] != '\0') {
        size_t step = w_utf8_seq_len((unsigned char)s[pos]);
        for (size_t k = 0; k < step && s[pos] != '\0'; k++) {
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
        size_t step = w_utf8_seq_len((unsigned char)s[pos]);
        size_t start = pos;
        for (size_t k = 0; k < step && s[pos] != '\0'; k++) {
            pos++;
        }
        if (idx == target_cp) {
            *out_off = start;
            *out_len = pos - start;
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
            fprintf(stderr, "RuntimeError: List index out of bounds\n");
            exit(1);
        }
        return obj.as.list->data[i];
    }
    if (obj.tag == W_STR) {
        size_t off = 0, blen = 0;
        if (!w_utf8_cp_offset(obj.as.s, idx.as.i, &off, &blen) || blen == 0) {
            fprintf(stderr, "RuntimeError: String index out of bounds\n");
            exit(1);
        }
        char* buf = (char*)malloc(blen + 1);
        memcpy(buf, obj.as.s + off, blen);
        buf[blen] = '\0';
        return w_str(buf);
    }
    if (obj.tag == W_DICT) {
        for (int32_t i = 0; i < obj.as.dict->len; i++) {
            if (w_eq(obj.as.dict->keys[i], idx)) {
                return obj.as.dict->vals[i];
            }
        }
        return w_none();
    }
    return w_none();
}

static inline WVal* w_index_ref(WVal* obj, WVal idx) {
    if (obj->tag == W_LIST) {
        w_list_detach(obj);
        int64_t i = idx.as.i;
        if (i < 0 || i >= obj->as.list->len) {
            fprintf(stderr, "RuntimeError: List index out of bounds\n");
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
            d->keys = (WVal*)realloc(d->keys, sizeof(WVal) * d->cap);
            d->vals = (WVal*)realloc(d->vals, sizeof(WVal) * d->cap);
        }
        d->keys[d->len] = w_clone(idx);
        d->vals[d->len] = w_none();
        d->len++;
        return &d->vals[d->len - 1];
    }
    fprintf(stderr, "RuntimeError: Cannot index-assign non-collection\n");
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
    fprintf(stderr, "RuntimeError: Invalid field '%s'\n", prop);
    exit(1);
}

/* Methods on List / Dict */
static inline WVal w_list_append(WVal* list_val, WVal item) {
    w_list_detach(list_val);
    WListBuf* b = list_val->as.list;
    if (b->len >= b->cap) {
        b->cap = b->cap > 0 ? b->cap * 2 : 4;
        b->data = (WVal*)realloc(b->data, sizeof(WVal) * b->cap);
    }
    b->data[b->len++] = w_clone(item);
    return w_unit();
}

static inline WVal w_list_pop(WVal* list_val) {
    w_list_detach(list_val);
    WListBuf* b = list_val->as.list;
    if (b->len == 0) {
        fprintf(stderr, "RuntimeError: pop from empty list\n");
        exit(1);
    }
    return b->data[--b->len];
}

static inline WVal w_list_clear(WVal* list_val) {
    w_list_detach(list_val);
    list_val->as.list->len = 0;
    return w_unit();
}

static inline WVal w_dict_get(WVal dict_val, WVal key) {
    return w_index_get(dict_val, key);
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
    if (a.tag == W_INT && b.tag == W_INT) return w_int(a.as.i + b.as.i);
    if (a.tag == W_FLOAT && b.tag == W_FLOAT) return w_float(a.as.f + b.as.f);
    if (a.tag == W_STR && b.tag == W_STR) {
        size_t la = strlen(a.as.s);
        size_t lb = strlen(b.as.s);
        char* res = (char*)malloc(la + lb + 1);
        memcpy(res, a.as.s, la);
        memcpy(res + la, b.as.s, lb);
        res[la + lb] = '\0';
        return w_str(res);
    }
    return w_unit();
}

static inline WVal w_sub(WVal a, WVal b) {
    if (a.tag == W_INT) return w_int(a.as.i - b.as.i);
    return w_float(a.as.f - b.as.f);
}

static inline WVal w_mul(WVal a, WVal b) {
    if (a.tag == W_INT) return w_int(a.as.i * b.as.i);
    return w_float(a.as.f * b.as.f);
}

static inline WVal w_div(WVal a, WVal b) {
    if (a.tag == W_INT) {
        if (b.as.i == 0) { fprintf(stderr, "RuntimeError: Division by zero\n"); exit(1); }
        return w_int(a.as.i / b.as.i);
    }
    if (b.as.f == 0.0) { fprintf(stderr, "RuntimeError: Division by zero\n"); exit(1); }
    return w_float(a.as.f / b.as.f);
}

static inline WVal w_mod(WVal a, WVal b) {
    if (b.as.i == 0) { fprintf(stderr, "RuntimeError: Modulo by zero\n"); exit(1); }
    return w_int(a.as.i % b.as.i);
}

static inline WVal w_neg(WVal a) {
    if (a.tag == W_INT) return w_int(-a.as.i);
    return w_float(-a.as.f);
}

static inline WVal w_lt(WVal a, WVal b) {
    if (a.tag == W_INT) return w_bool(a.as.i < b.as.i);
    if (a.tag == W_FLOAT) return w_bool(a.as.f < b.as.f);
    return w_bool(strcmp(a.as.s, b.as.s) < 0);
}

static inline WVal w_le(WVal a, WVal b) {
    if (a.tag == W_INT) return w_bool(a.as.i <= b.as.i);
    if (a.tag == W_FLOAT) return w_bool(a.as.f <= b.as.f);
    return w_bool(strcmp(a.as.s, b.as.s) <= 0);
}

static inline WVal w_gt(WVal a, WVal b) {
    if (a.tag == W_INT) return w_bool(a.as.i > b.as.i);
    if (a.tag == W_FLOAT) return w_bool(a.as.f > b.as.f);
    return w_bool(strcmp(a.as.s, b.as.s) > 0);
}

static inline WVal w_ge(WVal a, WVal b) {
    if (a.tag == W_INT) return w_bool(a.as.i >= b.as.i);
    if (a.tag == W_FLOAT) return w_bool(a.as.f >= b.as.f);
    return w_bool(strcmp(a.as.s, b.as.s) >= 0);
}

/* Formatting & String Conversion (matching W0 Values.__str__ exactly) */
static inline char* w_to_cstr(WVal v, bool quote_str) {
    char* buf;
    switch (v.tag) {
        case W_UNIT:
            buf = (char*)malloc(5);
            strcpy(buf, "unit");
            return buf;
        case W_NONE:
            buf = (char*)malloc(5);
            strcpy(buf, "none");
            return buf;
        case W_INT:
            buf = (char*)malloc(32);
            snprintf(buf, 32, "%" PRId64, v.as.i);
            return buf;
        case W_FLOAT: {
            buf = (char*)malloc(64);
            snprintf(buf, 64, "%g", v.as.f);
            if (!strchr(buf, '.') && !strchr(buf, 'e') && !strchr(buf, 'E')) {
                strcat(buf, ".0");
            }
            return buf;
        }
        case W_BOOL:
            buf = (char*)malloc(6);
            strcpy(buf, v.as.b ? "true" : "false");
            return buf;
        case W_STR: {
            size_t len = strlen(v.as.s);
            if (!quote_str) {
                buf = (char*)malloc(len + 1);
                strcpy(buf, v.as.s);
                return buf;
            }
            buf = (char*)malloc(len + 3);
            buf[0] = '"';
            memcpy(buf + 1, v.as.s, len);
            buf[len + 1] = '"';
            buf[len + 2] = '\0';
            return buf;
        }
        case W_ENUM: {
            size_t l1 = strlen(v.as.en.enum_name);
            size_t l2 = strlen(v.as.en.variant);
            buf = (char*)malloc(l1 + l2 + 2);
            snprintf(buf, l1 + l2 + 2, "%s.%s", v.as.en.enum_name, v.as.en.variant);
            return buf;
        }
        case W_LIST: {
            size_t cap = 64;
            size_t pos = 0;
            buf = (char*)malloc(cap);
            buf[pos++] = '[';
            for (int32_t i = 0; i < v.as.list->len; i++) {
                if (i > 0) {
                    if (pos + 3 >= cap) { cap *= 2; buf = (char*)realloc(buf, cap); }
                    buf[pos++] = ','; buf[pos++] = ' ';
                }
                char* sub = w_to_cstr(v.as.list->data[i], true);
                size_t sl = strlen(sub);
                while (pos + sl + 4 >= cap) { cap *= 2; buf = (char*)realloc(buf, cap); }
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
            buf = (char*)malloc(cap);
            buf[pos++] = '(';
            for (int32_t i = 0; i < v.as.tuple->len; i++) {
                if (i > 0) {
                    if (pos + 3 >= cap) { cap *= 2; buf = (char*)realloc(buf, cap); }
                    buf[pos++] = ','; buf[pos++] = ' ';
                }
                char* sub = w_to_cstr(v.as.tuple->items[i], true);
                size_t sl = strlen(sub);
                while (pos + sl + 4 >= cap) { cap *= 2; buf = (char*)realloc(buf, cap); }
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
            buf = (char*)malloc(cap);
            buf[pos++] = '{';
            for (int32_t i = 0; i < v.as.dict->len; i++) {
                if (i > 0) {
                    if (pos + 3 >= cap) { cap *= 2; buf = (char*)realloc(buf, cap); }
                    buf[pos++] = ','; buf[pos++] = ' ';
                }
                char* ks = w_to_cstr(v.as.dict->keys[i], true);
                char* vs = w_to_cstr(v.as.dict->vals[i], true);
                size_t kl = strlen(ks), vl = strlen(vs);
                while (pos + kl + vl + 6 >= cap) { cap *= 2; buf = (char*)realloc(buf, cap); }
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
            buf = (char*)malloc(cap);
            size_t nl = strlen(v.as.st->name);
            memcpy(buf + pos, v.as.st->name, nl); pos += nl;
            buf[pos++] = ' '; buf[pos++] = '{'; buf[pos++] = ' ';
            for (int32_t i = 0; i < v.as.st->len; i++) {
                if (i > 0) {
                    if (pos + 3 >= cap) { cap *= 2; buf = (char*)realloc(buf, cap); }
                    buf[pos++] = ','; buf[pos++] = ' ';
                }
                const char* fn = v.as.st->keys[i];
                char* vs = w_to_cstr(v.as.st->vals[i], true);
                size_t fl = strlen(fn), vl = strlen(vs);
                while (pos + fl + vl + 8 >= cap) { cap *= 2; buf = (char*)realloc(buf, cap); }
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
            char* inner = w_to_cstr(*v.as.box, false);
            size_t il = strlen(inner);
            buf = (char*)malloc(il + 5);
            snprintf(buf, il + 5, "Ok(%s)", inner);
            free(inner);
            return buf;
        }
        case W_ERR: {
            char* inner = w_to_cstr(*v.as.box, false);
            size_t il = strlen(inner);
            buf = (char*)malloc(il + 6);
            snprintf(buf, il + 6, "Err(%s)", inner);
            free(inner);
            return buf;
        }
    }
    buf = (char*)malloc(1);
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

static inline WVal w_builtin_len(WVal v) {
    if (v.tag == W_LIST) return w_int(v.as.list->len);
    if (v.tag == W_DICT) return w_int(v.as.dict->len);
    if (v.tag == W_STR) return w_int(w_utf8_cp_len(v.as.s));
    return w_int(0);
}

static inline WVal w_builtin_str(WVal v) {
    if (v.tag == W_STR) return v;
    return w_str(w_to_cstr(v, false));
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
        fprintf(stderr, "RuntimeError: ord() expects non-empty str\n");
        exit(1);
    }
    const unsigned char* u = (const unsigned char*)v.as.s;
    size_t slen = w_utf8_seq_len(u[0]);
    int64_t cp = 0;
    if (slen == 1) cp = u[0];
    else if (slen == 2) cp = ((u[0] & 0x1F) << 6) | (u[1] & 0x3F);
    else if (slen == 3) cp = ((u[0] & 0x0F) << 12) | ((u[1] & 0x3F) << 6) | (u[2] & 0x3F);
    else cp = ((u[0] & 0x07) << 18) | ((u[1] & 0x3F) << 12) | ((u[2] & 0x3F) << 6) | (u[3] & 0x3F);
    return w_int(cp);
}

static inline WVal w_builtin_chr(WVal v) {
    int64_t cp = v.as.i;
    char* buf = (char*)malloc(5);
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
    return w_str(buf);
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
    char* buf = (char*)malloc(blen + 1);
    memcpy(buf, s.as.s + st_off, blen);
    buf[blen] = '\0';
    return w_str(buf);
}

static inline WVal w_builtin_bytes(WVal s) {
    size_t slen = strlen(s.as.s);
    WListBuf* b = (WListBuf*)malloc(sizeof(WListBuf));
    b->refcount = 1;
    b->len = (int32_t)slen;
    b->cap = slen > 4 ? (int32_t)slen : 4;
    b->data = (WVal*)malloc(sizeof(WVal) * b->cap);
    for (size_t i = 0; i < slen; i++) {
        b->data[i] = w_int((int64_t)(unsigned char)s.as.s[i]);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal w_builtin_enumerate(WVal list_val) {
    WListBuf* src = list_val.as.list;
    WListBuf* b = (WListBuf*)malloc(sizeof(WListBuf));
    b->refcount = 1;
    b->len = src->len;
    b->cap = src->len > 4 ? src->len : 4;
    b->data = (WVal*)malloc(sizeof(WVal) * b->cap);
    for (int32_t i = 0; i < src->len; i++) {
        WVal pair[2] = { w_int(i), src->data[i] };
        b->data[i] = w_make_tuple(2, pair);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal w_builtin_dict_items(WVal dict_val) {
    WDictBuf* d = dict_val.as.dict;
    WListBuf* b = (WListBuf*)malloc(sizeof(WListBuf));
    b->refcount = 1;
    b->len = d->len;
    b->cap = d->len > 4 ? d->len : 4;
    b->data = (WVal*)malloc(sizeof(WVal) * b->cap);
    for (int32_t i = 0; i < d->len; i++) {
        WVal pair[2] = { d->keys[i], d->vals[i] };
        b->data[i] = w_make_tuple(2, pair);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

static inline WVal w_builtin_read_file(WVal path) {
    FILE* f = fopen(path.as.s, "rb");
    if (!f) {
        const char* k[1] = { "message" };
        WVal v[1] = { w_str("Failed to open file") };
        return w_err(w_make_struct("IoError", 1, k, v));
    }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char* buf = (char*)malloc((size_t)sz + 1);
    size_t read_bytes = fread(buf, 1, (size_t)sz, f);
    buf[read_bytes] = '\0';
    fclose(f);
    return w_ok(w_str(buf));
}

static inline WVal w_builtin_write_file(WVal path, WVal content) {
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
    WListBuf* b = (WListBuf*)malloc(sizeof(WListBuf));
    b->refcount = 1;
    b->len = (int32_t)w_g_argc;
    b->cap = w_g_argc > 4 ? (int32_t)w_g_argc : 4;
    b->data = (WVal*)malloc(sizeof(WVal) * b->cap);
    for (int i = 0; i < w_g_argc; i++) {
        b->data[i] = w_str(w_g_argv[i]);
    }
    WVal v; v.tag = W_LIST; v.as.list = b; return v;
}

#endif /* W_RUNTIME_H */
