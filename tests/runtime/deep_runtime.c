#include "runtime/wysna_runtime.h"

#define DEEP_VALUE_DEPTH 100000

int main(void) {
    WVal left = wysna_enum("Deep", "End");
    WVal right = wysna_enum("Deep", "End");

    for (int32_t i = 0; i < DEEP_VALUE_DEPTH; i++) {
        left = wysna_enum_payload("Deep", "Node", left);
        right = wysna_enum_payload("Deep", "Node", right);
    }

    if (!wysna_eq(left, right)) {
        fprintf(stderr, "deep values compared unequal\n");
        return 1;
    }

    char* rendered = wysna_to_cstr(left, false);
    size_t rendered_length = strlen(rendered);
    size_t expected_length = (size_t)DEEP_VALUE_DEPTH * 11 + 8;
    if (rendered_length != expected_length ||
        strncmp(rendered, "Deep.Node(Deep.Node(", 20) != 0 ||
        strncmp(rendered + (size_t)DEEP_VALUE_DEPTH * 10, "Deep.End", 8) != 0 ||
        rendered[rendered_length - 1] != ')') {
        fprintf(stderr, "unexpected deep rendering length=%zu\n", rendered_length);
        free(rendered);
        return 2;
    }
    free(rendered);

    wysna_release(left);
    wysna_release(right);
    wysna_runtime_cleanup();
    puts("deep runtime values passed");
    return 0;
}
