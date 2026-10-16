"""Recursive typed expression trees with lexical scopes and an independent model."""
from dataclasses import dataclass
import random


def integer(value):
    return (value + (1 << 63)) % (1 << 64) - (1 << 63)


def render(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return '[' + ', '.join(render(item) for item in value) + ']'
    return str(value)


def string_literal(value):
    escapes = {'\\': '\\\\', '"': '\\"', '\n': '\\n', '\0': '\\0'}
    return '"' + ''.join(escapes.get(character, character) for character in value) + '"'


@dataclass(frozen=True)
class Expression:
    kind: str
    type: str
    args: tuple = ()
    value: object = None

    def source(self):
        args = [arg.source() for arg in self.args]
        if self.kind == 'literal':
            return string_literal(self.value) if self.type == 'str' else render(self.value)
        if self.kind == 'variable':
            return self.value
        if self.kind == 'binary':
            return '(' + args[0] + ' ' + self.value + ' ' + args[1] + ')'
        if self.kind == 'not':
            return '(not ' + args[0] + ')'
        if self.kind == 'observe':
            return 'observe(' + str(self.value) + ', ' + args[0] + ')'
        if self.kind == 'if':
            return '(if ' + args[0] + ' { ' + args[1] + ' } else { ' + args[2] + ' })'
        if self.kind == 'match':
            return '(match ' + args[0] + ' { ' + str(self.value) + ' => ' + args[1] + ', _ => ' + args[2] + ' })'
        if self.kind == 'bind':
            return ('(if true { let ' + self.value + ' = ' + args[0] + '\nlet property_result = ' +
                    args[1] + '\nproperty_result } else { 0 })')
        if self.kind == 'recover':
            return '(attempt(' + args[0] + ', ' + args[1] + ') else failure { ' + args[2] + ' })'
        if self.kind == 'list':
            return '[' + ', '.join(args) + ']'
        if self.kind == 'index':
            return '(' + args[0] + ')[0]'
        raise AssertionError(self.kind)

    def evaluate(self, environment, events):
        def evaluate(index):
            return self.args[index].evaluate(environment, events)
        if self.kind == 'literal':
            return self.value
        if self.kind == 'variable':
            return environment[self.value]
        if self.kind == 'binary':
            left = evaluate(0)
            if self.value == 'and':
                return left and evaluate(1)
            if self.value == 'or':
                return left or evaluate(1)
            right = evaluate(1)
            if self.value == '+':
                result = left + right
                return integer(result) if self.type == 'int' else result
            if self.value == '-':
                return integer(left - right)
            if self.value == '*':
                return integer(left * right)
            return {'==': left == right, '!=': left != right, '<': left < right,
                    '<=': left <= right}[self.value]
        if self.kind == 'not':
            return not evaluate(0)
        if self.kind == 'observe':
            value = evaluate(0)
            events.append(self.value)
            return value
        if self.kind == 'if':
            return evaluate(1 if evaluate(0) else 2)
        if self.kind == 'match':
            return evaluate(1 if evaluate(0) == self.value else 2)
        if self.kind == 'bind':
            value = evaluate(0)
            scope = dict(environment)
            scope[self.value] = value
            return self.args[1].evaluate(scope, events)
        if self.kind == 'recover':
            value = evaluate(0)
            failed = evaluate(1)
            return evaluate(2) if failed else value
        if self.kind == 'list':
            return [evaluate(index) for index in range(len(self.args))]
        if self.kind == 'index':
            return evaluate(0)[0]
        raise AssertionError(self.kind)


class Generator:
    def __init__(self, seed):
        self.random = random.Random(seed)

    def expression(self, type, depth, names=()):
        rng = self.random
        if type == 'int':
            kinds = ['literal'] + (['variable'] if names else [])
            if depth:
                kinds += ['binary', 'observe', 'if', 'match', 'bind', 'recover', 'index']
            kind = rng.choice(kinds)
            child = lambda: self.expression('int', depth - 1, names)
            condition = lambda: self.expression('bool', depth - 1, names)
            if kind == 'literal':
                return Expression(kind, type, value=rng.randint(-10, 10))
            if kind == 'variable':
                return Expression(kind, type, value=rng.choice(names))
            if kind == 'binary':
                return Expression(kind, type, (child(), child()), rng.choice(['+', '-', '*']))
            if kind == 'observe':
                return Expression(kind, type, (child(),), rng.randint(1, 99))
            if kind == 'if':
                return Expression(kind, type, (condition(), child(), child()))
            if kind == 'match':
                return Expression(kind, type, (child(), child(), child()), rng.randint(-2, 2))
            if kind == 'bind':
                name = rng.choice(names) if names and rng.choice([True, False]) else 'scope' + str(depth)
                return Expression(kind, type, (child(), self.expression(type, depth - 1, names + (name,))), name)
            if kind == 'recover':
                return Expression(kind, type, (child(), condition(), child()))
            return Expression('index', type, (self.expression('list[int]', depth - 1, names),))
        if type == 'bool':
            kinds = ['literal'] + (['compare', 'and', 'or', 'not'] if depth else [])
            kind = rng.choice(kinds)
            if kind == 'literal':
                return Expression(kind, type, value=rng.choice([True, False]))
            if kind == 'compare':
                args = tuple(self.expression('int', depth - 1, names) for _ in range(2))
                return Expression('binary', type, args, rng.choice(['==', '!=', '<', '<=']))
            if kind == 'not':
                return Expression(kind, type, (self.expression(type, depth - 1, names),))
            return Expression('binary', type, tuple(self.expression(type, depth - 1, names) for _ in range(2)), kind)
        if type == 'str':
            if depth and rng.choice([True, False]):
                return Expression('binary', type, tuple(self.expression(type, depth - 1, names) for _ in range(2)), '+')
            return Expression('literal', type, value=rng.choice(['A', 'é', '🙂', '\0', 'xy']))
        if type == 'list[int]':
            return Expression('list', type, tuple(self.expression('int', max(depth - 1, 0), names)
                                                   for _ in range(rng.randint(1, 3))))
        raise AssertionError(type)


def generate_typed_properties(seed):
    generator = Generator(seed)
    expressions = []
    source = ['let mut events: list[int] = []',
              'fn observe(tag: int, value: int) -> int { events.append(tag)\nreturn value }',
              'fn attempt(value: int, fail: bool) -> int ! str { if fail { return Err("failed") }\nreturn value }',
              'fn properties() -> unit {']
    expected = []
    for type in ('int', 'bool', 'str', 'list[int]') * 2:
        expression = generator.expression(type, 4)
        expressions.append(expression)
        events = []
        value = expression.evaluate({}, events)
        source.extend(['events.clear()', 'print(' + expression.source() + ')', 'print(events)'])
        expected.extend([render(value), render(events)])
    initial = generator.expression('list[int]', 3)
    replacement = generator.expression('int', 3)
    expressions.extend([initial, replacement])
    events = []
    snapshot = initial.evaluate({}, events)
    mutated = list(snapshot)
    mutated[0] = replacement.evaluate({}, events)
    source.extend(['events.clear()', 'let mut values = ' + initial.source(), 'let snapshot = values',
                   'values[0] = ' + replacement.source(), 'print(snapshot, values)', 'print(events)'])
    expected.extend([render(snapshot) + ' ' + render(mutated), render(events)])
    initial = generator.expression('int', 3)
    replacement = generator.expression('int', 3)
    body = generator.expression('int', 3, ('captured', 'argument'))
    expressions.extend([initial, replacement, body])
    events = []
    captured = initial.evaluate({}, events)
    current = replacement.evaluate({}, events)
    returned = integer(integer(captured + 3) + body.evaluate({'captured': captured, 'argument': 3}, events))
    source.extend(['events.clear()', 'let mut captured = ' + initial.source(),
                   'let callback = |argument: int| -> int { return captured + argument + ' + body.source() + ' }',
                   'captured = ' + replacement.source(), 'print(callback(3), captured)', 'print(events)', '}', 'properties()'])
    expected.extend([str(returned) + ' ' + str(current), render(events)])
    return '\n'.join(source) + '\n', '\n'.join(expected) + '\n', expressions
