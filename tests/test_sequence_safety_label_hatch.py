"""Rehearsal for the sequence-safety label hatch (.github/workflows/sequence-safety.yml).

Sequence Safety is a REQUIRED branch-ruleset check. The ``allow-symbol-loss``
and ``docs-rewrite`` labels are the only in-workflow way to pass ``--advisory``
to a screen, and that pass must be an exact label match. A prefix, a different
case, a failed ``gh pr view``, or an empty PR number must leave the screen
blocking. The workflow still honors the tool's exit code: it does not zero a
failure locally just because the label was present.

Project: juniper-cascor-client
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 - the workflow's own extracted shell is the thing under test
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

WORKFLOW = "sequence-safety.yml"
STEP_NAME = "Run sequence-safety screens (symbol + docs)"
SYMBOL = "juniper-symbol-loss-check"
DOCS = "juniper-docs-additions-check"


@dataclass
class ScreenResult:
    returncode: int
    stdout: str
    stderr: str
    symbol_calls: tuple[str, ...]
    docs_calls: tuple[str, ...]
    gh_calls: tuple[str, ...]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workflow() -> dict:
    path = _repo_root() / ".github" / "workflows" / WORKFLOW
    assert path.is_file(), f"{WORKFLOW} missing -- the required check this test guards is gone"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _screen_script() -> str:
    steps = _workflow()["jobs"]["sequence-safety"]["steps"]
    match = next((step for step in steps if step.get("name") == STEP_NAME), None)
    assert match is not None and "run" in match, f"{STEP_NAME!r} missing from {WORKFLOW}"
    script = match["run"]
    assert isinstance(script, str)
    return script


def _child_env(**overrides: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),  # nosec B108 - git needs a HOME in the fixture
        "LANG": "C",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    env.update(overrides)
    return env


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(  # nosec B603 B607 - fixed git argv inside a temp repo
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_child_env(),
    )
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout.strip()


def _commit(repo: Path) -> str:
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-qm", "base")
    return _git(repo, "rev-parse", "HEAD")


def _run(
    *,
    base: str,
    labels: str = "",
    pr_number: str = "175",
    symbol_exit: int = 0,
    docs_exit: int = 0,
    gh_fail: bool = False,
) -> ScreenResult:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        work = root / "repo"
        work.mkdir()
        if base == "AUTO":
            base = _commit(work)
        stub = root / "bin"
        stub.mkdir()
        symbol_calls = root / "symbol_calls"
        docs_calls = root / "docs_calls"
        gh_calls = root / "gh_calls"
        _write_logged_stub(stub / SYMBOL, symbol_calls, "SYMBOL_EXIT")
        _write_logged_stub(stub / DOCS, docs_calls, "DOCS_EXIT")
        gh = stub / "gh"
        gh.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    'printf "%s\\n" "$*" >> "$GH_CALLS"',
                    'if [ -n "${GH_FAIL:-}" ]; then',
                    "  exit 1",
                    "fi",
                    'printf "%s" "$GH_LABELS"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        gh.chmod(0o755)
        env = _child_env(
            PATH=str(stub) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            PR_BASE_SHA=base,
            PR_NUMBER=pr_number,
            SYMBOL_EXIT=str(symbol_exit),
            DOCS_EXIT=str(docs_exit),
            GH_CALLS=str(gh_calls),
            GH_LABELS=labels,
        )
        if gh_fail:
            env["GH_FAIL"] = "1"
        script_path = root / "screens.sh"
        script_path.write_text(_screen_script(), encoding="utf-8")
        proc = subprocess.run(  # nosec B603 B607 - fixed bash argv, workflow shell under test
            ["bash", str(script_path)],
            cwd=work,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        return ScreenResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            symbol_calls=_lines(symbol_calls),
            docs_calls=_lines(docs_calls),
            gh_calls=_lines(gh_calls),
        )


def _write_logged_stub(path: Path, calls: Path, exit_var: str) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'printf "%s\\n" "$*" >> "{calls}"',
                'exit "${' + exit_var + ':-0}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _lines(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        return ()
    return tuple(line for line in path.read_text(encoding="utf-8").splitlines() if line)


def _advisory(calls: tuple[str, ...]) -> bool:
    return any("--advisory" in line for line in calls)


class TestExitCodes:
    def test_clean_screens_exit_zero(self) -> None:
        result = _run(base="AUTO")
        assert result.returncode == 0, result.stderr
        assert "::notice::sequence-safety screens clean" in result.stdout
        assert len(result.symbol_calls) == 2
        assert len(result.docs_calls) == 2

    def test_finding_exits_one(self) -> None:
        result = _run(base="AUTO", symbol_exit=1)
        assert result.returncode == 1
        assert "compositional-loss finding" in result.stdout

    def test_invocation_error_exits_two_ahead_of_a_finding(self) -> None:
        result = _run(base="AUTO", symbol_exit=1, docs_exit=2)
        assert result.returncode == 2
        assert "screen invocation error" in result.stdout

    def test_docs_finding_alone_exits_one(self) -> None:
        result = _run(base="AUTO", docs_exit=1)
        assert result.returncode == 1

    def test_missing_base_exits_two_without_screening(self) -> None:
        result = _run(base="")
        assert result.returncode == 2
        assert "could not resolve a base sha" in result.stdout
        assert result.symbol_calls == ()
        assert result.docs_calls == ()
        assert result.gh_calls == ()


class TestLabelHatch:
    def test_exact_symbol_label_advises_only_the_symbol_screen(self) -> None:
        result = _run(base="AUTO", labels="allow-symbol-loss\n", symbol_exit=1)
        # The workflow does not swallow the tool's exit. Advisory is a flag
        # the screen itself honors by exiting 0; a tool that still returns 1
        # must still fail this required check.
        assert result.returncode == 1
        assert _advisory(result.symbol_calls)
        assert not _advisory(result.docs_calls)
        assert all("--advisory" in line for line in result.symbol_calls)

    def test_exact_docs_label_advises_only_the_docs_screen(self) -> None:
        result = _run(base="AUTO", labels="docs-rewrite\n", docs_exit=1)
        assert result.returncode == 1
        assert _advisory(result.docs_calls)
        assert not _advisory(result.symbol_calls)

    def test_both_exact_labels_advise_both_screens(self) -> None:
        result = _run(base="AUTO", labels="allow-symbol-loss\ndocs-rewrite\n")
        assert result.returncode == 0, result.stderr
        assert _advisory(result.symbol_calls)
        assert _advisory(result.docs_calls)

    def test_prefix_case_and_padding_do_not_open_the_hatch(self) -> None:
        labels = "\n".join(
            [
                "allow-symbol-loss-extra",
                "Allow-Symbol-Loss",
                "allow-symbol-loss ",
                "docs-rewrite-please",
                "Docs-Rewrite",
                "not-allow-symbol-loss",
            ]
        )
        result = _run(base="AUTO", labels=labels + "\n", symbol_exit=1, docs_exit=1)
        assert result.returncode == 1
        assert not _advisory(result.symbol_calls)
        assert not _advisory(result.docs_calls)

    def test_gh_failure_does_not_apply_a_label_it_could_not_read(self) -> None:
        result = _run(base="AUTO", labels="allow-symbol-loss\n", gh_fail=True, symbol_exit=1)
        assert result.returncode == 1
        assert result.gh_calls
        assert not _advisory(result.symbol_calls)

    def test_empty_pr_number_does_not_consult_gh(self) -> None:
        result = _run(base="AUTO", labels="allow-symbol-loss\n", pr_number="", symbol_exit=1)
        assert result.returncode == 1
        assert result.gh_calls == ()
        assert not _advisory(result.symbol_calls)


class TestScreenInvocation:
    def test_symbol_screen_is_scoped_to_this_repo(self) -> None:
        result = _run(base="AUTO")
        assert result.symbol_calls
        for line in result.symbol_calls:
            assert "--scope juniper_cascor_client/**/*.py" in line
            assert "--scope tests/**/*.py" in line
            assert "--head HEAD" in line
            assert "--base " in line
        assert sum("--json" in line for line in result.symbol_calls) == 1

    def test_docs_screen_keeps_the_universal_scope(self) -> None:
        result = _run(base="AUTO")
        assert result.docs_calls
        for line in result.docs_calls:
            assert "--scope" not in line
            assert "--head HEAD" in line
            assert "--base " in line


class TestWorkflowContract:
    def test_job_name_is_the_required_context(self) -> None:
        job = _workflow()["jobs"]["sequence-safety"]
        assert job["name"] == "Sequence Safety"
        assert job["permissions"] == {"contents": "read", "pull-requests": "read"}

    def test_pull_request_only(self) -> None:
        # PyYAML 1.1 parses the bare key `on` as boolean True.
        document = _workflow()
        triggers = document["on"] if "on" in document else document[True]
        assert set(triggers) == {"pull_request"}
        assert triggers["pull_request"]["branches"] == ["main", "develop"]

    def test_not_wired_into_the_ci_quality_gate(self) -> None:
        # Required is a ruleset property. A needs: edge would make a skip on a
        # docs-only PR skip the gate, which is the failure mode the header
        # exists to keep distinct from "this check blocks merges".
        ci_path = _repo_root() / ".github" / "workflows" / "ci.yml"
        ci = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
        for job in ci["jobs"].values():
            needs = job.get("needs", [])
            if isinstance(needs, str):
                needs = [needs]
            assert "sequence-safety" not in needs
            assert "Sequence Safety" not in needs
