fn new_temp() -> str {
    let name = "_t" + str(g_temp_id)
    g_temp_id = g_temp_id + 1
    return name
}

fn new_aux(prefix: str) -> str {
    let s = prefix + str(g_aux_id)
    g_aux_id = g_aux_id + 1
    return s
}

fn push_scope(kind: str) -> unit {
    let empty_v: list[str] = []
    g_scope_stack.append(CleanupScope { kind: kind, vars: empty_v })
}

fn register_var(v: str) -> unit {
    let n = len(g_scope_stack)
    if n > 0 {
        g_scope_stack[n - 1].vars.append(v)
    }
}

fn declare_owned_var(var_name: str, init_c_expr: str) -> str {
    emit_line("WVal " + var_name + " = " + init_c_expr + ";")
    register_var(var_name)
    return var_name
}

fn pop_scope() -> unit {
    let n = len(g_scope_stack)
    if n == 0 {
        return
    }
    let top = g_scope_stack[n - 1]
    g_scope_stack.pop()
    let num_vars = len(top.vars)
    if num_vars > 0 {
        let mut idx = num_vars - 1
        while idx >= 0 {
            emit_line("w_release(" + top.vars[idx] + ");")
            idx = idx - 1
        }
    }
}

fn emit_cleanup_until_fn() -> unit {
    let num_scopes = len(g_scope_stack)
    let mut si = num_scopes - 1
    while si >= 0 {
        let sc = g_scope_stack[si]
        let num_vars = len(sc.vars)
        if num_vars > 0 {
            let mut vi = num_vars - 1
            while vi >= 0 {
                emit_line("w_release(" + sc.vars[vi] + ");")
                vi = vi - 1
            }
        }
        if sc.kind == "fn" {
            break
        }
        si = si - 1
    }
}

fn emit_cleanup_until_fn_indented() -> unit {
    let num_scopes = len(g_scope_stack)
    let mut si = num_scopes - 1
    while si >= 0 {
        let sc = g_scope_stack[si]
        let num_vars = len(sc.vars)
        if num_vars > 0 {
            let mut vi = num_vars - 1
            while vi >= 0 {
                emit_line("    w_release(" + sc.vars[vi] + ");")
                vi = vi - 1
            }
        }
        if sc.kind == "fn" {
            break
        }
        si = si - 1
    }
}

fn emit_cleanup_until_loop() -> unit {
    let num_scopes = len(g_scope_stack)
    let mut si = num_scopes - 1
    while si >= 0 {
        let sc = g_scope_stack[si]
        let num_vars = len(sc.vars)
        if num_vars > 0 {
            let mut vi = num_vars - 1
            while vi >= 0 {
                emit_line("w_release(" + sc.vars[vi] + ");")
                vi = vi - 1
            }
        }
        if sc.kind == "loop" {
            break
        }
        si = si - 1
    }
}

fn has_cleanup_until_loop() -> bool {
    let num_scopes = len(g_scope_stack)
    let mut si = num_scopes - 1
    while si >= 0 {
        let sc = g_scope_stack[si]
        if len(sc.vars) > 0 {
            return true
        }
        if sc.kind == "loop" {
            break
        }
        si = si - 1
    }
    return false
}

fn emit_cleanup_until_loop_indented() -> unit {
    let num_scopes = len(g_scope_stack)
    let mut si = num_scopes - 1
    while si >= 0 {
        let sc = g_scope_stack[si]
        let num_vars = len(sc.vars)
        if num_vars > 0 {
            let mut vi = num_vars - 1
            while vi >= 0 {
                emit_line("    w_release(" + sc.vars[vi] + ");")
                vi = vi - 1
            }
        }
        if sc.kind == "loop" {
            break
        }
        si = si - 1
    }
}

fn own_expr(val_expr: str) -> str {
    if len(val_expr) >= 2 and slice(val_expr, 0, 2) == "_t" {
        return "w_move(&" + val_expr + ")"
    }
    if len(val_expr) >= 7 and slice(val_expr, 0, 7) == "w_make_" {
        return val_expr
    }
    if len(val_expr) >= 6 and slice(val_expr, 0, 6) == "w_new_" {
        return val_expr
    }
    if len(val_expr) >= 8 and slice(val_expr, 0, 8) == "w_clone(" {
        return val_expr
    }
    return "w_clone(" + val_expr + ")"
}

fn emit_line(line: str) -> unit {
    g_cur_stmts.append(line)
}


fn snapshot_value(value: str) -> str {
    if len(value) >= 2 and slice(value, 0, 2) == "_t" {
        return value
    }
    if len(value) >= 7 and slice(value, 0, 7) == "w_make_" {
        return bind_call(value).val
    }
    return bind_call("w_clone(" + value + ")").val
}

fn is_bound_variable(value: str) -> bool {
    for name in g_borrowed_vars { if name == value { return true } }
    for name in g_globals { if name == value { return true } }
    for scope in g_scope_stack { for name in scope.vars { if name == value { return true } } }
    return false
}
fn emit_indirect_call(callee: str, args: list[str]) -> ExprRes {
    let mut joined = ""
    for i in 0..len(args) {
        if i > 0 { joined = joined + ", " }
        joined = joined + args[i]
    }
    if len(args) == 0 { return bind_call("w_call(" + callee + ", 0, NULL)") }
    let array = new_aux("_call_args")
    emit_line("WVal " + array + "[" + str(len(args)) + "] = { " + joined + " };")
    return bind_call("w_call(" + callee + ", " + str(len(args)) + ", " + array + ")")
}

fn emit_function_value(name: str) -> ExprRes {
    let index = sem_function(name)
    let arity = len(sem_functions[index].params)
    let adapter = "w_adapter_" + name
    let prototype = "static WVal " + adapter + "(WVal, int32_t, const WVal*);"
    let mut exists = false
    for declaration in g_protos { if declaration == prototype { exists = true } }
    if not exists {
        g_protos.append(prototype)
        let mut arguments = ""
        for i in 0..arity {
            if i > 0 { arguments = arguments + ", " }
            arguments = arguments + "argv[" + str(i) + "]"
        }
        g_fn_defs.append("static WVal " + adapter + "(WVal environment, int32_t argc, const WVal* argv) { (void)environment; if (argc != " + str(arity) + ") (fprintf(stderr, \"[W4003] RuntimeError: Call arity mismatch\\n\"), exit(1)); return " + c_fn_name(name) + "(" + arguments + "); }")
    }
    return bind_call("w_function_new(" + adapter + ", w_unit())")
}

fn emit_struct_constructor(name: str, values: list[str]) -> ExprRes {
    let mut keys: list[str] = []
    let mut field_count = 0
    for field in sem_fields {
        if field.owner == name {
            keys.append("\"" + field.name + "\"")
            field_count = field_count + 1
        }
    }
    if field_count != len(values) { report_error("W2005", at_tok().line, at_tok().col, "struct constructor arity: " + name) }
    if field_count == 0 { return bind_call("w_make_struct(\"" + name + "\", 0, NULL, NULL)") }
    let keys_var = new_aux("_keys")
    let values_var = new_aux("_values")
    let mut joined_keys = ""
    let mut joined_values = ""
    for i in 0..field_count {
        if i > 0 { joined_keys = joined_keys + ", " joined_values = joined_values + ", " }
        joined_keys = joined_keys + keys[i]
        joined_values = joined_values + values[i]
    }
    let count = str(field_count)
    emit_line("const char* " + keys_var + "[" + count + "] = { " + joined_keys + " };")
    emit_line("WVal " + values_var + "[" + count + "] = { " + joined_values + " };")
    return bind_call("w_make_struct(\"" + name + "\", " + count + ", " + keys_var + ", " + values_var + ")")
}
