# Contributing to W

Thank you for your interest in contributing to the **W Programming Language**! Whether you are reporting a bug, proposing language features, improving documentation, or submitting compiler patches, your contributions are welcome.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Architecture Overview](#architecture-overview)
- [Development Environment Setup](#development-environment-setup)
- [Testing & Quality Verification](#testing--quality-verification)
- [Self-Hosting Bootstrap Invariant](#self-hosting-bootstrap-invariant)
- [Coding & Commit Standards](#coding--commit-standards)
- [Pull Request Workflow](#pull-request-workflow)
- [Adding New Tests](#adding-new-tests)

---

## Code of Conduct

All contributors and participants are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please report any violations to [washington.yandun.morales@gmail.com](mailto:washington.yandun.morales@gmail.com).

---

## Architecture Overview

The W toolchain consists of two primary compiler engines and a unified C99 runtime:

```text
Source (.w)
   │
   ▼
[ Lexer ] ────────▶ [ TokenStream ]
   │
   ▼
[ Parser ] ───────▶ Canonical AST (node/NodeType.py)
   │
   ▼
[ TypeChecker ] ──▶ TypeInterner / Canonical TypeId (checker/TypeInterner.py)
   │
   ▼
[ HirBuilder ] ───▶ Typed HIR (hir/HirNodes.py)
   │
   ├──────────────────────────────┬──────────────────────────────┐
   ▼                              ▼                              ▼
[ W0 Interpreter ]       [ HirCCodeGen ]                [ W1 Compiler ]
runtime/Interpreter.py   hir/HirCCodeGen.py             selfhost/src/
   │                              │                              │
   ▼                              ▼                              ▼
Value Evaluation           ANSI C99 Code                  Pure W Self-Host
```

- **W0 Compiler / Driver (`main.py`, `w`):** Reference implementation in Python 3. Contains the two-pass type checker, monomorphization engine, Typed HIR middle-end, and C99 native code generator.
- **W1 Self-Hosting Compiler (`selfhost/src/`):** modular sources written in W, bundled into `selfhost/w1.w`. W1 is experimental; W0/HIR is the reference product.
- **C99 Runtime (`runtime/w_runtime.h`):** Single-header runtime with single-threaded ARC, copy-on-write value graphs, length-aware UTF-8 strings, and explicit weak references.

---

## Development Environment Setup

### Prerequisites

- **Python:** 3.10 or higher.
- **C Compiler:** Any standard C99 compiler (`clang` recommended, or `gcc`).
- **Make:** Optional, for shortcut commands.
- **Git:** Standard git version control.

### Cloning & Verification

```bash
git clone https://github.com/WashingtonYandun/W.git
cd W

# Verify toolchain CLI
./w --version

# Run the full conformance test suite
./w test
```

---

## Testing & Quality Verification

W adheres to strict conformance and correctness invariants. **All conformance tests must pass before submitting code.**

### 1. Conformance Test Suite
Runs all 13 stages of verification including lexer, parser, static type checker, formatter, Typed HIR lowering, C99 backend, runtime execution, and modular self-hosting:
```bash
./w test
```

### 2. Memory Safety with Sanitizers (Clang ASan / UBSan)
Compile and test with AddressSanitizer and UndefinedBehaviorSanitizer enabled:
```bash
./w test --sanitize
# or via environment variable:
W_SANITIZE=1 ./w test
```

### 3. Four-Engine Differential Oracle
Validates interpreter, AST C99, HIR C99 and standalone W1 outputs and diagnostics.
Feature support is declared in `tests/engine_profiles.json`; unsupported rows are reported separately:
```bash
./w test --differential 20
```

The CI corpus also verifies every runtime/example output and standalone negative fixture:
```bash
python3 tools/ci_conformance.py
CC=clang python3 tools/ci_conformance.py --sanitize
python3 tools/ci_conformance.py --profile=release
```

The integration profile reports explicitly unsupported engine/fixture combinations; the release profile requires every fixture to pass on every engine. CI reports coverage by engine and feature and retains source, generated C, commands, diagnostics, signals, timeouts, and toolchain versions for failures. See the [engine parity matrix](docs/ENGINE_PARITY_MATRIX.md) for the current tested boundary.

### 4. Modular Split Verification
Ensures the modular compiler files in `selfhost/src/` combine loss-lessly to exactly match `selfhost/w1.w`:
```bash
python3 -m tests.unit.test_w1_split_conformance
```

### 5. Performance Benchmark
Runs the standard micro-benchmark harness:
```bash
./w bench
```

---

## Self-Hosting Bootstrap Invariant

W guarantees a 3-stage cryptographic bootstrap fixed-point:
$$\text{SHA256}(\text{Stage}_1) == \text{SHA256}(\text{Stage}_2) == \text{SHA256}(\text{Stage}_3)$$

When modifying compiler frontend, parser, or code generation logic that affects W1:
1. Re-bundle the self-hosted compiler:
   ```bash
   python3 tools/bundle_w1.py
   ```
2. Verify the bootstrap fixed-point:
   ```bash
   python3 -m tests.unit.test_bootstrap_conformance
   ```

---

## Coding & Commit Standards

- **Language Policy:**
  - All source code, identifiers, types, comments, documentation, and commit messages must be strictly in **English**.
- **Code Formatting:**
  - W source code: Run `./w fmt <file>.w` or format whole directories with `./w fmt examples/`.
  - Python codebase: Follow PEP 8 guidelines.
- **Commit Messages:**
  - Follow [Conventional Commits](https://www.conventionalcommits.org/):
    - `feat:` New features or language capabilities
    - `fix:` Bug fixes in compiler, runtime, or tools
    - `docs:` Public documentation or specification updates
    - `test:` Adding or improving test cases
    - `chore:` Maintenance, build setup, or repo chores
    - `refactor:` Code restructuring without behavioral changes
    - `perf:` Performance optimizations

---

## Pull Request Workflow

1. **Branching Model:**
   - `main`: Stable release branch. Direct commits are forbidden.
   - `develop`: Integration branch. **All Pull Requests must target `develop`**.
   - Create your working branch off `develop`:
     ```bash
     git checkout develop
     git pull origin develop
     git checkout -b feat/your-feature-name
     ```
2. **Commit Your Changes:**
   - Keep commits small, atomic, and well-described.
3. **Verify Locally:**
   - Ensure `./w test` passes 100%.
   - Ensure `./w test --sanitize` passes without memory errors or leaks.
4. **Submit Pull Request:**
   - Open a PR from your branch to `develop`.
   - Fill out the [Pull Request Template](.github/pull_request_template.md).
   - Ensure all GitHub Actions CI checks pass.

---

## Adding New Tests

When adding a feature or fixing a bug, include corresponding regression tests in `tests/`:

- `tests/lexer/valid/` & `tests/lexer/invalid/`: Lexer token tests.
- `tests/parser/valid/` & `tests/parser/invalid/`: AST parsing and syntax error tests.
- `tests/types/valid/` & `tests/types/invalid/`: Static type checking and error code tests.
- `tests/runtime/`: End-to-end execution tests (`.w` file and expected output in `.expected`).
- `tests/differential/`: Cross-engine differential test programs.

Thank you for helping make W a robust, memory-safe, and performant systems language!
