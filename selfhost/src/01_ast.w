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

