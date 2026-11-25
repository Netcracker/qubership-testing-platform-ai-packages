"""List the Playwright test files (*.ts) of the project's test repository, sorted by name.

The tests live under TestGeneration/tests/TestScenario of the repository. The script reads
the folder tree from the GitLab API in one paginated request, keeps the *.ts files, applies
the filters, and prints a nested Markdown list, or a table with --format table. The agent
shows that output as written.

The repository and the branch come from --repo and --branch, or else from
ATP_TESTS_GIT_REPO_URL and ATP_TESTS_GIT_REPO_BRANCH in the variables file that
GENERATE_VARIABLES_FILE names in .tdm-assistant/config.json. The file branch counts only
when the repository comes from the file too; with --repo and no --branch the script reads
the default branch. The token comes from the environment variable GITLAB_TOKEN (the config
key GITLAB_TOKEN_ENV names another variable) or the first line of
.tdm-assistant/gitlab-token. Without a token the request is anonymous. The token is never
printed.

Filters:
  --folder NAME   Only the tests in the folders called NAME, at any depth under
                  TestScenario, with their subfolders. The match ignores case.
  --under PATH    Only the tests in PATH, counted from TestScenario (Name or A/B).
  --name TEXT     Only files whose name contains TEXT, ignoring case. TEXT with * or ?
                  is a mask for the whole name.

Exit codes: 0 for a result, also an empty one; 1 for an error, described by one JSON
object on stderr; 2 for a wrong command line. Python 3.9+, standard library only.
"""

import argparse
import fnmatch
import importlib
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "atp-tests-common" / "scripts"))
common = importlib.import_module("atp_tests_common")

TESTS_ROOT = "TestGeneration/tests/TestScenario"
TEST_SUFFIX = ".ts"
ROOT_LABEL = "TestScenario"
REPO_KEY = "ATP_TESTS_GIT_REPO_URL"
BRANCH_KEY = "ATP_TESTS_GIT_REPO_BRANCH"


def parse_arguments(argv=None):
    """Return the parsed command line; exit with 2 on a wrong one."""
    parser = argparse.ArgumentParser(description="List the test files of the test repository.")
    parser.add_argument("--repo", help="URL of the test repository; overrides the variables file")
    parser.add_argument("--branch", help="branch to read; overrides the variables file")
    parser.add_argument("--folder", help="name of a folder, at any depth under TestScenario")
    parser.add_argument("--under", help="path of a folder, counted from TestScenario")
    parser.add_argument("--name", help="part of a filename, or a mask with * and ?")
    parser.add_argument("--format", choices=("tree", "table"), default="tree", help="tree (default) or table")
    args = parser.parse_args(argv)
    if args.folder and args.under:
        parser.error("use either --folder or --under, not both")
    if args.folder and "/" in args.folder.strip("/"):
        parser.error("--folder takes one folder name; give a path with --under")
    return args


def collect(items):
    """Return the folders and the test files of a tree listing, as tuples of path parts.

    The parts are counted from the TestScenario folder. A folder is a tuple of names, and a
    file is the tuple of its folder and its name. The folders include the ancestors of
    every file.
    """
    folders, files = set(), set()
    prefix = TESTS_ROOT + "/"
    for item in items:
        path = item.get("path", "")
        if not path.startswith(prefix):
            continue
        parts = tuple(path.removeprefix(prefix).split("/"))
        if item.get("type") == "tree":
            folders.add(parts)
        elif item.get("type") == "blob" and parts[-1].lower().endswith(TEST_SUFFIX):
            files.add(parts)
        else:
            continue
        folders.update(parts[:depth] for depth in range(1, len(parts)))
    return folders, files


def choose_roots(folders, folder, under):
    """Return the folders to list, as tuples of names; () is TestScenario itself.

    A folder given by name is looked for at any depth, and a match inside another match is
    dropped, since the outer one lists it already. The result is sorted without regard to
    case and is empty when nothing matches.
    """
    if under:
        wanted = tuple(part.lower() for part in under.split("/") if part)
        found = [path for path in folders if tuple(part.lower() for part in path) == wanted]
    elif folder:
        found = [path for path in folders if path[-1].lower() == folder.strip("/").lower()]
    else:
        return [()]
    found.sort(key=lambda path: tuple(part.lower() for part in path))
    return [path for path in found if not any(path[:i] in found for i in range(1, len(path)))]


def make_name_filter(text):
    """Return a function that tells whether a filename passes the --name filter."""
    if not text:
        return lambda name: True
    low = text.lower()
    if "*" in low or "?" in low:
        mask = re.compile(fnmatch.translate(low.replace("[", "[[]")))
        return lambda name: bool(mask.match(name.lower()))
    return lambda name: low in name.lower()


def select_files(files, roots, name_filter):
    """Return the test files under the roots that pass the name filter, sorted."""
    chosen = [path for path in files if name_filter(path[-1]) and any(path[: len(root)] == root for root in roots)]
    return sorted(chosen, key=sort_key)


def sort_key(path):
    """Order files by folder first, then by name, ignoring case; a folder's files precede its subfolders."""
    return tuple(part.lower() for part in path[:-1]), path[-1].lower(), path


def render_tree(files, roots):
    """Return the lines of the nested list for the files, one top-level entry per root."""
    lines = []
    for root in roots:
        node = {"files": [], "folders": {}}
        depth = len(root)
        for path in files:
            if path[:depth] != root:
                continue
            target = node
            for part in path[depth:-1]:
                target = target["folders"].setdefault(part, {"files": [], "folders": {}})
            target["files"].append(path[-1])
        if node["files"] or node["folders"]:
            lines.append(f"- **{'/'.join(root) if root else ROOT_LABEL}/**")
            lines.extend(render_node(node, 1))
    return lines


def render_node(node, depth):
    """Return the lines of one folder: its files first, then its subfolders, each sorted."""
    indent = "  " * depth
    lines = [f"{indent}- `{name}`" for name in sorted(node["files"], key=lambda n: (n.lower(), n))]
    for name in sorted(node["folders"], key=lambda n: (n.lower(), n)):
        lines.append(f"{indent}- **{name}/**")
        lines.extend(render_node(node["folders"][name], depth + 1))
    return lines


def render_table(files):
    """Return the lines of a table with one row for each file."""
    lines = ["| Folder | File |", "| --- | --- |"]
    for path in files:
        folder = "/".join(path[:-1]) or ROOT_LABEL
        lines.append(f"| {folder.replace('|', chr(92) + '|')} | `{path[-1].replace('|', chr(92) + '|')}` |")
    return lines


def describe_filters(args):
    """Return the sentence that names the filters in use, or an empty string."""
    parts = []
    if args.folder:
        parts.append(f'folder "{args.folder.strip("/")}" at any depth')
    if args.under:
        parts.append(f'folder "{args.under.strip("/")}" counted from {ROOT_LABEL}')
    if args.name:
        masked = "*" in args.name or "?" in args.name
        parts.append(f'filename {"matches" if masked else "contains"} "{args.name}"')
    return "Filters: " + "; ".join(parts) + "." if parts else ""


def resolve_source(args, config):
    """Return the repository URL and the branch from the command line and the variables file."""
    variables = {} if args.repo and args.branch is not None else common.read_variables(config)
    repo = args.repo or str(variables.get(REPO_KEY) or "").strip()
    if not repo:
        common.fail(
            "repo_missing",
            "No test repository. Give --repo, or set ATP_TESTS_GIT_REPO_URL in the variables file "
            "that GENERATE_VARIABLES_FILE names in .tdm-assistant/config.json.",
        )
    if args.branch is not None:
        branch = args.branch.strip()
    else:
        branch = "" if args.repo else str(variables.get(BRANCH_KEY) or "").strip()
    return repo, branch


def read_tree(base, project, branch, token):
    """Return the entries of the tests folder, or fail with a message for the user."""
    query = {"path": TESTS_ROOT, "recursive": "true", "per_page": "100"}
    if branch:
        query["ref"] = branch
    try:
        return common.get_all(base, project, "/repository/tree", query, token)
    except common.GitLabError as exc:
        where = f"{base}/{project}"
        if exc.status == 404 and "Tree Not Found" in exc.body:
            common.fail(
                "tests_folder_missing",
                f"The folder {TESTS_ROOT} does not exist in {where}, branch {branch or '(default)'}, "
                "or the branch does not exist.",
            )
        if exc.status in (401, 403, 404):
            hint = (
                "The token is not accepted or cannot read this repository."
                if token
                else ("GitLab wants a token for this repository: set GITLAB_TOKEN or fill .tdm-assistant/gitlab-token.")
            )
            common.fail("repo_inaccessible", f"GitLab answered HTTP {exc.status} for {where}. {hint}")
        return common.fail(exc.code, f"{exc.message} ({where}) {exc.body}".strip())


def build_report(args, where, branch, files, roots):
    """Return the lines of the whole answer: the heading, the filters, and the list or table."""
    count = len(files)
    folder_count = len({path[:-1] for path in files})
    found = (
        f"Found {count} test file{'s' if count != 1 else ''} in {folder_count} folder{'s' if folder_count != 1 else ''}"
    )
    head = [f"{found} of {where}, branch {branch or '(default)'}, under {TESTS_ROOT}."]
    filters = describe_filters(args)
    if filters:
        head.append(filters)
    body = render_table(files) if args.format == "table" else render_tree(files, roots)
    return [*head, "", *body]


def main():
    """Read the tree, apply the filters, and print the answer."""
    args = parse_arguments()
    common.use_utf8_output()
    config = common.load_config()
    repo, branch = resolve_source(args, config)
    base, project = common.split_repo_url(repo, config.get("GITLAB_URL"))
    where = f"{base}/{project}"
    items = read_tree(base, project, branch, common.read_token(config))
    folders, files = collect(items)
    roots = choose_roots(folders, args.folder, args.under)
    if not roots:
        wanted = args.folder or args.under
        common.fail("folder_not_found", f'No folder "{wanted.strip("/")}" under {TESTS_ROOT} in {where}.')
    chosen = select_files(files, roots, make_name_filter(args.name))
    if not chosen:
        message = f"No test files (*{TEST_SUFFIX}) found in {where}, branch {branch or '(default)'}"
        print(f"{message}, under {TESTS_ROOT}. {describe_filters(args)}".strip())
        return
    print("\n".join(build_report(args, where, branch, chosen, roots)))


if __name__ == "__main__":
    main()
