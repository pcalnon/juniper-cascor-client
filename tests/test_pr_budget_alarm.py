"""Rehearsal for the open-PR budget alarm (.github/workflows/pr-budget-alarm.yml).

The alarm (#166) is report-only and runs on a daily cron. A breach must stay
green, a failed ``gh pr list`` must stay green with ``level=OK`` (so the Slack
step does not fire on an API blip), and the webhook URL must never appear in
the notice. These tests extract the workflow's own shell.

Project: juniper-cascor-client
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - the workflow's own extracted shell is the thing under test
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

WORKFLOW = "pr-budget-alarm.yml"
COUNT_STEP = "Count open PRs and evaluate the budget"
SLACK_STEP = "Slack notification on breach (non-blocking, Q-CHANNEL)"
REPO = "pcalnon/juniper-cascor-client"


@dataclass
class ShellResult:
    returncode: int
    stdout: str
    stderr: str
    github_output: str = ""
    step_summary: str = ""
    gh_argv: str = ""
    curl_args: tuple[str, ...] = ()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workflow() -> dict:
    path = _repo_root() / ".github" / "workflows" / WORKFLOW
    assert path.is_file(), f"{WORKFLOW} missing -- the alarm this test guards is gone"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _step(name: str) -> dict:
    steps = _workflow()["jobs"]["budget-alarm"]["steps"]
    match = next((step for step in steps if step.get("name") == name), None)
    assert match is not None and "run" in match, f"{name!r} run step missing from {WORKFLOW}"
    return match


def _child_env(**overrides: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),  # nosec B108 - bash fallback only
        "LANG": "C",
    }
    env.update(overrides)
    return env


def _prs(*names: str) -> str:
    return json.dumps([{"number": index + 1, "headRefName": name} for index, name in enumerate(names)])


def _outputs(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            parsed[key] = value
    return parsed


def _run_shell(script: str, env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    script_path = cwd / "step.sh"
    script_path.write_text(script, encoding="utf-8")
    return subprocess.run(  # nosec B603 B607 - fixed bash argv, workflow shell under test
        ["bash", str(script_path)],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _run_count(
    body: str,
    *,
    warn: str | None = None,
    alarm: str | None = None,
    fail: bool = False,
    stderr: str = "",
    repo: str = REPO,
) -> ShellResult:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        argv = root / "gh_argv"
        body_path = root / "body.json"
        err_path = root / "stderr.txt"
        output = root / "github_output"
        summary = root / "step_summary"
        body_path.write_text(body, encoding="utf-8")
        err_path.write_text(stderr, encoding="utf-8")
        stub = root / "bin"
        stub.mkdir()
        gh = stub / "gh"
        gh.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    'printf "%s\\n" "$*" >> "$GH_ARGV"',
                    'if [ -n "${GH_FAIL:-}" ]; then',
                    '  cat "$GH_STDERR_FILE" >&2',
                    "  exit 1",
                    "fi",
                    'cat "$GH_BODY_FILE"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        gh.chmod(0o755)
        env = _child_env(
            PATH=str(stub) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            GH_REPO=repo,
            GH_ARGV=str(argv),
            GH_BODY_FILE=str(body_path),
            GH_STDERR_FILE=str(err_path),
            GITHUB_OUTPUT=str(output),
            GITHUB_STEP_SUMMARY=str(summary),
        )
        if fail:
            env["GH_FAIL"] = "1"
        if warn is not None:
            env["PR_BUDGET_WARN"] = warn
        if alarm is not None:
            env["PR_BUDGET_ALARM"] = alarm
        proc = _run_shell(_step(COUNT_STEP)["run"], env, root)
        return ShellResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            github_output=output.read_text(encoding="utf-8") if output.is_file() else "",
            step_summary=summary.read_text(encoding="utf-8") if summary.is_file() else "",
            gh_argv=argv.read_text(encoding="utf-8") if argv.is_file() else "",
        )


def _run_slack(
    *,
    level: str = "WARN",
    total: str = "16",
    cursor: str = "2",
    warn: str = "15",
    alarm: str = "30",
    webhook: str | None = None,
    curl_fail: bool = False,
) -> ShellResult:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        curl_log = root / "curl_args"
        stub = root / "bin"
        stub.mkdir()
        curl = stub / "curl"
        curl.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    'printf "%s\\0" "$@" >> "$CURL_LOG"',
                    'if [ -n "${CURL_FAIL:-}" ]; then',
                    "  exit 22",
                    "fi",
                    "exit 0",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        curl.chmod(0o755)
        env = _child_env(
            PATH=str(stub) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            LEVEL=level,
            TOTAL=total,
            CURSOR=cursor,
            WARN=warn,
            ALARM=alarm,
            RUN_URL="https://github.com/pcalnon/juniper-cascor-client/actions/runs/1",
            CURL_LOG=str(curl_log),
        )
        if webhook is not None:
            env["SLACK_WEBHOOK_URL"] = webhook
        if curl_fail:
            env["CURL_FAIL"] = "1"
        proc = _run_shell(_step(SLACK_STEP)["run"], env, root)
        raw_args = curl_log.read_text(encoding="utf-8") if curl_log.is_file() else ""
        args = tuple(part for part in raw_args.split("\0") if part)
        return ShellResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            curl_args=args,
        )


class TestBudgetThresholds:
    def test_unset_thresholds_default_to_15_and_30(self) -> None:
        proc = _run_count("[]")
        assert proc.returncode == 0, proc.stderr
        assert _outputs(proc.github_output) == {"total": "0", "cursor": "0", "warn": "15", "alarm": "30", "level": "OK"}
        assert "**OK**" in proc.step_summary

    def test_empty_threshold_variables_use_the_same_defaults(self) -> None:
        # ${VAR:-15} substitutes for an empty string, which is what an unset
        # repository variable looks like inside the step env.
        proc = _run_count("[]", warn="", alarm="")
        assert proc.returncode == 0, proc.stderr
        outputs = _outputs(proc.github_output)
        assert outputs["warn"] == "15"
        assert outputs["alarm"] == "30"
        assert outputs["level"] == "OK"

    @pytest.mark.parametrize(
        ("count", "level"),
        [(14, "OK"), (15, "WARN"), (29, "WARN"), (30, "ALARM")],
    )
    def test_total_boundaries_are_inclusive(self, count: int, level: str) -> None:
        names = tuple(f"feature/{index}" for index in range(count))
        proc = _run_count(_prs(*names))
        assert proc.returncode == 0, proc.stderr
        outputs = _outputs(proc.github_output)
        assert outputs["total"] == str(count)
        assert outputs["cursor"] == "0"
        assert outputs["level"] == level

    @pytest.mark.parametrize(
        ("cursor_count", "level"),
        [(14, "OK"), (15, "WARN"), (30, "ALARM")],
    )
    def test_cursor_subset_breaches_on_its_own(self, cursor_count: int, level: str) -> None:
        names = tuple(f"cursor/agent-{index}" for index in range(cursor_count))
        proc = _run_count(_prs(*names))
        assert proc.returncode == 0, proc.stderr
        outputs = _outputs(proc.github_output)
        assert outputs["cursor"] == str(cursor_count)
        assert outputs["total"] == str(cursor_count)
        assert outputs["level"] == level

    def test_equal_thresholds_alarm_at_the_shared_boundary(self) -> None:
        # ALARM is tested first, so warn==alarm does not report WARN.
        names = tuple(f"feature/{index}" for index in range(15))
        proc = _run_count(_prs(*names), warn="15", alarm="15")
        assert proc.returncode == 0, proc.stderr
        assert _outputs(proc.github_output)["level"] == "ALARM"

    def test_warn_zero_warns_on_an_empty_queue(self) -> None:
        proc = _run_count("[]", warn="0", alarm="30")
        assert proc.returncode == 0, proc.stderr
        assert _outputs(proc.github_output)["level"] == "WARN"

    def test_alarm_zero_alarms_before_warn(self) -> None:
        proc = _run_count("[]", warn="0", alarm="0")
        assert proc.returncode == 0, proc.stderr
        assert _outputs(proc.github_output)["level"] == "ALARM"


class TestCursorPrefix:
    def test_only_the_cursor_slash_prefix_counts(self) -> None:
        proc = _run_count(
            _prs(
                "cursor/real",
                "cursor/",
                "cursor",
                "Cursor/cased",
                "cursor-agent",
                "feature/cursor/nested",
            )
        )
        assert proc.returncode == 0, proc.stderr
        outputs = _outputs(proc.github_output)
        assert outputs["total"] == "6"
        assert outputs["cursor"] == "2"
        assert outputs["level"] == "OK"

    def test_gh_lists_open_prs_with_a_bounded_page(self) -> None:
        proc = _run_count("[]", repo=REPO)
        assert proc.returncode == 0, proc.stderr
        assert f"--repo {REPO}" in proc.gh_argv
        assert "--state open" in proc.gh_argv
        assert "--limit 500" in proc.gh_argv
        assert "--json number,headRefName" in proc.gh_argv


class TestQueryFailureStaysGreen:
    def test_gh_failure_is_ok_and_not_an_empty_queue(self) -> None:
        proc = _run_count("[]", fail=True, stderr="api down\ntry later\n")
        assert proc.returncode == 0, proc.stderr
        assert _outputs(proc.github_output) == {"level": "OK"}
        assert "::warning title=pr-budget-alarm::" in proc.stdout
        assert "api down try later" in proc.stdout
        assert "\napi down" not in proc.stdout
        assert "Could not query open PRs" in proc.step_summary
        assert "Open PRs (total)" not in proc.step_summary

    def test_truncated_json_does_not_report_an_empty_ok_queue(self) -> None:
        proc = _run_count("[")
        assert proc.returncode != 0
        assert "level=OK" not in proc.github_output
        assert "Open PRs (total)" not in proc.step_summary

    def test_pr_with_no_branch_name_is_not_an_empty_queue(self) -> None:
        # startswith() on a null headRefName is a jq error. Swallowing it as
        # zero would hide a shape change in `gh pr list` behind level=OK.
        proc = _run_count(json.dumps([{"number": 1}]))
        assert proc.returncode != 0
        assert "level=OK" not in proc.github_output


class TestSlackNotice:
    def test_missing_webhook_warns_and_does_not_post(self) -> None:
        proc = _run_slack(level="ALARM", total="31", cursor="4")
        assert proc.returncode == 0, proc.stderr
        assert proc.curl_args == ()
        assert "::warning title=PR budget ALARM with no Slack webhook::" in proc.stdout
        assert "31 open PR(s), 4 on cursor/ branches" in proc.stdout
        assert "SLACK_WEBHOOK_URL is not set" in proc.stdout

    def test_notice_is_text_only_and_omits_the_webhook(self) -> None:
        webhook = "https://hooks.example.test/services/T00/B00/not-a-real-secret"
        proc = _run_slack(webhook=webhook, level="WARN", total="16", cursor="3", warn="15", alarm="30")
        assert proc.returncode == 0, proc.stderr
        assert "-fsS" in proc.curl_args
        assert "-X" in proc.curl_args and "POST" in proc.curl_args
        assert "Content-Type: application/json" in proc.curl_args
        payload = proc.curl_args[proc.curl_args.index("-d") + 1]
        assert proc.curl_args[-1] == webhook
        body = json.loads(payload)
        assert set(body) == {"text"}
        text = body["text"]
        assert text.startswith("PR budget WARN:")
        assert "16 open PR(s), 3 on cursor/ branches" in text
        assert "warn=15" in text and "alarm=30" in text
        assert webhook not in text
        assert webhook not in proc.stdout
        assert webhook not in proc.stderr

    def test_post_failure_fails_the_script(self) -> None:
        # continue-on-error is a workflow property (pinned below). The script
        # itself must still surface a failed POST.
        webhook = "https://hooks.example.test/services/T00/B00/not-a-real-secret"
        proc = _run_slack(webhook=webhook, curl_fail=True)
        assert proc.returncode != 0


class TestWorkflowContract:
    def test_schedule_and_dispatch_only(self) -> None:
        # PyYAML 1.1 parses the bare key `on` as boolean True.
        document = _workflow()
        triggers = document["on"] if "on" in document else document[True]
        assert set(triggers) == {"schedule", "workflow_dispatch"}
        assert triggers["schedule"] == [{"cron": "0 14 * * *"}]

    def test_permissions_are_read_only(self) -> None:
        assert _workflow()["permissions"] == {"contents": "read", "pull-requests": "read"}

    def test_slack_fires_only_on_breach_and_cannot_fail_the_run(self) -> None:
        slack = _step(SLACK_STEP)
        assert slack["if"] == "steps.count.outputs.level != 'OK'"
        assert slack["continue-on-error"] is True

    def test_count_step_has_no_webhook_and_slack_step_does(self) -> None:
        count_env = _step(COUNT_STEP).get("env", {})
        slack_env = _step(SLACK_STEP).get("env", {})
        assert "SLACK_WEBHOOK_URL" not in count_env
        assert "SLACK_WEBHOOK_URL" in slack_env
        assert count_env["GH_REPO"] == "${{ github.repository }}"

    def test_concurrency_cancels_the_older_report(self) -> None:
        concurrency = _workflow()["concurrency"]
        assert concurrency["group"] == "pr-budget-alarm"
        assert concurrency["cancel-in-progress"] is True
