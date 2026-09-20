import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gh_stack_master = load_script("gh_stack_master_under_test", "scripts/gh_stack_master.py")


def completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class GitHubCommandTests(unittest.TestCase):
    def test_gh_invokes_cli_with_optional_working_directory(self):
        with mock.patch.object(gh_stack_master.subprocess, "run", return_value=completed()) as run:
            result = gh_stack_master.gh(["repo", "list"], cwd=Path("/tmp/repo"))

        self.assertEqual(result.returncode, 0)
        run.assert_called_once_with(
            ["gh", "repo", "list"], cwd="/tmp/repo", text=True, capture_output=True
        )

    def test_must_gh_exits_when_authentication_fails(self):
        with mock.patch.object(
            gh_stack_master, "gh", return_value=completed(1, stderr="not logged in")
        ), contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                gh_stack_master.must_gh()

        self.assertEqual(raised.exception.code, 1)
        self.assertIn("not logged in", output.getvalue())
        self.assertIn("FAIL gh not authenticated", output.getvalue())

    def test_repo_names_returns_names_from_github_json(self):
        payload = json.dumps([{"name": "alpha"}, {"name": "beta"}])
        with mock.patch.object(gh_stack_master, "gh", return_value=completed(stdout=payload)) as gh:
            self.assertEqual(gh_stack_master.repo_names(), ["alpha", "beta"])

        gh.assert_called_once_with(
            ["repo", "list", gh_stack_master.OWNER, "--limit", "200", "--json", "name"]
        )

    def test_repo_names_exits_when_listing_fails(self):
        with mock.patch.object(
            gh_stack_master, "gh", return_value=completed(1, stderr="API unavailable")
        ), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                gh_stack_master.repo_names()


class ClassifyPullRequestTests(unittest.TestCase):
    def classify(self, payload):
        with mock.patch.object(
            gh_stack_master, "gh", return_value=completed(stdout=json.dumps(payload))
        ):
            return gh_stack_master.classify_pr("demo", 17)

    def test_successful_open_pull_request_is_safe(self):
        row = self.classify(
            {
                "number": 17,
                "title": "Ready",
                "url": "https://example.test/pr/17",
                "isDraft": False,
                "mergeable": "MERGEABLE",
                "state": "OPEN",
                "headRefName": "feature",
                "baseRefName": "main",
                "statusCheckRollup": [{"conclusion": "SUCCESS", "state": "COMPLETED"}],
                "files": [{"path": "src/app.py"}],
            }
        )

        self.assertEqual(row["verdict"], "SAFE")
        self.assertEqual(row["why"], [])
        self.assertEqual(row["checks"], ["SUCCESS"])
        self.assertEqual(row["files"], ["src/app.py"])
        self.assertEqual((row["head"], row["base"]), ("feature", "main"))

    def test_unsafe_reasons_are_aggregated(self):
        row = self.classify(
            {
                "number": 17,
                "title": "WIP: risky change",
                "isDraft": True,
                "mergeable": "CONFLICTING",
                "state": "CLOSED",
                "statusCheckRollup": [
                    {"state": "IN_PROGRESS", "conclusion": None},
                    {"state": "COMPLETED", "conclusion": "FAILURE"},
                ],
                "files": [{"path": "data/cache.sqlite-wal"}],
            }
        )

        self.assertEqual(row["verdict"], "UNSAFE")
        self.assertEqual(
            row["why"],
            [
                "draft",
                "mergeable=CONFLICTING",
                "state=CLOSED",
                "wip-title",
                "pending-checks=1",
                "failed-checks=1",
                "runtime-files=data/cache.sqlite-wal",
            ],
        )
        self.assertEqual(row["checks"], ["IN_PROGRESS", "FAILURE"])

    def test_missing_checks_make_pull_request_unsafe(self):
        row = self.classify(
            {
                "number": 17,
                "title": "No CI",
                "isDraft": False,
                "mergeable": "MERGEABLE",
                "state": "OPEN",
                "statusCheckRollup": None,
                "files": None,
            }
        )

        self.assertEqual(row["verdict"], "UNSAFE")
        self.assertEqual(row["why"], ["no-checks"])
        self.assertEqual(row["files"], [])

    def test_runtime_file_detection_includes_compound_archive_suffix(self):
        row = self.classify(
            {
                "number": 17,
                "title": "Archive",
                "isDraft": False,
                "mergeable": "MERGEABLE",
                "state": "OPEN",
                "statusCheckRollup": [{"conclusion": "SUCCESS"}],
                "files": [{"path": "release/snapshot.tar.gz"}, {"path": "docs/db.md"}],
            }
        )

        self.assertEqual(row["why"], ["runtime-files=release/snapshot.tar.gz"])

    def test_only_first_twenty_files_are_returned(self):
        row = self.classify(
            {
                "number": 17,
                "title": "Many files",
                "isDraft": False,
                "mergeable": "MERGEABLE",
                "state": "OPEN",
                "statusCheckRollup": [{"conclusion": "SUCCESS"}],
                "files": [{"path": "file-{}.txt".format(index)} for index in range(25)],
            }
        )

        self.assertEqual(len(row["files"]), 20)
        self.assertEqual(row["files"][-1], "file-19.txt")

    def test_github_failure_returns_error_without_parsing_json(self):
        stderr = "x" * 350
        with mock.patch.object(
            gh_stack_master, "gh", return_value=completed(1, stderr=stderr)
        ):
            row = gh_stack_master.classify_pr("demo", 17)

        self.assertEqual(row["verdict"], "ERROR")
        self.assertEqual(row["why"], ["x" * 300])


class ScanCommandTests(unittest.TestCase):
    def test_scan_classifies_pull_requests_and_writes_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "gh_pr_scan.json"

            def fake_gh(args, cwd=None):
                repo = args[args.index("--repo") + 1]
                if repo.endswith("/empty"):
                    return completed(stdout="[]")
                if repo.endswith("/broken"):
                    return completed(1, stderr="cannot list")
                return completed(stdout='[{"number": 1}, {"number": 2}]')

            rows = [
                {"verdict": "SAFE", "repo": "mixed", "number": 1, "title": "one", "why": []},
                {
                    "verdict": "UNSAFE",
                    "repo": "mixed",
                    "number": 2,
                    "title": "two",
                    "why": ["draft"],
                },
            ]
            with mock.patch.object(gh_stack_master, "must_gh"), mock.patch.object(
                gh_stack_master, "repo_names", return_value=["empty", "mixed", "broken"]
            ), mock.patch.object(gh_stack_master, "gh", side_effect=fake_gh), mock.patch.object(
                gh_stack_master, "classify_pr", side_effect=rows
            ) as classify, mock.patch.object(
                gh_stack_master, "Path", return_value=report
            ), contextlib.redirect_stdout(io.StringIO()) as output:
                result = gh_stack_master.cmd_scan()

            self.assertEqual(result, 0)
            self.assertEqual(
                json.loads(report.read_text(encoding="utf-8")),
                {"safe": [rows[0]], "unsafe": [rows[1]]},
            )
            self.assertEqual(classify.call_args_list, [mock.call("mixed", 1), mock.call("mixed", 2)])
            self.assertIn("REPO_ERR broken cannot list", output.getvalue())
            self.assertIn("SAFE 1", output.getvalue())
            self.assertIn("UNSAFE 1", output.getvalue())
            self.assertIn("NO_OPEN_PR 1", output.getvalue())


class OpenStackPullRequestTests(unittest.TestCase):
    def test_existing_pull_request_is_not_created_again(self):
        with tempfile.TemporaryDirectory() as directory:
            wisdom = Path(directory)
            (wisdom / ".git").mkdir()
            responses = [
                completed(stdout=gh_stack_master.STACK_BRANCH + "\n"),
                completed(stdout='[{"number":22,"url":"https://example.test/22"}]'),
            ]
            with mock.patch.object(gh_stack_master, "must_gh"), mock.patch.object(
                gh_stack_master, "WISDOM", wisdom
            ), mock.patch.object(
                gh_stack_master.subprocess, "run", return_value=responses[0]
            ), mock.patch.object(
                gh_stack_master, "gh", return_value=responses[1]
            ) as gh, contextlib.redirect_stdout(io.StringIO()):
                result = gh_stack_master.cmd_open_stack_pr()

            self.assertEqual(result, 0)
            self.assertEqual(gh.call_count, 1)

    def test_open_stack_pull_request_requires_expected_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            wisdom = Path(directory)
            (wisdom / ".git").mkdir()
            with mock.patch.object(gh_stack_master, "must_gh"), mock.patch.object(
                gh_stack_master, "WISDOM", wisdom
            ), mock.patch.object(
                gh_stack_master.subprocess,
                "run",
                return_value=completed(stdout="main\n"),
            ), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    gh_stack_master.cmd_open_stack_pr()

    def test_open_stack_pull_request_creates_when_none_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            wisdom = Path(directory)
            (wisdom / ".git").mkdir()
            with mock.patch.object(gh_stack_master, "must_gh"), mock.patch.object(
                gh_stack_master, "WISDOM", wisdom
            ), mock.patch.object(
                gh_stack_master.subprocess,
                "run",
                return_value=completed(stdout=gh_stack_master.STACK_BRANCH + "\n"),
            ), mock.patch.object(
                gh_stack_master,
                "gh",
                side_effect=[completed(stdout="[]"), completed(stdout="created")],
            ) as gh, contextlib.redirect_stdout(io.StringIO()):
                result = gh_stack_master.cmd_open_stack_pr()

            self.assertEqual(result, 0)
            create_args, create_kwargs = gh.call_args_list[1]
            self.assertEqual(create_args[0][:2], ["pr", "create"])
            self.assertEqual(create_kwargs["cwd"], wisdom)


class ApplyCommandTests(unittest.TestCase):
    def test_apply_rechecks_safety_and_counts_only_successful_merges(self):
        candidates = [
            {"repo": "changed", "number": 1, "title": "changed"},
            {"repo": "fails", "number": 2, "title": "fails"},
            {"repo": "good", "number": 3, "title": "good"},
            {"repo": "after-limit", "number": 4, "title": "later"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "scan.json"
            report.write_text(json.dumps({"safe": candidates}), encoding="utf-8")

            live_rows = [
                {"verdict": "UNSAFE", "why": ["state=CLOSED"]},
                {"verdict": "SAFE", "why": [], "title": "fails"},
                {"verdict": "SAFE", "why": [], "title": "good"},
            ]

            def fake_gh(args, cwd=None):
                number = args[2]
                if number == "2":
                    return completed(1, stderr="merge rejected")
                return completed(stdout="merged")

            with mock.patch.object(gh_stack_master, "must_gh"), mock.patch.object(
                gh_stack_master, "Path", return_value=report
            ), mock.patch.object(
                gh_stack_master, "classify_pr", side_effect=live_rows
            ) as classify, mock.patch.object(
                gh_stack_master, "gh", side_effect=fake_gh
            ) as gh, contextlib.redirect_stdout(io.StringIO()) as output:
                result = gh_stack_master.cmd_apply(limit=1)

            self.assertEqual(result, 0)
            self.assertEqual(classify.call_count, 3)
            self.assertEqual([call.args[0][2] for call in gh.call_args_list], ["2", "3"])
            self.assertIn("SKIP_NOW_UNSAFE changed 1", output.getvalue())
            self.assertIn("MERGE_FAIL fails 2", output.getvalue())
            self.assertIn("merged 1", output.getvalue())

    def test_apply_requires_prior_scan_file(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            with mock.patch.object(gh_stack_master, "must_gh"), mock.patch.object(
                gh_stack_master, "Path", return_value=missing
            ), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    gh_stack_master.cmd_apply(limit=1)


class MainDispatchTests(unittest.TestCase):
    def test_main_dispatches_apply_limit(self):
        with mock.patch.object(sys, "argv", ["gh_stack_master.py", "apply", "--limit", "4"]), mock.patch.object(
            gh_stack_master, "cmd_apply", return_value=23
        ) as apply:
            result = gh_stack_master.main()

        self.assertEqual(result, 23)
        apply.assert_called_once_with(4)


if __name__ == "__main__":
    unittest.main()
