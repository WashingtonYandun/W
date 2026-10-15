"""Specialized class vtables using one compatible C invocation signature."""


def emit_vtables(class_names, methods, resolve):
    definitions = []
    adapters = set()
    tables = []
    for class_name in class_names:
        slots = []
        for name, arity in methods:
            resolved = resolve(class_name, name)
            if resolved is None or len(resolved[1].params) != arity:
                slots.append('NULL')
                continue
            owner, _ = resolved
            adapter = 'w_vinvoke_' + owner + '__' + name
            slots.append(adapter)
            if adapter not in adapters:
                adapters.add(adapter)
                arguments = ', '.join(['receiver'] + [f'argv[{index}]' for index in range(arity)])
                definitions.append(f'static WVal {adapter}(WVal receiver, int32_t argc, const WVal* argv) {{ '
                                   f'(void)argc; (void)argv; return w_method_{owner}__{name}({arguments}); }}')
        if slots:
            tables.append(f'static const WInvoke w_slots_{class_name}[{len(slots)}] = {{ ' + ', '.join(slots) + ' };')
            tables.append(f'static const WClassVTable w_vtable_{class_name} = {{ {len(slots)}, w_slots_{class_name} }};')
        else:
            tables.append(f'static const WClassVTable w_vtable_{class_name} = {{ 0, NULL }};')
    definitions.extend(tables)
    for slot, (name, arity) in enumerate(methods):
        parameters = ', '.join(['WVal v_self'] + [f'WVal _a{index}' for index in range(arity)])
        arguments = '(WVal[]){ ' + ', '.join(f'_a{index}' for index in range(arity)) + ' }' if arity else 'NULL'
        definitions.append(f'static WVal w_dispatch__{name}__{arity}({parameters}) {{ '
                           f'return w_virtual_call(v_self, {slot}, {arity}, {arguments}); }}')
    return definitions
