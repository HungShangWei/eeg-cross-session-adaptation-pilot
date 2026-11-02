#!/usr/bin/env python3
"""Write or check the file identity manifest of the pilot code folder (standard library only).

A manifest lists every regular file under the candidate folder with its size in bytes and its
SHA-256, using paths relative to the folder's parent (for example "candidate/launch.py"). This is
the format read by identity_check() in candidate/launch.py.

    python tools/code_identity.py verify --candidate code/pilot/candidate \\
        --manifest code/pilot/RELEASE_CODE_IDENTITY.json
    python tools/code_identity.py generate --candidate code/pilot/candidate \\
        --output code/pilot/LOCAL_CODE_IDENTITY.json

A manifest records file identity only. It is not the identity of the code as originally executed,
not an execution approval and not a signature: a SHA-256 mismatch shows that a file differs from
the manifest, but a manifest edited together with the files cannot show where they came from.

Exit status: 0 success; 1 the candidate folder does not match the manifest; 2 invalid arguments or
input, an unsafe file tree, or a refused output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata
from pathlib import Path

SCHEMA = "release-code-identity/1"
PURPOSE = ("SHA-256 identity of the files in the candidate folder of this copy, in the format read by "
           "identity_check() in candidate/launch.py; not the identity of the originally executed code, "
           "not an execution approval and not a signature")
# identity_check() in candidate/launch.py skips every path that contains a __pycache__ component.
EXCLUDED_PART = "__pycache__"
TOP_LEVEL_KEYS = {"schema", "purpose", "file_count", "files"}
ROW_KEYS = {"path", "bytes", "sha256"}
HEX64 = re.compile(r"[0-9a-f]{64}")
CHUNK = 1 << 20

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_INVALID = 2


class IdentityError(Exception):
    """Invalid input, unsafe file tree or refused output (exit status 2)."""


def _file_identity(path: Path) -> tuple[int, str]:
    """Size and SHA-256 of a regular file, read in chunks."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _check_path_text(text: str, prefix: str) -> None:
    """Accept only a plain relative POSIX path that starts with the candidate folder name."""
    if not text or text.startswith("/") or "\\" in text or any(ord(ch) < 32 for ch in text):
        raise IdentityError(f"unsafe path {text!r}")
    parts = text.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise IdentityError(f"unsafe path {text!r}")
    if len(parts) < 2 or parts[0] != prefix:
        raise IdentityError(f"path {text!r} is not inside {prefix}/")


def _collision_key(text: str) -> str:
    """Paths that differ only in case or Unicode form name the same file on some file systems."""
    return unicodedata.normalize("NFC", text).casefold()


def _check_unique(paths: list[str]) -> None:
    seen: dict[str, str] = {}
    for text in paths:
        key = _collision_key(text)
        if key in seen:
            raise IdentityError(f"duplicate or colliding paths {seen[key]!r} and {text!r}")
        seen[key] = text


def scan_candidate(candidate: Path) -> list[dict]:
    """Rows (path, bytes, sha256) for every regular file under the candidate folder, sorted by path.

    Symbolic links anywhere under the folder, and non-regular files, are refused rather than followed.
    """
    try:
        info = os.lstat(candidate)
    except OSError as exc:
        raise IdentityError(f"cannot read candidate folder {candidate}: {exc.strerror}") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise IdentityError(f"candidate {candidate} is not a plain directory")
    prefix = candidate.name
    rows = []

    def walk_error(exc: OSError) -> None:
        raise IdentityError(f"cannot list {exc.filename}: {exc.strerror}")

    for dirpath, dirnames, filenames in os.walk(candidate, onerror=walk_error, followlinks=False):
        base = Path(dirpath)
        for name in list(dirnames):
            if stat.S_ISLNK(os.lstat(base / name).st_mode):
                raise IdentityError(f"symbolic link to a directory: {base / name}")
        dirnames[:] = sorted(name for name in dirnames if name != EXCLUDED_PART)
        for name in sorted(filenames):
            full = base / name
            mode = os.lstat(full).st_mode
            if stat.S_ISLNK(mode):
                raise IdentityError(f"symbolic link: {full}")
            if not stat.S_ISREG(mode):
                raise IdentityError(f"not a regular file: {full}")
            if name == EXCLUDED_PART:
                continue
            text = "/".join((prefix,) + full.relative_to(candidate).parts)
            _check_path_text(text, prefix)
            size, sha256 = _file_identity(full)
            rows.append({"path": text, "bytes": size, "sha256": sha256})
    if not rows:
        raise IdentityError(f"no files under {candidate}")
    rows.sort(key=lambda row: row["path"])
    _check_unique([row["path"] for row in rows])
    return rows


def manifest_bytes(rows: list[dict]) -> bytes:
    """Deterministic serialisation: no dates, no machine paths, fixed key order, sorted rows."""
    document = {"schema": SCHEMA, "purpose": PURPOSE, "file_count": len(rows), "files": rows}
    return (json.dumps(document, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise IdentityError("duplicate key in manifest JSON")
    return dict(pairs)


def load_manifest(path: Path, prefix: str) -> tuple[bytes, list[dict]]:
    """Read and validate a manifest; return its raw bytes and rows."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise IdentityError(f"cannot read manifest {path}: {exc.strerror}") from None
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IdentityError(f"manifest is not valid JSON: {exc}") from None
    if not isinstance(document, dict) or "files" not in document:
        raise IdentityError("manifest must be a JSON object with a 'files' list")
    unknown = set(document) - TOP_LEVEL_KEYS
    if unknown:
        raise IdentityError(f"unknown manifest keys: {sorted(unknown)}")
    if "schema" in document and document["schema"] != SCHEMA:
        raise IdentityError(f"unknown schema {document['schema']!r}")
    if "purpose" in document and not isinstance(document["purpose"], str):
        raise IdentityError("'purpose' must be a string")
    rows = document["files"]
    if not isinstance(rows, list) or not rows:
        raise IdentityError("'files' must be a non-empty list")
    for row in rows:
        if not isinstance(row, dict) or set(row) != ROW_KEYS:
            raise IdentityError("each entry of 'files' needs exactly the keys path, bytes and sha256")
        if not isinstance(row["path"], str):
            raise IdentityError("'path' must be a string")
        _check_path_text(row["path"], prefix)
        size = row["bytes"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise IdentityError(f"'bytes' of {row['path']!r} must be a non-negative integer")
        if not isinstance(row["sha256"], str) or not HEX64.fullmatch(row["sha256"]):
            raise IdentityError(f"'sha256' of {row['path']!r} must be 64 lowercase hexadecimal characters")
    if "file_count" in document:
        count = document["file_count"]
        if isinstance(count, bool) or count != len(rows):
            raise IdentityError("'file_count' does not equal the number of entries")
    _check_unique([row["path"] for row in rows])
    return raw, rows


def _is_inside(path: Path, folder: Path) -> bool:
    path, folder = path.resolve(), folder.resolve()
    return path == folder or folder in path.parents


def generate(candidate: Path, output: Path, reference: Path | None = None) -> int:
    """Write a new manifest for the current candidate folder; never overwrite an existing file."""
    if os.path.lexists(output):
        raise IdentityError(f"output {output} already exists; choose a new file name")
    if not output.parent.is_dir():
        raise IdentityError(f"output folder {output.parent} does not exist")
    if _is_inside(output.parent / output.name, candidate):
        raise IdentityError("output must be outside the candidate folder")
    rows = scan_candidate(candidate)
    if reference is not None:
        expected = {row["path"].split("/", 1)[1]: (row["bytes"], row["sha256"]) for row in scan_candidate(reference)}
        found = {row["path"].split("/", 1)[1]: (row["bytes"], row["sha256"]) for row in rows}
        if expected != found:
            differing = sorted(set(expected) ^ set(found)) + sorted(p for p in set(expected) & set(found) if expected[p] != found[p])
            raise IdentityError(f"candidate differs from the reference folder in {len(differing)} file(s), e.g. {differing[:5]}")
    data = manifest_bytes(rows)
    with open(output, "xb") as handle:
        handle.write(data)
    print(f"WROTE {output}: {len(rows)} files; manifest SHA-256 {hashlib.sha256(data).hexdigest()}; "
          "identity only; not execution approval")
    return EXIT_OK


def verify(candidate: Path, manifest: Path) -> int:
    """Compare the candidate folder with a manifest. Read-only: nothing is rewritten or changed."""
    if _is_inside(manifest, candidate):
        raise IdentityError("the manifest must be outside the candidate folder")
    raw, rows = load_manifest(manifest, candidate.name)
    listed = {row["path"]: row for row in rows}
    present = {row["path"]: row for row in scan_candidate(candidate)}
    problems = [f"{path}: listed but not present" for path in sorted(set(listed) - set(present))]
    problems += [f"{path}: present but not listed" for path in sorted(set(present) - set(listed))]
    for path in sorted(set(listed) & set(present)):
        if listed[path]["bytes"] != present[path]["bytes"]:
            problems.append(f"{path}: size differs (listed {listed[path]['bytes']}, found {present[path]['bytes']})")
        elif listed[path]["sha256"] != present[path]["sha256"]:
            problems.append(f"{path}: SHA-256 differs")
    if problems:
        for line in problems:
            print(f"MISMATCH {line}")
        print(f"NOT VERIFIED: {len(problems)} difference(s) between {candidate} and {manifest}")
        return EXIT_MISMATCH
    print(f"VERIFIED {len(rows)} files; manifest SHA-256 {hashlib.sha256(raw).hexdigest()}; "
          "identity only; not execution approval")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write or check the file identity manifest of the candidate code folder.",
        epilog="Exit status: 0 success; 1 the folder does not match the manifest; 2 invalid arguments or input, "
               "an unsafe file tree or a refused output. A manifest records file identity only; it is not an "
               "execution approval.")
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate", help="write a new manifest for the current files (never overwrites)")
    gen.add_argument("--candidate", required=True, type=Path, help="the candidate folder, e.g. code/pilot/candidate")
    gen.add_argument("--output", required=True, type=Path, help="new manifest file, outside the candidate folder")
    gen.add_argument("--reference", type=Path,
                     help="optional folder that the candidate must match file by file before a manifest is written")
    ver = commands.add_parser("verify", help="check the current files against a manifest (read-only)")
    ver.add_argument("--candidate", required=True, type=Path, help="the candidate folder, e.g. code/pilot/candidate")
    ver.add_argument("--manifest", required=True, type=Path, help="manifest file, outside the candidate folder")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            return generate(args.candidate, args.output, args.reference)
        return verify(args.candidate, args.manifest)
    except IdentityError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return EXIT_INVALID


if __name__ == "__main__":
    sys.exit(main())
