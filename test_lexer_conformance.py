import os
import sys
from lexer.Lexer import Lexer
from error.Error import LexerError
from token.TokenType import TokenType

def test_lexer_suite():
    valid_dir = "tests/lexer/valid"
    invalid_dir = "tests/lexer/invalid"

    valid_files = sorted([f for f in os.listdir(valid_dir) if f.endswith(".w")])
    invalid_files = sorted([f for f in os.listdir(invalid_dir) if f.endswith(".w")])

    valid_passed = 0
    invalid_passed = 0
    failures = []

    print("==================================================")
    print("W Language Lexer Conformance Suite (SPEC v0.1)")
    print("==================================================")

    print(f"\n--- Lexer Valid ({len(valid_files)} tests) ---")
    for f in valid_files:
        path = os.path.join(valid_dir, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()

        try:
            lexer = Lexer(code, file=f)
            tokens = lexer.tokenize()

            # Verify token structure
            assert len(tokens) > 0, "Token stream should not be empty"
            assert tokens[-1].type == TokenType.EOF, "Last token must be EOF"
            for tok in tokens:
                assert tok.line >= 1, f"Token {tok} has invalid line < 1"
                assert tok.col >= 1, f"Token {tok} has invalid col < 1"

            print(f"  [PASS] {f} ({len(tokens)} tokens)")
            valid_passed += 1
        except Exception as e:
            print(f"  [FAIL] {f}: {e}")
            failures.append((f, str(e)))

    print(f"\n--- Lexer Invalid ({len(invalid_files)} tests) ---")
    for f in invalid_files:
        path = os.path.join(invalid_dir, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()

        try:
            lexer = Lexer(code, file=f)
            tokens = lexer.tokenize()
            print(f"  [FAIL] {f}: Expected LexerError, but tokens produced: {tokens}")
            failures.append((f, "Expected LexerError but succeeded"))
        except LexerError as err:
            print(f"  [PASS] {f}: Caught {err.code} at line {err.line}:{err.col} -> {err.message}")
            invalid_passed += 1
        except Exception as e:
            print(f"  [FAIL] {f}: Unexpected exception type {type(e).__name__}: {e}")
            failures.append((f, f"Wrong exception: {e}"))

    print("\n==================================================")
    print(f"Lexer valid:   {valid_passed}/{len(valid_files)}")
    print(f"Lexer invalid: {invalid_passed}/{len(invalid_files)}")
    print(f"FAILED:        {len(failures)}")
    print("==================================================")

    if failures:
        sys.exit(1)
    else:
        print("ALL LEXER CONFORMANCE TESTS PASSED.")
        sys.exit(0)

if __name__ == "__main__":
    test_lexer_suite()
