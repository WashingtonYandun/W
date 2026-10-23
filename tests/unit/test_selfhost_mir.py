"""Independent Compiler MIR production, interchange rejection, and execution parity."""
from copy import deepcopy
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from checker.TypeInterner import TypeInterner
from common.Platform import compiler_command, executable_name
from compiler.CompilerService import CompilerService
from error.Error import WysnaError
from mir.CCodeGen import CCodeGen
from mir.Exchange import import_module
from tooling.MirCLI import emit_mir, run_mir_command

ROOT = Path(__file__).resolve().parents[2]


class CompilerMirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import ensure_selfhost_compiler_binary
        cls.compiler = ensure_selfhost_compiler_binary(str(ROOT))

    def compile_ir(self, source, output, executable=None):
        completed = subprocess.run(
            [executable or self.compiler, "--emit-mir", str(source)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        if completed.returncode == 0:
            output.write_text(completed.stdout, encoding="utf-8")
        return completed

    def seed_ir(self, source):
        service = CompilerService()
        checked = service.check_file(source)
        return service.export_mir(checked)

    def execute_ir(self, payload, directory, name):
        module, interner = import_module(payload)
        c_path = directory / (name + ".c")
        binary = directory / executable_name(name)
        c_path.write_text(CCodeGen(interner).generate(module), encoding="utf-8")
        built = subprocess.run(
            compiler_command() + ["-std=c99", "-O1", f"-I{ROOT}", str(c_path), "-lm", "-o", str(binary)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(built.returncode, 0, built.stderr)
        return subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)

    def test_scalar_execution_matches_seed(self):
        cases = [
            ("fn add(x: int, y: int) -> int { x + y }\nprint(add(10, 20))", "30\n"),
            ("fn outer(x: int) -> int { inner(x) }\nfn inner(x: int) -> int { x * 2 }\nprint(outer(21))", "42\n"),
            ("fn main() -> int { print(7) return 12 }", "7\n"),
            ("fn main() { print(7) }\nprint(9)", "9\n"),
            ("fn main() { print(7) }\nmain()", "7\n"),
            ("fn main() -> int { print(7) return 12 }\n(main())", "7\n"),
            ("fn main() -> int { print(7) return 12 }\nmain() + 1", "7\n"),
            ("fn unit_id(x: unit) -> unit { return x }\nunit_id(print())", "\n"),
            ("fn identity(x: bool) -> bool { x }\nprint(identity(not false), 1 < 2, 2 >= 3, true != false)", "true true false true\n"),
            ("let number: float = -0.0\nprint(number, 0.1 + 0.2, int(4.75), float(true))", "-0.0 0.30000000000000004 4 1.0\n"),
            ("let x: int = 00012\nprint(-x * 2 + 30 / 3, 17 % 4)", "-14 1\n"),
            ("let maximum = 9223372036854775807\nlet minimum = -9223372036854775808\nprint(maximum + 1, minimum / -1, minimum % -1, -minimum)", "-9223372036854775808 -9223372036854775808 0 -9223372036854775808\n"),
            ("fn first() -> int { print(1) return 10 }\nfn second() -> int { print(2) return 20 }\nfn combine(x: int, y: int) -> int { x + y }\nprint(combine(first(), second()))", "1\n2\n30\n"),
            ("pub fn twice(x: float) -> float { x * 2.0 }\neprint(twice(1.25))\nprint()", "\n"),
        ]
        with tempfile.TemporaryDirectory(prefix="wysna-mir-parity-") as temporary:
            root = Path(temporary)
            source = root / "program.wysna"
            output = root / "compiler.mir.json"
            for code, expected in cases:
                with self.subTest(source=code):
                    source.write_text(code + "\n", encoding="utf-8")
                    compiled = subprocess.run(
                        [sys.executable, str(ROOT / "main.py"), "emit-mir", "--implementation=compiler", str(source), "-o", str(output)],
                        cwd=ROOT, capture_output=True, text=True, timeout=120,
                    )
                    self.assertEqual(compiled.returncode, 0, compiled.stderr)
                    payload = output.read_text(encoding="utf-8")
                    self.assertEqual(json.loads(payload)["type_arena"], TypeInterner().to_snapshot())
                    seed_payload = self.seed_ir(source)
                    compiler_module, _ = import_module(payload)
                    seed_module, _ = import_module(seed_payload)
                    self.assertEqual(compiler_module.functions[-1].return_type, seed_module.functions[-1].return_type)
                    compiler_result = self.execute_ir(payload, root, "compiler-program")
                    seed_result = self.execute_ir(seed_payload, root, "seed-program")
                    self.assertEqual((compiler_result.returncode, compiler_result.stdout, compiler_result.stderr),
                                     (seed_result.returncode, seed_result.stdout, seed_result.stderr))
                    self.assertEqual(compiler_result.stdout, expected)

    def test_control_flow_execution_matches_seed(self):
        cases = [
            ("fn choose(x: int) -> int { if x < 0 { 1 } elif x == 0 { 2 } else { 3 } }\nprint(choose(-1), choose(0), choose(1))", "1 2 3\n"),
            ("fn choose(x: bool) -> int { if x { return 7 } else { return 9 } }\nprint(choose(true), choose(false))", "7 9\n"),
            ("fn choose(x: bool) -> int { if x { return 7 }\n10 }\nprint(choose(true), choose(false))", "7 10\n"),
            ("let mut x = 1\nlet mut y = 0\nprint(x + (x = 2), x, y = x = 3, x, y)", "3 2 3 3 3\n"),
            ("fn pair(a: int, b: int) { print(a, b) }\nlet mut x = 1\npair(x, x = 2)\nprint(x)", "1 2\n2\n"),
            ("let mut x = 0\nwhile x < 5 { x = x + 1\nif x == 2 { continue }\nif x == 4 { break }\nprint(x) }\nprint(x)", "1\n3\n4\n"),
            ("let mut i = 0\nlet mut total = 0\nwhile i < 3 { let mut j = 0\nwhile j < 4 { j = j + 1\nif j == 2 { continue }\nif j == 4 { break }\ntotal = total + 1 }\ni = i + 1 }\nprint(total)", "6\n"),
            ("fn search() -> int { let mut i = 0\nwhile i < 5 { if i == 3 { return i }\ni = i + 1 }\nreturn -1 }\nprint(search())", "3\n"),
            ("let mut b = false\nlet mut x = 1.0\nwhile not b { x = x + 1.5\nb = true }\nprint(b, x)", "true 2.5\n"),
            ("fn yes() -> bool { print(1) true }\nprint(false and yes(), true or yes(), true and yes(), false or yes())", "1\n1\nfalse true true true\n"),
            ("let mut x = 0\nprint(false and ((x = 1) == 1), true or ((x = 2) == 2), x)\nprint(true and ((x = 3) == 3), x)", "false true 0\ntrue 3\n"),
            ("print(false and (1 / 0 == 0), true or (1 / 0 == 0))", "false true\n"),
            ("let x = 10\nif true { let x = 20\nprint(x) }\nprint(x)\nwhile false { print(99) }", "20\n10\n"),
            ("fn work() { let value = print(1)\nlet mut i = 0\nwhile i < 3 { let local = print(i)\ni = i + 1\nif i == 1 { continue }\nif i == 3 { break } }\nvalue }\nwork()", "1\n0\n1\n2\n"),
            ("fn check(x: bool) -> bool { let value = print(1)\nx }\nlet mut i = 0\nwhile check(i < 2) { i = i + 1 }\nprint(i)", "1\n1\n1\n2\n"),
            ("fn choose(a: bool, b: bool) -> int { if a { if b { 1 } else { 2 } } else { 3 } }\nprint(choose(true, false), choose(false, true))", "2 3\n"),
        ]
        with tempfile.TemporaryDirectory(prefix="wysna-cfg-parity-") as temporary:
            root = Path(temporary)
            source = root / "program.wysna"
            output = root / "module.json"
            for code, expected in cases:
                with self.subTest(source=code):
                    source.write_text(code + "\n", encoding="utf-8")
                    compiled = self.compile_ir(source, output)
                    self.assertEqual(compiled.returncode, 0, compiled.stderr)
                    compiler_result = self.execute_ir(output.read_text(), root, "compiler")
                    seed_result = self.execute_ir(self.seed_ir(source), root, "seed")
                    self.assertEqual((compiler_result.returncode, compiler_result.stdout, compiler_result.stderr),
                                     (seed_result.returncode, seed_result.stdout, seed_result.stderr))
                    self.assertEqual(compiler_result.stdout, expected)

    def test_native_cfg_verifier_rejects_corruption(self):
        from tools.bundle_selfhost import MODULE_ORDER
        driver = r'''
let cli = args()
let payload = emit_scalar_mir("fn choose(flag: bool) -> int { let output = print(8)\nlet chosen = if flag { 2 } else { 3 }\nchosen }\nprint(choose(true))", "verifier.wysna")
let fault = cli[1]
if fault == "target" { mir_functions[0].blocks[0].terminator.targets[0] = 999 }
if fault == "condition" {
    for i in 0..len(mir_functions[0].slots) {
        if mir_functions[0].slots[i].type_id == 1 { mir_functions[0].blocks[0].terminator.value = i break }
    }
}
if fault == "parameter" { mir_functions[0].params.append(0) }
if fault == "opcode" { mir_functions[0].blocks[0].operations[0].opcode = "invalid" }
if fault == "terminator" { mir_functions[0].blocks[0].terminator.kind = "" }
if fault == "join" {
    # Each arm ends by moving its escaped value to the common result slot.
    mir_functions[0].blocks[1].operations.pop()
}
if fault == "leak" {
    for i in 0..len(mir_functions[0].blocks) {
        let mut operations: list[MirOperation] = []
        for operation in mir_functions[0].blocks[i].operations {
            if operation.opcode != "release" { operations.append(operation) }
        }
        mir_functions[0].blocks[i].operations = operations
    }
}
if fault == "consumed" {
    for i in 0..len(mir_functions[0].blocks) {
        if mir_functions[0].blocks[i].terminator.kind == "return" {
            let block = mir_functions[0].blocks[i]
            let mut moved = -1
            for operation in block.operations { if operation.opcode == "store" { moved = operation.args[0] } }
            let returned = block.terminator.value
            mir_functions[0].blocks[i].operations.append(MirOperation { opcode: "clone", result: returned, args: [moved], name: "", value: mir_literal_unit(), source: block.terminator.source })
        }
    }
}
if fault == "backedge" or fault == "live_backedge" {
    let ignored = emit_scalar_mir("let mut i = 0\nwhile i < 2 { i = i + 1 }\nprint(i)", "loop.wysna")
    let function = mir_functions[0]
    let source = function.source
    let slot = len(function.slots)
    if fault == "backedge" {
        mir_functions[0].slots.append(MirSlot { type_id: 3, name: "", parameter: false, origin: -1 })
        let binding = function.blocks[0].operations[1].result
        mir_functions[0].blocks[2].operations.append(MirOperation { opcode: "store", result: slot, args: [binding], name: "", value: mir_literal_unit(), source: source })
    } else {
        mir_functions[0].slots.append(MirSlot { type_id: 1, name: "", parameter: false, origin: -1 })
        let operands: list[int] = []
        mir_functions[0].blocks[2].operations.append(MirOperation { opcode: "const", result: slot, args: operands, name: "", value: mir_literal_unit(), source: source })
    }
}
mir_verify()
print("verified")
'''
        modules = [(ROOT / "selfhost/src" / name).read_text() for name in MODULE_ORDER if name != "09_main.wysna"]
        service = CompilerService()
        checked = service.check("".join(modules) + driver, "mir-verifier-test.wysna")
        generated = service.emit_c(checked, backend="ast").source
        with tempfile.TemporaryDirectory(prefix="wysna-cfg-verifier-") as temporary:
            root = Path(temporary)
            c_path = root / "verifier.c"
            binary = root / executable_name("verifier")
            c_path.write_text(generated, encoding="utf-8")
            built = subprocess.run(compiler_command() + ["-std=c99", "-O0", f"-I{ROOT}", str(c_path), "-lm", "-o", str(binary)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stderr)
            for fault in ("valid", "target", "condition", "parameter", "opcode", "terminator", "join", "leak", "consumed", "backedge", "live_backedge"):
                with self.subTest(fault=fault):
                    result = subprocess.run([str(binary), fault], capture_output=True, text=True, timeout=15)
                    if fault == "valid":
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout, "verified\n")
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("[W9999]", result.stderr)

    def test_runtime_checks_keep_source_locations(self):
        with tempfile.TemporaryDirectory(prefix="wysna-mir-runtime-") as temporary:
            root = Path(temporary)
            source = root / 'árbol "quoted".wysna'
            output = root / "module.json"
            for operator in ("/", "%"):
                source.write_text(f"fn divide(x: int) -> int {{\n return x {operator} 0\n}}\nprint(divide(1))\n", encoding="utf-8")
                compiled = self.compile_ir(source, output)
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                payload = output.read_text(encoding="utf-8")
                self.assertEqual(json.loads(payload)["module"]["file"], str(source))
                for name, candidate in (("compiler", payload), ("seed", self.seed_ir(source))):
                    result = self.execute_ir(candidate, root, name)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("[W4001]", result.stderr)
                    self.assertIn(f"{source}:2:", result.stderr)

    def test_semantic_rejections_match_seed_and_preserve_output(self):
        cases = [
            ("fn f(x: int) -> int { x }\nprint(f(true))", "W2001"),
            ("fn f() -> int { return true }", "W2004"),
            ("print(missing)", "W1001"),
            ("fn f(x: int) -> int { x }\nprint(f())", "W2005"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "invalid.wysna"
            output = Path(temporary) / "module.json"
            for code, expected in cases:
                with self.subTest(source=code):
                    source.write_text(code + "\n", encoding="utf-8")
                    output.write_text("keep existing artifact", encoding="utf-8")
                    compiled = subprocess.run(
                        [sys.executable, str(ROOT / "main.py"), "emit-mir", "--implementation=compiler", str(source), "-o", str(output)],
                        cwd=ROOT, capture_output=True, text=True, timeout=120,
                    )
                    self.assertNotEqual(compiled.returncode, 0)
                    self.assertIn(f"[{expected}]", compiled.stderr)
                    self.assertEqual(output.read_text(), "keep existing artifact")
                    with self.assertRaises(WysnaError) as caught:
                        CompilerService().check_file(source)
                    self.assertEqual(caught.exception.code, expected)

    def test_unsupported_features_are_explicit(self):
        cases = [
            'print("text")',
            "for i in 0..3 { print(i) }",
            "fn identity[T](x: T) -> T { x }\nprint(identity(2))",
            "struct Box { value: int }\nlet box = Box { value: 1 }\nprint(box.value)",
            "let global = 3\nfn read() -> int { global }\nprint(read())",
            'fn fail() -> int ! str { return Err("error") }',
            "let values = [1, 2]\nprint(len(values))",
            "let increment = |x: int| { x + 1 }\nprint(increment(2))",
            'extern "C" fn native(x: int) -> int\nprint(1)',
        ]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "unsupported.wysna"
            output = Path(temporary) / "module.json"
            for code in cases:
                with self.subTest(source=code):
                    source.write_text(code + "\n", encoding="utf-8")
                    CompilerService().check_file(source)
                    compiled = self.compile_ir(source, output)
                    self.assertNotEqual(compiled.returncode, 0)
                    self.assertIn("[W2013]", compiled.stderr)
                    self.assertIn("scalar-cfg-v1", compiled.stderr)
                    self.assertFalse(output.exists())
            source.write_text('import "missing.wysna"\n', encoding="utf-8")
            imported = self.compile_ir(source, output)
            self.assertIn("[W2013]", imported.stderr)
            self.assertIn("imports", imported.stderr)

    def test_exchange_verifier_rejects_tampered_compiler_ir(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "program.wysna"
            output = Path(temporary) / "module.json"
            source.write_text("fn add(x: int, y: int) -> int { x + y }\nprint(add(1, 2))\n")
            result = self.compile_ir(source, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = json.loads(output.read_text())
            mutations = []
            bad = deepcopy(original)
            bad["module"]["functions"][0]["slots"][0]["type_id"] = 999
            mutations.append(bad)
            bad = deepcopy(original)
            bad["module"]["functions"][0]["blocks"][0]["operations"][0]["args"] = {"$tuple": [999]}
            mutations.append(bad)
            bad = deepcopy(original)
            bad["module"]["functions"][0]["return_type"] = 2
            mutations.append(bad)
            bad = deepcopy(original)
            op = next(op for fn in bad["module"]["functions"] for op in fn["blocks"][0]["operations"] if op["opcode"] == "call")
            op["data"]["name"] = "missing"
            mutations.append(bad)
            bad = deepcopy(original)
            op = next(op for op in bad["module"]["functions"][0]["blocks"][0]["operations"] if op["opcode"] == "runtime")
            op["data"]["name"] = "system"
            mutations.append(bad)
            for payload in mutations:
                with self.assertRaises(WysnaError):
                    import_module(json.dumps(payload))

    def test_exchange_rejects_corrupted_control_flow(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "branch.wysna"
            output = root / "module.json"
            source.write_text("fn choose(flag: bool) -> int { if flag { 2 } else { 3 } }\nprint(choose(true))\n")
            result = self.compile_ir(source, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = json.loads(output.read_text())
            for fault in ("target", "condition", "terminator", "join"):
                with self.subTest(fault=fault):
                    bad = deepcopy(original)
                    function = bad["module"]["functions"][0]
                    branch = function["blocks"][0]["terminator"]
                    if fault == "target":
                        branch["targets"] = {"$tuple": [999, 2]}
                    elif fault == "condition":
                        branch["value"] = next(slot["id"] for slot in function["slots"] if slot["type_id"] == 3)
                    elif fault == "terminator":
                        branch["kind"] = ""
                    else:
                        function["blocks"][1]["operations"].pop()
                    with self.assertRaises(WysnaError):
                        import_module(json.dumps(bad))

    def test_bootstrap_stages_emit_identical_ir(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "same.wysna"
            source.write_text("fn add(x: int) -> int { let mut y = x\nwhile y < 3 { y = y + 1 }\nif y == 3 { y + 2 } else { y } }\nprint(add(1))\n")
            outputs = []
            for stage in ("stage1", "stage2"):
                output = Path(temporary) / (stage + ".json")
                binary = ROOT / ".wysna_cache" / executable_name(stage)
                result = self.compile_ir(source, output, str(binary))
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(output.read_bytes())
            self.assertEqual(outputs[0], outputs[1])

    def test_cli_producers_and_source_protection(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "program.wysna"
            source.write_text("print(42)\n")
            for implementation in ("seed", "compiler"):
                output = Path(temporary) / (implementation + ".json")
                result = subprocess.run(
                    [sys.executable, str(ROOT / "main.py"), "emit-mir", f"--implementation={implementation}", str(source), "-o", str(output)],
                    cwd=ROOT, capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                import_module(output.read_text())
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(run_mir_command([f"--implementation={implementation}", str(source), "-o", str(source)]), 2)
                self.assertEqual(source.read_text(), "print(42)\n")
            # A prebuilt Compiler checks the program without invoking Seed's frontend.
            with patch("main.ensure_selfhost_compiler_binary", return_value=self.compiler), patch.object(CompilerService, "check", side_effect=AssertionError("Seed fallback")):
                payload, _ = emit_mir(source, "compiler")
                import_module(payload)

            alias = Path(temporary) / "source-alias.json"
            os.link(source, alias)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(run_mir_command([str(source), "-o", str(alias)]), 2)
            dependency = Path(temporary) / "dependency.wysna"
            dependency.write_text("pub fn number() -> int { 42 }\n")
            source.write_text('import "dependency.wysna"\nprint(dependency.number())\n')
            before = dependency.read_bytes()
            with redirect_stderr(io.StringIO()):
                self.assertEqual(run_mir_command([str(source), "-o", str(dependency)]), 2)
            self.assertEqual(dependency.read_bytes(), before)

    def test_service_export_rejects_foreign_checked_programs(self):
        owner = CompilerService()
        checked = owner.check("print(42)")
        import_module(owner.export_mir(checked))
        with self.assertRaises(WysnaError) as caught:
            CompilerService().export_mir(checked)
        self.assertEqual(caught.exception.stage, "semantic-boundary")

    def test_cli_usage_and_missing_input(self):
        for args, code in (([], "W5002"), (["--implementation=other", "file.wysna"], "W5002"),
                           (["/nonexistent-wysna-mir-source.wysna"], "W5003")):
            with self.subTest(args=args), redirect_stderr(io.StringIO()) as stderr:
                self.assertNotEqual(run_mir_command(args), 0)
                self.assertIn(f"[{code}]", stderr.getvalue())

    def test_numeric_literal_bounds(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "literal.wysna"
            output = Path(temporary) / "module.json"
            for literal in ("9223372036854775808", "-9223372036854775809", "999999999999999999999999999999", "9" * 400 + ".0"):
                source.write_text(f"print({literal})\n")
                result = self.compile_ir(source, output)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("[W0002]", result.stderr)
                self.assertFalse(output.exists())
                with self.assertRaises(WysnaError) as caught:
                    CompilerService().check_file(source)
                self.assertEqual(caught.exception.code, "W0002")


if __name__ == "__main__":
    unittest.main()
