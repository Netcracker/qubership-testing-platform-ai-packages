"""Clone the test repository into the folder of the local tests, or update that clone.

  update_local_tests.py [--path FOLDER] [--repo URL] [--branch BRANCH]

The folder is --path, or else LOCAL_ROOT_FOLDER of the config. A folder that is missing or
empty gets a clone. A clone of the same repository is updated by a fast-forward only:
nothing is merged, rebased, stashed, or discarded, so local work is never lost. Another
branch is checked out only when --branch names it.

The repository and the branch come from --repo and --branch, or else from
ATP_TESTS_GIT_REPO_URL and ATP_TESTS_GIT_REPO_BRANCH in "variables" of
.atp-assistant/config.json, as for the list of tests. A clone is made over http or https.
The token comes from the environment variable GITLAB_TOKEN (the config key
GITLAB_TOKEN_ENV names another variable) or the first line of
.atp-assistant/gitlab-token. git gets it from the environment, as a header for the host of
the repository, so it is in no command line, URL, or file. It is never printed.

After the clone or the update, the folder is checked as set_local_folder.py does, and a
folder given by --path is written to LOCAL_ROOT_FOLDER.

The output is Markdown, and the agent shows it as written. Exit codes: 0 for a folder that
is up to date; 1 for an error, described by one JSON object on stderr; 2 for a wrong
command line. Error codes: config_missing, config_unreadable, config_unwritable,
repo_missing, repo_url_invalid, invalid_value, local_root_missing, local_root_invalid (with
"problems"), local_root_not_a_clone, local_root_other_repo, branch_differs,
branch_missing, local_changes (with "files"), local_diverged, git_missing, git_timeout,
git_failed. Needs git 2.31 or later. Python 3.9+, standard library only.
"""

import argparse
import base64
import functools
import importlib
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "atp-common" / "scripts"))
common = importlib.import_module("atp_common")

GIT_TIMEOUT = 600
SHOWN_FILES = 10
URL_USER = re.compile(r"(\w+://)[^/\s@]+@")


def parse_arguments(argv=None):
    """Return the parsed command line; exit with 2 on a wrong one."""
    parser = argparse.ArgumentParser(description="Clone or update the local copy of the test repository.")
    parser.add_argument("--path", help="the folder of the local tests; the default is LOCAL_ROOT_FOLDER")
    parser.add_argument("--repo", help="URL of the test repository; overrides the config")
    parser.add_argument("--branch", help="branch to check out and update; overrides the config")
    args = parser.parse_args(argv)
    if args.path is not None and not args.path.strip():
        parser.error("--path must not be empty")
    if args.branch is not None and (not args.branch.strip() or args.branch.strip().startswith("-")):
        parser.error("--branch must be a branch name")
    return args


def git_environment(token, base):
    """Return the environment of git: no prompts, and the token as a header for base only."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    if token:
        index = int(env.get("GIT_CONFIG_COUNT") or 0)
        secret = base64.b64encode(f"oauth2:{token}".encode()).decode("ascii")
        env[f"GIT_CONFIG_KEY_{index}"] = f"http.{base}/.extraHeader"
        env[f"GIT_CONFIG_VALUE_{index}"] = f"Authorization: Basic {secret}"
        env["GIT_CONFIG_COUNT"] = str(index + 1)
    return env


def run_git(env, *args, folder=None):
    """Return the output of a git command, run in folder when given, or fail."""
    command = ["git", *(["-C", str(folder)] if folder else []), *args]
    try:
        done = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except FileNotFoundError:
        common.fail("git_missing", "git is not installed or not in PATH.")
    except subprocess.TimeoutExpired:
        common.fail("git_timeout", f"git {args[0]} did not finish in {GIT_TIMEOUT} s.")
    if done.returncode != 0:
        reason = URL_USER.sub(r"\1", done.stderr.strip())[-600:]
        common.fail("git_failed", f"git {args[0]} failed: {reason}")
    return done.stdout.rstrip()


def repository_identity(url):
    """Return host/path of a repository URL in lower case, whatever its scheme or user."""
    text = url.strip()
    match = common.SCP_URL.fullmatch(text)
    if match:
        host, path = match.groups()
    else:
        parts = urllib.parse.urlsplit(text)
        host, path = parts.hostname or "", parts.path
    path = path.strip("/").removesuffix(".git").strip("/")
    return f"{host}/{path}".lower()


def require_clean(git, root):
    """Fail when a tracked file of the clone has a change that is not committed."""
    files = [line[3:] for line in git("status", "--porcelain", "--untracked-files=no").splitlines()]
    if files:
        shown = ", ".join(files[:SHOWN_FILES]) + (", ..." if len(files) > SHOWN_FILES else "")
        message = f"{root} has changes that are not committed: {shown}. Nothing was updated."
        common.fail("local_changes", message, files=files)


def choose_branch(git, root, branch, explicit):
    """Return the checked out branch and the branch to update, or fail.

    branch is the one asked for, and "" means the checked out one. A branch of the config,
    where explicit is false, never replaces the checked out branch.
    """
    current = git("branch", "--show-current")
    target = branch or current
    if not target:
        common.fail("branch_differs", f"{root} has no branch checked out. Name one with --branch.")
    if current != target and not explicit:
        where = f"branch {current}" if current else "no branch"
        message = f"{root} has {where} checked out, and the config names {target}. Nothing was updated."
        common.fail("branch_differs", f"{message} Name the branch to update with --branch.")
    return current, target


def require_same_repository(git, root, repo):
    """Fail when the origin of the clone in root is not the repository."""
    origin = git("remote", "get-url", "origin")
    if repository_identity(origin) != repository_identity(repo):
        shown = URL_USER.sub(r"\1", origin)
        common.fail("local_root_other_repo", f"{root} is a clone of {shown}, not of the test repository.")


def describe_update(root, branch, head, ahead, behind):
    """Return the sentence that says what an update did; ahead and behind count commits."""
    if behind:
        commits = f"{behind} new commit{'s' if behind != 1 else ''}"
        return f"Updated `{root}`, branch {branch}: {commits}, now at {head}."
    extra = f", and has {ahead} that the repository does not" if ahead else ""
    return f"`{root}`, branch {branch}, has every commit of the repository{extra}. It is at {head}."


def update(git, root, repo, branch, explicit):
    """Fast-forward the clone in root to the branch of its origin and return what was done."""
    require_same_repository(git, root, repo)
    current, target = choose_branch(git, root, branch, explicit)
    git("fetch", "--quiet", "origin")
    upstream = f"refs/remotes/origin/{target}"
    if not git("for-each-ref", "--format=%(refname)", upstream):
        common.fail("branch_missing", f"The test repository has no branch {target}. Nothing was updated.")
    switched = ""
    if current != target:
        require_clean(git, root)
        git("switch", "--quiet", target)
        switched = f"Checked out branch {target} instead of {current or 'a commit'}. "
    ahead, behind = (int(count) for count in git("rev-list", "--left-right", "--count", f"HEAD...{upstream}").split())
    if ahead and behind:
        message = f"{switched}Branch {target} of {root} and of the repository have both changed"
        common.fail("local_diverged", f"{message}: {ahead} local and {behind} new commits. Nothing was updated.")
    if behind:
        require_clean(git, root)
        git("merge", "--quiet", "--ff-only", upstream)
    return switched + describe_update(root, target, git("rev-parse", "--short", "HEAD"), ahead, behind)


def clone(git, root, url, branch):
    """Clone the repository into root, a missing or empty folder, and return what was done."""
    options = ["--branch", branch] if branch else []
    git("clone", "--quiet", *options, "--", url, str(root))
    here = functools.partial(git, folder=root)
    name, head = here("branch", "--show-current"), here("rev-parse", "--short", "HEAD")
    return f"Cloned {url} into `{root}`, branch {name or branch}, at {head}."


def synchronize(config, root, repo, branch, explicit):
    """Clone the repository into root, or update the clone there, and return what was done."""
    base, project = common.split_repo_url(repo, config.get("GITLAB_URL"))
    git = functools.partial(run_git, git_environment(common.read_token(config), base))
    if not root.exists() or (root.is_dir() and not any(root.iterdir())):
        return clone(git, root, f"{base}/{project}.git", branch)
    if not (root / ".git").exists():
        message = f"{root} is not empty and is not a clone of a repository. Nothing was changed."
        common.fail("local_root_not_a_clone", f"{message} Give an empty or a new folder.")
    return update(functools.partial(git, folder=root), root, repo, branch, explicit)


def save_root(config, root):
    """Write root to LOCAL_ROOT_FOLDER and return the lines that say so, none without a change."""
    config_file = config["CONFIG_FILE"]
    if common.write_setting(Path(config_file), common.LOCAL_ROOT_KEY, str(root)) == str(root):
        return []
    return [f"Set {common.LOCAL_ROOT_KEY} to `{root}` in {config_file}."]


def main():
    """Clone or update the folder of the local tests, check it, and print what was done."""
    args = parse_arguments()
    common.use_utf8_output()
    config = common.load_config_for_local_root()
    repo, branch = common.test_source(args, config)
    root = common.absolute_path(args.path.strip()) if args.path else common.local_root(config)
    done = synchronize(config, root, repo, branch, args.branch is not None)
    contents = common.read_local_root(root, config)
    if contents.problems:
        message = " ".join([done, "The folder cannot hold the local tests.", *contents.problems])
        unchanged = f"{common.LOCAL_ROOT_KEY} was not changed."
        common.fail("local_root_invalid", f"{message} {unchanged}", problems=contents.problems)
    saved = save_root(config, root) if args.path else []
    print("\n".join([done, *saved, "", *common.describe_local_root(contents, config)]))


if __name__ == "__main__":
    main()
