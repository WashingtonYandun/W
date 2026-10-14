"""C01: shared type arenas, module identity, reuse and invalidation contracts."""
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from compiler.CompilationSession import CompilationSession
from checker.TypeChecker import TypeChecker
from parser.Parser import Parser
from runtime.Interpreter import Interpreter
from codegen.CCodeGen import CCodeGen
from hir.HirBuilder import HirBuilder
from hir.HirCCodeGen import HirCCodeGen
from error.Error import WError


def run_session_tests():
    with tempfile.TemporaryDirectory(prefix='w-session-') as temporary:
        root = Path(temporary).resolve()
        sources = {
            'shared.w': """
                print("init")
                struct Item { value: bool }
                enum Mode { On, Off }
                fn mode() -> Mode { return On }
                fn shadow(value: int) -> int { return value }
                fn identity[Item](x: Item) -> Item { return x }
                fn id[T](x: T) -> T { return x }
                let values = [3]
                fn value() -> int { return id(values[0]) }
            """.strip(),
            'left.w': """
                import "shared.w"
                struct Item { value: int }
                fn make() -> Item { return Item { value: shared.value() } }
            """.strip(),
            'right.w': """
                import "shared.w"
                struct Item { value: str }
                fn make() -> Item { return Item { value: "right" } }
            """.strip(),
            'main.w': """
                import "left.w"
                import "right.w"
                import "shared.w"
                fn main() { let a = left.make()
                let b = right.make()
                print(a.value, b.value, shared.id(7), shared.id[str]("yes"), shared.id(Some(4)) ?? 0)
                let c = shared.identity(a)
                print(a, b, c.value, shared.mode(), shared.shadow(2)) }
            """.strip(),
        }
        for name, source in sources.items():
            (root / name).write_text(source)
        session = CompilationSession(root)
        entry = root / 'main.w'
        unit = session.check_source(sources['main.w'], str(entry))
        assert len(session.modules) == 4
        assert all(count == 1 for count in session.check_counts.values())
        assert all(count == 1 for count in session.parse_counts.values())
        assert all(count == 1 for count in session.sources.read_counts.values())
        left = session.modules[str(root / 'left.w')]
        right = session.modules[str(root / 'right.w')]
        left_type = left.exports.lookup_type('Item')
        right_type = right.exports.lookup_type('Item')
        assert left_type != right_type
        assert session.interner.intern(left_type) != session.interner.intern(right_type)
        assert left.dependencies[0] is right.dependencies[0]
        assert len({node.decl_id for node in session.declarations.values()}) == len(session.declarations)
        assert all(module.checker.interner is session.interner for module in session.modules.values())
        # Consumers must not read or check a dependency after the checked snapshot exists.
        original_read, original_check = session.sources.read, TypeChecker._check_program
        session.sources.read = lambda path: (_ for _ in ()).throw(AssertionError('Source reread during lowering'))
        TypeChecker._check_program = lambda *args: (_ for _ in ()).throw(AssertionError('Rechecked during lowering'))
        try:
            expected = 'init\n3 right 7 yes 4\nItem { value: 3 } Item { value: \"right\" } 3 Mode.On 2\n'
            output = io.StringIO()
            Interpreter(stdout=output).interpret(unit.program)
            assert output.getvalue() == expected, output.getvalue()
            for backend in ('ast', 'hir'):
                if backend == 'hir':
                    module = HirBuilder(session.interner, str(entry)).lower(unit.program)
                    imported = next(function for function in module.functions if function.name == left.names['make'])
                    assert imported.span.file_path == str(root / 'left.w')
                    assert imported.span.file_id == left.module_id
                    from checker.TypeInterner import TypeInterner
                    try:
                        HirCCodeGen(TypeInterner(), str(entry)).generate(module)
                    except WError as error:
                        assert error.code == 'W9999'
                    else:
                        raise AssertionError('Foreign arena was accepted by HIR emitter')
                    old_type = imported.return_type_id
                    imported.return_type_id = 0
                    try:
                        HirCCodeGen(session.interner, str(entry)).generate(module)
                    except WError as error:
                        assert error.file == str(root / 'left.w'), str(error)
                    else:
                        raise AssertionError('Malformed dependency HIR was accepted')
                    imported.return_type_id = old_type
                    code = HirCCodeGen(session.interner, str(entry)).generate(module)
                else:
                    code = CCodeGen(file=str(entry)).generate(unit.program)
                c_path, binary = root / (backend + '.c'), root / backend
                c_path.write_text(code)
                flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if os.environ.get('W_SANITIZE') == '1' else []
                compile_result = subprocess.run([os.environ.get('CC', 'cc')] + flags + ['-std=c99', '-I' + str(Path(__file__).parent), str(c_path), '-o', str(binary)], capture_output=True, text=True, timeout=120)
                assert compile_result.returncode == 0, compile_result.stderr
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30, env=dict(os.environ, W_MEM_CHECK='1', ASAN_OPTIONS='detect_leaks=' + ('1' if sys.platform.startswith('linux') else '0'), UBSAN_OPTIONS='halt_on_error=1'))
                assert result.returncode == 0, result.stderr
                assert result.stdout == expected, (backend, result.stdout)
        finally:
            session.sources.read, TypeChecker._check_program = original_read, original_check
        assert session.check_source(sources['main.w'], str(entry)) is unit
        from checker.TypeInterner import TypeInterner
        try:
            HirBuilder(TypeInterner(), str(entry)).lower(unit.program)
        except WError as error:
            assert error.code == 'W9999'
        else:
            raise AssertionError('Foreign arena was accepted by HIR builder')
        # Same canonical file through two namespaces executes initialization once.
        (root / 'alias.w').symlink_to(root / 'shared.w')
        alias_source = 'import "shared.w"\nimport "alias.w"\nprint(shared.value(), alias.value())'
        alias_unit = session.check_source(alias_source, str(entry))
        assert alias_unit.dependencies[0] is alias_unit.dependencies[1]
        alias_output = io.StringIO()
        Interpreter(stdout=alias_output).interpret(alias_unit.program)
        assert alias_output.getvalue() == 'init\n3 3\n'
        unit = session.check_source(sources['main.w'], str(entry))
        previous_stat = (root / 'shared.w').stat()
        (root / 'shared.w').write_text(sources['shared.w'].replace('[3]', '[9]'))
        os.utime(root / 'shared.w', ns=(previous_stat.st_atime_ns, previous_stat.st_mtime_ns))
        refreshed = session.check_source(sources['main.w'], str(entry))
        assert refreshed is not unit and refreshed.generation == unit.generation + 1
        refreshed_output = io.StringIO()
        Interpreter(stdout=refreshed_output).interpret(refreshed.program)
        assert refreshed_output.getvalue() == 'init\n9 right 7 yes 4\nItem { value: 9 } Item { value: "right" } 9 Mode.On 2\n'
        try:
            session.link(unit.program)
        except WError as error:
            assert error.code == 'W9999'
        else:
            raise AssertionError('Stale arena was accepted')
        # Nominal mismatches identify the source modules without exposing mangling.
        mismatch = 'import "left.w"\nimport "right.w"\nfn take(x: int) {}\ntake(left.make())'
        try:
            session.check_source(mismatch, str(entry))
        except WError as error:
            assert '__wm_' not in str(error) and 'left.w::Item' in str(error), str(error)
        else:
            raise AssertionError('Nominal argument mismatch was accepted')
        for suffix in ('let alias = shared', 'print(shared)', 'print(left.shared)'):
            try:
                session.check_source('import "shared.w"\nimport "left.w"\n' + suffix, str(entry))
            except WError as error:
                assert error.code == 'W2003' and 'runtime values' in error.message, str(error)
            else:
                raise AssertionError('Runtime module value reached lowering')
        # Prefix collisions are rejected even in local scopes.
        for source in ('fn main(__wm_local: int) {}', 'enum Option[T] { Mine(T) }'):
            try:
                session.check_source(source, str(entry))
            except WError as error:
                assert error.code == 'W1002', str(error)
            else:
                raise AssertionError('Reserved identity was accepted')
        refreshed = session.check_source(sources['main.w'], str(entry))
        session.options['profile'] = 'strict'
        changed_options = session.check_source(sources['main.w'], str(entry))
        assert changed_options is not refreshed
        (root / 'cycle.w').write_text('import "main.w"')
        cycle_source = 'import "cycle.w"'
        try:
            session.check_source(cycle_source, str(entry))
        except WError as error:
            assert error.code == 'W1003' and 'main.w -> cycle.w -> main.w' in str(error), str(error)
            assert error.file == str(root / 'cycle.w')
        else:
            raise AssertionError('Import cycle was accepted')
        (root / 'bad.w').write_text('let value: int = "wrong"')
        try:
            session.check_source('import "bad.w"', str(entry))
        except WError as error:
            assert error.file == str(root / 'bad.w'), str(error)
        else:
            raise AssertionError('Invalid dependency was accepted')
        # The legacy checker API also reparses its original source on invalidation.
        legacy_session = CompilationSession(root)
        legacy_ast = Parser(file=str(entry)).parse(sources['main.w'])
        legacy_checker = TypeChecker(file=str(entry), session=legacy_session)
        legacy_checker.check(legacy_ast)
        checked_scope = legacy_checker.global_scope
        legacy_checker.check(legacy_ast)
        assert legacy_checker.global_scope is checked_scope
        assert legacy_checker.global_scope.lookup_symbol('main') is not None
        previous_arena = legacy_checker.interner
        legacy_session.options['debug'] = True
        legacy_checker.check(legacy_ast)
        assert legacy_checker.interner is not previous_arena
        assert legacy_ast.interner is legacy_checker.interner
    print('C01 shared arenas, checked reuse, diamond imports, generic exports, identity, invalidation and diagnostics passed')
    return True


if __name__ == '__main__':
    run_session_tests()
