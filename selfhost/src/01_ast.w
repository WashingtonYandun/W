struct Token {
    kind: str,
    val: str,
    line: int,
    col: int,
}

struct ExprRes {
    val: str,
    lref: str,
}

struct ClassMeta {
    name: str,
    super_name: str,
    field_names: list[str],
    field_defaults: list[str],
    method_names: list[str],
    method_arities: list[int],
    init_params: list[str],
}

struct CleanupScope {
    kind: str,
    vars: list[str],
}

let mut g_tokens: list[Token] = []
let mut g_pos: int = 0
let mut g_temp_id: int = 0
let mut g_fn_fallible: bool = false
let mut g_ns: str = ""
let mut g_enums: list[str] = []
let mut g_enum_variant_names: list[str] = []
let mut g_enum_variant_owners: list[str] = []
let mut g_enum_variant_arities: list[int] = []
let mut g_pattern_bind_lines: list[str] = []
let mut g_pattern_bind_names: list[str] = []
let mut g_modules: list[str] = []
let mut g_classes: list[ClassMeta] = []
let mut g_dispatch_names: list[str] = []
let mut g_dispatch_arities: list[int] = []
let mut g_cur_class: str = ""
let mut g_cur_super: str = ""
let mut g_globals: list[str] = []
let mut g_protos: list[str] = []
let mut g_fn_defs: list[str] = []
let mut g_cur_stmts: list[str] = []
let mut g_scope_stack: list[CleanupScope] = []
let mut g_aux_id: int = 0
let mut g_cur_err_type: str = ""
let mut g_in_path: str = ""


let mut g_borrowed_vars: list[str] = []

# Standalone semantic parsing. Types are interned structures, never fixture names.
struct SemType { kind: str, name: str, args: list[int] }
struct SemGenericType { name: str, kind: str, params: list[str] }
struct SemVar { name: str, type_id: int, mutable: bool, depth: int }
struct SemFunction { name: str, params: list[str], type_params: list[str], constraints: list[str], type_id: int, body: int, end: int, owner: str, visible: bool }
struct SemField { owner: str, name: str, type_id: int, visible: bool }
struct SemClass { name: str, parent: str, interfaces: list[str] }
struct SemValue { type_id: int, root: str, writable: int, terminates: bool }
struct SemFlow { type_id: int, terminates: bool }
let mut sem_tokens: list[Token] = []
let mut sem_pos = 0
let mut sem_types: list[SemType] = []
let mut sem_generic_types: list[SemGenericType] = []
let mut sem_type_params: list[str] = []
let mut sem_active_constraints: list[str] = []
let mut sem_unify_names: list[str] = []
let mut sem_unify_types: list[int] = []
let mut sem_variables: list[SemVar] = []
let mut sem_functions: list[SemFunction] = []
let mut sem_fields: list[SemField] = []
let mut sem_classes: list[SemClass] = []
let mut sem_variants: list[str] = []
let mut sem_variant_types: list[int] = []
let mut sem_variant_payloads: list[list[int]] = []
let mut sem_depth = 0
let mut sem_return = 0
let mut sem_owner = ""
let mut sem_current_function = ""
let mut sem_layout_seen: list[str] = []
let mut sem_loop = 0
let mut sem_int = 0
let mut sem_float = 0
let mut sem_bool = 0
let mut sem_str = 0
let mut sem_unit = 0
let mut sem_none = 0
let mut sem_initializing = false
let mut sem_initialized: list[str] = []


struct SemLambda { position: int, line: int, col: int, params: list[str], captures: list[str], type_id: int }
let mut sem_lambdas: list[SemLambda] = []
let mut sem_capture_names: list[str] = []
let mut sem_capture_depth = -1

let mut sem_statement_context = false

let mut sem_token_offset = 0

let mut sem_indirect_positions: list[int] = []

let mut sem_class_projection_positions: list[int] = []

let mut sem_collection_call_positions: list[int] = []
let mut sem_result_lift_positions: list[int] = []
