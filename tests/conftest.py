import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def tmp_log_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
        f.write("[INFO] Server started\n")
        f.write("[ERROR] Connection refused: database is down\n")
        f.write("Traceback (most recent call last):\n")
        f.write('  File "app.py", line 10, in <module>\n')
        f.write("    import pandas\n")
        f.write("ModuleNotFoundError: No module named 'pandas'\n")
        f.write("[WARN] Retrying in 5s\n")
        path = f.name
    yield Path(path)
    os.unlink(path)


@pytest.fixture
def tmp_log_folder():
    folder = Path(tempfile.mkdtemp())
    (folder / "server.log").write_text(
        "[ERROR] DB connection timeout\n", encoding="utf-8"
    )
    (folder / "crash.err").write_text(
        "FATAL: out of memory\n", encoding="utf-8"
    )
    (folder / "access.log").write_text(
        "GET / 200 OK\n", encoding="utf-8"
    )
    yield folder
    import shutil
    shutil.rmtree(str(folder), ignore_errors=True)


@pytest.fixture
def tmp_git_repo():
    repo_dir = Path(tempfile.mkdtemp())
    import subprocess
    subprocess.run(["git", "init"], cwd=str(repo_dir), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo_dir), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo_dir), capture_output=True)
    (repo_dir / "test.txt").write_text("hello world\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(repo_dir), capture_output=True)
    yield repo_dir
    import shutil
    shutil.rmtree(str(repo_dir), ignore_errors=True)
