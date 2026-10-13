import os
import sys
from typing import Any, Dict, List, Optional, TextIO, Tuple
from error.Error import WRuntimeError
from node.NodeType import (
    Program, Stmt, Expr, ExprStmt, LetDecl, FnDecl, StructDecl, EnumDecl, ImportDecl,
    InterfaceDecl, ClassDecl, MethodDecl,
    WhileStmt, ForStmt, ReturnStmt, BreakStmt, ContinueStmt, Block,
    IntLiteral, FloatLiteral, StringLiteral, BoolLiteral, NoneLiteral, IdentExpr,
    ThisExpr, SuperExpr, NewExpr,
    UnaryExpr, BinaryExpr, CoalesceExpr, RangeExpr, PostfixTryExpr, ElseErrExpr, CallExpr,
    MemberExpr, IndexExpr, AssignmentExpr, StructInitExpr, ListExpr, DictExpr, TupleExpr,
    IfExpr, MatchExpr, Pattern, IdentifierPattern, TuplePattern, EnumPattern,
    LiteralPattern, WildcardPattern,
    NamedType, OptionalType as AstOptionalType, ListType as AstListType, DictType as AstDictType
)
from runtime.Values import (
    WValue, WInt, WFloat, WBool, WStr, WUnit, WNone,
    WList, WDict, WTuple, WRange, WStructInstance, WEnumValue,
    WResult, WOk, WErr, WFunction, WNativeFunction, WBoundMethod,
    WClassDef, WObjectInstance, WSuperProxy,
    WEnumNamespace, WModule
)

from runtime.Environment import (
    Environment, ReturnSignal, BreakSignal, ContinueSignal,
    PropagationSignal, create_global_environment
)

class Interpreter:
    """
    Canonical Tree-Walking Interpreter for W Language v0.1 (W0).
    Executes AST programs preserving strict value semantics (ARC + CoW)
    for structs/collections and reference semantics for class instances.
    """
    def __init__(self, stdout: Optional[TextIO] = None, file: str = "<stdin>"):
        self.file = file
        self.stdout = stdout if stdout is not None else sys.stdout
        self.global_env = create_global_environment(stdout=self.stdout)

    def interpret(self, program: Program) -> WValue:
        # Pass 1: Register top-level enums, classes, structs, and functions
        for stmt in program.body:
            if isinstance(stmt, EnumDecl):
                self.global_env.declare(
                    stmt.name,
                    WEnumNamespace(stmt.name, stmt.variants),
                    is_mut=False
                )
            elif isinstance(stmt, ClassDecl):
                methods_map = {m.name: m for m in stmt.methods}
                self.global_env.declare(
                    stmt.name,
                    WClassDef(
                        name=stmt.name,
                        superclass_name=stmt.superclass,
                        fields=stmt.fields,
                        methods=methods_map,
                        closure_env=self.global_env
                    ),
                    is_mut=False
                )
            elif isinstance(stmt, FnDecl):
                self.global_env.declare(
                    stmt.name,
                    WFunction(decl=stmt, closure_env=self.global_env),
                    is_mut=False
                )
            elif isinstance(stmt, ImportDecl):
                self.eval_import_decl(stmt, self.global_env)

        # Pass 2: Execute statements
        non_decls = [s for s in program.body if not isinstance(s, (FnDecl, StructDecl, EnumDecl, InterfaceDecl, ClassDecl, ImportDecl))]
        last_val: WValue = WUnit()

        if non_decls:
            for stmt in program.body:
                if not isinstance(stmt, (FnDecl, StructDecl, EnumDecl, InterfaceDecl, ClassDecl)):
                    last_val = self.eval_stmt(stmt, self.global_env)
        elif self.global_env.exists("main"):
            main_fn = self.global_env.lookup("main")
            if isinstance(main_fn, WFunction):
                last_val = self.call_function(main_fn, [])

        return last_val

    # ==========================================
    # Statement Dispatch
    # ==========================================

    def eval_stmt(self, stmt: Stmt, env: Environment) -> WValue:
        if isinstance(stmt, ExprStmt):
            return self.eval_expr(stmt.expr, env)

        if isinstance(stmt, LetDecl):
            val = self.eval_expr(stmt.initializer, env)
            env.declare(stmt.name, val, is_mut=stmt.is_mut)
            return val

        if isinstance(stmt, WhileStmt):
            while True:
                cond_val = self.eval_expr(stmt.condition, env)
                if not isinstance(cond_val, WBool) or not cond_val.value:
                    break
                try:
                    self.eval_block(stmt.body, env)
                except ContinueSignal:
                    continue
                except BreakSignal:
                    break
            return WUnit()

        if isinstance(stmt, ForStmt):
            iter_val = self.eval_expr(stmt.iterable, env)
            elements: List[WValue]
            if isinstance(iter_val, WList):
                elements = list(iter_val.storage.data)
            elif isinstance(iter_val, WRange):
                elements = list(iter_val)
            else:
                raise WRuntimeError(
                    message=f"Cannot iterate over type '{type(iter_val).__name__}'",
                    line=stmt.line,
                    col=stmt.col,
                    file=self.file
                )

            for item in elements:
                loop_env = Environment(parent=env)
                self.bind_pattern(stmt.pattern, item, loop_env)
                try:
                    self.eval_block(stmt.body, loop_env)
                except ContinueSignal:
                    continue
                except BreakSignal:
                    break
            return WUnit()

        if isinstance(stmt, ReturnStmt):
            ret_val = self.eval_expr(stmt.value, env) if stmt.value is not None else WUnit()
            raise ReturnSignal(ret_val)

        if isinstance(stmt, BreakStmt):
            raise BreakSignal()

        if isinstance(stmt, ContinueStmt):
            raise ContinueSignal()

        if isinstance(stmt, ImportDecl):
            return self.eval_import_decl(stmt, env)

        return WUnit()

    def eval_block(self, block: Block, env: Environment) -> WValue:
        block_env = Environment(parent=env)
        for s in block.statements:
            self.eval_stmt(s, block_env)
        if block.tail_expr is not None:
            return self.eval_expr(block.tail_expr, block_env)
        return WUnit()

    def eval_import_decl(self, stmt: ImportDecl, env: Environment) -> WValue:
        # Resolve path relative to source file directory or cwd
        current_dir = os.path.dirname(os.path.abspath(self.file)) if self.file != "<stdin>" else os.getcwd()
        resolved_path = os.path.join(current_dir, stmt.path)
        if not os.path.exists(resolved_path):
            # Fallback to direct path
            resolved_path = stmt.path

        if not os.path.exists(resolved_path):
            raise WRuntimeError(
                message=f"Module not found: '{stmt.path}'",
                line=stmt.line,
                col=stmt.col,
                file=self.file
            )

        with open(resolved_path, "r", encoding="utf-8") as f:
            code = f.read()

        from parser.Parser import Parser

        ast = Parser(file=resolved_path).parse(code)


        sub_interpreter = Interpreter(stdout=self.stdout, file=resolved_path)
        sub_interpreter.interpret(ast)

        mod = WModule(name=stmt.namespace, env=sub_interpreter.global_env)
        env.declare(stmt.namespace, mod, is_mut=False)
        return mod

    def bind_pattern(self, pattern: Pattern, value: WValue, env: Environment) -> None:
        if isinstance(pattern, IdentifierPattern):
            env.declare(pattern.name, value, is_mut=False)
        elif isinstance(pattern, TuplePattern):
            if not isinstance(value, WTuple) or len(pattern.elements) != len(value.elements):
                raise WRuntimeError(
                    message="Cannot destructure tuple: length mismatch",
                    line=pattern.line,
                    col=pattern.col,
                    file=self.file
                )
            for p, elem in zip(pattern.elements, value.elements):
                self.bind_pattern(p, elem, env)
        elif isinstance(pattern, WildcardPattern):
            pass

    # ==========================================
    # Expression Dispatch
    # ==========================================

    def eval_expr(self, expr: Expr, env: Environment) -> WValue:
        if isinstance(expr, IntLiteral):
            return WInt(expr.value)

        if isinstance(expr, FloatLiteral):
            return WFloat(expr.value)

        if isinstance(expr, StringLiteral):
            return WStr(expr.value)

        if isinstance(expr, BoolLiteral):
            return WBool(expr.value)

        if isinstance(expr, NoneLiteral):
            return WNone()

        if isinstance(expr, IdentExpr):
            return env.lookup(expr.name)

        if isinstance(expr, UnaryExpr):
            operand_val = self.eval_expr(expr.operand, env)
            if expr.op == "-":
                if isinstance(operand_val, WInt):
                    return WInt(-operand_val.value)
                if isinstance(operand_val, WFloat):
                    return WFloat(-operand_val.value)
            if expr.op == "not":
                if isinstance(operand_val, WBool):
                    return WBool(not operand_val.value)
            raise WRuntimeError(
                message=f"Invalid unary operator '{expr.op}' on '{operand_val}'",
                line=expr.line,
                col=expr.col,
                file=self.file
            )

        if isinstance(expr, BinaryExpr):
            # Short-circuit logical operators
            if expr.op == "and":
                lhs = self.eval_expr(expr.left, env)
                if not isinstance(lhs, WBool):
                    raise WRuntimeError("Expected bool operand for 'and'", line=expr.line, col=expr.col, file=self.file)
                if not lhs.value:
                    return WBool(False)
                rhs = self.eval_expr(expr.right, env)
                if not isinstance(rhs, WBool):
                    raise WRuntimeError("Expected bool operand for 'and'", line=expr.line, col=expr.col, file=self.file)
                return WBool(rhs.value)

            if expr.op == "or":
                lhs = self.eval_expr(expr.left, env)
                if not isinstance(lhs, WBool):
                    raise WRuntimeError("Expected bool operand for 'or'", line=expr.line, col=expr.col, file=self.file)
                if lhs.value:
                    return WBool(True)
                rhs = self.eval_expr(expr.right, env)
                if not isinstance(rhs, WBool):
                    raise WRuntimeError("Expected bool operand for 'or'", line=expr.line, col=expr.col, file=self.file)
                return WBool(rhs.value)

            lhs = self.eval_expr(expr.left, env)
            rhs = self.eval_expr(expr.right, env)

            if expr.op == "+":
                if isinstance(lhs, WInt) and isinstance(rhs, WInt):
                    return WInt(lhs.value + rhs.value)
                if isinstance(lhs, WFloat) and isinstance(rhs, WFloat):
                    return WFloat(lhs.value + rhs.value)
                if isinstance(lhs, WStr) and isinstance(rhs, WStr):
                    return WStr(lhs.value + rhs.value)

            if expr.op == "-":
                if isinstance(lhs, WInt) and isinstance(rhs, WInt):
                    return WInt(lhs.value - rhs.value)
                if isinstance(lhs, WFloat) and isinstance(rhs, WFloat):
                    return WFloat(lhs.value - rhs.value)

            if expr.op == "*":
                if isinstance(lhs, WInt) and isinstance(rhs, WInt):
                    return WInt(lhs.value * rhs.value)
                if isinstance(lhs, WFloat) and isinstance(rhs, WFloat):
                    return WFloat(lhs.value * rhs.value)

            if expr.op == "/":
                if isinstance(lhs, WInt) and isinstance(rhs, WInt):
                    if rhs.value == 0:
                        raise WRuntimeError("Division by zero", line=expr.line, col=expr.col, file=self.file, code="W4001")
                    if lhs.value == -9223372036854775808 and rhs.value == -1:
                        return WInt(-9223372036854775808)
                    q = abs(lhs.value) // abs(rhs.value)
                    if (lhs.value < 0) ^ (rhs.value < 0):
                        q = -q
                    return WInt(q)
                if isinstance(lhs, WFloat) and isinstance(rhs, WFloat):
                    if rhs.value == 0.0:
                        raise WRuntimeError("Division by zero", line=expr.line, col=expr.col, file=self.file, code="W4001")
                    return WFloat(lhs.value / rhs.value)

            if expr.op == "%":
                if isinstance(lhs, WInt) and isinstance(rhs, WInt):
                    if rhs.value == 0:
                        raise WRuntimeError("Modulo by zero", line=expr.line, col=expr.col, file=self.file, code="W4001")
                    if lhs.value == -9223372036854775808 and rhs.value == -1:
                        return WInt(0)
                    q = abs(lhs.value) // abs(rhs.value)
                    if (lhs.value < 0) ^ (rhs.value < 0):
                        q = -q
                    return WInt(lhs.value - q * rhs.value)

            if expr.op == "==":
                return WBool(lhs == rhs)

            if expr.op == "!=":
                return WBool(lhs != rhs)

            if expr.op == "<":
                return WBool(lhs.value < rhs.value)

            if expr.op == "<=":
                return WBool(lhs.value <= rhs.value)

            if expr.op == ">":
                return WBool(lhs.value > rhs.value)

            if expr.op == ">=":
                return WBool(lhs.value >= rhs.value)

            raise WRuntimeError(
                message=f"Binary operator '{expr.op}' not supported for '{lhs}' and '{rhs}'",
                line=expr.line,
                col=expr.col,
                file=self.file
            )

        if isinstance(expr, CoalesceExpr):
            lhs = self.eval_expr(expr.left, env)
            if isinstance(lhs, WNone):
                return self.eval_expr(expr.right, env)
            return lhs

        if isinstance(expr, RangeExpr):
            start_val = self.eval_expr(expr.start, env)
            end_val = self.eval_expr(expr.end, env)
            if not isinstance(start_val, WInt) or not isinstance(end_val, WInt):
                raise WRuntimeError("Range bounds must be integers", line=expr.line, col=expr.col, file=self.file)
            stop = end_val.value + 1 if expr.inclusive else end_val.value
            return WList(elements=[WInt(i) for i in range(start_val.value, stop)])

        if isinstance(expr, PostfixTryExpr):
            val = self.eval_expr(expr.operand, env)
            if isinstance(val, WNone):
                raise PropagationSignal(WNone())
            if isinstance(val, WErr):
                raise PropagationSignal(val, is_error=True)
            if isinstance(val, WOk):
                return val.value
            return val

        if isinstance(expr, ElseErrExpr):
            val = self.eval_expr(expr.operand, env)
            if isinstance(val, WOk):
                return val.value
            if isinstance(val, WErr):
                handler_env = Environment(parent=env)
                if expr.err_name is not None:
                    handler_env.declare(expr.err_name, val.error, is_mut=False)
                return self.eval_block(expr.handler, handler_env)
            if isinstance(val, WNone):
                handler_env = Environment(parent=env)
                return self.eval_block(expr.handler, handler_env)
            return val

        if isinstance(expr, ThisExpr):
            return env.lookup("this")

        if isinstance(expr, SuperExpr):
            return env.lookup("super")

        if isinstance(expr, NewExpr):
            return self.instantiate_class(expr.class_name, [self.eval_expr(a, env) for a in expr.args], env, expr.line, expr.col)

        if isinstance(expr, AssignmentExpr):
            target = expr.target
            val = self.eval_expr(expr.value, env)

            if isinstance(target, IdentExpr):
                env.assign(target.name, val)
                return val

            if isinstance(target, IndexExpr):
                obj = self.eval_mutable_lvalue(target.object, env)
                idx = self.eval_expr(target.index, env)
                if isinstance(obj, WList) and isinstance(idx, WInt):
                    if idx.value < 0 or idx.value >= len(obj):
                        raise WRuntimeError(f"List index out of bounds: {idx.value}", line=target.line, col=target.col, file=self.file)
                    obj.set(idx.value, val)
                    return val
                if isinstance(obj, WDict):
                    key_raw = idx.value if hasattr(idx, 'value') else idx
                    obj.set(key_raw, val)
                    return val
                raise WRuntimeError(f"Cannot assign to index of '{type(obj).__name__}'", line=target.line, col=target.col, file=self.file)

            if isinstance(target, MemberExpr):
                obj = self.eval_mutable_lvalue(target.object, env)
                if isinstance(obj, WObjectInstance):
                    obj.set_field(target.property, val)
                    return val
                if isinstance(obj, WStructInstance):
                    obj.set_field(target.property, val)
                    return val
                raise WRuntimeError(f"Cannot assign to property of '{type(obj).__name__}'", line=target.line, col=target.col, file=self.file)

            raise WRuntimeError("Invalid assignment target", line=expr.line, col=expr.col, file=self.file)

        if isinstance(expr, MemberExpr):
            if expr.property in ("append", "pop", "clear"):
                obj = self.eval_mutable_lvalue(expr.object, env)
            else:
                obj = self.eval_expr(expr.object, env)
            if isinstance(obj, WEnumNamespace):
                return obj.get_variant(expr.property)
            if isinstance(obj, WSuperProxy):
                return WBoundMethod(receiver=obj.receiver, method_name=expr.property, target_class_name=obj.superclass_name)
            if isinstance(obj, WObjectInstance):
                if expr.property in obj.fields:
                    return obj.get_field(expr.property)
                return WBoundMethod(receiver=obj, method_name=expr.property, target_class_name=obj.class_name)
            if isinstance(obj, WStructInstance):
                return obj.get_field(expr.property)
            if isinstance(obj, (WList, WDict)):
                return WBoundMethod(receiver=obj, method_name=expr.property)
            if isinstance(obj, WModule):
                return obj.get_member(expr.property)
            raise WRuntimeError(f"Cannot access property '{expr.property}' on '{obj}'", line=expr.line, col=expr.col, file=self.file)

        if isinstance(expr, IndexExpr):
            obj = self.eval_expr(expr.object, env)
            idx = self.eval_expr(expr.index, env)

            if isinstance(obj, WList):
                if not isinstance(idx, WInt):
                    raise WRuntimeError("List index must be int", line=expr.line, col=expr.col, file=self.file)
                if idx.value < 0 or idx.value >= len(obj):
                    raise WRuntimeError(f"List index out of bounds: index {idx.value}, length {len(obj)}", line=expr.line, col=expr.col, file=self.file)
                return obj.get(idx.value)

            if isinstance(obj, WStr):
                if not isinstance(idx, WInt):
                    raise WRuntimeError("String index must be int", line=expr.line, col=expr.col, file=self.file)
                if idx.value < 0 or idx.value >= len(obj.value):
                    raise WRuntimeError(f"String index out of bounds: index {idx.value}, length {len(obj.value)}", line=expr.line, col=expr.col, file=self.file)
                return WStr(obj.value[idx.value])

            if isinstance(obj, WDict):
                key_raw = idx.value if hasattr(idx, 'value') else idx
                res = obj.get(key_raw)
                return res if res is not None else WNone()

            raise WRuntimeError(f"Cannot index type '{type(obj).__name__}'", line=expr.line, col=expr.col, file=self.file)

        if isinstance(expr, CallExpr):
            callee = self.eval_expr(expr.callee, env)
            args = [self.eval_expr(a, env) for a in expr.args]

            if isinstance(callee, WClassDef):
                return self.instantiate_class(callee.name, args, env, expr.line, expr.col)
            if isinstance(callee, WNativeFunction):
                return callee.call_fn(args)
            if isinstance(callee, WFunction):
                return self.call_function(callee, args)
            if isinstance(callee, WBoundMethod):
                return self.call_bound_method(callee, args)

            raise WRuntimeError(f"Cannot call non-function '{callee}'", line=expr.line, col=expr.col, file=self.file)

        if isinstance(expr, StructInitExpr):
            field_dict = {}
            for f in expr.fields:
                field_dict[f.name] = self.eval_expr(f.value, env)
            return WStructInstance(expr.struct_name, fields=field_dict)

        if isinstance(expr, ListExpr):
            return WList(elements=[self.eval_expr(e, env) for e in expr.elements])

        if isinstance(expr, DictExpr):
            pairs = {}
            for entry in expr.entries:
                k = self.eval_expr(entry.key, env)
                v = self.eval_expr(entry.value, env)
                key_raw = k.value if hasattr(k, 'value') else k
                pairs[key_raw] = v
            return WDict(pairs=pairs)

        if isinstance(expr, TupleExpr):
            return WTuple(elements=[self.eval_expr(e, env) for e in expr.elements])

        if isinstance(expr, IfExpr):
            cond_val = self.eval_expr(expr.condition, env)
            if not isinstance(cond_val, WBool):
                raise WRuntimeError("Condition of 'if' must be bool", line=expr.line, col=expr.col, file=self.file)
            if cond_val.value:
                return self.eval_block(expr.then_branch, env)

            for elif_b in expr.elif_branches:
                elif_cond = self.eval_expr(elif_b.condition, env)
                if not isinstance(elif_cond, WBool):
                    raise WRuntimeError("Condition of 'elif' must be bool", line=elif_b.line, col=elif_b.col, file=self.file)
                if elif_cond.value:
                    return self.eval_block(elif_b.body, env)

            if expr.else_branch is not None:
                return self.eval_block(expr.else_branch, env)
            return WUnit()

        if isinstance(expr, MatchExpr):
            subj_val = self.eval_expr(expr.subject, env)
            for arm in expr.arms:
                matched, arm_bindings = self.match_pattern(arm.pattern, subj_val)
                if matched:
                    arm_env = Environment(parent=env)
                    for k, v in arm_bindings.items():
                        arm_env.declare(k, v, is_mut=False)
                    return self.eval_block(arm.body, arm_env)
            raise WRuntimeError("Non-exhaustive match at runtime", line=expr.line, col=expr.col, file=self.file)

        return WUnit()

    # ==========================================
    # Helper Call & OOP Methods
    # ==========================================

    def eval_mutable_lvalue(self, expr: Expr, env: Environment) -> WValue:
        if isinstance(expr, IdentExpr):
            val = env.lookup(expr.name)
            if isinstance(val, (WList, WDict, WStructInstance)):
                val.ensure_unique()
            return val

        if isinstance(expr, ThisExpr):
            return env.lookup("this")

        if isinstance(expr, IndexExpr):
            parent = self.eval_mutable_lvalue(expr.object, env)
            idx = self.eval_expr(expr.index, env)
            if isinstance(parent, WList):
                if not isinstance(idx, WInt):
                    raise WRuntimeError("List index must be int", line=expr.line, col=expr.col, file=self.file)
                if idx.value < 0 or idx.value >= len(parent):
                    raise WRuntimeError(f"List index out of bounds: index {idx.value}, length {len(parent)}", line=expr.line, col=expr.col, file=self.file)
                elem = parent.get(idx.value)
                if isinstance(elem, (WList, WDict, WStructInstance)):
                    elem.ensure_unique()
                return elem
            if isinstance(parent, WDict):
                key_raw = idx.value if hasattr(idx, 'value') else idx
                elem = parent.get(key_raw)
                if elem is not None and isinstance(elem, (WList, WDict, WStructInstance)):
                    elem.ensure_unique()
                return elem if elem is not None else WNone()

        if isinstance(expr, MemberExpr):
            parent = self.eval_mutable_lvalue(expr.object, env)
            if isinstance(parent, (WStructInstance, WObjectInstance)):
                elem = parent.get_field(expr.property)
                if isinstance(elem, (WList, WDict, WStructInstance)):
                    elem.ensure_unique()
                return elem

        return self.eval_expr(expr, env)

    def _default_value_for_type(self, type_ann: Any) -> WValue:
        if isinstance(type_ann, NamedType):
            if type_ann.name == "int":
                return WInt(0)
            if type_ann.name == "float":
                return WFloat(0.0)
            if type_ann.name == "bool":
                return WBool(False)
            if type_ann.name == "str":
                return WStr("")
        elif isinstance(type_ann, AstOptionalType):
            return WNone()
        elif isinstance(type_ann, AstListType):
            return WList(elements=[])
        elif isinstance(type_ann, AstDictType):
            return WDict(pairs={})
        return WNone()

    def _resolve_class_def(self, class_name: str, env: Environment) -> WClassDef:
        val = env.lookup(class_name) if env.exists(class_name) else self.global_env.lookup(class_name)
        if not isinstance(val, WClassDef):
            raise WRuntimeError(f"Unknown class '{class_name}'", file=self.file)
        return val

    def _find_method_in_hierarchy(self, start_class_name: str, method_name: str, env: Environment) -> Tuple[WClassDef, MethodDecl]:
        curr_name: Optional[str] = start_class_name
        while curr_name is not None:
            cls_def = self._resolve_class_def(curr_name, env)
            if method_name in cls_def.methods:
                return cls_def, cls_def.methods[method_name]
            curr_name = cls_def.superclass_name
        raise WRuntimeError(f"Method '{method_name}' not found in class hierarchy starting at '{start_class_name}'", file=self.file)

    def instantiate_class(self, class_name: str, args: List[WValue], env: Environment, line: int = 0, col: int = 0) -> WObjectInstance:
        cls_def = self._resolve_class_def(class_name, env)
        # Collect hierarchy from root ancestor down to target class
        lineage: List[WClassDef] = []
        curr: Optional[WClassDef] = cls_def
        while curr is not None:
            lineage.append(curr)
            curr = self._resolve_class_def(curr.superclass_name, env) if curr.superclass_name is not None else None
        lineage.reverse()

        fields_dict: Dict[str, WValue] = {}
        for ancestor in lineage:
            for f in ancestor.fields:
                fields_dict[f.name] = self._default_value_for_type(f.type_ann)

        instance = WObjectInstance(class_name=class_name, fields=fields_dict)

        # Invoke constructor 'init' if present in hierarchy
        curr_init_cls: Optional[WClassDef] = cls_def
        while curr_init_cls is not None:
            if "init" in curr_init_cls.methods:
                self.call_class_method(curr_init_cls, curr_init_cls.methods["init"], instance, args)
                break
            curr_init_cls = self._resolve_class_def(curr_init_cls.superclass_name, env) if curr_init_cls.superclass_name is not None else None

        return instance

    def call_class_method(self, defining_cls: WClassDef, method_decl: MethodDecl, receiver: WObjectInstance, args: List[WValue]) -> WValue:
        if len(args) != len(method_decl.params):
            raise WRuntimeError(
                message=f"Method '{defining_cls.name}.{method_decl.name}' expected {len(method_decl.params)} arguments, got {len(args)}",
                line=method_decl.line,
                col=method_decl.col,
                file=self.file
            )

        call_env = Environment(parent=defining_cls.closure_env, is_function_boundary=True)
        call_env.declare("this", receiver, is_mut=False)
        call_env.declare("self", receiver, is_mut=False)
        if defining_cls.superclass_name is not None:
            call_env.declare("super", WSuperProxy(receiver=receiver, superclass_name=defining_cls.superclass_name), is_mut=False)

        for param, arg in zip(method_decl.params, args):
            call_env.declare(param.name, arg, is_mut=False)

        ret_val: WValue
        try:
            ret_val = self.eval_block(method_decl.body, call_env)
        except ReturnSignal as ret:
            ret_val = ret.value
        except PropagationSignal as prop:
            ret_val = prop.value

        from node.NodeType import ResultType as AstResultType
        if isinstance(method_decl.return_type, AstResultType):
            if not isinstance(ret_val, WResult):
                ret_val = WOk(ret_val)

        return ret_val

    def call_function(self, func: WFunction, args: List[WValue]) -> WValue:
        if len(args) != len(func.decl.params):
            raise WRuntimeError(
                message=f"Function '{func.decl.name}' expected {len(func.decl.params)} arguments, got {len(args)}",
                line=func.decl.line,
                col=func.decl.col,
                file=self.file
            )

        call_env = Environment(parent=func.closure_env, is_function_boundary=True)
        for param, arg in zip(func.decl.params, args):
            call_env.declare(param.name, arg, is_mut=False)

        ret_val: WValue
        try:
            ret_val = self.eval_block(func.decl.body, call_env)
        except ReturnSignal as ret:
            ret_val = ret.value
        except PropagationSignal as prop:
            ret_val = prop.value

        from node.NodeType import ResultType as AstResultType
        if isinstance(func.decl.return_type, AstResultType):
            if not isinstance(ret_val, WResult):
                ret_val = WOk(ret_val)

        return ret_val


    def call_bound_method(self, bound: WBoundMethod, args: List[WValue]) -> WValue:
        receiver = bound.receiver
        method = bound.method_name

        if isinstance(receiver, WObjectInstance):
            start_cls = bound.target_class_name if bound.target_class_name is not None else receiver.class_name
            defining_cls, method_decl = self._find_method_in_hierarchy(start_cls, method, self.global_env)
            return self.call_class_method(defining_cls, method_decl, receiver, args)

        if isinstance(receiver, WList):
            if method == "append":
                if len(args) != 1:
                    raise WRuntimeError("append() takes 1 argument", file=self.file)
                receiver.append(args[0])
                return WUnit()
            if method == "pop":
                if len(args) == 0:
                    return receiver.pop()
                if len(args) == 1 and isinstance(args[0], WInt):
                    return receiver.pop(args[0].value)
                raise WRuntimeError("pop() invalid argument", file=self.file)
            if method == "clear":
                receiver.clear()
                return WUnit()

        if isinstance(receiver, WDict):
            if method == "get":
                if len(args) != 1:
                    raise WRuntimeError("get() takes 1 argument", file=self.file)
                key_raw = args[0].value if hasattr(args[0], 'value') else args[0]
                val = receiver.get(key_raw)
                return val if val is not None else WNone()
            if method == "keys":
                return WList(elements=receiver.keys())
            if method == "values":
                return WList(elements=receiver.values())

        raise WRuntimeError(f"Method '{method}' not found on '{receiver}'", file=self.file)

    def match_pattern(self, pattern: Pattern, value: WValue) -> Tuple[bool, Dict[str, WValue]]:
        if isinstance(pattern, WildcardPattern):
            return True, {}

        if isinstance(pattern, LiteralPattern):
            lit_val = self.eval_expr(pattern.literal, self.global_env)
            return lit_val == value, {}

        if isinstance(pattern, EnumPattern):
            if isinstance(value, WEnumValue) and value.enum_name == pattern.enum_name and value.variant == pattern.variant:
                return True, {}
            return False, {}

        if isinstance(pattern, IdentifierPattern):
            return True, {pattern.name: value}

        if isinstance(pattern, TuplePattern):
            if not isinstance(value, WTuple) or len(pattern.elements) != len(value.elements):
                return False, {}
            all_bindings: Dict[str, WValue] = {}
            for p, elem in zip(pattern.elements, value.elements):
                matched, sub_b = self.match_pattern(p, elem)
                if not matched:
                    return False, {}
                all_bindings.update(sub_b)
            return True, all_bindings

        return False, {}


# Backward compatibility helper
def evaluate(node: Any, env: Environment) -> WValue:
    interpreter = Interpreter()
    if isinstance(node, Program):
        return interpreter.interpret(node)
    if isinstance(node, Stmt):
        return interpreter.eval_stmt(node, env)
    if isinstance(node, Expr):
        return interpreter.eval_expr(node, env)
    return WUnit()