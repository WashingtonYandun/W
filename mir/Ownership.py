"""Remove redundant copies of immutable string parameters with caller-owned lifetimes."""
from collections import Counter
from checker.TypeInterner import TYPE_STR
from mir.Verifier import Verifier


def optimize_parameter_reads(module, interner):
    """Substitute stable borrowed parameters only when no use consumes the copy."""
    verifier = Verifier(interner)
    verifier.verify(module)
    for function in module.functions:
        operations = [operation for block in function.blocks for operation in block.operations]
        definitions = Counter(operation.result for operation in operations if operation.result is not None)
        parameters = {index for index in function.params if function.slots[index].type_id == TYPE_STR}
        replacements = {
            operation.result: operation.args[0]
            for operation in operations
            if operation.opcode == 'clone' and operation.args[0] in parameters
            and definitions[operation.result] == 1
        }
        # A move, return, or mutable place needs its own protected value. Parameters
        # themselves cannot be overwritten or consumed under the verified MIR ABI.
        protected = {block.terminator.value for block in function.blocks}
        for operation in operations:
            protected.update(operation.args[index] for index in operation.moves)
            place = operation.data.get('place')
            if place is not None:
                protected.add(place.root)
                protected.update(projection.index for projection in place.projections if projection.kind == 'index')
        replacements = {result: parameter for result, parameter in replacements.items() if result not in protected}
        if not replacements:
            continue
        for block in function.blocks:
            remaining = []
            for operation in block.operations:
                if operation.opcode == 'clone' and operation.result in replacements:
                    continue
                if operation.opcode == 'release' and operation.args[0] in replacements:
                    continue
                operation.args = tuple(replacements.get(argument, argument) for argument in operation.args)
                remaining.append(operation)
            block.operations = remaining
    verifier.verify(module)
    return module
