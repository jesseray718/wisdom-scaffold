import contextlib
import importlib.util
import io
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


stack_recreate = load_script("stack_recreate_under_test", "scripts/stack_recreate.py")


def completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class RunAndStatusTests(unittest.TestCase):
    def test_run_captures_text_output_in_requested_directory(self):
        with mock.patch.object(stack_recreate.subprocess, "run", return_value=completed()) as run:
            result = stack_recreate.run(["git", "status"], cwd=Path("/tmp/repo"))

        self.assertEqual(result.returncode, 0)
        run.assert_called_once_with(
            ["git", "status"], cwd="/tmp/repo", text=True, capture_output=True
        )

    def test_status_reports_repositories_and_missing_git_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wisdom = root / "wisdom"
            openroot = root / "openroot"
            une = root / "une"
            recovery = root / "recovery"
            (wisdom / ".git").mkdir(parents=True)
            (openroot / ".git").mkdir(parents=True)

            def fake_run(args, cwd=None):
                if args[1:3] == ["rev-parse", "--abbrev-ref"]:
                    return completed(stdout="main\n")
                if args[1:3] == ["log", "-1"]:
                    return completed(stdout="abc123 message\n")
                return completed(stdout="## main...origin/main\n")

            with mock.patch.multiple(
                stack_recreate,
                WISDOM=wisdom,
                OPENROOT=openroot,
                UNE=une,
                RECOVERY=recovery,
            ), mock.patch.object(
                stack_recreate, "run", side_effect=fake_run
            ) as run, contextlib.redirect_stdout(io.StringIO()) as output:
                result = stack_recreate.cmd_status()

            self.assertEqual(result, 0)
            self.assertEqual(run.call_count, 6)
            self.assertIn("wisdom-scaffold " + str(wisdom), output.getvalue())
            self.assertIn("NO_GIT", output.getvalue())
            self.assertTrue(output.getvalue().rstrip().endswith("DONE_STATUS"))


class IgnoreDraftTests(unittest.TestCase):
    def test_write_ignore_draft_creates_expected_file(self):
        with tempfile.TemporaryDirectory() as directory:
            census = Path(directory) / "nested" / "census"
            with mock.patch.object(stack_recreate, "CENSUS", census), contextlib.redirect_stdout(
                io.StringIO()
            ):
                result = stack_recreate.cmd_write_ignore_draft()

            self.assertEqual(result, 0)
            lines = (census / "gitignore.draft").read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, ["# draft"] + stack_recreate.IGNORE_LINES)


class RecreateCommandTests(unittest.TestCase):
    def test_recreate_clones_each_remote_and_builds_support_files(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "stack"

            def fake_clone(args, cwd=None):
                target = Path(args[-1])
                target.mkdir(parents=True)
                if target.name == "wisdom-scaffold":
                    (target / ".gitignore").write_text("existing-rule\n", encoding="utf-8")
                elif target.name == "openroot":
                    (target / ".gitignore").write_text("*.sqlite\nkeep-me\n", encoding="utf-8")
                return completed()

            with mock.patch.object(
                stack_recreate, "run", side_effect=fake_clone
            ) as run, contextlib.redirect_stdout(io.StringIO()):
                result = stack_recreate.cmd_recreate(dest)

            self.assertEqual(result, 0)
            self.assertEqual(run.call_count, len(stack_recreate.REMOTES))
            for name, url in stack_recreate.REMOTES.items():
                self.assertIn(
                    mock.call(["git", "clone", "--depth", "1", url, str(dest / name)]),
                    run.call_args_list,
                )
            wisdom_ignore = (dest / "wisdom-scaffold" / ".gitignore").read_text(encoding="utf-8")
            self.assertTrue(wisdom_ignore.startswith("existing-rule\n"))
            self.assertIn("data/tidbit.sqlite*\n", wisdom_ignore)
            self.assertEqual(
                (dest / "openroot" / ".gitignore").read_text(encoding="utf-8"),
                "*.sqlite\nkeep-me\n",
            )
            self.assertEqual(
                (dest / "une" / ".gitignore").read_text(encoding="utf-8"),
                "\n".join(stack_recreate.IGNORE_LINES) + "\n",
            )
            self.assertIn("Three remotes. Not one repo.", (dest / "STACK.txt").read_text())

    def test_recreate_skips_existing_target_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            existing = dest / "wisdom-scaffold"
            existing.mkdir()
            marker = existing / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")

            def fake_clone(args, cwd=None):
                Path(args[-1]).mkdir()
                return completed()

            with mock.patch.object(
                stack_recreate, "run", side_effect=fake_clone
            ) as run, contextlib.redirect_stdout(io.StringIO()) as output:
                stack_recreate.cmd_recreate(dest)

            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
            cloned_targets = [Path(call.args[0][-1]).name for call in run.call_args_list]
            self.assertNotIn("wisdom-scaffold", cloned_targets)
            self.assertIn("EXISTS " + str(existing), output.getvalue())

    def test_recreate_stops_on_clone_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "stack"
            with mock.patch.object(
                stack_recreate, "run", return_value=completed(1, stderr="network error")
            ) as run, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    stack_recreate.cmd_recreate(dest)

            self.assertEqual(raised.exception.code, 1)
            self.assertEqual(run.call_count, 1)
            self.assertFalse((dest / "STACK.txt").exists())


class CommitSelfCommandTests(unittest.TestCase):
    def test_commit_self_copies_script_switches_branch_and_commits_only_self(self):
        with tempfile.TemporaryDirectory() as directory:
            wisdom = Path(directory) / "wisdom"
            (wisdom / ".git").mkdir(parents=True)

            def fake_run(args, cwd=None):
                if args[1:3] == ["rev-parse", "--abbrev-ref"]:
                    return completed(stdout="main\n")
                if args[:3] == ["git", "diff", "--cached"]:
                    return completed(stdout=str(stack_recreate.SELF_REL) + "\n")
                return completed(stdout="ok\n")

            with mock.patch.object(stack_recreate, "WISDOM", wisdom), mock.patch.object(
                stack_recreate, "run", side_effect=fake_run
            ) as run, contextlib.redirect_stdout(io.StringIO()):
                result = stack_recreate.cmd_commit_self()

            self.assertEqual(result, 0)
            copied = wisdom / stack_recreate.SELF_REL
            self.assertEqual(
                copied.read_text(encoding="utf-8"),
                (REPO_ROOT / stack_recreate.SELF_REL).read_text(encoding="utf-8"),
            )
            self.assertIn(
                mock.call(["git", "checkout", "-B", stack_recreate.BRANCH], cwd=wisdom),
                run.call_args_list,
            )
            self.assertIn(
                mock.call(
                    [
                        "git",
                        "commit",
                        "-m",
                        "feat(stack): add recreatable three-remote helper (no add -A)",
                    ],
                    cwd=wisdom,
                ),
                run.call_args_list,
            )

    def test_commit_self_refuses_unrelated_staged_files_and_resets_index(self):
        with tempfile.TemporaryDirectory() as directory:
            wisdom = Path(directory)
            (wisdom / ".git").mkdir()

            def fake_run(args, cwd=None):
                if args[1:3] == ["rev-parse", "--abbrev-ref"]:
                    return completed(stdout=stack_recreate.BRANCH + "\n")
                if args[:3] == ["git", "diff", "--cached"]:
                    return completed(stdout=str(stack_recreate.SELF_REL) + "\nsecrets.db\n")
                return completed()

            with mock.patch.object(stack_recreate, "WISDOM", wisdom), mock.patch.object(
                stack_recreate, "run", side_effect=fake_run
            ) as run, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    stack_recreate.cmd_commit_self()

            self.assertIn(mock.call(["git", "reset", "HEAD"], cwd=wisdom), run.call_args_list)
            self.assertFalse(any(call.args[0][1] == "commit" for call in run.call_args_list))

    def test_commit_self_returns_without_commit_when_nothing_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            wisdom = Path(directory)
            (wisdom / ".git").mkdir()

            def fake_run(args, cwd=None):
                if args[1:3] == ["rev-parse", "--abbrev-ref"]:
                    return completed(stdout=stack_recreate.BRANCH + "\n")
                return completed(stdout="")

            with mock.patch.object(stack_recreate, "WISDOM", wisdom), mock.patch.object(
                stack_recreate, "run", side_effect=fake_run
            ) as run, contextlib.redirect_stdout(io.StringIO()) as output:
                result = stack_recreate.cmd_commit_self()

            self.assertEqual(result, 0)
            self.assertFalse(any(call.args[0][1] == "commit" for call in run.call_args_list))
            self.assertIn("NOTHING_TO_COMMIT", output.getvalue())

    def test_commit_self_requires_wisdom_git_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(
                stack_recreate, "WISDOM", Path(directory)
            ), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    stack_recreate.cmd_commit_self()


class PushSelfCommandTests(unittest.TestCase):
    def test_push_self_rejects_wrong_branch(self):
        with mock.patch.object(
            stack_recreate, "run", return_value=completed(stdout="main\n")
        ) as run, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                stack_recreate.cmd_push_self()

        self.assertEqual(run.call_count, 1)

    def test_push_self_rejects_dirty_index(self):
        with mock.patch.object(
            stack_recreate,
            "run",
            side_effect=[
                completed(stdout=stack_recreate.BRANCH + "\n"),
                completed(stdout="unexpected.txt\n"),
            ],
        ) as run, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                stack_recreate.cmd_push_self()

        self.assertEqual(run.call_count, 2)

    def test_push_self_pushes_expected_branch_when_index_is_clean(self):
        with mock.patch.object(
            stack_recreate,
            "run",
            side_effect=[
                completed(stdout=stack_recreate.BRANCH + "\n"),
                completed(stdout=""),
                completed(stdout="pushed\n"),
            ],
        ) as run, contextlib.redirect_stdout(io.StringIO()):
            result = stack_recreate.cmd_push_self()

        self.assertEqual(result, 0)
        self.assertEqual(
            run.call_args_list[-1],
            mock.call(
                ["git", "push", "-u", "origin", stack_recreate.BRANCH],
                cwd=stack_recreate.WISDOM,
            ),
        )

    def test_push_self_propagates_push_failure_as_exit(self):
        with mock.patch.object(
            stack_recreate,
            "run",
            side_effect=[
                completed(stdout=stack_recreate.BRANCH + "\n"),
                completed(stdout=""),
                completed(1, stderr="denied"),
            ],
        ), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                stack_recreate.cmd_push_self()


class MainDispatchTests(unittest.TestCase):
    def test_main_converts_recreate_destination_to_path(self):
        with mock.patch.object(
            sys, "argv", ["stack_recreate.py", "recreate", "--dest", "/tmp/target"]
        ), mock.patch.object(stack_recreate, "cmd_recreate", return_value=19) as recreate:
            result = stack_recreate.main()

        self.assertEqual(result, 19)
        recreate.assert_called_once_with(Path("/tmp/target"))


if __name__ == "__main__":
    unittest.main()
