import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_check_json_v1_success_has_one_versioned_envelope(tmp_path):
    source = tmp_path / "valid.wysna"
    source.write_text("fn main() -> unit { print(42) }\n", encoding="utf-8")

    result = run_cli("check", "--output-format=json-v1", source)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    assert payload["schema_version"] == "wysna.tool-result/1"
    assert payload["command"] == "check"
    assert payload["status"] == "ok"
    assert payload["tool_exit_code"] == payload["process_exit_code"] == 0
    assert payload["diagnostics"] == []


def test_check_json_v1_diagnostic_uses_exact_source_hash_and_byte_position(tmp_path):
    source_bytes = '## café\r\nlet value: int = "wrong"\r\n'.encode("utf-8")
    source = tmp_path / "invalid.wysna"
    source.write_bytes(source_bytes)

    result = run_cli("check", "--output-format=json-v1", source)

    payload = json.loads(result.stdout)
    diagnostic = payload["diagnostics"][0]
    span = diagnostic["primary_span"]
    assert result.returncode == 1
    assert result.stderr == ""
    assert payload["status"] == "diagnostic_error"
    assert diagnostic["code"] == "W2001"
    assert span["source_sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert span["start_byte"] == span["end_byte"] == source_bytes.index(b"let")


def test_check_json_v1_serializes_usage_and_file_errors(tmp_path):
    usage_result = run_cli("check", "--output-format=json-v1", "--unknown")
    missing_file = tmp_path / "missing.wysna"
    file_result = run_cli("check", "--output-format=json-v1", missing_file)
    invalid_utf8 = tmp_path / "invalid-utf8.wysna"
    invalid_utf8.write_bytes(b"\xff")
    decode_result = run_cli("check", "--output-format=json-v1", invalid_utf8)

    usage_payload = json.loads(usage_result.stdout)
    file_payload = json.loads(file_result.stdout)
    decode_payload = json.loads(decode_result.stdout)
    assert usage_result.returncode == 2
    assert usage_result.stderr == ""
    assert usage_payload["status"] == "usage_error"
    assert usage_payload["tool_exit_code"] == 2
    assert usage_payload["diagnostics"][0]["code"] == "W5002"
    assert file_result.returncode == 3
    assert file_result.stderr == ""
    assert file_payload["status"] == "toolchain_error"
    assert file_payload["tool_exit_code"] == 3
    assert file_payload["diagnostics"][0]["code"] == "W5003"
    assert decode_result.returncode == 3
    assert decode_result.stderr == ""
    assert decode_payload["status"] == "toolchain_error"
    assert decode_payload["diagnostics"][0]["code"] == "W5003"


def test_check_json_v1_rejects_legacy_json_combination(tmp_path):
    source = tmp_path / "valid.wysna"
    source.write_text("fn main() -> unit { }\n", encoding="utf-8")

    result = run_cli("check", "--json", "--output-format=json-v1", source)

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert result.stderr == ""
    assert payload["status"] == "usage_error"


def test_run_passes_json_v1_looking_argument_after_separator(tmp_path):
    source = tmp_path / "argv.wysna"
    source.write_text("fn main() -> unit { print(args()[1]) }\n", encoding="utf-8")

    result = run_cli("run", source, "--", "--output-format=json-v1")

    assert result.returncode == 0
    assert result.stdout == "--output-format=json-v1\n"
    assert result.stderr == ""
