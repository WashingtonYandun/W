"""Versioned machine-readable results for Wysna CLI tools."""

import hashlib
import json
import os
import uuid

from common.Version import WYSNA_VERSION


SCHEMA_VERSION = "wysna.tool-result/1"


def _line_starts(source):
    starts = [0]
    index = 0
    while index < len(source):
        if source[index] == "\r":
            index += 2 if source[index:index + 2] == "\r\n" else 1
            starts.append(index)
        elif source[index] == "\n":
            index += 1
            starts.append(index)
        else:
            index += 1
    return starts


def _byte_offset(source, line, column):
    """Map a one-based Unicode-scalar position to its UTF-8 byte offset."""
    if not isinstance(line, int) or not isinstance(column, int) or line < 1 or column < 1:
        return None

    starts = _line_starts(source)
    if line > len(starts):
        return None

    start = starts[line - 1]
    end = start
    while end < len(source) and source[end] not in "\r\n":
        end += 1

    character_offset = min(start + column - 1, end)
    return len(source[:character_offset].encode("utf-8"))


def _source_for_file(source_by_file, filename):
    if not filename:
        return None
    source = source_by_file.get(filename)
    if source is not None:
        return source
    try:
        for candidate in (os.path.abspath(filename), os.path.realpath(filename)):
            source = source_by_file.get(candidate)
            if source is not None:
                return source
    except (OSError, TypeError, ValueError):
        pass
    return None


def _primary_span(filename, line, column, source):
    if source is None:
        return None
    start_byte = _byte_offset(source, line, column)
    if start_byte is None:
        return None
    return {
        "source_id": filename,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "start_byte": start_byte,
        "end_byte": start_byte,
    }


def diagnostic_from_error(error, source_by_file=None):
    """Adapt a legacy compiler diagnostic without inventing an unknown range."""
    source_by_file = source_by_file or {}
    filename = getattr(error, "file", None)
    source = _source_for_file(source_by_file, filename)

    return {
        "code": getattr(error, "code", "W9999"),
        "severity": getattr(error, "severity", "error"),
        "stage": getattr(error, "stage", "internal"),
        "message": getattr(error, "message", str(error)),
        "primary_span": _primary_span(
            filename,
            getattr(error, "line", None),
            getattr(error, "col", None),
            source,
        ),
        "related": [],
        "data": {},
        "fixes": [],
    }


def diagnostic_record(code, stage, message, *, severity="error", filename=None,
                      line=None, column=None, source=None):
    """Create a protocol diagnostic for CLI and host errors."""
    return {
        "code": code,
        "severity": severity,
        "stage": stage,
        "message": message,
        "primary_span": _primary_span(filename, line, column, source),
        "related": [],
        "data": {},
        "fixes": [],
    }


def artifact_inline(kind, media_type, content):
    """Describe a UTF-8 text artifact embedded in the result envelope."""
    encoded = content.encode("utf-8")
    return {
        "kind": kind,
        "media_type": media_type,
        "content": content,
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def artifact_file(kind, media_type, path):
    """Describe a completed file artifact using the bytes actually written."""
    path = os.fspath(path)
    digest = hashlib.sha256()
    with open(path, "rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "kind": kind,
        "media_type": media_type,
        "path": path,
        "sha256": digest.hexdigest(),
    }


def tool_result(command, status, exit_code, *, diagnostics=None, artifacts=None,
                invocation_id=None, target=None):
    """Build the stable v1 envelope; process_exit_code mirrors tool_exit_code."""
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": status,
        "invocation_id": invocation_id or str(uuid.uuid4()),
        "tool_exit_code": exit_code,
        "process_exit_code": exit_code,
        "execution": None,
        "toolchain": {"compiler": WYSNA_VERSION},
        "target": target or {"profile": "native-cli", "triple": None},
        "diagnostics": diagnostics or [],
        "artifacts": artifacts or [],
        "telemetry": None,
    }


def write_tool_result(result, stream):
    """Write exactly one JSON document to the selected stream."""
    stream.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
