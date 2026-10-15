import os
import sys
import json
from parser.Parser import Parser
from error.Error import ParserError
from node.NodeType import Program

def test_parser_suite():
    valid_dir = "tests/parser/valid"
    invalid_dir = "tests/parser/invalid"

    valid_files = sorted([f for f in os.listdir(valid_dir) if f.endswith(".w")])
    invalid_files = sorted([f for f in os.listdir(invalid_dir) if f.endswith(".w")])

    valid_passed = 0
    invalid_passed = 0
    failures = []

    print("==================================================")
    print("W Language Parser Conformance Suite (SPEC v0.1)")
    print("==================================================")

    print(f"\n--- Parser Valid ({len(valid_files)} tests) ---")
    for f in valid_files:
        path = os.path.join(valid_dir, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()

        try:
            parser = Parser(file=f)
            ast = parser.parse(code)

            # Assert AST validity
            assert isinstance(ast, Program), f"Expected Program AST root, got {type(ast)}"
            ast_dict = ast.to_dict()
            assert ast_dict.get("w_ast_version") == "0.1", "AST must have w_ast_version 0.1"

            # Check that AST is serializable to JSON
            json_str = json.dumps(ast_dict)
            assert len(json_str) > 0

            print(f"  [PASS] {f} ({len(ast.body)} statements)")
            valid_passed += 1
        except Exception as e:
            print(f"  [FAIL] {f}: {e}")
            failures.append((f, str(e)))

    print(f"\n--- Parser Invalid ({len(invalid_files)} tests) ---")
    for f in invalid_files:
        path = os.path.join(invalid_dir, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()

        try:
            parser = Parser(file=f)
            ast = parser.parse(code)
            print(f"  [FAIL] {f}: Expected ParserError, but AST produced: {ast}")
            failures.append((f, "Expected ParserError but succeeded"))
        except ParserError as err:
            assert err.code.startswith("P"), f"Parser error code should start with 'P', got {err.code}"
            assert err.line >= 1 and err.col >= 1, f"Invalid position line={err.line}, col={err.col}"
            print(f"  [PASS] {f}: Caught {err.code} at line {err.line}:{err.col} -> {err.message}")
            invalid_passed += 1
        except Exception as e:
            print(f"  [FAIL] {f}: Unexpected exception type {type(e).__name__}: {e}")
            failures.append((f, f"Wrong exception: {e}"))

    print("\n==================================================")
    print(f"Parser valid:   {valid_passed}/{len(valid_files)}")
    print(f"Parser invalid: {invalid_passed}/{len(invalid_files)}")
    print(f"FAILED:         {len(failures)}")
    print("==================================================")

    if failures:
        sys.exit(1)
    else:
        print("ALL PARSER CONFORMANCE TESTS PASSED.")
        sys.exit(0)

if __name__ == "__main__":
    test_parser_suite()
