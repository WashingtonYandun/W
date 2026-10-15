# Milestone D01: Public Engine Feature Parity Matrix & Boundary Transparency

## Executive Summary
Milestone D01 inaugurates **Phase D (Self-Hosting & Consolidation)** by delivering an unambiguous, versioned, and verifiable **Engine Feature Parity Matrix** across all four compiler targets. In direct response to external architectural audit findings, this milestone eliminates deceptive claims of "universal self-hosting parity", formally documents the exact implementation boundary of the native W1 compiler (86/102 fixtures, 84.3%), and separates the guarantees of the **3-stage bootstrap fixed-point** from **full language parity**.

---

## 1. Architectural Reasoning & Foundation

### 1.1 The Audit Finding
The external compiler audit revealed a crucial architectural gap:
> *"El compilador W1 no soporta la superficie lingüística completa que el README presenta... el bootstrap solo cubre 38 fixtures porque excluye explícitamente genéricos y módulos. El 'self-hosting' es real para un subconjunto, pero no para el lenguaje completo."*

Previously, these limitations were recorded only in internal CI harness JSON files (`tests/engine_profiles.json`) and skipped without public documentation, giving an external observer the false impression that W1 had full parity with W0.

### 1.2 The Public Contract
Milestone D01 establishes the public contract:
1. **No Deceptive Release Claims:** The release profile (`--profile=release`) is codified to fail immediately if any engine has an unsupported feature. Releases cannot claim full parity until Milestone D02 completes W1 generic and module support.
2. **Transparent Integration Reporting:** The integration profile (`--profile=integration`) continues to evaluate the supported core language subset while explicitly displaying unsupported feature counts and their remediation targets.
3. **Distinct Guarantees:**
   - **Bootstrap Fixed-Point ($\text{SHA256}(c_0) == \text{SHA256}(c_1) == \text{SHA256}(c_2)$):** Proves that W1 emits deterministic C code when compiling itself.
   - **Feature Parity:** Proves that W1 accepts all language constructs defined in the specification.

---

## 2. Deliverables & Tooling Enhancements

### 2.1 Canonical Matrix Documentation
Created [`docs/ENGINE_PARITY_MATRIX.md`](file:///Users/washingtonyandun/Documents/ChatGPT/w_lang_compiler/docs/ENGINE_PARITY_MATRIX.md) detailing:
- Breakdown of all 4 engines (`W0 Interpreter`, `W0 AST C99`, `W0 Typed HIR`, `W1 Self-Hosted`).
- Feature categories (`core`, `generics`, `checked_modules`).
- Specific limitations and remediation tracking (`D02: generic specialization and diagnostics are not implemented in W1`).

### 2.2 Dynamic Matrix Generation (`tools/ci_conformance.py --matrix`)
Added the `--matrix` flag to `tools/ci_conformance.py`, enabling automated generation of the Markdown engine parity matrix directly from verified test corpus fixtures:
```bash
python3 tools/ci_conformance.py --matrix
```

Output:
| Feature Category | Fixtures | W0 Interpreter | W0 AST C99 | W0 Typed HIR (Default) | W1 Self-Hosted C99 | Status / Milestone |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **`core`** | 86 | ✅ 86/86 | ✅ 86/86 | ✅ 86/86 | ✅ 86/86 (Supported) | Stable (100% Parity) |
| **`generics`** | 15 | ✅ 15/15 | ✅ 15/15 | ✅ 15/15 | ⏳ 0/15 (Unsupported) | Pending D02 |
| **`checked_modules`** | 1 | ✅ 1/1 | ✅ 1/1 | ✅ 1/1 | ⏳ 0/1 (Unsupported) | Pending D02 |
| **Total Verified** | **102** | **102/102 (100%)** | **102/102 (100%)** | **102/102 (100%)** | **86/102 (84.3%)** | **Full W0 Parity &bull; W1 Core Subset** |

### 2.3 Standalone W1 Execution Invariant
Verified that `w build --backend=selfhost <file.w>` runs the native Stage-2 W1 binary directly without running W0 python checkers or filters first, ensuring W1's standalone error handling is directly exercised.

---

## 3. Verification & Test Coverage

### 3.1 Dedicated Test Suite: `test_d01_w1_parity_matrix.py`
Exercises:
1. `test_fixture_accounting_and_staleness`: Verifies that all 102 fixtures are mapped without orphan or stale entries.
2. `test_unsupported_reasons_and_milestones`: Ensures all engine limitations carry an explicit, non-empty tracking reason referencing a roadmap milestone.
3. `test_standalone_w1_execution_contracts`: Confirms W1 compiles core fixtures standalone and rejects unsupported generic fixtures directly with non-zero exit codes.
4. `test_ci_matrix_generation_tooling`: Validates CLI matrix generator output.
5. `test_documentation_consistency`: Verifies parity numbers in `docs/ENGINE_PARITY_MATRIX.md` match `tests/engine_profiles.json`.

### 3.2 Test Results
- **Unit Suite:** `test_d01_w1_parity_matrix.py` passed 100% (5/5).
- **Conformance Suite:** `./w test` passed **402/402 tests (100%)**.
- **Integration Profile:** `python3 tools/ci_conformance.py --profile=integration` passed **102/102 cases**.
- **Sanitizer Profile:** `python3 tools/ci_conformance.py --sanitize` passed **102/102 cases** (0 memory errors, 0 leaks under ASan/UBSan).
