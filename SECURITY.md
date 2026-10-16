# Security Policy

The W programming language team takes security, memory safety, and compiler correctness seriously. This document outlines how to report security issues, our response process, and supported versions.

## Supported Versions

Only the latest minor release line receives security updates and backports.

| Version | Supported          | Security Status |
| ------- | ------------------ | --------------- |
| 0.4.0a1 | :white_check_mark: | Experimental alpha; no production profile approved |
| 0.3.0.dev1 | :x: | Superseded by the W 0.4.0 alpha line |
| 0.2.x | :x: | Superseded by W 0.3.0 |
| 0.1.x   | :x:                | Unsupported historical release |
| < 0.1.0 | :x:                | Unsupported experimental releases |

## Reporting a Vulnerability

If you discover a security vulnerability in the W compiler, runtime, or tooling, please **do not report it via a public GitHub issue**. Instead, follow one of these responsible disclosure methods:

1. **GitHub Security Advisory (Preferred):** Open a private report at [github.com/WashingtonYandun/W/security/advisories/new](https://github.com/WashingtonYandun/W/security/advisories/new).
2. **Direct Email:** Send an encrypted or plain email to [washington.yandun.morales@gmail.com](mailto:washington.yandun.morales@gmail.com) with the subject prefix `[SECURITY]`.

### What to Include in Your Report

To help us triage and resolve the issue quickly, please provide:
- A description of the vulnerability, including severity assessment (CVSS if available).
- A minimal reproducing W code snippet (`.w`) or script.
- The affected component (e.g., C99 runtime `w_runtime.h`, Typed HIR lowerer, C codegen, parser, or self-hosting compiler).
- Exact environment details: OS, CPU architecture, compiler version (`./w version`), and C toolchain (`clang --version` or `gcc --version`).
- Sanitizer trace if applicable (e.g., ASan/UBSan report via `./w run <file>.w --sanitize`).

## Security Response Process

When we receive a vulnerability report:

1. **Acknowledgement:** We will acknowledge receipt of your report within **48 hours**.
2. **Assessment & Triage:** We will investigate and assess the vulnerability within **5 business days**, validating reproduction and impact.
3. **Remediation & Patching:** A fix will be developed in a private security branch and verified with AddressSanitizer, UndefinedBehaviorSanitizer, and differential oracle testing.
4. **Release & Advisory:** A patch release and coordinated public GitHub Security Advisory will be published. Reporters will be credited unless they request anonymity.

## In-Scope Security Areas

- **C99 Runtime Memory Safety:** Use-after-free, double-free, dangling references, buffer overruns, or reference-count underflow/overflow in `runtime/w_runtime.h`.
- **Type Confusion:** Bypasses in the static type checker (`checker/TypeChecker.py`) or Typed HIR that allow unchecked memory access at runtime.
- **Compiler Code Injection:** Unsanitized string literals or identifiers in AST lowering that escape into arbitrary C execution during code generation.
- **Copy-on-Write Invariant Violations:** Observable in-place mutation of shared values across threads or scopes violating W's pure value semantics.

## Out-of-Scope

- Denial-of-Service via excessively large input files or deeply nested expressions causing recursion limits during parsing (unless bypassing AST depth guards).
- Vulnerabilities requiring root/administrator access or tampering with local binaries outside the W toolchain.
