
fn parse_let_stmt(is_global: bool) -> unit {
    expect_kind("LET")
    match_kind("MUT")
    let name_tok = expect_kind("IDENT")
    if match_kind("COLON") {
        parse_type_ann()
    }
    expect_kind("ASSIGN")
    let mut val_r = ExprRes { val: "", lref: "" }
    if is_global and check_kind("LBRACKET") and peek_tok(1).kind == "RBRACKET" {
        advance_tok()
        advance_tok()
        val_r = ExprRes { val: "w_make_list(0, NULL)", lref: "" }
    } else {
        val_r = parse_expr(0, true)
    }
    let mut vname = "v_" + name_tok.val
    if is_global and g_ns != "" {
        vname = "v_" + g_ns + "_" + name_tok.val
    }
    if is_global {
        g_globals.append(vname)
        emit_line("w_assign(&" + vname + ", " + own_expr(val_r.val) + ");")
    } else {
        declare_owned_var(vname, own_expr(val_r.val))
    }
}

fn parse_return_stmt() -> unit {
    let return_token = expect_kind("RETURN")
    if check_kind("RBRACE") or is_eof() or at_tok().line > return_token.line {
        emit_cleanup_until_fn()
        if g_fn_fallible {
            emit_line("return w_ok(w_unit());")
        } else {
            emit_line("return w_unit();")
        }
        return
    }
    let val_r = parse_expr(0, true)
    let ret_hold = new_aux("_ret")
    emit_line("WVal " + ret_hold + " = " + own_expr(val_r.val) + ";")
    emit_cleanup_until_fn()
    if g_fn_fallible {
        emit_line("return w_wrap_result(" + ret_hold + ", \"" + g_cur_err_type + "\");")
    } else {
        emit_line("return " + ret_hold + ";")
    }
}

fn parse_while_stmt() -> unit {
    expect_kind("WHILE")
    emit_line("while (1) {")
    push_scope("loop")
    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    let cond_r = parse_expr(0, false)
    let cond_b = new_aux("_cond")
    emit_line("bool " + cond_b + " = (" + cond_r.val + ").as.b;")
    if has_cleanup_until_loop() {
        emit_line("if (!" + cond_b + ") {")
        emit_cleanup_until_loop_indented()
        emit_line("    break;")
        emit_line("}")
    } else {
        emit_line("if (!" + cond_b + ") break;")
    }
    let body_v = parse_block_expr()
    emit_line("(void)" + body_v + ";")
    pop_scope()
    let inner = g_cur_stmts
    g_cur_stmts = saved
    for l in inner {
        emit_line("    " + l)
    }
    emit_line("}")
}

fn parse_for_stmt() -> unit {
    expect_kind("FOR")
    let pat0 = expect_kind("IDENT")
    let mut pat_names: list[str] = [pat0.val]
    while match_kind("COMMA") {
        let pn = expect_kind("IDENT")
        pat_names.append(pn.val)
    }
    expect_kind("IN")
    emit_line("{")
    push_scope("block")
    let saved_outer = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    let iter_r = parse_expr(0, false)
    let iter_tmp = new_temp()
    let idx_tmp = new_aux("_idx")
    let item_tmp = new_aux("_item")
    declare_owned_var(iter_tmp, own_expr(iter_r.val))
    emit_line("for (int32_t " + idx_tmp + " = 0; " + idx_tmp + " < " + iter_tmp + ".as.list->len; " + idx_tmp + "++) {")
    push_scope("loop")
    let saved_loop = g_cur_stmts
    g_cur_stmts = empty
    emit_line("WVal " + item_tmp + " = " + iter_tmp + ".as.list->data[" + idx_tmp + "];")
    if len(pat_names) == 1 {
        declare_owned_var("v_" + pat_names[0], "w_clone(" + item_tmp + ")")
    } else {
        for pi in 0..len(pat_names) {
            declare_owned_var("v_" + pat_names[pi], "w_clone((" + item_tmp + ").as.tuple->items[" + str(pi) + "])")
        }
    }
    let body_v = parse_block_expr()
    emit_line("(void)" + body_v + ";")
    pop_scope()
    let loop_lines = g_cur_stmts
    g_cur_stmts = saved_loop
    for l in loop_lines {
        emit_line("    " + l)
    }
    emit_line("}")
    pop_scope()
    let outer_lines = g_cur_stmts
    g_cur_stmts = saved_outer
    for l in outer_lines {
        emit_line("    " + l)
    }
    emit_line("}")
}

fn parse_struct_decl() -> unit {
    expect_kind("STRUCT")
    expect_kind("IDENT")
    expect_kind("LBRACE")
    while not check_kind("RBRACE") and not is_eof() {
        expect_kind("IDENT")
        expect_kind("COLON")
        if check_kind("RBRACE") or check_kind("EOF") {
            report_error("W0001", at_tok().line, at_tok().col, "expected type name in struct field")
        }
        parse_type_ann()
        match_kind("COMMA")
    }
    expect_kind("RBRACE")
}

fn parse_enum_decl() -> unit {
    expect_kind("ENUM")
    let name_tok = expect_kind("IDENT")
    g_enums.append(name_tok.val)
    expect_kind("LBRACE")
    while not check_kind("RBRACE") and not is_eof() {
        expect_kind("IDENT")
        match_kind("COMMA")
    }
    expect_kind("RBRACE")
}

fn parse_interface_decl() -> unit {
    expect_kind("INTERFACE")
    expect_kind("IDENT")
    expect_kind("LBRACE")
    while not check_kind("RBRACE") and not is_eof() {
        expect_kind("FN")
        expect_kind("IDENT")
        expect_kind("LPAREN")
        if not check_kind("RPAREN") {
            expect_kind("IDENT")
            expect_kind("COLON")
            parse_type_ann()
            while match_kind("COMMA") {
                if check_kind("RPAREN") {
                    break
                }
                expect_kind("IDENT")
                expect_kind("COLON")
                parse_type_ann()
            }
        }
        expect_kind("RPAREN")
        if match_kind("ARROW") {
            parse_type_ann()
        }
        match_kind("COMMA")
    }
    expect_kind("RBRACE")
}

fn parse_class_decl() -> unit {
    expect_kind("CLASS")
    let cname_tok = expect_kind("IDENT")
    let cls_name = cname_tok.val
    let mut sup_name = ""
    if match_kind("EXTENDS") {
        let s_tok = expect_kind("IDENT")
        sup_name = s_tok.val
    }
    if match_kind("IMPLEMENTS") {
        expect_kind("IDENT")
        while match_kind("COMMA") {
            expect_kind("IDENT")
        }
    }
    let mut f_names: list[str] = []
    let mut f_defaults: list[str] = []
    let mut m_names: list[str] = []
    let mut m_arities: list[int] = []
    let mut init_p: list[str] = []
    let prev_cls = g_cur_class
    let prev_sup = g_cur_super
    g_cur_class = cls_name
    g_cur_super = sup_name
    expect_kind("LBRACE")
    while not check_kind("RBRACE") and not is_eof() {
        let mut is_pub = true
        if check_kind("PUBLIC") {
            advance_tok()
            is_pub = true
        } elif check_kind("PRIVATE") {
            advance_tok()
            is_pub = false
        }
        if check_kind("FN") {
            advance_tok()
            let m_tok = expect_kind("IDENT")
            let mname = m_tok.val
            expect_kind("LPAREN")
            let mut p_names: list[str] = []
            if not check_kind("RPAREN") {
                let p0 = expect_kind("IDENT")
                expect_kind("COLON")
                parse_type_ann()
                p_names.append(p0.val)
                while match_kind("COMMA") {
                    if check_kind("RPAREN") {
                        break
                    }
                    let pn = expect_kind("IDENT")
                    expect_kind("COLON")
                    parse_type_ann()
                    p_names.append(pn.val)
                }
            }
            expect_kind("RPAREN")
            let mut fallible = false
            if match_kind("ARROW") {
                fallible = parse_type_ann()
            }
            m_names.append(mname)
            m_arities.append(len(p_names))
            if mname == "init" {
                init_p = p_names
            } else {
                register_dispatch(mname, len(p_names))
            }
            let mut m_sig = "WVal v_self"
            for idx in 0..len(p_names) {
                m_sig = m_sig + ", WVal v_" + p_names[idx]
            }
            let c_mname = "w_method_" + cls_name + "__" + mname
            g_protos.append("static WVal " + c_mname + "(" + m_sig + ");")
            let prev_fall = g_fn_fallible
            let prev_err = g_cur_err_type
            g_fn_fallible = fallible
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty
            push_scope("fn")
            let ret_v = parse_block_expr()
            let ret_hold = new_aux("_ret")
            emit_line("WVal " + ret_hold + " = " + own_expr(ret_v) + ";")
            pop_scope()
            if g_fn_fallible {
                emit_line("return w_wrap_result(" + ret_hold + ", \"" + g_cur_err_type + "\");")
            } else {
                emit_line("return " + ret_hold + ";")
            }
            let body_lines = g_cur_stmts
            g_cur_stmts = saved
            g_fn_fallible = prev_fall
            g_cur_err_type = prev_err
            let mut m_str = "static WVal " + c_mname + "(" + m_sig + ") {\n"
            for l in body_lines {
                m_str = m_str + "    " + l + "\n"
            }
            m_str = m_str + "}"
            g_fn_defs.append(m_str)
        } else {
            let f_tok = expect_kind("IDENT")
            expect_kind("COLON")
            let f_def = parse_field_default()
            match_kind("COMMA")
            f_names.append(f_tok.val)
            f_defaults.append(f_def)
        }
    }
    expect_kind("RBRACE")
    g_cur_class = prev_cls
    g_cur_super = prev_sup
    g_classes.append(ClassMeta { name: cls_name, super_name: sup_name, field_names: f_names, field_defaults: f_defaults, method_names: m_names, method_arities: m_arities, init_params: init_p })
    let mut lineage: list[int] = []
    let mut cur_c = cls_name
    while cur_c != "" {
        let cidx = find_class_meta_idx(cur_c)
        if cidx == -1 {
            break
        }
        lineage.append(cidx)
        cur_c = g_classes[cidx].super_name
    }
    let mut all_fnames: list[str] = []
    let mut all_fdefs: list[str] = []
    let mut li = len(lineage) - 1
    while li >= 0 {
        let cm = g_classes[lineage[li]]
        for fi in 0..len(cm.field_names) {
            all_fnames.append(cm.field_names[fi])
            all_fdefs.append(cm.field_defaults[fi])
        }
        li = li - 1
    }
    let init_owner = find_class_method_owner(cls_name, "init")
    let mut eff_init_p: list[str] = []
    if init_owner != "" {
        let oidx = find_class_meta_idx(init_owner)
        if oidx != -1 {
            eff_init_p = g_classes[oidx].init_params
        }
    }
    let mut new_sig = "void"
    let mut init_call_args = "v_self"
    if len(eff_init_p) > 0 {
        new_sig = ""
        for idx in 0..len(eff_init_p) {
            if idx > 0 {
                new_sig = new_sig + ", "
            }
            new_sig = new_sig + "WVal v_" + eff_init_p[idx]
            init_call_args = init_call_args + ", v_" + eff_init_p[idx]
        }
    }
    g_protos.append("static const WClassVTable w_vtable_" + cls_name + ";")
    g_protos.append("static WVal w_new_" + cls_name + "(" + new_sig + ");")
    let mut new_str = "static WVal w_new_" + cls_name + "(" + new_sig + ") {\n"
    if len(all_fnames) > 0 {
        let mut kj = ""
        let mut vj = ""
        for fi in 0..len(all_fnames) {
            if fi > 0 {
                kj = kj + ", "
                vj = vj + ", "
            }
            kj = kj + "\"" + all_fnames[fi] + "\""
            vj = vj + all_fdefs[fi]
        }
        let fcnt = str(len(all_fnames))
        new_str = new_str + "    const char* _k[" + fcnt + "] = { " + kj + " };\n"
        new_str = new_str + "    WVal _v[" + fcnt + "] = { " + vj + " };\n"
        new_str = new_str + "    WVal v_self = w_make_object(\"" + cls_name + "\", " + fcnt + ", _k, _v);\n"
        new_str = new_str + "    w_release_array(" + fcnt + ", _v);\n"
    } else {
        new_str = new_str + "    WVal v_self = w_make_object(\"" + cls_name + "\", 0, NULL, NULL);\n"
    }
    new_str = new_str + "    v_self.as.st->vtable = &w_vtable_" + cls_name + ";\n"
    if init_owner != "" {
        new_str = new_str + "    w_release(w_method_" + init_owner + "__init(" + init_call_args + "));\n"
    }
    new_str = new_str + "    return v_self;\n}"
    g_fn_defs.append(new_str)
}

fn emit_oop_dispatchers() -> unit {
    let mut adapters: list[str] = []
    let mut tables: list[str] = []
    for class_ in g_classes {
        let mut slots: list[str] = []
        for di in 0..len(g_dispatch_names) {
            let name = g_dispatch_names[di]
            let arity = g_dispatch_arities[di]
            let owner = find_class_method_owner(class_.name, name)
            if owner == "" or find_class_method_arity(class_.name, name) != arity { slots.append("NULL") }
            else {
                let adapter = "w_vinvoke_" + owner + "__" + name
                slots.append(adapter)
                if not module_contains(adapters, adapter) {
                    adapters.append(adapter)
                    let mut arguments = "receiver"
                    for i in 0..arity { arguments = arguments + ", argv[" + str(i) + "]" }
                    g_fn_defs.append("static WVal " + adapter + "(WVal receiver, int32_t argc, const WVal* argv) { (void)argc; (void)argv; return w_method_" + owner + "__" + name + "(" + arguments + "); }")
                }
            }
        }
        if len(slots) > 0 {
            let mut joined = ""
            for i in 0..len(slots) { if i > 0 { joined = joined + ", " } joined = joined + slots[i] }
            tables.append("static const WInvoke w_slots_" + class_.name + "[" + str(len(slots)) + "] = { " + joined + " };")
            tables.append("static const WClassVTable w_vtable_" + class_.name + " = { " + str(len(slots)) + ", w_slots_" + class_.name + " };")
        } else { tables.append("static const WClassVTable w_vtable_" + class_.name + " = { 0, NULL };") }
    }
    for table in tables { g_fn_defs.append(table) }
    for di in 0..len(g_dispatch_names) {
        let name = g_dispatch_names[di]
        let arity = g_dispatch_arities[di]
        let mut signature = "WVal v_self"
        let mut arguments = ""
        for i in 0..arity {
            signature = signature + ", WVal _a" + str(i)
            if i > 0 { arguments = arguments + ", " }
            arguments = arguments + "_a" + str(i)
        }
        if arity == 0 { arguments = "NULL" } else { arguments = "(WVal[]){ " + arguments + " }" }
        g_fn_defs.append("static WVal w_dispatch__" + name + "__" + str(arity) + "(" + signature + ") { return w_virtual_call(v_self, " + str(di) + ", " + str(arity) + ", " + arguments + "); }")
    }
}

fn parse_import_decl() -> unit {
    expect_kind("IMPORT")
    let path_tok = expect_kind("STR")
    let ns = extract_module_ns(path_tok.val)
    if is_module_name(ns) {
        return
    }
    g_modules.append(ns)
    let mod_src = read_file(path_tok.val) else err {
        ""
    }
    if mod_src == "" {
        return
    }
    let saved_tokens = g_tokens
    let saved_pos = g_pos
    let saved_ns = g_ns
    g_tokens = tokenize(mod_src)
    g_pos = 0
    g_ns = ns
    while not is_eof() {
        if match_kind("PUB") { continue }
        if check_kind("STRUCT") {
            parse_struct_decl()
        } elif check_kind("ENUM") {
            parse_enum_decl()
        } elif check_kind("INTERFACE") {
            parse_interface_decl()
        } elif check_kind("CLASS") {
            parse_class_decl()
        } elif check_kind("FN") {
            parse_fn_decl()
        } elif check_kind("LET") {
            parse_let_stmt(true)
        } else {
            let expr_r = parse_expr(0, true)
            emit_line("(void)" + expr_r.val + ";")
        }
    }
    g_tokens = saved_tokens
    g_pos = saved_pos
    g_ns = saved_ns
}

fn parse_fn_decl() -> unit {
    expect_kind("FN")
    let name_tok = expect_kind("IDENT")
    expect_kind("LPAREN")
    let mut param_names: list[str] = []
    if not check_kind("RPAREN") {
        let p0 = expect_kind("IDENT")
        expect_kind("COLON")
        parse_type_ann()
        param_names.append(p0.val)
        while match_kind("COMMA") {
            if check_kind("RPAREN") {
                break
            }
            let pn = expect_kind("IDENT")
            expect_kind("COLON")
            parse_type_ann()
            param_names.append(pn.val)
        }
    }
    expect_kind("RPAREN")
    let mut fallible = false
    if match_kind("ARROW") {
        fallible = parse_type_ann()
    }
    let mut sig = "void"
    if len(param_names) > 0 {
        sig = ""
        for idx in 0..len(param_names) {
            if idx > 0 {
                sig = sig + ", "
            }
            sig = sig + "WVal v_" + param_names[idx]
        }
    }
    let c_name = c_fn_name(name_tok.val)
    g_protos.append("static WVal " + c_name + "(" + sig + ");")
    let prev_fallible = g_fn_fallible
    let prev_err = g_cur_err_type
    g_fn_fallible = fallible
    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    let previous_bindings = g_borrowed_vars
    let mut borrowed: list[str] = []
    for parameter in param_names { borrowed.append("v_" + parameter) }
    g_borrowed_vars = borrowed
    push_scope("fn")
    let ret_v = parse_block_expr()
    let ret_hold = new_aux("_ret")
    emit_line("WVal " + ret_hold + " = " + own_expr(ret_v) + ";")
    pop_scope()
    if g_fn_fallible {
        emit_line("return w_wrap_result(" + ret_hold + ", \"" + g_cur_err_type + "\");")
    } else {
        emit_line("return " + ret_hold + ";")
    }
    let body_lines = g_cur_stmts
    g_cur_stmts = saved
    g_borrowed_vars = previous_bindings
    g_fn_fallible = prev_fallible
    g_cur_err_type = prev_err
    let mut fn_str = "static WVal " + c_name + "(" + sig + ") {\n"
    for l in body_lines {
        fn_str = fn_str + "    " + l + "\n"
    }
    fn_str = fn_str + "}"
    g_fn_defs.append(fn_str)
}

fn ffi_c_type(name: str, returned: bool) -> str {
    if name == "int32" { return "int32_t" }
    if name == "int" or name == "int64" { return "int64_t" }
    if name == "float" or name == "double" { return "double" }
    if name == "bool" { return "bool" }
    if name == "opaque" { return "void*" }
    if name == "unit" and returned { return "void" }
    report_error("W2001", at_tok().line, at_tok().col, "unsupported C ABI type")
    return "void"
}
fn parse_extern_decl() {
    expect_kind("EXTERN")
    if expect_kind("STR").val != "C" { report_error("W2013", at_tok().line, at_tok().col, "only C ABI is supported") }
    expect_kind("FN")
    let name = expect_kind("IDENT").val
    expect_kind("LPAREN")
    let mut types: list[str] = []
    while not check_kind("RPAREN") {
        expect_kind("IDENT")
        expect_kind("COLON")
        types.append(expect_kind("IDENT").val)
        if not match_kind("COMMA") { break }
    }
    expect_kind("RPAREN")
    expect_kind("ARROW")
    let returned = expect_kind("IDENT").val
    let mut native_name = name
    if len(name) > 6 and slice(name, 0, 6) == "__w1_m" {
        for i in 6..len(name) - 1 { if slice(name, i, i + 2) == "__" { native_name = slice(name, i + 2, len(name)) break } }
    }
    let mut native_params = ""
    let mut wrapped_params = ""
    let mut arguments = ""
    for i in 0..len(types) {
        if i > 0 { native_params = native_params + ", " wrapped_params = wrapped_params + ", " arguments = arguments + ", " }
        native_params = native_params + ffi_c_type(types[i], false)
        let variable = "v_" + str(i)
        wrapped_params = wrapped_params + "WVal " + variable
        if types[i] == "int32" { arguments = arguments + "w_ffi_int32(" + variable + ")" }
        elif types[i] == "int" or types[i] == "int64" { arguments = arguments + variable + ".as.i" }
        elif types[i] == "float" or types[i] == "double" { arguments = arguments + variable + ".as.f" }
        elif types[i] == "bool" { arguments = arguments + variable + ".as.b" }
        else { arguments = arguments + variable + ".as.pointer" }
    }
    if len(types) == 0 { native_params = "void" wrapped_params = "void" }
    let c_name = c_fn_name(name)
    g_protos.append("extern " + ffi_c_type(returned, true) + " " + native_name + "(" + native_params + ");")
    g_protos.append("static WVal " + c_name + "(" + wrapped_params + ");")
    let call = native_name + "(" + arguments + ")"
    let mut result = ""
    if returned == "unit" { result = call + "; return w_unit();" }
    elif returned == "int" or returned == "int32" or returned == "int64" { result = "return w_int(" + call + ");" }
    elif returned == "float" or returned == "double" { result = "return w_float(" + call + ");" }
    elif returned == "bool" { result = "return w_bool(" + call + ");" }
    else { result = "return w_pointer(" + call + ");" }
    g_fn_defs.append("static WVal " + c_name + "(" + wrapped_params + ") { " + result + " }")
}
