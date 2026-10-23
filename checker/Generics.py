"""Generic definition checking and specialization orchestration."""
from copy import copy

from checker.WysnaType import FunctionType, TypeParamType


class GenericDefinitionChecker:
    """Check generic function bodies with symbolic parameters before use."""

    def __init__(self, checker):
        self.checker = checker

    def check_all(self):
        for template in self.checker.generic_fn_templates.values():
            self.check_function(template)

    def check_function(self, template):
        checker = self.checker
        symbol = checker.global_scope.lookup_symbol(template.name)
        if symbol is None:
            return

        substitutions = {}
        for parameter in template.type_params:
            constraint = getattr(parameter, "constraint", None)
            resolved_constraint = (
                checker._resolve_constraint_interface(constraint, parameter.line, parameter.col)
                if constraint is not None else None
            )
            substitutions[parameter.name] = TypeParamType(
                parameter.name, constraint=resolved_constraint, owner=template.name
            )

        saved = {
            "symbol_type": symbol.type,
            "active_subst": checker._active_type_subst,
            "generic_definition": getattr(checker, "_checking_generic_definition", None),
            "symbols": dict(checker.global_scope.symbols),
            "types": dict(checker.global_scope.types),
            "specializations": dict(checker.specializations),
            "monomorphized_structs": dict(checker.monomorphized_structs),
            "monomorphized_fns": dict(checker.monomorphized_fns),
            "monomorphized_enums": dict(checker.monomorphized_enums),
            "oop_decls": len(checker.monomorphized_oop_decls),
            "struct_decls": len(checker.monomorphized_struct_decls),
            "fn_decls": len(checker.monomorphized_fn_decls),
            "enum_decls": len(checker.monomorphized_enum_decls),
            "telemetry": copy(checker.telemetry),
        }

        try:
            checker._active_type_subst = substitutions
            checker._checking_generic_definition = template
            clone = checker._clone_generic_definition(template, substitutions)
            parameter_types = [checker._resolve_type_node(parameter.type_ann) for parameter in clone.params]
            return_type = checker._resolve_type_node(clone.return_type)
            symbol.type = FunctionType(parameter_types, return_type)

            with checker.type_relations.capture_obligations() as obligations:
                checker._check_fn_decl(clone)
            template.obligations = tuple(obligations)
        finally:
            symbol.type = saved["symbol_type"]
            checker._active_type_subst = saved["active_subst"]
            checker._checking_generic_definition = saved["generic_definition"]
            checker.global_scope.symbols.clear()
            checker.global_scope.symbols.update(saved["symbols"])
            checker.global_scope.types.clear()
            checker.global_scope.types.update(saved["types"])
            checker.specializations.clear()
            checker.specializations.update(saved["specializations"])
            checker.monomorphized_structs.clear()
            checker.monomorphized_structs.update(saved["monomorphized_structs"])
            checker.monomorphized_fns.clear()
            checker.monomorphized_fns.update(saved["monomorphized_fns"])
            checker.monomorphized_enums.clear()
            checker.monomorphized_enums.update(saved["monomorphized_enums"])
            del checker.monomorphized_oop_decls[saved["oop_decls"]:]
            del checker.monomorphized_struct_decls[saved["struct_decls"]:]
            del checker.monomorphized_fn_decls[saved["fn_decls"]:]
            del checker.monomorphized_enum_decls[saved["enum_decls"]:]
            checker.telemetry = saved["telemetry"]


class Instantiator:
    """Own the boundary between generic templates and concrete specializations."""

    def __init__(self, checker):
        self.checker = checker

    def function(self, template, concrete_args, line, col):
        return self.checker._monomorphize_fn_impl(template, concrete_args, line, col)

    def structure(self, template, concrete_args, line, col):
        return self.checker._monomorphize_struct_impl(template, concrete_args, line, col)

    def enumeration(self, template, concrete_args, line, col):
        return self.checker._monomorphize_enum_impl(template, concrete_args, line, col)
