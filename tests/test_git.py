"""Tests for mcp_git.py — all 18 git tools mocked with @patch('mcp_git.git.Repo')."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock, call
from git.exc import BadName, GitCommandError
from datetime import datetime

from mcp_git import (
    git_status, git_diff_unstaged, git_diff_staged, git_diff,
    git_commit, git_add, git_reset, git_log,
    git_create_branch, git_checkout, git_show, git_branch,
    git_stash, git_merge, git_rebase, git_clone,
    git_tag, git_blame, _reject_flag,
)

# ── Existing _reject_flag tests ──────────────────────────────────────────

class TestRejectFlag:
    def test_rejects_dash_prefix(self):
        with pytest.raises(BadName):
            _reject_flag("--dangerous", "flag")

    def test_rejects_single_dash(self):
        with pytest.raises(BadName):
            _reject_flag("-rf", "flag")

    def test_allows_normal_value(self):
        _reject_flag("main", "branch")  # should not raise

    def test_allows_none(self):
        _reject_flag(None, "param")  # should not raise

    def test_allows_empty(self):
        _reject_flag("", "param")  # should not raise

# ── Helper ───────────────────────────────────────────────────────────────

def _make_commit_mock(**kwargs):
    c = MagicMock()
    c.hexsha = kwargs.get("hexsha", "a1b2c3d4e5f6")
    c.author = kwargs.get("author", "Test User <test@test.com>")
    c.authored_datetime = kwargs.get("authored_datetime", datetime(2024, 6, 1, 12, 0, 0))
    c.message = kwargs.get("message", "Test commit\n")
    c.parents = kwargs.get("parents", [])
    return c

def _make_diff_entry_mock(a_path="file.py", b_path="file.py", diff=b"@@ -1 +1 @@\n-old\n+new"):
    d = MagicMock()
    d.a_path = a_path
    d.b_path = b_path
    d.diff = diff
    return d

# ── 1. git_status ────────────────────────────────────────────────────────

class TestGitStatus:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_basic(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.status.return_value = "On branch main\nnothing to commit"
        mock_repo.active_branch.name = "main"

        result = await git_status("/fake/path")

        assert "Branch: main" in result
        assert "nothing to commit" in result
        mock_repo.git.status.assert_called_once()

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_dirty_status(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.status.return_value = "On branch feature\nChanges not staged for commit:\n  modified: foo.py"
        mock_repo.active_branch.name = "feature"

        result = await git_status("/fake/path")

        assert "Branch: feature" in result
        assert "modified: foo.py" in result

# ── 2. git_diff_unstaged ─────────────────────────────────────────────────

class TestGitDiffUnstaged:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_basic(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.diff.return_value = "diff --git a/f.py b/f.py\nindex abc..def 100644"

        result = await git_diff_unstaged("/fake/path")

        assert "Unstaged changes:" in result
        assert "diff --git" in result
        mock_repo.git.diff.assert_called_once_with("--unified=3")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_custom_context(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.diff.return_value = "diff"

        result = await git_diff_unstaged("/fake/path", context_lines=10)

        assert "Unstaged changes:" in result
        mock_repo.git.diff.assert_called_once_with("--unified=10")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_empty(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.diff.return_value = ""

        result = await git_diff_unstaged("/fake/path")

        assert "Unstaged changes:" in result

# ── 3. git_diff_staged ───────────────────────────────────────────────────

class TestGitDiffStaged:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_basic(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.diff.return_value = "diff --git a/f.py b/f.py"

        result = await git_diff_staged("/fake/path")

        assert "Staged changes:" in result
        mock_repo.git.diff.assert_called_once_with("--unified=3", "--cached")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_custom_context(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.diff.return_value = "diff"

        result = await git_diff_staged("/fake/path", context_lines=1)

        assert "Staged changes:" in result
        mock_repo.git.diff.assert_called_once_with("--unified=1", "--cached")

# ── 4. git_diff ──────────────────────────────────────────────────────────

class TestGitDiff:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_basic(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.diff.return_value = "diff --git a/f.py b/f.py"

        result = await git_diff("/fake/path", "main")

        assert "Diff with main:" in result
        mock_repo.rev_parse.assert_called_once_with("main")
        mock_repo.git.diff.assert_called_once_with("--unified=3", "main")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_flag(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_diff("/fake/path", "-bad")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_rev_parse_fails(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.rev_parse.side_effect = BadName("invalid ref")

        with pytest.raises(BadName):
            await git_diff("/fake/path", "nonexistent")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_custom_context(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.diff.return_value = "diff"

        result = await git_diff("/fake/path", "topic", context_lines=5)

        assert "Diff with topic:" in result
        mock_repo.git.diff.assert_called_once_with("--unified=5", "topic")

# ── 5. git_commit ────────────────────────────────────────────────────────

class TestGitCommit:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_basic(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_commit = _make_commit_mock()
        mock_repo.index.commit.return_value = mock_commit

        result = await git_commit("/fake/path", "fix: oops")

        assert "a1b2c3d" in result
        mock_repo.index.commit.assert_called_once_with("fix: oops")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_all_flag_adds_all(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_commit = _make_commit_mock()
        mock_repo.index.commit.return_value = mock_commit

        result = await git_commit("/fake/path", "mass change", all=True)

        assert "a1b2c3d" in result
        mock_repo.git.add.assert_called_once_with(".")
        mock_repo.index.commit.assert_called_once_with("mass change")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_all_false_does_not_add(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_commit = _make_commit_mock()
        mock_repo.index.commit.return_value = mock_commit

        result = await git_commit("/fake/path", "msg", all=False)

        assert "a1b2c3d" in result
        mock_repo.git.add.assert_not_called()

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_propagates_git_error(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.index.commit.side_effect = GitCommandError("commit", "nothing to commit")

        with pytest.raises(GitCommandError):
            await git_commit("/fake/path", "msg")

# ── 6. git_add ───────────────────────────────────────────────────────────

class TestGitAdd:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_all_files_dot(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_add("/fake/path", ["."])

        assert "Files staged" in result
        mock_repo.git.add.assert_called_once_with(".")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_specific_files(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_add("/fake/path", ["a.txt", "b.txt"])

        assert "Files staged" in result
        mock_repo.git.add.assert_called_once_with("--", "a.txt", "b.txt")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_single_file(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_add("/fake/path", ["foo.py"])

        assert "Files staged" in result
        mock_repo.git.add.assert_called_once_with("--", "foo.py")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_propagates_git_error(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.add.side_effect = GitCommandError("add", "fatal: pathspec 'x' did not match")

        with pytest.raises(GitCommandError):
            await git_add("/fake/path", ["x"])

# ── 7. git_reset ─────────────────────────────────────────────────────────

class TestGitReset:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_mixed_default(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_reset("/fake/path")

        assert "Reset mixed to HEAD" in result
        mock_repo.git.reset.assert_called_once_with("HEAD")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_soft(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_reset("/fake/path", mode="soft")

        assert "Reset soft to HEAD" in result
        mock_repo.git.reset.assert_called_once_with("--soft", "HEAD")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_hard(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_reset("/fake/path", mode="hard")

        assert "Reset hard to HEAD" in result
        mock_repo.git.reset.assert_called_once_with("--hard", "HEAD")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_custom_target(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_reset("/fake/path", mode="hard", target="abc123")

        assert "Reset hard to abc123" in result
        mock_repo.git.reset.assert_called_once_with("--hard", "abc123")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_flag(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_reset("/fake/path", target="-bad")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_propagates_git_error(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.reset.side_effect = GitCommandError("reset", "failed")

        with pytest.raises(GitCommandError):
            await git_reset("/fake/path", mode="hard")

# ── 8. git_log ───────────────────────────────────────────────────────────

class TestGitLog:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_basic(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.log.return_value = (
            "abc1234|Alice|alice@test.com|2024-06-01 12:00:00|Initial commit\n"
            "def5678|Bob|bob@test.com|2024-06-02 13:00:00|Second commit"
        )

        result = await git_log("/fake/path")

        assert "Commit history (10):" in result
        assert "abc1234" in result
        assert "def5678" in result
        assert "Alice" in result
        mock_repo.git.log.assert_called_once_with(
            "--max-count=10", "--format=%H|%an|%ae|%ad|%s", "--date=iso"
        )

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_all_filters(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.log.return_value = "abc1234|A|a@t.com|2024-06-01 12:00:00|work"

        result = await git_log(
            "/fake/path", max_count=5,
            start_timestamp="2024-01-01", end_timestamp="2024-12-31",
            branch="main", author="Alice"
        )

        assert "Commit history (5):" in result
        mock_repo.git.log.assert_called_once_with(
            "--max-count=5", "--format=%H|%an|%ae|%ad|%s", "--date=iso",
            "--since", "2024-01-01", "--until", "2024-12-31",
            "main", "--author", "Alice"
        )

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_empty(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.log.return_value = ""

        result = await git_log("/fake/path")

        assert result == "(no commits found)"

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_whitespace_only(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.log.return_value = "   \n  \n"

        result = await git_log("/fake/path")

        assert result == "(no commits found)"

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_start_timestamp(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_log("/fake/path", start_timestamp="-malicious")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_end_timestamp(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_log("/fake/path", end_timestamp="-evil")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_malformed_line(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.log.return_value = "short\nabc1234|A|a@t.com|2024-06-01|valid"

        result = await git_log("/fake/path", max_count=2)

        assert "short" in result
        assert "valid" in result

# ── 9. git_create_branch ─────────────────────────────────────────────────

class TestGitCreateBranch:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_without_base(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.active_branch.name = "main"

        result = await git_create_branch("/fake/path", "feature")

        assert "Created branch 'feature'" in result
        assert "main" in result
        mock_repo.create_head.assert_called_once_with("feature", mock_repo.active_branch)

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_with_base(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_base = MagicMock()
        mock_base.name = "develop"
        mock_repo.references = {"develop": mock_base}

        result = await git_create_branch("/fake/path", "feature", base_branch="develop")

        assert "Created branch 'feature'" in result
        assert "develop" in result
        mock_repo.create_head.assert_called_once_with("feature", mock_base)

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_branch_name(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_create_branch("/fake/path", "-bad")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_base_branch(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_create_branch("/fake/path", "good", base_branch="-bad")

# ── 10. git_checkout ─────────────────────────────────────────────────────

class TestGitCheckout:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_basic(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_checkout("/fake/path", "main")

        assert "Switched to branch 'main'" in result
        mock_repo.rev_parse.assert_called_once_with("main")
        mock_repo.git.checkout.assert_called_once_with("main")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_create(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_checkout("/fake/path", "new-branch", create=True)

        assert "Created and switched to branch 'new-branch'" in result
        mock_repo.git.checkout.assert_called_once_with("-b", "new-branch")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_flag(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_checkout("/fake/path", "-bad")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_rev_parse_fails(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.rev_parse.side_effect = BadName("unknown")

        with pytest.raises(BadName):
            await git_checkout("/fake/path", "does-not-exist")

# ── 11. git_show ─────────────────────────────────────────────────────────

class TestGitShow:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_with_parents(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_parent = _make_commit_mock(hexsha="parent000")
        mock_commit = _make_commit_mock(parents=[mock_parent])
        mock_repo.commit.return_value = mock_commit
        diff_entry = _make_diff_entry_mock(diff=b"@@ -1 +1 @@\n-old\n+new")
        mock_parent.diff.return_value = [diff_entry]

        result = await git_show("/fake/path", "HEAD")

        assert "Commit: a1b2c3d" in result
        assert "'Test User <test@test.com>'" in result
        assert "Test commit" in result
        assert "--- file.py" in result
        assert "+++ file.py" in result
        assert "+new" in result
        mock_repo.commit.assert_called_once_with("HEAD")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_initial_commit(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        import git
        mock_commit = _make_commit_mock(parents=[])
        mock_repo.commit.return_value = mock_commit
        diff_entry = _make_diff_entry_mock(diff=b"@@ -0,0 +1 @@\n+new file")
        mock_commit.diff.return_value = [diff_entry]

        result = await git_show("/fake/path", "abc123")

        assert "Commit: a1b2c3d" in result
        assert "new file" in result
        mock_commit.diff.assert_called_once_with(git.NULL_TREE, create_patch=True)

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_diff_string_content(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_commit = _make_commit_mock(parents=[])
        mock_repo.commit.return_value = mock_commit
        diff_entry = _make_diff_entry_mock(diff="string diff (not bytes)")
        mock_commit.diff.return_value = [diff_entry]

        result = await git_show("/fake/path", "abc123")

        assert "string diff (not bytes)" in result

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_diff_no_content(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_commit = _make_commit_mock(parents=[])
        mock_repo.commit.return_value = mock_commit
        diff_entry = _make_diff_entry_mock(diff=None)
        mock_commit.diff.return_value = [diff_entry]

        result = await git_show("/fake/path", "abc123")

        assert "--- file.py" in result
        assert "+++ file.py" in result

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_flag(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_show("/fake/path", "-bad")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_trim_diff(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_commit = _make_commit_mock(parents=[])
        mock_repo.commit.return_value = mock_commit
        long_diff = b"x" * 60000
        diff_entry = _make_diff_entry_mock(diff=long_diff)
        mock_commit.diff.return_value = [diff_entry]

        result = await git_show("/fake/path", "abc123")

        assert "[...diff truncated at 50000 chars]" in result
        assert len(result) < 55000

# ── 12. git_branch ───────────────────────────────────────────────────────

class TestGitBranch:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_local(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.branch.return_value = "* main\n  feature"

        result = await git_branch("/fake/path", branch_type="local")

        assert "Branches (local):" in result
        assert "* main" in result
        mock_repo.git.branch.assert_called_once_with()

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_remote(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.branch.return_value = "  origin/main"

        result = await git_branch("/fake/path", branch_type="remote")

        assert "Branches (remote):" in result
        assert "origin/main" in result
        mock_repo.git.branch.assert_called_once_with("-r")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_all(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.branch.return_value = "* main\n  feature\n  remotes/origin/main"

        result = await git_branch("/fake/path", branch_type="all")

        assert "Branches (all):" in result
        mock_repo.git.branch.assert_called_once_with("-a")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_invalid_type(self, mock_repo_class):
        result = await git_branch("/fake/path", branch_type="bogus")

        assert "Invalid branch type: bogus" in result

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_contains_filter(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.branch.return_value = "* main"

        result = await git_branch("/fake/path", contains="main")

        assert "Branches (local):" in result
        mock_repo.git.branch.assert_called_once_with("--contains", "main")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_not_contains_filter(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.branch.return_value = "* main"

        result = await git_branch("/fake/path", not_contains="stale")

        assert "Branches (local):" in result
        mock_repo.git.branch.assert_called_once_with("--no-contains", "stale")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_contains(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_branch("/fake/path", contains="-bad")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_not_contains(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_branch("/fake/path", not_contains="-bad")

# ── 13. git_stash ────────────────────────────────────────────────────────

class TestGitStash:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_push(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_stash("/fake/path", action="push")

        assert result == "Changes stashed"
        mock_repo.git.stash.assert_called_once_with("push")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_push_with_message(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_stash("/fake/path", action="push", message="WIP: foo")

        assert result == "Changes stashed"
        mock_repo.git.stash.assert_called_once_with("push", "-m", "WIP: foo")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_pop(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_stash("/fake/path", action="pop")

        assert "applied and removed" in result
        mock_repo.git.stash.assert_called_once_with("pop")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_apply(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_stash("/fake/path", action="apply")

        assert "applied (kept in stash)" in result
        mock_repo.git.stash.assert_called_once_with("apply")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_drop(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_stash("/fake/path", action="drop")

        assert "dropped" in result
        mock_repo.git.stash.assert_called_once_with("drop")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_list(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.stash.return_value = "stash@{0}: WIP on main: abc1234 fix"

        result = await git_stash("/fake/path", action="list")

        assert "stash@{0}" in result
        mock_repo.git.stash.assert_called_once_with("list")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_list_empty(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.stash.return_value = ""

        result = await git_stash("/fake/path", action="list")

        assert result == "(no stashes)"

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_unknown_action(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_stash("/fake/path", action="unknown")

        assert "Unknown action: unknown" in result

# ── 14. git_merge ────────────────────────────────────────────────────────

class TestGitMerge:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_basic(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.active_branch.name = "main"

        result = await git_merge("/fake/path", "feature")

        assert "Merged 'feature' into 'main'" in result
        mock_repo.git.merge.assert_called_once_with("feature")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_ff_only(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.active_branch.name = "main"

        result = await git_merge("/fake/path", "feature", ff_only=True)

        assert "Merged 'feature' into 'main'" in result
        mock_repo.git.merge.assert_called_once_with("--ff-only", "feature")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_squash(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.active_branch.name = "main"

        result = await git_merge("/fake/path", "feature", squash=True)

        assert "Merged 'feature' into 'main'" in result
        mock_repo.git.merge.assert_called_once_with("--squash", "feature")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_ff_only_and_squash(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.active_branch.name = "main"

        result = await git_merge("/fake/path", "feature", ff_only=True, squash=True)

        assert "Merged 'feature' into 'main'" in result
        mock_repo.git.merge.assert_called_once_with("--squash", "--ff-only", "feature")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_conflict(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        err = GitCommandError("merge", "merge failed")
        err.stderr = "CONFLICT (content): Merge conflict in file.py"
        mock_repo.git.merge.side_effect = err

        result = await git_merge("/fake/path", "feature")

        assert "merge conflict" in result
        assert "CONFLICT" in result

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_flag(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_merge("/fake/path", "-bad")

# ── 15. git_rebase ───────────────────────────────────────────────────────

class TestGitRebase:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_basic(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_rebase("/fake/path", "main")

        assert "Rebased onto 'main'" in result
        mock_repo.git.rebase.assert_called_once_with("main")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_interactive(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_rebase("/fake/path", "main", interactive=True)

        assert "Rebased onto 'main'" in result
        mock_repo.git.rebase.assert_called_once_with("-i", "main")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_conflict(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        err = GitCommandError("rebase", "rebase failed")
        err.stderr = " rebase conflict in file.py"
        mock_repo.git.rebase.side_effect = err

        result = await git_rebase("/fake/path", "main")

        assert "rebase conflict" in result
        assert "file.py" in result

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_reject_flag(self, mock_repo_class):
        with pytest.raises(BadName):
            await git_rebase("/fake/path", "-bad")

# ── 16. git_clone ────────────────────────────────────────────────────────

class TestGitClone:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_basic(self, mock_repo_class):
        mock_repo_class.clone_from = MagicMock()

        result = await git_clone("https://github.com/x/y.git", "/tmp/repo")

        assert "Cloned" in result
        mock_repo_class.clone_from.assert_called_once_with(
            "https://github.com/x/y.git", "/tmp/repo",
            branch=None, depth=None
        )

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_with_branch_and_depth(self, mock_repo_class):
        mock_repo_class.clone_from = MagicMock()

        result = await git_clone(
            "https://github.com/x/y.git", "/tmp/repo",
            branch="develop", depth=1
        )

        assert "Cloned" in result
        mock_repo_class.clone_from.assert_called_once_with(
            "https://github.com/x/y.git", "/tmp/repo",
            branch="develop", depth=1
        )

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_failure(self, mock_repo_class):
        err = GitCommandError("clone", "fatal: repository not found")
        err.stderr = "repository not found"
        mock_repo_class.clone_from = MagicMock(side_effect=err)

        result = await git_clone("https://github.com/x/y.git", "/tmp/repo")

        assert "clone failed" in result
        assert "repository not found" in result

# ── 17. git_tag ──────────────────────────────────────────────────────────

class TestGitTag:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_list(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.tag.return_value = "v1.0\nv2.0"

        result = await git_tag("/fake/path", action="list")

        assert "v1.0" in result
        assert "v2.0" in result
        mock_repo.git.tag.assert_called_once_with()

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_list_empty(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.tag.return_value = ""

        result = await git_tag("/fake/path", action="list")

        assert result == "(no tags)"

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_create(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_tag("/fake/path", action="create", tag_name="v1")

        assert "Tag 'v1' created" in result
        mock_repo.git.tag.assert_called_once_with("v1", None, None)

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_create_with_message(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_tag("/fake/path", action="create", tag_name="v1", message="Release v1")

        assert "Tag 'v1' created" in result
        mock_repo.git.tag.assert_called_once_with("v1", "-m", "Release v1")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_create_missing_tag_name(self, mock_repo_class):
        result = await git_tag("/fake/path", action="create")

        assert "tag_name required" in result

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_delete(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value

        result = await git_tag("/fake/path", action="delete", tag_name="v1")

        assert "Tag 'v1' deleted" in result
        mock_repo.git.tag.assert_called_once_with("-d", "v1")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_delete_missing_tag_name(self, mock_repo_class):
        result = await git_tag("/fake/path", action="delete")

        assert "tag_name required" in result

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_unknown_action(self, mock_repo_class):
        result = await git_tag("/fake/path", action="export")

        assert "Unknown action: export" in result

# ── 18. git_blame ────────────────────────────────────────────────────────

class TestGitBlame:
    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_basic(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.blame.return_value = (
            "abc1234 (Author 2024-06-01) 1) line one\n"
            "def5678 (Other  2024-06-02) 2) line two"
        )

        result = await git_blame("/fake/path", "file.py")

        assert "abc1234" in result
        assert "line one" in result
        mock_repo.git.blame.assert_called_once_with("file.py")

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_truncation(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.blame.return_value = "x" * 20000

        result = await git_blame("/fake/path", "long.py")

        assert "[...truncated]" in result
        assert len(result) < 10100

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_no_truncation_under_10k(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        mock_repo.git.blame.return_value = "abc1234 (A 2024-06-01) 1) x"

        result = await git_blame("/fake/path", "short.py")

        assert "[...truncated]" not in result

    @pytest.mark.asyncio
    @patch("mcp_git.git.Repo")
    async def test_file_not_found(self, mock_repo_class):
        mock_repo = mock_repo_class.return_value
        err = GitCommandError("blame", "fatal: cannot exist")
        err.stderr = "fatal: not a known file"
        mock_repo.git.blame.side_effect = err

        result = await git_blame("/fake/path", "missing.py")

        assert "error:" in result
        assert "not a known file" in result
