#!/usr/bin/env python3
"""Engineering tests for tools/code_identity.py (standard library only).

Run from the repository root:

    python tools/tests/test_code_identity.py

The tests copy files into temporary folders and only read the files of this repository. The
compatibility tests load the unmodified candidate/launch.py from such a copy in a separate Python
process, under a module name other than __main__, and call only its identity_check(); no other
candidate module is imported and nothing else from the candidate is run. Passing tests show how
file identity is handled. They do not test the environment, data, resources, approvals or a run.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "code_identity.py"
PILOT = REPO / "code" / "pilot"
RELEASE_MANIFEST = PILOT / "RELEASE_CODE_IDENTITY.json"
OBSERVATIONS: list[dict] = []  # one record per case, for callers that keep a report of the run

_spec = importlib.util.spec_from_file_location("code_identity_under_test", TOOL)
ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci)

# Runs in a separate process. It reviews the top level of launch.py (standard-library imports, two
# path constants, function definitions and the __main__ guard only), loads the file under another
# module name and calls identity_check() once. An audit hook reports any write, any read outside the
# copied code folder and the standard library, and any process, network or file-system change.
CHECKER = r'''
import ast, hashlib, importlib.util, json, os, sys, sysconfig
launch_path, manifest_path = os.path.realpath(sys.argv[1]), os.path.realpath(sys.argv[2])
code_folder = os.path.dirname(os.path.dirname(launch_path))
ALLOWED_IMPORTS = {"pathlib", "json", "sys", "os", "hashlib", "argparse", "traceback"}
problems = []
for index, node in enumerate(ast.parse(open(launch_path, "rb").read()).body):
    if index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        continue
    if isinstance(node, ast.Import) and {a.name.split(".")[0] for a in node.names} <= ALLOWED_IMPORTS:
        continue
    if isinstance(node, ast.FunctionDef):
        continue
    if isinstance(node, ast.Assign) and all(
            ast.unparse(c.func) in ("pathlib.Path", "pathlib.Path(__file__).resolve")
            for c in ast.walk(node.value) if isinstance(c, ast.Call)):
        continue
    if isinstance(node, ast.If) and ast.unparse(node.test) == "__name__ == '__main__'":
        continue
    problems.append("line %d: %s" % (node.lineno, type(node).__name__))
if problems:
    print(json.dumps({"loaded": False, "top_level_problems": problems}))
    sys.exit(3)
paths = sysconfig.get_paths()
library = [os.path.realpath(p) for p in {paths["stdlib"], paths["platstdlib"], sys.base_prefix, sys.prefix}]
WRITE = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
unexpected = []
def inside(path, folder):
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)
def hook(event, args):
    if event == "open":
        if not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = os.path.realpath(os.fsdecode(args[0]))
        mode = args[1] if len(args) > 1 and isinstance(args[1], str) else ""
        flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
        writing = any(ch in mode for ch in "wax+") or bool(flags & WRITE)
        known = path in (launch_path, manifest_path) or inside(path, code_folder) or any(inside(path, f) for f in library)
        if writing or not known:
            unexpected.append(["open", path, mode, flags])
    elif event.startswith(("subprocess.", "os.system", "os.exec", "os.spawn", "os.posix_spawn", "os.fork", "socket.",
                           "ctypes.", "os.remove", "os.unlink", "os.rename", "os.replace", "os.mkdir", "os.rmdir",
                           "os.symlink", "os.link", "os.chmod", "os.truncate", "shutil.")):
        unexpected.append([event])
sys.addaudithook(hook)
before = set(sys.modules)
spec = importlib.util.spec_from_file_location("release_identity_launch_under_test", launch_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    result = {"accepted": True, "returned_sha256": module.identity_check(manifest_path)}
except BaseException as exc:
    result = {"accepted": False, "error_type": type(exc).__name__, "error": str(exc)[:200]}
foreign = []
for name in sorted(set(sys.modules) - before):
    if name == "release_identity_launch_under_test":
        continue
    origin = getattr(getattr(sys.modules[name], "__spec__", None), "origin", None)
    if origin not in (None, "built-in", "frozen") and not any(inside(os.path.realpath(origin), f) for f in library):
        foreign.append([name, origin])
result.update(loaded=True, launch_sha256=hashlib.sha256(open(launch_path, "rb").read()).hexdigest(),
              manifest_sha256=hashlib.sha256(open(manifest_path, "rb").read()).hexdigest(),
              foreign_modules=foreign, unexpected_events=unexpected)
print(json.dumps(result))
'''


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", "-B", str(TOOL), *args], capture_output=True, text=True, timeout=600)


def run_launcher_check(code_folder: Path, manifest: Path) -> dict:
    """identity_check() of the unmodified launch.py in code_folder/candidate, in a separate process."""
    with tempfile.TemporaryDirectory() as work:
        proc = subprocess.run([sys.executable, "-I", "-B", "-c", CHECKER, str(code_folder / "candidate" / "launch.py"),
                               str(manifest)], capture_output=True, text=True, timeout=600, cwd=work)
    lines = proc.stdout.strip().splitlines()
    if proc.returncode != 0 or not lines:
        raise AssertionError(f"checker process ended with {proc.returncode}: {proc.stdout[-300:]} {proc.stderr[-300:]}")
    result = json.loads(lines[-1])
    if result.get("unexpected_events") or result.get("foreign_modules"):
        raise AssertionError(f"unexpected action while loading launch.py: {result}")
    return result


def summary(proc: subprocess.CompletedProcess) -> dict:
    first = (proc.stdout.strip().splitlines() or proc.stderr.strip().splitlines() or [""])[0]
    return {"exit": proc.returncode, "first_line": first[:200]}


def record(case: str, tool: subprocess.CompletedProcess | None, launcher: dict | None, note: str = "") -> None:
    OBSERVATIONS.append({"case": case, "tool": summary(tool) if tool else None,
                         "launcher_identity_check": launcher, "note": note})


def copy_code_folder(root: Path) -> Path:
    """A real copy of code/pilot/candidate and the release manifest under root/pilot."""
    folder = root / "pilot"
    shutil.copytree(PILOT / "candidate", folder / "candidate", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(RELEASE_MANIFEST, folder / RELEASE_MANIFEST.name)
    return folder


def make_fixture(root: Path) -> Path:
    """A small neutral code folder: the unmodified launch.py, three short text files and one file outside it."""
    folder = root / "fixture"
    candidate = folder / "candidate"
    (candidate / "sub").mkdir(parents=True)
    shutil.copyfile(PILOT / "candidate" / "launch.py", candidate / "launch.py")
    (candidate / "one.txt").write_bytes(b"1")
    (candidate / "two.txt").write_bytes(b"two\n")
    (candidate / "sub" / "three.txt").write_bytes(b"three\n")
    (folder / "notes.txt").write_bytes(b"outside the candidate folder\n")
    return folder


def tree_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for base in paths:
        files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        for path in files:
            digest.update(str(path.relative_to(REPO)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


GUARDED = [PILOT / "candidate", RELEASE_MANIFEST, TOOL]
_START_DIGEST = ""


def setUpModule() -> None:
    global _START_DIGEST
    _START_DIGEST = tree_digest(GUARDED)


def tearDownModule() -> None:
    if tree_digest(GUARDED) != _START_DIGEST:
        raise AssertionError("files of this repository changed during the tests")


class ReleaseManifestTests(unittest.TestCase):
    def test_rows_match_files_by_independent_computation(self) -> None:
        document = json.loads(RELEASE_MANIFEST.read_bytes())
        found = {}
        for dirpath, dirnames, filenames in os.walk(PILOT / "candidate"):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                path = Path(dirpath) / name
                found["/".join(("candidate",) + path.relative_to(PILOT / "candidate").parts)] = path
        rows = document["files"]
        self.assertEqual([row["path"] for row in rows], sorted(found))
        for row in rows:
            data = found[row["path"]].read_bytes()
            self.assertEqual(row["bytes"], len(data), row["path"])
            self.assertEqual(row["sha256"], hashlib.sha256(data).hexdigest(), row["path"])
        self.assertEqual(document["file_count"], len(rows))
        self.assertEqual(document["schema"], ci.SCHEMA)
        self.assertIn("not an execution approval", document["purpose"])
        record("release manifest rows recomputed independently", None, None, f"{len(rows)} rows")

    def test_verify_command_accepts_release_manifest(self) -> None:
        proc = run_tool("verify", "--candidate", str(PILOT / "candidate"), "--manifest", str(RELEASE_MANIFEST))
        record("verify release manifest against this copy", proc, None)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(sha256_of(RELEASE_MANIFEST), proc.stdout)
        self.assertIn("identity only; not execution approval", proc.stdout)

    def test_launcher_identity_check_accepts_release_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = copy_code_folder(Path(tmp))
            manifest = folder / RELEASE_MANIFEST.name
            result = run_launcher_check(folder, manifest)
            record("launcher identity_check on a copy with the release manifest", None, result)
            self.assertTrue(result["accepted"], result)
            self.assertEqual(result["returned_sha256"], sha256_of(manifest))
            listed = {row["path"]: row["sha256"] for row in json.loads(manifest.read_bytes())["files"]}
            self.assertEqual(result["launch_sha256"], listed["candidate/launch.py"])

    def test_regenerated_manifest_is_byte_identical_across_roots(self) -> None:
        outputs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                folder = copy_code_folder(Path(tmp))
                for name in ("first.json", "second.json"):
                    proc = run_tool("generate", "--candidate", str(folder / "candidate"), "--output", str(folder / name))
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    outputs.append((folder / name).read_bytes())
        record("generate twice in each of two roots", None, None, f"{len(outputs)} manifests compared")
        self.assertTrue(all(data == RELEASE_MANIFEST.read_bytes() for data in outputs))


class GenerateTests(unittest.TestCase):
    def test_generate_verify_and_launcher_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = copy_code_folder(Path(tmp))
            out = folder / "LOCAL_CODE_IDENTITY.json"
            gen = run_tool("generate", "--candidate", str(folder / "candidate"), "--output", str(out))
            ver = run_tool("verify", "--candidate", str(folder / "candidate"), "--manifest", str(out))
            result = run_launcher_check(folder, out)
            record("generate, verify and launcher identity_check on a copy", ver, result)
            self.assertEqual(gen.returncode, 0, gen.stderr)
            self.assertEqual(ver.returncode, 0, ver.stdout + ver.stderr)
            self.assertTrue(result["accepted"], result)
            self.assertEqual(result["returned_sha256"], sha256_of(out))

    def test_reference_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = copy_code_folder(Path(tmp))
            same = run_tool("generate", "--candidate", str(folder / "candidate"), "--reference", str(PILOT / "candidate"),
                            "--output", str(folder / "same.json"))
            self.assertEqual(same.returncode, 0, same.stderr)
            self.assertEqual((folder / "same.json").read_bytes(), RELEASE_MANIFEST.read_bytes())
            target = folder / "candidate" / "launch.py"
            target.write_bytes(target.read_bytes() + b"\n")
            other = run_tool("generate", "--candidate", str(folder / "candidate"), "--reference", str(PILOT / "candidate"),
                             "--output", str(folder / "other.json"))
            record("generate with a reference that differs", other, None)
            self.assertEqual(other.returncode, 2)
            self.assertFalse((folder / "other.json").exists())

    def test_output_inside_candidate_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = make_fixture(Path(tmp))
            out = folder / "candidate" / "inside.json"
            proc = run_tool("generate", "--candidate", str(folder / "candidate"), "--output", str(out))
            record("output inside the candidate folder", proc, None)
            self.assertEqual(proc.returncode, 2)
            self.assertFalse(out.exists())

    def test_existing_output_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = make_fixture(Path(tmp))
            out = folder / "existing.json"
            out.write_bytes(b"keep these bytes\n")
            proc = run_tool("generate", "--candidate", str(folder / "candidate"), "--output", str(out))
            record("existing output file", proc, None)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(out.read_bytes(), b"keep these bytes\n")


class StaleManifestTests(unittest.TestCase):
    """A manifest written before a change must be rejected by the tool and by the launcher's check."""

    def check_stale(self, case: str, change) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = make_fixture(Path(tmp))
            manifest = folder / "manifest.json"
            self.assertEqual(run_tool("generate", "--candidate", str(folder / "candidate"), "--output", str(manifest)).returncode, 0)
            before = manifest.read_bytes()
            change(folder / "candidate")
            proc = run_tool("verify", "--candidate", str(folder / "candidate"), "--manifest", str(manifest))
            result = run_launcher_check(folder, manifest)
            record(case, proc, result)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertFalse(result["accepted"], result)
            self.assertEqual(manifest.read_bytes(), before)

    def test_same_length_change(self) -> None:
        self.check_stale("same-length change of one byte", lambda c: (c / "two.txt").write_bytes(b"twx\n"))

    def test_appended_bytes(self) -> None:
        self.check_stale("bytes appended", lambda c: (c / "two.txt").write_bytes(b"two\nmore\n"))

    def test_removed_file(self) -> None:
        self.check_stale("file removed", lambda c: (c / "sub" / "three.txt").unlink())

    def test_added_file(self) -> None:
        self.check_stale("file added", lambda c: (c / "sub" / "four.txt").write_bytes(b"four\n"))

    def test_renamed_file(self) -> None:
        self.check_stale("file renamed", lambda c: (c / "two.txt").rename(c / "two_renamed.txt"))


class ManifestDefectTests(unittest.TestCase):
    """Manifests with defects. Where the launcher's own check also rejects a case, both are asserted;
    cases marked as stricter are rejected by the tool, while the launcher's result is only recorded."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = make_fixture(Path(self._tmp.name))
        good = self.folder / "good.json"
        self.assertEqual(run_tool("generate", "--candidate", str(self.folder / "candidate"), "--output", str(good)).returncode, 0)
        self.document = json.loads(good.read_bytes())

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, name: str, document: dict | None = None, text: str | None = None) -> Path:
        path = self.folder / name
        path.write_text(text if text is not None else json.dumps(document, indent=2), encoding="utf-8")
        return path

    def row(self, path: str) -> dict:
        return next(r for r in self.document["files"] if r["path"] == path)

    def run_both(self, case: str, manifest: Path, launcher_also_rejects: bool, tool_exit: int) -> None:
        proc = run_tool("verify", "--candidate", str(self.folder / "candidate"), "--manifest", str(manifest))
        result = run_launcher_check(self.folder, manifest)
        record(case, proc, result, "" if launcher_also_rejects else "stricter than the launcher's check")
        self.assertEqual(proc.returncode, tool_exit, proc.stdout + proc.stderr)
        if launcher_also_rejects:
            self.assertFalse(result["accepted"], result)

    def test_missing_entry(self) -> None:
        doc = dict(self.document, files=[r for r in self.document["files"] if r["path"] != "candidate/two.txt"], file_count=3)
        self.run_both("entry missing", self.write("missing.json", doc), True, 1)

    def test_duplicate_entry(self) -> None:
        doc = dict(self.document, files=self.document["files"] + [self.row("candidate/one.txt")], file_count=5)
        self.run_both("entry duplicated", self.write("duplicate.json", doc), True, 2)

    def test_wrong_size(self) -> None:
        doc = json.loads(json.dumps(self.document))
        next(r for r in doc["files"] if r["path"] == "candidate/two.txt")["bytes"] += 1
        self.run_both("wrong size", self.write("size.json", doc), True, 1)

    def test_wrong_hash(self) -> None:
        doc = json.loads(json.dumps(self.document))
        row = next(r for r in doc["files"] if r["path"] == "candidate/two.txt")
        row["sha256"] = ("0" if row["sha256"][0] != "0" else "1") + row["sha256"][1:]
        self.run_both("wrong SHA-256", self.write("hash.json", doc), True, 1)

    def test_uppercase_hash(self) -> None:
        doc = json.loads(json.dumps(self.document))
        row = next(r for r in doc["files"] if r["path"] == "candidate/two.txt")
        row["sha256"] = row["sha256"].upper()
        self.run_both("SHA-256 in upper case", self.write("upper.json", doc), True, 2)

    def test_path_outside_code_folder(self) -> None:
        doc = dict(self.document, files=self.document["files"] + [{"path": "../elsewhere.txt", "bytes": 1, "sha256": "0" * 64}], file_count=5)
        self.run_both("path outside the code folder", self.write("outside.json", doc), True, 2)

    def test_absolute_path(self) -> None:
        doc = json.loads(json.dumps(self.document))
        row = next(r for r in doc["files"] if r["path"] == "candidate/two.txt")
        row["path"] = str((self.folder / "candidate" / "two.txt").resolve())
        self.run_both("absolute path", self.write("absolute.json", doc), True, 2)

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links not available")
    def test_symbolic_link_to_file(self) -> None:
        target = self.folder / "two_copy.txt"
        target.write_bytes(b"two\n")
        (self.folder / "candidate" / "two.txt").unlink()
        os.symlink(target, self.folder / "candidate" / "two.txt")
        self.run_both("symbolic link to a file", self.write("link.json", self.document), True, 2)

    def test_extra_entry_outside_candidate_folder(self) -> None:
        notes = self.folder / "notes.txt"
        extra = {"path": "notes.txt", "bytes": notes.stat().st_size, "sha256": sha256_of(notes)}
        doc = dict(self.document, files=self.document["files"] + [extra], file_count=5)
        self.run_both("extra entry outside the candidate folder", self.write("extra.json", doc), False, 2)

    def test_dot_dot_entry_inside_folder(self) -> None:
        one = self.row("candidate/one.txt")
        doc = dict(self.document, files=self.document["files"] + [dict(one, path="candidate/sub/../one.txt")], file_count=5)
        self.run_both("'..' entry that stays inside the folder", self.write("dotdot.json", doc), False, 2)

    def test_boolean_size(self) -> None:
        doc = json.loads(json.dumps(self.document))
        next(r for r in doc["files"] if r["path"] == "candidate/one.txt")["bytes"] = True
        self.run_both("size given as a boolean", self.write("boolean.json", doc), False, 2)

    def test_duplicate_json_key(self) -> None:
        one = self.row("candidate/one.txt")
        text = json.dumps(self.document, indent=2)
        wrong = '"sha256": "' + "0" * 64 + '",\n      "sha256": "' + one["sha256"] + '"'
        text = text.replace('"sha256": "' + one["sha256"] + '"', wrong, 1)
        self.run_both("duplicate JSON key in an entry", self.write("dupkey.json", text=text), False, 2)

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links not available")
    def test_symbolic_link_to_folder(self) -> None:
        elsewhere = Path(self._tmp.name) / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "hidden.txt").write_bytes(b"not listed\n")
        os.symlink(elsewhere, self.folder / "candidate" / "linked", target_is_directory=True)
        self.run_both("symbolic link to a folder", self.write("dirlink.json", self.document), False, 2)

    def test_generate_refuses_symbolic_links(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links not available")
        os.symlink(self.folder / "notes.txt", self.folder / "candidate" / "link.txt")
        proc = run_tool("generate", "--candidate", str(self.folder / "candidate"), "--output", str(self.folder / "new.json"))
        record("generate with a symbolic link in the folder", proc, None)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.folder / "new.json").exists())


class ChangedConfigurationTests(unittest.TestCase):
    def test_changed_configuration_needs_new_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = copy_code_folder(Path(tmp))
            release = folder / RELEASE_MANIFEST.name
            config = folder / "candidate" / "config" / "RUN_CONFIG_v1.json"
            data = config.read_bytes()
            self.assertIn(b"<PROJECT_ROOT>", data)
            config.write_bytes(data.replace(b"<PROJECT_ROOT>", b"/example/project"))
            stale_tool = run_tool("verify", "--candidate", str(folder / "candidate"), "--manifest", str(release))
            stale_launcher = run_launcher_check(folder, release)
            record("configuration edited; release manifest no longer matches", stale_tool, stale_launcher)
            self.assertEqual(stale_tool.returncode, 1)
            self.assertFalse(stale_launcher["accepted"], stale_launcher)
            local = folder / "LOCAL_CODE_IDENTITY.json"
            self.assertEqual(run_tool("generate", "--candidate", str(folder / "candidate"), "--output", str(local)).returncode, 0)
            new_tool = run_tool("verify", "--candidate", str(folder / "candidate"), "--manifest", str(local))
            new_launcher = run_launcher_check(folder, local)
            record("configuration edited; new local manifest written", new_tool, new_launcher,
                   "identity only; this does not approve running the edited configuration")
            self.assertEqual(new_tool.returncode, 0, new_tool.stdout + new_tool.stderr)
            self.assertTrue(new_launcher["accepted"], new_launcher)
            self.assertEqual(new_launcher["returned_sha256"], sha256_of(local))
            self.assertEqual(release.read_bytes(), RELEASE_MANIFEST.read_bytes())


if __name__ == "__main__":
    unittest.main()
