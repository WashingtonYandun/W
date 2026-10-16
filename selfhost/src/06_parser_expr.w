fn snapshot_callee(callee: ExprRes, collection: bool) -> ExprRes {
    if is_bound_variable(callee.val) { return ExprRes { val: snapshot_value(callee.val), lref: "" } }
    let raw = callee.lref
    let mut separators: list[int] = []
    let mut skip = -1
    for i in 0..len(raw) - 1 {
        if i > skip and slice(raw, i, i + 2) == "::" {
            separators.append(i)
            skip = i + 1
        }
    }
    if len(separators) < 3 { return callee }
    let method = slice(raw, separators[0] + 2, separators[1])
    let receiver = slice(raw, separators[2] + 2, len(raw))
    if (collection and (method == "append" or method == "pop" or method == "clear")) or receiver == "v_super" { return callee }
    if len(receiver) >= 2 and slice(receiver, 0, 2) == "v_" {
        if is_module_name(slice(receiver, 2, len(receiver))) { return callee }
    }
    let held = snapshot_value(receiver)
    return ExprRes { val: callee.val, lref: slice(raw, 0, separators[2] + 2) + held }
}

fn projection_is_mutated() -> bool {
    let mut offset = 0
    while true {
        let kind = peek_tok(offset).kind
        if kind == "ASSIGN" { return true }
        if kind == "DOT" {
            let method = peek_tok(offset + 1).val
            if peek_tok(offset + 2).kind == "LPAREN" {
                return method == "append" or method == "pop" or method == "clear"
            }
            offset = offset + 2
        } elif kind == "LBRACKET" {
            let mut depth = 1
            offset = offset + 1
            while depth > 0 and peek_tok(offset).kind != "EOF" {
                if peek_tok(offset).kind == "LBRACKET" { depth = depth + 1 }
                if peek_tok(offset).kind == "RBRACKET" { depth = depth - 1 }
                offset = offset + 1
            }
        } else { return false }
    }
    return false
}


fn emit_call(callee: ExprRes, args_c: list[str], collection: bool, line: int, col: int) -> ExprRes {
    if len(callee.val) >= 6 and slice(callee.val, 0, 6) == "enum::" {
        let marker = slice(callee.val, 6, len(callee.val))
        let mut separator = -1
        for i in 0..len(marker) - 1 { if slice(marker, i, i + 2) == "::" { separator = i } }
        if separator < 0 { report_error("W9999", at_tok().line, at_tok().col, "invalid enum constructor marker") }
        let owner = slice(marker, 0, separator)
        let variant = slice(marker, separator + 2, len(marker))
        if owner == "Option" and variant == "Some" {
            if len(args_c) != 1 { report_error("W2005", at_tok().line, at_tok().col, "Option.Some arity") }
            return bind_call("w_enum_payload(\"Option\", \"Some\", " + own_expr(args_c[0]) + ")")
        }
        if owner == "Result" and variant == "Ok" {
            if len(args_c) != 1 { report_error("W2005", at_tok().line, at_tok().col, "Result.Ok arity") }
            return bind_call("w_ok(" + own_expr(args_c[0]) + ")")
        }
        if owner == "Result" and variant == "Err" {
            if len(args_c) != 1 { report_error("W2005", at_tok().line, at_tok().col, "Result.Err arity") }
            return bind_call("w_err(" + own_expr(args_c[0]) + ")")
        }
        let mut arity = -1
        for i in 0..len(g_enum_variant_names) {
            if g_enum_variant_names[i] == variant and g_enum_variant_owners[i] == owner { arity = g_enum_variant_arities[i] }
        }
        if arity != len(args_c) { report_error("W2005", at_tok().line, at_tok().col, "enum constructor arity: " + owner + "." + variant) }
        if arity == 0 { return bind_call("w_enum(\"" + owner + "\", \"" + variant + "\")") }
        if arity == 1 { return bind_call("w_enum_payload(\"" + owner + "\", \"" + variant + "\", " + own_expr(args_c[0]) + ")") }
        let payload_values = new_aux("_enum_values")
        let mut values = ""
        for i in 0..len(args_c) {
            if i > 0 { values = values + ", " }
            values = values + args_c[i]
        }
        emit_line("WVal " + payload_values + "[" + str(len(args_c)) + "] = { " + values + " };")
        let payload = "w_make_tuple(" + str(len(args_c)) + ", " + payload_values + ")"
        return bind_call("w_enum_payload(\"" + owner + "\", \"" + variant + "\", " + payload + ")")
    }
    if is_bound_variable(callee.val) or (callee.lref == "" and not (len(callee.val) >= 2 and slice(callee.val, 0, 2) == "v_")) {
        return emit_indirect_call(callee.val, args_c)
    }
    let raw = callee.lref
    let n = len(raw)
    let mut s1 = -1
    let mut s2 = -1
    let mut s3 = -1
    let mut skip = -1
    if n >= 2 {
        for i in 0..n - 1 {
            if i > skip and slice(raw, i, i + 2) == "::" {
                skip = i + 1
                if s1 == -1 {
                    s1 = i
                } elif s2 == -1 {
                    s2 = i
                } else {
                    s3 = i
                    break
                }
            }
        }
    }
    if s1 != -1 and s2 != -1 and s3 != -1 {
        let method = slice(raw, s1 + 2, s2)
        let recv_lref = clean_lref(slice(raw, s2 + 2, s3))
        let recv_val = slice(raw, s3 + 2, n)
        if recv_val == "v_super" {
            let def_cls = find_class_method_owner(g_cur_super, method)
            if def_cls != "" {
                let mut joined = "v_self"
                for idx in 0..len(args_c) {
                    joined = joined + ", " + args_c[idx]
                }
                return bind_call("w_method_" + def_cls + "__" + method + "(" + joined + ")")
            }
            return ExprRes { val: "w_unit()", lref: "" }
        }
        if len(recv_val) >= 2 and slice(recv_val, 0, 2) == "v_" {
            let obj_name = slice(recv_val, 2, len(recv_val))
            if is_module_name(obj_name) {
                let mut joined = ""
                for idx in 0..len(args_c) {
                    if idx > 0 {
                        joined = joined + ", "
                    }
                    joined = joined + args_c[idx]
                }
                return bind_call("w_fn_" + obj_name + "__" + method + "(" + joined + ")")
            }
        }
        if collection and method == "append" {
            return bind_call("w_list_append(" + recv_lref + ", " + args_c[0] + ")")
        }
        if collection and method == "pop" {
            return bind_call("w_list_pop_at(" + recv_lref + ", " + escape_c_str(g_in_path) + ", " + str(line) + ", " + str(col) + ")")
        }
        if collection and method == "clear" {
            return bind_call("w_list_clear(" + recv_lref + ")")
        }
        if collection and method == "get" {
            return bind_call("w_dict_get(" + recv_val + ", " + args_c[0] + ")")
        }
        if collection and method == "keys" {
            return bind_call("w_dict_keys(" + recv_val + ")")
        }
        if collection and method == "values" {
            return bind_call("w_dict_values(" + recv_val + ")")
        }
        let mut d_args = recv_val
        for idx in 0..len(args_c) {
            d_args = d_args + ", " + args_c[idx]
        }
        return bind_call("w_dispatch__" + method + "__" + str(len(args_c)) + "(" + d_args + ")")
    }
    if len(callee.val) >= 2 and slice(callee.val, 0, 2) == "v_" {
        let fn_name = slice(callee.val, 2, len(callee.val))
        if fn_name == "weak" or fn_name == "upgrade" {
            if len(args_c) != 1 { report_error("W2005", at_tok().line, at_tok().col, "weak/upgrade expects one argument") }
            if fn_name == "weak" {
                return bind_call("w_builtin_weak_owned(" + own_expr(args_c[0]) + ")")
            }
            return bind_call("w_builtin_" + fn_name + "(" + args_c[0] + ")")
        }
        if fn_name == "Ok" and len(args_c) == 1 {
            return bind_call("w_ok(" + own_expr(args_c[0]) + ")")
        }
        if fn_name == "Err" and len(args_c) == 1 {
            return bind_call("w_err(" + own_expr(args_c[0]) + ")")
        }
        if fn_name == "Some" and len(args_c) == 1 {
            return bind_call("w_enum_payload(\"Option\", \"Some\", " + own_expr(args_c[0]) + ")")
        }
        if fn_name == "print" {
            if len(args_c) == 0 {
                return bind_call("w_builtin_print(0, NULL)")
            }
            let arr_tmp = new_aux("_arr")
            let mut joined = ""
            for idx in 0..len(args_c) {
                if idx > 0 {
                    joined = joined + ", "
                }
                joined = joined + args_c[idx]
            }
            let cnt = str(len(args_c))
            emit_line("WVal " + arr_tmp + "[" + cnt + "] = { " + joined + " };")
            return bind_call("w_builtin_print(" + cnt + ", " + arr_tmp + ")")
        }
        if fn_name == "eprint" {
            if len(args_c) == 0 {
                return bind_call("w_builtin_eprint(0, NULL)")
            }
            let arr_tmp = new_aux("_arr")
            let mut joined = ""
            for idx in 0..len(args_c) {
                if idx > 0 {
                    joined = joined + ", "
                }
                joined = joined + args_c[idx]
            }
            let cnt = str(len(args_c))
            emit_line("WVal " + arr_tmp + "[" + cnt + "] = { " + joined + " };")
            return bind_call("w_builtin_eprint(" + cnt + ", " + arr_tmp + ")")
        }
        if fn_name == "exit" and len(args_c) == 1 {
            return bind_call("w_builtin_exit(" + args_c[0] + ")")
        }
        if fn_name == "len" {
            return bind_call("w_builtin_len(" + args_c[0] + ")")
        }
        if fn_name == "str" {
            return bind_call("w_builtin_str(" + args_c[0] + ")")
        }
        if fn_name == "int" {
            return bind_call("w_builtin_int(" + args_c[0] + ")")
        }
        if fn_name == "float" {
            return bind_call("w_builtin_float(" + args_c[0] + ")")
        }
        if fn_name == "ord" {
            return bind_call("w_builtin_ord(" + args_c[0] + ")")
        }
        if fn_name == "chr" {
            return bind_call("w_builtin_chr(" + args_c[0] + ")")
        }
        if fn_name == "bytes" {
            return bind_call("w_builtin_bytes(" + args_c[0] + ")")
        }
        if fn_name == "enumerate" {
            return bind_call("w_builtin_enumerate(" + args_c[0] + ")")
        }
        if fn_name == "dict_items" {
            return bind_call("w_builtin_dict_items(" + args_c[0] + ")")
        }
        if fn_name == "read_file" {
            return bind_call("w_builtin_read_file(" + args_c[0] + ")")
        }
        if fn_name == "write_file" {
            return bind_call("w_builtin_write_file(" + args_c[0] + ", " + args_c[1] + ")")
        }
        if fn_name == "slice" {
            return bind_call("w_builtin_slice(" + args_c[0] + ", " + args_c[1] + ", " + args_c[2] + ")")
        }
        if fn_name == "args" {
            return bind_call("w_builtin_args()")
        }
        let mut joined = ""
        for idx in 0..len(args_c) {
            if idx > 0 {
                joined = joined + ", "
            }
            joined = joined + args_c[idx]
        }
        if find_class_meta_idx(fn_name) != -1 {
            return bind_call("w_new_" + fn_name + "(" + joined + ")")
        }
        let generic_type = sem_generic_type(fn_name)
        if generic_type >= 0 and sem_generic_types[generic_type].kind == "struct" { return emit_struct_constructor(fn_name, args_c) }
        return bind_call(c_fn_name(fn_name) + "(" + joined + ")")
    }
    return ExprRes { val: "w_unit()", lref: "" }
}

fn parse_block_expr() -> str {
    expect_kind("LBRACE")
    let res = new_temp()
    declare_owned_var(res, "w_unit()")
    emit_line("{")
    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    push_scope("block")
    let mut tail_val = "w_unit()"
    while not check_kind("RBRACE") and not is_eof() {
        if check_kind("LET") {
            parse_let_stmt(false)
            tail_val = "w_unit()"
        } elif check_kind("WHILE") {
            parse_while_stmt()
            tail_val = "w_unit()"
        } elif check_kind("FOR") {
            parse_for_stmt()
            tail_val = "w_unit()"
        } elif check_kind("RETURN") {
            parse_return_stmt()
            tail_val = "w_unit()"
        } elif check_kind("BREAK") {
            advance_tok()
            emit_cleanup_until_loop()
            emit_line("break;")
            tail_val = "w_unit()"
        } elif check_kind("CONTINUE") {
            advance_tok()
            emit_cleanup_until_loop()
            emit_line("continue;")
            tail_val = "w_unit()"
        } else {
            let expr_r = parse_expr(0, true)
            if check_kind("RBRACE") {
                tail_val = expr_r.val
            } else {
                emit_line("(void)" + expr_r.val + ";")
                tail_val = "w_unit()"
            }
        }
    }
    expect_kind("RBRACE")
    if tail_val != "w_unit()" {
        emit_line("w_assign(&" + res + ", " + own_expr(tail_val) + ");")
    }
    pop_scope()
    let inner = g_cur_stmts
    g_cur_stmts = saved
    for l in inner {
        emit_line("    " + l)
    }
    emit_line("}")
    return res
}

fn parse_if_expr() -> ExprRes {
    expect_kind("IF")
    let res = new_temp()
    declare_owned_var(res, "w_unit()")
    let cond_r = parse_expr(0, false)
    emit_line("if ((" + cond_r.val + ").as.b) {")
    push_scope("block")
    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    let then_v = parse_block_expr()
    emit_line("w_assign(&" + res + ", " + own_expr(then_v) + ");")
    pop_scope()
    let then_lines = g_cur_stmts
    g_cur_stmts = saved
    for l in then_lines {
        emit_line("    " + l)
    }
    emit_line("}")
    parse_elif_chain(res)
    return ExprRes { val: res, lref: "" }
}

fn parse_elif_chain(res: str) -> unit {
    if match_kind("ELIF") {
        emit_line("else {")
        push_scope("block")
        let saved = g_cur_stmts
        let empty: list[str] = []
        g_cur_stmts = empty
        let eb_cond = parse_expr(0, false)
        emit_line("if ((" + eb_cond.val + ").as.b) {")
        push_scope("block")
        let saved_inner = g_cur_stmts
        let empty2: list[str] = []
        g_cur_stmts = empty2
        let eb_v = parse_block_expr()
        emit_line("w_assign(&" + res + ", " + own_expr(eb_v) + ");")
        pop_scope()
        let eb_lines = g_cur_stmts
        g_cur_stmts = saved_inner
        for l in eb_lines {
            emit_line("    " + l)
        }
        emit_line("}")
        parse_elif_chain(res)
        pop_scope()
        let outer_lines = g_cur_stmts
        g_cur_stmts = saved
        for l in outer_lines {
            emit_line("    " + l)
        }
        emit_line("}")
    } elif match_kind("ELSE") {
        emit_line("else {")
        push_scope("block")
        let saved = g_cur_stmts
        let empty: list[str] = []
        g_cur_stmts = empty
        let else_v = parse_block_expr()
        emit_line("w_assign(&" + res + ", " + own_expr(else_v) + ");")
        pop_scope()
        let else_lines = g_cur_stmts
        g_cur_stmts = saved
        for l in else_lines {
            emit_line("    " + l)
        }
        emit_line("}")
    }
}

fn parse_match_expr() -> ExprRes {
    expect_kind("MATCH")
    let subj_r = parse_expr(0, false)
    let subj_tmp = new_temp()
    declare_owned_var(subj_tmp, own_expr(subj_r.val))
    let res = new_temp()
    declare_owned_var(res, "w_unit()")
    expect_kind("LBRACE")
    if not check_kind("RBRACE") {
        parse_match_arms(subj_tmp, res)
    }
    expect_kind("RBRACE")
    return ExprRes { val: res, lref: "" }
}

fn parse_pattern_condition(subject: str) -> str {
    let pattern_position = g_pos + 1
    let mut error_pattern_kind = ""
    let mut error_pattern_name = ""
    for i in 0..len(sem_error_pattern_positions) {
        if sem_error_pattern_positions[i] == pattern_position {
            error_pattern_kind = sem_error_pattern_kinds[i]
            error_pattern_name = sem_error_pattern_names[i]
        }
    }
    if error_pattern_kind != "" {
        expect_kind("IDENT")
        expect_kind("LPAREN")
        let mut condition = "w_value_is_error_type(" + subject + ", " + escape_c_str(error_pattern_kind) + ", " + escape_c_str(error_pattern_name) + ")"
        if not check_kind("RPAREN") {
            let child = parse_pattern_condition(subject)
            condition = "(" + condition + ") && (" + child + ")"
        }
        expect_kind("RPAREN")
        return condition
    }
    if match_kind("ELSE") { return "true" }
    if match_kind("NONE") { return "w_is_none(" + subject + ")" }
    if check_kind("INT") or check_kind("FLOAT") or check_kind("STR") or check_kind("TRUE") or check_kind("FALSE") {
        let literal = parse_prefix_expr(false)
        return "w_eq(" + subject + ", " + literal.val + ")"
    }
    let name = expect_kind("IDENT").val
    if name == "_" { return "true" }
    let mut owner = ""
    let mut variant = name
    if match_kind("DOT") {
        owner = name
        variant = expect_kind("IDENT").val
    }
    let mut enum_owner = owner
    let mut arity = -1
    if owner == "Option" and variant == "None" { return "w_is_none(" + subject + ")" }
    if (owner == "Option" or owner == "") and variant == "Some" { arity = 1 enum_owner = "Option" }
    if (owner == "Result" or owner == "") and (variant == "Ok" or variant == "Err") { arity = 1 enum_owner = "Result" }
    if arity < 0 {
        for i in 0..len(g_enum_variant_names) {
            if g_enum_variant_names[i] == variant and (owner == "" or g_enum_variant_owners[i] == owner) {
                arity = g_enum_variant_arities[i]
                enum_owner = g_enum_variant_owners[i]
            }
        }
    }
    if arity >= 0 {
        let mut condition = "true"
        if enum_owner == "Option" and variant == "Some" { condition = "!w_is_none(" + subject + ")" }
        elif enum_owner == "Result" and variant == "Ok" { condition = "(" + subject + ").tag == W_OK" }
        elif enum_owner == "Result" and variant == "Err" { condition = "(" + subject + ").tag == W_ERR" }
        else { condition = "w_is_enum_variant(" + subject + ", \"" + enum_owner + "\", \"" + variant + "\")" }
        if match_kind("LPAREN") {
            let mut index = 0
            if not check_kind("RPAREN") {
                let mut payload = "w_peek_enum_payload(" + subject + ")"
                if enum_owner == "Option" { payload = "w_peek_optional(" + subject + ")" }
                elif enum_owner == "Result" and variant == "Ok" { payload = "w_peek_ok(" + subject + ")" }
                elif enum_owner == "Result" and variant == "Err" { payload = "w_peek_err(" + subject + ")" }
                if arity > 1 { payload = "(" + payload + ").as.tuple->items[0]" }
                let child = parse_pattern_condition(payload)
                condition = "(" + condition + ") && (" + child + ")"
                index = 1
                while match_kind("COMMA") {
                    if check_kind("RPAREN") { break }
                    if index >= arity { report_error("W2001", at_tok().line, at_tok().col, "too many enum pattern elements") }
                    let mut next_payload = "w_peek_enum_payload(" + subject + ")"
                    if enum_owner == "Option" { next_payload = "w_peek_optional(" + subject + ")" }
                    elif enum_owner == "Result" and variant == "Ok" { next_payload = "w_peek_ok(" + subject + ")" }
                    elif enum_owner == "Result" and variant == "Err" { next_payload = "w_peek_err(" + subject + ")" }
                    next_payload = "(" + next_payload + ").as.tuple->items[" + str(index) + "]"
                    let next_condition = parse_pattern_condition(next_payload)
                    condition = "(" + condition + ") && (" + next_condition + ")"
                    index = index + 1
                }
            }
            expect_kind("RPAREN")
            if index != arity { report_error("W2001", at_tok().line, at_tok().col, "enum pattern arity") }
        } elif arity != 0 {
            report_error("W2005", at_tok().line, at_tok().col, "enum pattern requires payload")
        }
        return condition
    }
    if owner != "" { return "w_is_enum_variant(" + subject + ", \"" + owner + "\", \"" + variant + "\")" }
    g_pattern_bind_lines.append("WVal v_" + name + " = w_clone(" + subject + ");")
    g_pattern_bind_names.append("v_" + name)
    return "true"
}

fn parse_match_arms(subj_tmp: str, res: str) -> unit {
    let matched = new_aux("_match_taken")
    emit_line("bool " + matched + " = false;")
    while not check_kind("RBRACE") and not is_eof() {
        let empty_bindings: list[str] = []
        g_pattern_bind_lines = empty_bindings
        g_pattern_bind_names = empty_bindings
        let condition = parse_pattern_condition(subj_tmp)
        emit_line("if (!" + matched + " && (" + condition + ")) {")
        push_scope("block")
        for binding in g_pattern_bind_lines { emit_line(binding) }
        for binding_name in g_pattern_bind_names { register_var(binding_name) }
        let has_guard = match_kind("IF")
        if has_guard {
            let guard = parse_expr(0, false)
            emit_line("if ((" + guard.val + ").as.b) {")
            push_scope("block")
        }
        expect_kind("FAT_ARROW")
        if check_kind("LBRACE") {
            let arm_value = parse_block_expr()
            emit_line("w_assign(&" + res + ", " + own_expr(arm_value) + ");")
        } else {
            let arm_value = parse_expr(0, true)
            emit_line("w_assign(&" + res + ", " + own_expr(arm_value.val) + ");")
        }
        emit_line(matched + " = true;")
        if has_guard { pop_scope() emit_line("}") }
        pop_scope()
        emit_line("}")
        match_kind("COMMA")
    }
}

fn parse_prefix_expr(allow_struct: bool) -> ExprRes {
    let tok = at_tok()
    if check_kind("PIPE") { return parse_lambda() }
    if match_kind("INT") {
        return ExprRes { val: "w_int(" + tok.val + "LL)", lref: "" }
    }
    if match_kind("FLOAT") {
        return ExprRes { val: "w_float(" + tok.val + ")", lref: "" }
    }
    if match_kind("STR") {
        return ExprRes { val: "w_str_n(" + escape_c_str(tok.val) + ", " + str(len(bytes(tok.val))) + ")", lref: "" }
    }
    if match_kind("TRUE") {
        return ExprRes { val: "w_bool(true)", lref: "" }
    }
    if match_kind("FALSE") {
        return ExprRes { val: "w_bool(false)", lref: "" }
    }
    if match_kind("NONE") {
        return ExprRes { val: "w_none()", lref: "" }
    }
    if match_kind("THIS") {
        return ExprRes { val: "v_self", lref: "&v_self" }
    }
    if match_kind("SUPER") {
        return ExprRes { val: "v_super", lref: "&v_super" }
    }
    if match_kind("NEW") {
        let cname_tok = expect_kind("IDENT")
        expect_kind("LPAREN")
        let mut args_c: list[str] = []
        if not check_kind("RPAREN") {
            let a0 = parse_expr(0, true)
            args_c.append(snapshot_value(a0.val))
            while match_kind("COMMA") {
                if check_kind("RPAREN") {
                    break
                }
                let an = parse_expr(0, true)
                args_c.append(snapshot_value(an.val))
            }
        }
        expect_kind("RPAREN")
        let mut joined = ""
        for idx in 0..len(args_c) {
            if idx > 0 {
                joined = joined + ", "
            }
            joined = joined + args_c[idx]
        }
        return bind_call("w_new_" + cname_tok.val + "(" + joined + ")")
    }
    if match_kind("IDENT") {
        let name = tok.val
        if name == "None" { return ExprRes { val: "w_none()", lref: "" } }
        let function_index = sem_function(name)
        if function_index >= 0 and len(sem_functions[function_index].type_params) > 0 and match_kind("LBRACKET") {
            while not check_kind("RBRACKET") and not is_eof() {
                parse_type_ann()
                if not match_kind("COMMA") { break }
            }
            expect_kind("RBRACKET")
        }
        let generic_type = sem_generic_type(name)
        if generic_type >= 0 and match_kind("LBRACKET") {
            while not check_kind("RBRACKET") and not is_eof() {
                parse_type_ann()
                if not match_kind("COMMA") { break }
            }
            expect_kind("RBRACKET")
        }
        if allow_struct and check_kind("LBRACE") {
            let p1 = peek_tok(1)
            let p2 = peek_tok(2)
            if p1.kind == "RBRACE" or p1.kind == "IDENT" and p2.kind == "COLON" {
                advance_tok()
                let mut f_names: list[str] = []
                let mut f_vals: list[str] = []
                while not check_kind("RBRACE") and not is_eof() {
                    let f_tok = expect_kind("IDENT")
                    expect_kind("COLON")
                    let f_v = parse_expr(0, true)
                    f_names.append("\"" + f_tok.val + "\"")
                    f_vals.append(snapshot_value(f_v.val))
                    match_kind("COMMA")
                }
                expect_kind("RBRACE")
                if len(f_names) == 0 {
                    return bind_call("w_make_struct(\"" + name + "\", 0, NULL, NULL)")
                }
                let k_tmp = new_aux("_k")
                let v_tmp = new_aux("_v")
                let mut k_joined = ""
                let mut v_joined = ""
                for idx in 0..len(f_names) {
                    if idx > 0 {
                        k_joined = k_joined + ", "
                        v_joined = v_joined + ", "
                    }
                    k_joined = k_joined + f_names[idx]
                    v_joined = v_joined + f_vals[idx]
                }
                let cnt = str(len(f_names))
                emit_line("const char* " + k_tmp + "[" + cnt + "] = { " + k_joined + " };")
                emit_line("WVal " + v_tmp + "[" + cnt + "] = { " + v_joined + " };")
                return bind_call("w_make_struct(\"" + name + "\", " + cnt + ", " + k_tmp + ", " + v_tmp + ")")
            }
        }
        if not check_kind("LPAREN") and not is_bound_variable("v_" + name) and sem_function(name) >= 0 {
            return emit_function_value(name)
        }
        if not is_bound_variable("v_" + name) {
            let mut variant_owner = ""
            let mut variant_arity = -1
            for variant_index in 0..len(g_enum_variant_names) {
                if g_enum_variant_names[variant_index] == name {
                    variant_owner = g_enum_variant_owners[variant_index]
                    variant_arity = g_enum_variant_arities[variant_index]
                }
            }
            if variant_arity == 0 { return ExprRes { val: "w_enum(\"" + variant_owner + "\", \"" + name + "\")", lref: "" } }
            if variant_arity > 0 { return ExprRes { val: "enum::" + variant_owner + "::" + name, lref: "" } }
        }
        return ExprRes { val: "v_" + name, lref: "&v_" + name }
    }
    if match_kind("MINUS") {
        # SPEC 5 puts unary at level 3, tighter than multiplicative (level 4), so the
        # operand stops below `* / %`. A literal operand folds into a negative constant
        # so negated whole-number literals emit identically to W0's C99 backend, which
        # is what keeps the three-stage bootstrap hash a fixed point.
        if check_kind("INT") {
            let mut lit = advance_tok().val
            let digits = slice(lit, 0, len(lit))
            return ExprRes { val: "w_int(-" + digits + "LL)", lref: "" }
        }
        let op_r = parse_expr(9, allow_struct)
        return ExprRes { val: "w_neg(" + op_r.val + ")", lref: "" }
    }
    if match_kind("NOT") {
        let op_r = parse_expr(9, allow_struct)
        return ExprRes { val: "w_bool(!(" + op_r.val + ").as.b)", lref: "" }
    }
    if match_kind("LPAREN") {
        if match_kind("RPAREN") {
            return bind_call("w_make_tuple(0, NULL)")
        }
        let first = parse_expr(0, true)
        if match_kind("COMMA") {
            let mut t_elems: list[str] = [snapshot_value(first.val)]
            if not check_kind("RPAREN") {
                let second = parse_expr(0, true)
                t_elems.append(snapshot_value(second.val))
                while match_kind("COMMA") {
                    if check_kind("RPAREN") {
                        break
                    }
                    let nxt = parse_expr(0, true)
                    t_elems.append(snapshot_value(nxt.val))
                }
            }
            expect_kind("RPAREN")
            let arr_tmp = new_aux("_arr")
            let mut joined = ""
            for idx in 0..len(t_elems) {
                if idx > 0 {
                    joined = joined + ", "
                }
                joined = joined + t_elems[idx]
            }
            let cnt = str(len(t_elems))
            emit_line("WVal " + arr_tmp + "[" + cnt + "] = { " + joined + " };")
            return bind_call("w_make_tuple(" + cnt + ", " + arr_tmp + ")")
        }
        expect_kind("RPAREN")
        return first
    }
    if match_kind("LBRACKET") {
        let mut elems: list[str] = []
        if not check_kind("RBRACKET") {
            let first = parse_expr(0, true)
            elems.append(snapshot_value(first.val))
            while match_kind("COMMA") {
                if check_kind("RBRACKET") {
                    break
                }
                let nxt = parse_expr(0, true)
                elems.append(snapshot_value(nxt.val))
            }
        }
        expect_kind("RBRACKET")
        if len(elems) == 0 {
            return bind_call("w_make_list(0, NULL)")
        }
        let arr_tmp = new_aux("_arr")
        let mut joined = ""
        for idx in 0..len(elems) {
            if idx > 0 {
                joined = joined + ", "
            }
            joined = joined + elems[idx]
        }
        let cnt = str(len(elems))
        emit_line("WVal " + arr_tmp + "[" + cnt + "] = { " + joined + " };")
        return bind_call("w_make_list(" + cnt + ", " + arr_tmp + ")")
    }
    if match_kind("LBRACE") {
        let mut d_keys: list[str] = []
        let mut d_vals: list[str] = []
        if not check_kind("RBRACE") {
            let k0 = parse_expr(0, true)
            if len(k0.val) >= 7 and slice(k0.val, 0, 7) == "w_float" {
                report_error("W2010", at_tok().line, at_tok().col, "invalid dictionary key type: float is not allowed as dictionary key")
            }
            expect_kind("COLON")
            let key0 = snapshot_value(k0.val)
            let v0 = parse_expr(0, true)
            d_keys.append(key0)
            d_vals.append(snapshot_value(v0.val))
            while match_kind("COMMA") {
                if check_kind("RBRACE") {
                    break
                }
                let kn = parse_expr(0, true)
                if len(kn.val) >= 7 and slice(kn.val, 0, 7) == "w_float" {
                    report_error("W2010", at_tok().line, at_tok().col, "invalid dictionary key type: float is not allowed as dictionary key")
                }
                expect_kind("COLON")
                let keyn = snapshot_value(kn.val)
                let vn = parse_expr(0, true)
                d_keys.append(keyn)
                d_vals.append(snapshot_value(vn.val))
            }
        }
        expect_kind("RBRACE")
        if len(d_keys) == 0 {
            return bind_call("w_make_dict(0, NULL, NULL)")
        }
        let k_tmp = new_temp()
        let v_tmp = new_temp()
        let mut kj = ""
        let mut vj = ""
        for idx in 0..len(d_keys) {
            if idx > 0 {
                kj = kj + ", "
                vj = vj + ", "
            }
            kj = kj + d_keys[idx]
            vj = vj + d_vals[idx]
        }
        let cnt = str(len(d_keys))
        emit_line("WVal " + k_tmp + "[" + cnt + "] = { " + kj + " };")
        emit_line("WVal " + v_tmp + "[" + cnt + "] = { " + vj + " };")
        return bind_call("w_make_dict(" + cnt + ", " + k_tmp + ", " + v_tmp + ")")
    }
    if check_kind("IF") {
        return parse_if_expr()
    }
    if check_kind("MATCH") {
        return parse_match_expr()
    }
    advance_tok()
    return ExprRes { val: "w_unit()", lref: "" }
}

fn parse_expr(min_prec: int, allow_struct: bool) -> ExprRes {
    let expression_start = g_pos
    let statements_before = g_cur_stmts
    let scopes_before = g_scope_stack
    let temps_before = g_temp_id
    let aux_before = g_aux_id
    let mut left = parse_prefix_expr(allow_struct)
    while true {
        while true {
            if check_kind("LPAREN") {
                let call_tok = at_tok()
                let mut collection = false
                for position in sem_collection_call_positions { if position == g_pos + 1 { collection = true } }
                for position in sem_indirect_positions {
                    if position == g_pos + 1 { left = ExprRes { val: snapshot_value(left.val), lref: "" } }
                }
                left = snapshot_callee(left, collection)
                advance_tok()
                let mut args_c: list[str] = []
                if not check_kind("RPAREN") {
                    let a0 = parse_expr(0, true)
                    args_c.append(snapshot_value(a0.val))
                    while match_kind("COMMA") {
                        if check_kind("RPAREN") {
                            break
                        }
                        let an = parse_expr(0, true)
                        args_c.append(snapshot_value(an.val))
                    }
                }
                expect_kind("RPAREN")
                left = emit_call(left, args_c, collection, call_tok.line, call_tok.col)
            } elif check_kind("DOT") {
                let projection_position = g_pos + 1
                advance_tok()
                let prop_tok = expect_kind("IDENT")
                let prop = prop_tok.val
                if projection_is_mutated() {
                    for position in sem_class_projection_positions {
                        if position == projection_position {
                            let held = snapshot_value(left.val)
                            left = ExprRes { val: held, lref: "&" + held }
                        }
                    }
                }
                if len(left.val) >= 2 and slice(left.val, 0, 2) == "v_" {
                    let raw_obj = slice(left.val, 2, len(left.val))
                    if is_enum_name(raw_obj) or raw_obj == "Option" or raw_obj == "Result" {
                        if raw_obj == "Option" and prop == "None" { left = ExprRes { val: "w_none()", lref: "" } }
                        elif (raw_obj == "Option" and prop == "Some") or (raw_obj == "Result" and (prop == "Ok" or prop == "Err")) { left = ExprRes { val: "enum::" + raw_obj + "::" + prop, lref: "" } }
                        else {
                            let mut variant_arity = 0
                            for variant_index in 0..len(g_enum_variant_names) {
                                if g_enum_variant_names[variant_index] == prop and g_enum_variant_owners[variant_index] == raw_obj { variant_arity = g_enum_variant_arities[variant_index] }
                            }
                            if variant_arity > 0 { left = ExprRes { val: "enum::" + raw_obj + "::" + prop, lref: "" } }
                            else { left = ExprRes { val: "w_enum(\"" + raw_obj + "\", \"" + prop + "\")", lref: "" } }
                        }
                    } else {
                        left = ExprRes { val: "w_member_get(" + left.val + ", \"" + prop + "\")", lref: "w_member_ref(" + clean_lref(left.lref) + ", \"" + prop + "\")::" + prop + "::" + clean_lref(left.lref) + "::" + left.val }
                    }
                } else {
                    left = ExprRes { val: "w_member_get(" + left.val + ", \"" + prop + "\")", lref: "w_member_ref(" + clean_lref(left.lref) + ", \"" + prop + "\")::" + prop + "::" + clean_lref(left.lref) + "::" + left.val }
                }
                if not projection_is_mutated() and not check_kind("LPAREN") and left.lref != "" {
                    left = ExprRes { val: bind_call("w_clone(" + left.val + ")").val, lref: left.lref }
                }
            } elif check_kind("LBRACKET") {
                let bracket_tok = at_tok()
                let mutated = projection_is_mutated()
                advance_tok()
                let mut object_value = left.val
                if not mutated {
                    object_value = snapshot_value(left.val)
                }
                let mut idx_r = parse_expr(0, true)
                expect_kind("RBRACKET")
                if mutated {
                    idx_r = ExprRes { val: snapshot_value(idx_r.val), lref: idx_r.lref }
                }
                let source_args = escape_c_str(g_in_path) + ", " + str(bracket_tok.line) + ", " + str(bracket_tok.col)
                let index_lref = "w_index_ref_at(" + clean_lref(left.lref) + ", " + idx_r.val + ", " + source_args + ")"
                if mutated {
                    left = ExprRes { val: "w_index_get_at(" + left.val + ", " + idx_r.val + ", " + source_args + ")", lref: index_lref }
                } else {
                    left = ExprRes { val: bind_call("w_index_get_owned_at(" + object_value + ", " + idx_r.val + ", " + source_args + ")").val, lref: index_lref }
                }
            } elif check_kind("QUESTION") {
                advance_tok()
                let tmp = new_temp()
                declare_owned_var(tmp, own_expr(left.val))
                emit_line("if (" + str(not g_fn_fallible) + " && (" + tmp + ".tag == W_NONE)) {")
                emit_cleanup_until_fn_indented()
                emit_line("    return w_none();")
                emit_line("}")
                let err_hold = new_aux("_err")
                emit_line("if (" + str(g_fn_fallible) + " && (" + tmp + ".tag == W_ERR)) {")
                emit_line("    WVal " + err_hold + " = w_clone(" + tmp + ");")
                emit_cleanup_until_fn_indented()
                emit_line("    return " + err_hold + ";")
                emit_line("}")
                let unw = new_temp()
                let mut unwrap_helper = "w_unwrap_optional"
                if g_fn_fallible { unwrap_helper = "w_unwrap_ok" }
                declare_owned_var(unw, unwrap_helper + "(" + tmp + ")")
                left = ExprRes { val: unw, lref: "" }
            } elif check_kind("ELSE") {
                advance_tok()
                let mut err_name = ""
                if check_kind("IDENT") {
                    let et = advance_tok()
                    err_name = et.val
                }
                let tmp = new_temp()
                declare_owned_var(tmp, own_expr(left.val))
                let res = new_temp()
                declare_owned_var(res, "w_unit()")
                emit_line("if (" + tmp + ".tag == W_ERR || " + tmp + ".tag == W_NONE) {")
                push_scope("block")
                let saved = g_cur_stmts
                let empty: list[str] = []
                g_cur_stmts = empty
                if err_name != "" {
                    declare_owned_var("v_" + err_name, "w_unwrap_err(" + tmp + ")")
                }
                let hv = parse_block_expr()
                emit_line("w_assign(&" + res + ", " + own_expr(hv) + ");")
                pop_scope()
                let h_lines = g_cur_stmts
                g_cur_stmts = saved
                for l in h_lines {
                    emit_line("    " + l)
                }
                emit_line("} else {")
                emit_line("    w_assign(&" + res + ", w_unwrap_success(" + tmp + "));")
                emit_line("}")
                left = ExprRes { val: res, lref: "" }
            } else {
                break
            }
        }
        let op_tok = at_tok()
        let prec = op_precedence(op_tok.kind)
        if prec <= min_prec {
            break
        }
        advance_tok()
        let mut next_min = prec
        if op_tok.kind == "ASSIGN" or op_tok.kind == "QQ" {
            next_min = prec - 1
        }
        if op_tok.kind == "AND" {
            let res = new_temp()
            declare_owned_var(res, "w_bool(false)")
            emit_line("if ((" + left.val + ").as.b) {")
            push_scope("block")
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty
            let rhs = parse_expr(next_min, allow_struct)
            emit_line(res + " = w_bool((" + rhs.val + ").as.b);")
            pop_scope()
            let r_lines = g_cur_stmts
            g_cur_stmts = saved
            for l in r_lines {
                emit_line("    " + l)
            }
            emit_line("}")
            left = ExprRes { val: res, lref: "" }
        } elif op_tok.kind == "OR" {
            let res = new_temp()
            declare_owned_var(res, "w_bool(true)")
            emit_line("if (!(" + left.val + ").as.b) {")
            push_scope("block")
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty
            let rhs = parse_expr(next_min, allow_struct)
            emit_line(res + " = w_bool((" + rhs.val + ").as.b);")
            pop_scope()
            let r_lines = g_cur_stmts
            g_cur_stmts = saved
            for l in r_lines {
                emit_line("    " + l)
            }
            emit_line("}")
            left = ExprRes { val: res, lref: "" }
        } elif op_tok.kind == "QQ" {
            let res = new_temp()
            declare_owned_var(res, own_expr(left.val))
            emit_line("if (" + res + ".tag == W_NONE) {")
            push_scope("block")
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty
            let rhs = parse_expr(next_min, allow_struct)
            emit_line("w_assign(&" + res + ", " + own_expr(rhs.val) + ");")
            pop_scope()
            let r_lines = g_cur_stmts
            g_cur_stmts = saved
            for l in r_lines {
                emit_line("    " + l)
            }
            emit_line("} else {")
            emit_line("    w_assign(&" + res + ", w_unwrap_optional(" + res + "));")
            emit_line("}")
            left = ExprRes { val: res, lref: "" }
        } else {
            if op_tok.kind != "ASSIGN" {
                left = ExprRes { val: snapshot_value(left.val), lref: left.lref }
            }
            let right = parse_expr(next_min, allow_struct)
            if op_tok.kind == "ASSIGN" {
                if (len(left.val) < 2 or slice(left.val, 0, 2) != "v_") and left.lref == "" {
                    report_error("W2002", op_tok.line, op_tok.col, "invalid assignment target")
                }
                let rhs_hold = new_aux("_rhs")
                declare_owned_var(rhs_hold, own_expr(right.val))
                if len(left.val) >= 2 and slice(left.val, 0, 2) == "v_" {
                    emit_line("w_assign(&" + left.val + ", " + "w_move(&" + rhs_hold + "));")
                    left = ExprRes { val: left.val, lref: left.lref }
                } else {
                    let target_ref = clean_lref(left.lref)
                    emit_line("w_assign(" + target_ref + ", " + "w_move(&" + rhs_hold + "));")
                    left = ExprRes { val: "w_unit()", lref: "" }
                }
            } elif op_tok.kind == "DOT_DOT" {
                left = bind_call("w_make_range(" + left.val + ", " + right.val + ", false)")
            } elif op_tok.kind == "DOT_DOT_EQ" {
                left = bind_call("w_make_range(" + left.val + ", " + right.val + ", true)")
            } elif op_tok.kind == "PLUS" {
                left = ExprRes { val: bind_call("w_add(" + left.val + ", " + right.val + ")").val, lref: "" }
            } elif op_tok.kind == "MINUS" {
                left = ExprRes { val: "w_sub(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "STAR" {
                left = ExprRes { val: "w_mul(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "SLASH" {
                left = ExprRes { val: "w_div_at(" + left.val + ", " + right.val + ", " + escape_c_str(g_in_path) + ", " + str(op_tok.line) + ", " + str(op_tok.col) + ")", lref: "" }
            } elif op_tok.kind == "PERCENT" {
                left = ExprRes { val: "w_mod_at(" + left.val + ", " + right.val + ", " + escape_c_str(g_in_path) + ", " + str(op_tok.line) + ", " + str(op_tok.col) + ")", lref: "" }
            } elif op_tok.kind == "LT" {
                left = ExprRes { val: "w_lt(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "LTE" {
                left = ExprRes { val: "w_le(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "GT" {
                left = ExprRes { val: "w_gt(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "GTE" {
                left = ExprRes { val: "w_ge(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "EQ" {
                left = ExprRes { val: "w_bool(w_eq(" + left.val + ", " + right.val + "))", lref: "" }
            } elif op_tok.kind == "NEQ" {
                left = ExprRes { val: "w_bool(!w_eq(" + left.val + ", " + right.val + "))", lref: "" }
            }
        }
    }
    let mut needs_result_lift = false
    for position in sem_result_lift_positions { if position == expression_start + 1 { needs_result_lift = true } }
    if needs_result_lift { left = bind_call("w_ok(" + own_expr(left.val) + ")") }
    return left
}

fn parse_lambda() -> ExprRes {
    let token = expect_kind("PIPE")
    let mut index = -1
    for i in 0..len(sem_lambdas) { if sem_lambdas[i].position == g_pos { index = i } }
    if index < 0 { report_error("W9999", token.line, token.col, "missing checked closure") }
    let lambda = sem_lambdas[index]
    while not check_kind("PIPE") {
        expect_kind("IDENT")
        if match_kind("COLON") { parse_type_ann() }
        if not match_kind("COMMA") { break }
    }
    expect_kind("PIPE")
    if match_kind("ARROW") { parse_type_ann() }
    let saved_statements = g_cur_stmts
    let saved_scopes = g_scope_stack
    let saved_borrowed = g_borrowed_vars
    let saved_fallible = g_fn_fallible
    let saved_error = g_cur_err_type
    let empty_statements: list[str] = []
    let empty_scopes: list[CleanupScope] = []
    let mut borrowed: list[str] = []
    g_cur_stmts = empty_statements
    g_scope_stack = empty_scopes
    g_fn_fallible = false
    g_cur_err_type = ""
    push_scope("fn")
    for i in 0..len(lambda.params) {
        let variable = "v_" + lambda.params[i]
        emit_line("WVal " + variable + " = argv[" + str(i) + "];")
        borrowed.append(variable)
    }
    for i in 0..len(lambda.captures) {
        let variable = "v_" + lambda.captures[i]
        declare_owned_var(variable, "w_clone(environment.as.tuple->items[" + str(i) + "])")
    }
    g_borrowed_vars = borrowed
    let mut result = "w_unit()"
    if match_kind("FAT_ARROW") { result = parse_expr(0, true).val }
    else { result = parse_block_expr() }
    let returned = new_aux("_ret")
    emit_line("WVal " + returned + " = " + own_expr(result) + ";")
    pop_scope()
    emit_line("return " + returned + ";")
    let name = "w_lambda_" + str(index)
    let signature = "static WVal " + name + "(WVal environment, int32_t argc, const WVal* argv)"
    let mut definition = signature + " {\n"
    definition = definition + "    if (argc != " + str(len(lambda.params)) + ") { fprintf(stderr, \"[W4003] RuntimeError: Call arity mismatch\\n\"); exit(1); }\n"
    for line in g_cur_stmts { definition = definition + "    " + line + "\n" }
    definition = definition + "}"
    g_protos.append(signature + ";")
    g_fn_defs.append(definition)
    g_cur_stmts = saved_statements
    g_scope_stack = saved_scopes
    g_borrowed_vars = saved_borrowed
    g_fn_fallible = saved_fallible
    g_cur_err_type = saved_error
    let mut captures = ""
    for i in 0..len(lambda.captures) {
        if i > 0 { captures = captures + ", " }
        captures = captures + "v_" + lambda.captures[i]
    }
    let mut environment = "w_make_tuple(0, NULL)"
    if len(lambda.captures) > 0 {
        let array = new_aux("_captures")
        emit_line("WVal " + array + "[" + str(len(lambda.captures)) + "] = { " + captures + " };")
        environment = "w_make_tuple(" + str(len(lambda.captures)) + ", " + array + ")"
    }
    return bind_call("w_function_new(" + name + ", " + environment + ")")
}
