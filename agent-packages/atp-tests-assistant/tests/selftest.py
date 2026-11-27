"""Self-test of the scripts of the atp-tests-assistant package.

Run: python tests/selftest.py

It starts a fake GitLab on localhost that answers the repository tree and file requests,
runs list_tests.py, list_environments.py, show_environment.py, and set_environment.py
against it, and checks the output and the change of the config file: the sorting, the
nesting, the filters, the table, the pagination, the search for an environment, the
source of the repository and the branch, the token, and the errors. How the agent reads a
request in plain language is not tested.

The tests of run_tests.py, manage_config.py, and set_local_folder.py are in test_run.py,
test_config.py, and test_local.py, which this module loads.

Requires Python 3.9 or later.
"""

import importlib
import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

sys.dont_write_bytecode = True  # keep __pycache__ out of the package
SKILLS = Path(__file__).resolve().parents[1] / ".apm" / "skills"
SCRIPT = SKILLS / "atp-tests-list" / "scripts" / "list_tests.py"
ENV_SCRIPT = SKILLS / "atp-environments-list" / "scripts" / "list_environments.py"
SHOW_SCRIPT = SKILLS / "atp-environment-show" / "scripts" / "show_environment.py"
SET_SCRIPT = SKILLS / "atp-environment-set" / "scripts" / "set_environment.py"
ROOT = "TestGeneration/tests/TestScenario"
PAGE_SIZE = 3
TOKEN = "secret-token-value"

FILES = [
    "root-b.spec.ts",
    "Root-a.spec.ts",
    "Customers/create.spec.ts",
    "Customers/Domestic/create-domestic.spec.ts",
    "Customers/Domestic/Delete.spec.ts",
    "Customers/Domestic/helper.js",
    "Customers/Domestic/types.d.ts",
    "Customers/Corporate/Domestic/create-nested.spec.ts",
    "Billing/invoice_one.spec.ts",
    "Billing/Empty/readme.md",
    "Domestic/other.spec.ts",
]


def tree_entries(root):
    """Return the entries the fake GitLab lists for the tests folder root, files and folders."""
    entries, seen = [], set()
    for name in FILES:
        parts = name.split("/")
        for depth in range(1, len(parts)):
            folder = "/".join(parts[:depth])
            if folder not in seen:
                seen.add(folder)
                entries.append({"name": parts[depth - 1], "type": "tree", "path": f"{root}/{folder}"})
        entries.append({"name": parts[-1], "type": "blob", "path": f"{root}/{name}"})
    return entries


def environment_entries():
    """Return the entries the fake GitLab lists for the environments folder."""
    names = ["prod.yaml", "dev-CI-Ivory.yaml", "atp3prod_dyn-CI-Ivory.yaml", "Zeta.yaml", "alpha.yaml", "old.yml"]
    entries = [{"name": name, "type": "blob", "path": f"environments/{name}"} for name in names]
    entries.append({"name": "README.md", "type": "blob", "path": "environments/README.md"})
    entries.append({"name": "archive.yaml", "type": "tree", "path": "environments/archive.yaml"})
    return entries


def file_content(path):
    """Return the content the fake GitLab holds in a file, with a non-ASCII text and a code fence."""
    return f"# {path}\r\nname: Окружение\r\nnote: |\r\n  ```\r\n"


class FakeGitLab(BaseHTTPRequestHandler):
    """Answer the repository tree requests, three entries a page, and the raw file requests, like GitLab."""

    requests: ClassVar[list] = []

    def log_message(self, *args):  # silence the server log
        pass

    def do_GET(self):  # pylint: disable=invalid-name
        """Serve one page of the tree or one file, or an error chosen by the project path."""
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        FakeGitLab.requests.append((url.path, query, self.headers.get("PRIVATE-TOKEN")))
        project = url.path.split("/")[4]
        if project == "group%2Fprivate":
            return self.reply(404, {"message": "404 Project Not Found"})
        if project == "group%2Fsecured" and self.headers.get("PRIVATE-TOKEN") != TOKEN:
            return self.reply(401, {"message": "401 Unauthorized"})
        if "/repository/files/" in url.path:
            return self.reply_file(unquote(url.path.split("/")[7]), query.get("ref", [""])[0])
        if query.get("ref", [""])[0] == "nobranch" or project == "group%2Fnotests":
            return self.reply(404, {"message": "404 Tree Not Found"})
        entries = environment_entries() if query.get("path") == ["environments"] else tree_entries(query["path"][0])
        page = int(query.get("page", ["1"])[0])
        first = (page - 1) * PAGE_SIZE
        last = first + PAGE_SIZE
        link = None
        if last < len(entries):
            host = f"http://127.0.0.1:{self.server.server_port}"
            fields = {key: values[0] for key, values in query.items() if key != "page"}
            link = f'<{host}{url.path}?{urlencode({**fields, "page": page + 1})}>; rel="next"'
        return self.reply(200, entries[first:last], link)

    def reply_file(self, path, ref):
        """Send the raw content of a listed environment file, or GitLab's 404 for it."""
        listed = {entry["path"] for entry in environment_entries() if entry["type"] == "blob"}
        if ref == "nobranch":
            return self.reply(404, {"message": "404 Commit Not Found"})
        if path not in listed:
            return self.reply(404, {"message": "404 File Not Found"})
        return self.send_body(200, file_content(path).encode("utf-8-sig"))

    def reply(self, status, payload, link=None):
        """Send a JSON answer with an optional Link header."""
        self.send_body(status, json.dumps(payload).encode("utf-8"), link)

    def send_body(self, status, body, link=None):
        """Send the bytes of an answer."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if link:
            self.send_header("Link", link)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ScriptCase(unittest.TestCase):
    """Run the script against the fake GitLab, in a folder with an optional config."""

    script = SCRIPT

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeGitLab)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeGitLab.requests = []
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)

    def config_file(self):
        """Return the path of the config file of the project."""
        return self.project / ".atp-assistant" / "config.json"

    def save_config(self, config=None, text=None):
        """Write the config file from an object, or from the given text."""
        self.config_file().parent.mkdir(exist_ok=True)
        self.config_file().write_bytes((json.dumps(config) if text is None else text).encode("utf-8"))

    def write_config(self, repo="group/tests.git", branch="release", token_file=None):
        """Write a config whose variables name the test repository, and a token file if given."""
        variables = {"ATP_TESTS_GIT_REPO_URL": f"{self.url}/{repo}", "ATP_TESTS_GIT_REPO_BRANCH": branch}
        self.save_config({"variables": variables})
        if token_file:
            (self.config_file().parent / "gitlab-token").write_text(token_file + "\n", encoding="utf-8")

    def run_script(self, *args, token=None, cwd=None):
        """Return (exit code, stdout, stderr) of the script, run from the project folder."""
        done = importlib.import_module("test_run").run_isolated(self.script, args, cwd or self.project, token)
        return done.returncode, done.stdout, done.stderr

    def lines(self, *args, **kwargs):
        """Return the output lines, and fail the test on a nonzero exit."""
        code, out, err = self.run_script(*args, **kwargs)
        self.assertEqual(code, 0, err)
        return out.splitlines()

    def error_of(self, *args, **kwargs):
        """Run the script, expect exit status 1, and return the error object from stderr."""
        code, _, err = self.run_script(*args, **kwargs)
        self.assertEqual(code, 1, err)
        return json.loads(err)


class OutputCase(ScriptCase):
    """The listing: sorting, nesting, filters, table, and the empty result."""

    def test_full_tree_is_sorted_and_nested(self):
        """Files come before subfolders at every level, and both are sorted ignoring case."""
        self.write_config()
        lines = self.lines()
        self.assertTrue(lines[0].startswith("Found 9 test files in 6 folders of "), lines[0])
        self.assertEqual(
            lines[2:],
            [
                "- **TestScenario/**",
                "  - `Root-a.spec.ts`",
                "  - `root-b.spec.ts`",
                "  - **Billing/**",
                "    - `invoice_one.spec.ts`",
                "  - **Customers/**",
                "    - `create.spec.ts`",
                "    - **Corporate/**",
                "      - **Domestic/**",
                "        - `create-nested.spec.ts`",
                "    - **Domestic/**",
                "      - `create-domestic.spec.ts`",
                "      - `Delete.spec.ts`",
                "      - `types.d.ts`",
                "  - **Domestic/**",
                "    - `other.spec.ts`",
            ],
        )

    def test_only_ts_files_and_pagination(self):
        """Other files are not listed, and the script follows the Link header to the last page."""
        self.write_config()
        out = "\n".join(self.lines())
        self.assertNotIn("helper.js", out)
        self.assertNotIn("readme.md", out)
        self.assertGreater(len(FakeGitLab.requests), 3)

    def test_folder_name_matches_at_any_depth(self):
        """A folder name without a slash finds every folder of that name, ignoring case."""
        self.write_config()
        lines = self.lines("--folder", "domestic")
        self.assertIn('Filters: folder "domestic" at any depth.', lines)
        self.assertEqual(
            [line for line in lines if line.startswith("- ")],
            ["- **Customers/Corporate/Domestic/**", "- **Customers/Domestic/**", "- **Domestic/**"],
        )

    def test_folder_match_inside_another_match_is_listed_once(self):
        """A folder inside another matching folder is shown under it and not again."""
        self.write_config()
        out = "\n".join(self.lines("--folder", "Customers"))
        self.assertEqual(out.count("create-nested.spec.ts"), 1)
        self.assertEqual(out.count("- **Customers/**"), 1)

    def test_under_counts_from_the_tests_root(self):
        """--under takes a path from TestScenario and matches no folder of that name deeper down."""
        self.write_config()
        lines = self.lines("--under", "Domestic")
        self.assertEqual([line for line in lines if line.startswith("- ")], ["- **Domestic/**"])
        lines = self.lines("--under", "/Customers/Domestic")
        self.assertEqual(
            lines[3:],
            [
                "- **Customers/Domestic/**",
                "  - `create-domestic.spec.ts`",
                "  - `Delete.spec.ts`",
                "  - `types.d.ts`",
            ],
        )

    def test_name_filter_is_a_case_insensitive_substring(self):
        """--name keeps the files whose name contains the text, whatever the case."""
        self.write_config()
        out = "\n".join(self.lines("--name", "CREATE"))
        self.assertIn("create-domestic.spec.ts", out)
        self.assertIn("create-nested.spec.ts", out)
        self.assertNotIn("Delete.spec.ts", out)

    def test_name_filter_with_a_mask_matches_the_whole_name(self):
        """A value with * or ? is a mask for the whole filename."""
        self.write_config()
        out = "\n".join(self.lines("--name", "*.d.ts"))
        self.assertIn("types.d.ts", out)
        self.assertNotIn("create.spec.ts", out)
        self.assertIn("Found 1 test file in 1 folder of", out)

    def test_folder_and_name_together(self):
        """The folder narrows the search and the name filters the files in it."""
        self.write_config()
        lines = self.lines("--folder", "Domestic", "--name", "del")
        self.assertEqual([line for line in lines if line.startswith("  - ")], ["  - `Delete.spec.ts`"])

    def test_table_format(self):
        """--format table prints one row for each file, in the order of the list."""
        self.write_config()
        lines = self.lines("--format", "table", "--under", "Customers")
        start = lines.index("| Folder | File |")
        table = lines[start:]
        self.assertEqual(table[2], "| Customers | `create.spec.ts` |")
        self.assertEqual(table[3], "| Customers/Corporate/Domestic | `create-nested.spec.ts` |")
        self.assertEqual(table[4], "| Customers/Domestic | `create-domestic.spec.ts` |")

    def test_empty_result_exits_with_zero(self):
        """A filter that matches no file is an answer, not an error."""
        self.write_config()
        code, out, _ = self.run_script("--name", "nothing-like-this")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("No test files (*.ts) found"), out)


class SourceCase(ScriptCase):
    """Where the repository, the branch, and the token come from."""

    def test_branch_comes_from_the_config(self):
        """The script reads the repository and the branch of the config."""
        self.write_config(branch="release")
        self.lines()
        self.assertEqual(FakeGitLab.requests[0][1]["ref"], ["release"])
        self.assertEqual(FakeGitLab.requests[0][1]["path"], [ROOT])
        self.assertEqual(FakeGitLab.requests[0][0], "/api/v4/projects/group%2Ftests/repository/tree")

    def test_the_tests_folder_comes_from_the_config(self):
        """TESTS_FOLDER moves the tests, and its last part names the root of the answer."""
        repo = f"{self.url}/group/tests.git"
        self.save_config({"TESTS_FOLDER": "/e2e/specs/", "variables": {"ATP_TESTS_GIT_REPO_URL": repo}})
        lines = self.lines()
        self.assertTrue(lines[0].endswith("under e2e/specs."), lines[0])
        self.assertEqual(lines[2], "- **specs/**")
        self.assertEqual(FakeGitLab.requests[0][1]["path"], ["e2e/specs"])
        self.save_config({"TESTS_FOLDER": "../specs", "variables": {"ATP_TESTS_GIT_REPO_URL": repo}})
        self.assertEqual(self.error_of()["error"], "invalid_value")

    def test_repo_option_ignores_the_file_branch(self):
        """With --repo and no --branch, the request has no ref, so GitLab uses the default branch."""
        self.write_config(branch="release")
        self.lines("--repo", f"{self.url}/other/project.git")
        self.assertNotIn("ref", FakeGitLab.requests[0][1])
        self.assertEqual(FakeGitLab.requests[0][0], "/api/v4/projects/other%2Fproject/repository/tree")
        self.lines("--repo", f"{self.url}/other/project.git", "--branch", "dev")
        self.assertEqual(FakeGitLab.requests[-1][1]["ref"], ["dev"])

    def test_works_without_any_config(self):
        """--repo and --branch are enough when the project has no .atp-assistant folder."""
        lines = self.lines("--repo", f"{self.url}/group/tests", "--branch", "main")
        self.assertTrue(lines[0].startswith("Found 9 test files"), lines[0])

    def test_config_is_found_from_a_subfolder(self):
        """The config is looked for from the working directory up."""
        self.write_config()
        sub = self.project / "a" / "b"
        sub.mkdir(parents=True)
        self.assertEqual(self.run_script(cwd=sub)[0], 0)

    def test_token_goes_in_the_header_and_is_never_printed(self):
        """The token from the environment is sent as PRIVATE-TOKEN and appears in no output."""
        self.write_config(repo="group/secured.git")
        code, out, err = self.run_script(token=TOKEN)
        self.assertEqual(code, 0, err)
        self.assertEqual(FakeGitLab.requests[0][2], TOKEN)
        self.assertNotIn(TOKEN, out + err)

    def test_token_file_is_used_when_the_variable_is_empty(self):
        """The first line of .atp-assistant/gitlab-token is the token when GITLAB_TOKEN is not set."""
        self.write_config(repo="group/secured.git", token_file=TOKEN)
        self.assertEqual(self.run_script()[0], 0)


class ErrorCase(ScriptCase):
    """The errors: each has a code, a message with the remedy, and exit status 1 or 2."""

    def test_no_repository_is_an_error(self):
        """Without --repo and a config, the script says where to set the repository."""
        self.assertEqual(self.error_of()["error"], "repo_missing")

    def test_unknown_folder_is_an_error(self):
        """A folder that does not exist under TestScenario is folder_not_found."""
        self.write_config()
        self.assertEqual(self.error_of("--folder", "Nope")["error"], "folder_not_found")

    def test_missing_token_is_reported_with_the_remedy(self):
        """A 401 without a token names GITLAB_TOKEN as the remedy."""
        self.write_config(repo="group/secured.git")
        error = self.error_of()
        self.assertEqual(error["error"], "repo_inaccessible")
        self.assertIn("GITLAB_TOKEN", error["message"])

    def test_unknown_project_is_reported_as_inaccessible(self):
        """A 404 for the project means that it does not exist or the token cannot read it."""
        self.write_config(repo="group/private.git")
        self.assertEqual(self.error_of(token=TOKEN)["error"], "repo_inaccessible")

    def test_missing_tests_folder_and_missing_branch(self):
        """A 404 for the tree is tests_folder_missing, whether the folder or the branch is absent."""
        self.write_config(repo="group/notests.git")
        self.assertEqual(self.error_of()["error"], "tests_folder_missing")
        error = self.error_of("--repo", f"{self.url}/group/tests.git", "--branch", "nobranch")
        self.assertEqual(error["error"], "tests_folder_missing")

    def test_folder_with_a_slash_is_a_usage_error(self):
        """--folder takes one name; a path is for --under, and the message says so."""
        self.write_config()
        code, _, err = self.run_script("--folder", "A/B")
        self.assertEqual(code, 2)
        self.assertIn("--under", err)

    def test_folder_and_under_together_are_a_usage_error(self):
        """--folder and --under exclude each other."""
        self.write_config()
        self.assertEqual(self.run_script("--folder", "A", "--under", "B")[0], 2)


class EnvironmentsCase(ScriptCase):
    """list_environments.py: the names, the filter, the settings, the token, and the errors."""

    script = ENV_SCRIPT

    def write_gitlab_config(self, project="7", ref="main", url=None):
        """Write a config that holds only the GITLAB_* keys."""
        self.save_config({"GITLAB_URL": url or self.url, "GITLAB_PROJECT_ID": project, "GITLAB_REF": ref})

    def names(self, *args, **kwargs):
        """Return the environment names of the list in the output."""
        return [line[3:-1] for line in self.lines(*args, **kwargs) if line.startswith("- `")]

    def test_names_are_sorted_without_the_extension(self):
        """Only .yaml files count; the names lose the extension and are sorted ignoring case."""
        self.write_gitlab_config()
        lines = self.lines()
        self.assertTrue(lines[0].startswith("Found 5 environments in "), lines[0])
        self.assertEqual(self.names(), ["alpha", "atp3prod_dyn-CI-Ivory", "dev-CI-Ivory", "prod", "Zeta"])

    def test_request_reads_the_folder_of_the_configured_project_and_branch(self):
        """The request goes to the project ID and the branch of the config, for the folder environments."""
        self.write_gitlab_config(project="7", ref="release")
        self.lines()
        path, query, _ = FakeGitLab.requests[0]
        self.assertEqual(path, "/api/v4/projects/7/repository/tree")
        self.assertEqual((query["path"], query["ref"]), (["environments"], ["release"]))

    def test_name_filters_ignoring_case(self):
        """--name keeps the names that contain the text, and the heading says how many of all."""
        self.write_gitlab_config()
        self.assertEqual(self.names("--name", "IVORY"), ["atp3prod_dyn-CI-Ivory", "dev-CI-Ivory"])
        self.assertTrue(self.lines("--name", "ivory")[0].startswith("Found 2 of 5 environments in "))

    def test_name_with_a_mask_matches_the_whole_name(self):
        """A value with * or ? is a mask for the whole name, as in list_tests.py."""
        self.write_gitlab_config()
        self.assertEqual(self.names("--name", "*-ci-*"), ["atp3prod_dyn-CI-Ivory", "dev-CI-Ivory"])
        self.assertEqual(self.names("--name", "prod"), ["atp3prod_dyn-CI-Ivory", "prod"])
        self.assertEqual(self.names("--name", "prod?"), [])
        self.assertIn('Filter: name matches "*-ci-*".', self.lines("--name", "*-ci-*")[0])

    def test_nothing_matched_is_an_answer(self):
        """A filter that matches no name exits with 0 and says how many environments there are."""
        self.write_gitlab_config()
        code, out, _ = self.run_script("--name", "nothing-like-this")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("No environments (*.yaml) found in "), out)
        self.assertIn('5 in all. Filter: name contains "nothing-like-this".', out)

    def test_options_replace_the_config(self):
        """--url, --project, and --ref are enough when the project has no config."""
        self.assertEqual(
            self.names("--url", self.url, "--project", "group/pipeline", "--ref", "main")[:2],
            ["alpha", "atp3prod_dyn-CI-Ivory"],
        )
        self.assertEqual(FakeGitLab.requests[0][0], "/api/v4/projects/group%2Fpipeline/repository/tree")

    def test_token_goes_in_the_header_and_is_never_printed(self):
        """The token from the environment is sent as PRIVATE-TOKEN and appears in no output."""
        self.write_gitlab_config(project="group/secured")
        code, out, err = self.run_script(token=TOKEN)
        self.assertEqual(code, 0, err)
        self.assertEqual(FakeGitLab.requests[0][2], TOKEN)
        self.assertNotIn(TOKEN, out + err)

    def test_missing_settings_are_named(self):
        """Without GITLAB_PROJECT_ID the error names the key and says where it goes."""
        self.write_gitlab_config(project="")
        error = self.error_of()
        self.assertEqual(error["error"], "gitlab_settings_missing")
        self.assertIn("GITLAB_PROJECT_ID", error["message"])

    def test_missing_folder_inaccessible_project_and_missing_token(self):
        """A 404 for the tree is environments_folder_missing; a 404 or 401 for the project is repo_inaccessible."""
        self.write_gitlab_config(project="group/notests")
        self.assertEqual(self.error_of()["error"], "environments_folder_missing")
        self.assertEqual(self.error_of("--project", "group/private")["error"], "repo_inaccessible")
        error = self.error_of("--project", "group/secured")
        self.assertEqual(error["error"], "repo_inaccessible")
        self.assertIn("GITLAB_TOKEN", error["message"])


class ShowEnvironmentCase(ScriptCase):
    """show_environment.py: the current environment, the search by name, and the errors."""

    script = SHOW_SCRIPT

    def write_pipeline_config(self, current="environments/atp3prod_dyn-CI-Ivory.yaml", project="7", ref="main"):
        """Write the GITLAB_* keys and the variable PIPELINE_RUNTIME_CONFIG."""
        config = {"GITLAB_URL": self.url, "GITLAB_PROJECT_ID": project, "GITLAB_REF": ref}
        self.save_config({**config, "variables": {"PIPELINE_RUNTIME_CONFIG": current}})

    def assert_shows(self, lines, path):
        """Check that the output holds the whole file in a fence longer than the fence inside it."""
        self.assertEqual(lines[2:], ["````yaml", *file_content(path).splitlines(), "````"])

    def test_current_environment_is_the_file_of_the_variable(self):
        """Without --name, the script reads the file that PIPELINE_RUNTIME_CONFIG names, on GITLAB_REF."""
        self.write_pipeline_config(ref="release")
        lines = self.lines()
        self.assertTrue(lines[0].startswith("Current environment (PIPELINE_RUNTIME_CONFIG) `atp3prod_dyn-CI-Ivory`"))
        self.assert_shows(lines, "environments/atp3prod_dyn-CI-Ivory.yaml")
        path, query, _ = FakeGitLab.requests[0]
        self.assertEqual(path, "/api/v4/projects/7/repository/files/environments%2Fatp3prod_dyn-CI-Ivory.yaml/raw")
        self.assertEqual(query["ref"], ["release"])

    def test_exact_name_needs_one_request(self):
        """A full name is read directly, without a listing of the folder."""
        self.write_pipeline_config()
        lines = self.lines("--name", "dev-CI-Ivory")
        self.assertTrue(lines[0].startswith("Environment `dev-CI-Ivory`: "), lines[0])
        self.assert_shows(lines, "environments/dev-CI-Ivory.yaml")
        self.assertEqual(len(FakeGitLab.requests), 1)

    def test_a_part_of_one_name_shows_that_file(self):
        """A text that one name contains, ignoring case, shows the file of that name."""
        self.write_pipeline_config()
        lines = self.lines("--name", "DYN-ci")
        self.assertTrue(lines[0].startswith('The only environment that matches "DYN-ci" is `atp3prod_dyn-CI-Ivory`'))
        self.assert_shows(lines, "environments/atp3prod_dyn-CI-Ivory.yaml")

    def test_a_name_equal_ignoring_case_beats_the_substring_matches(self):
        """'PROD' is the environment prod, although atp3prod_dyn-CI-Ivory contains the text too."""
        self.write_pipeline_config()
        self.assert_shows(self.lines("--name", "PROD"), "environments/prod.yaml")

    def test_several_matches_are_listed_and_no_file_is_shown(self):
        """A text that several names contain lists them for the user to choose."""
        self.write_pipeline_config()
        lines = self.lines("--name", "ci-ivory")
        self.assertTrue(lines[0].startswith('2 environments match "ci-ivory" in '), lines[0])
        self.assertEqual(lines[2:], ["- `atp3prod_dyn-CI-Ivory`", "- `dev-CI-Ivory`"])

    def test_no_match_is_an_answer(self):
        """A text that no name contains exits with 0 and says how many environments there are."""
        self.write_pipeline_config()
        lines = self.lines("--name", "nothing-like-this")
        self.assertTrue(lines[0].startswith('No environment matches "nothing-like-this" in '), lines[0])
        self.assertTrue(lines[0].endswith(", 5 in all."), lines[0])

    def test_missing_current_environment(self):
        """An empty PIPELINE_RUNTIME_CONFIG and a value that names no file are two different errors."""
        self.write_pipeline_config(current="")
        self.assertEqual(self.error_of()["error"], "runtime_config_missing")
        self.write_pipeline_config(current="environments/gone.yaml")
        error = self.error_of()
        self.assertEqual(error["error"], "environment_file_missing")
        self.assertIn("environments/gone.yaml", error["message"])

    def test_wrong_branch_project_and_token(self):
        """A branch, a project, or a token that GitLab refuses is reported, not searched around."""
        self.write_pipeline_config()
        self.assertEqual(self.error_of("--ref", "nobranch")["error"], "environment_file_missing")
        self.assertEqual(self.error_of("--name", "prod", "--ref", "nobranch")["error"], "environments_folder_missing")
        self.assertEqual(self.error_of("--project", "group/private")["error"], "repo_inaccessible")
        self.assertEqual(self.error_of("--project", "group/secured")["error"], "repo_inaccessible")

    def test_token_goes_in_the_header_and_is_never_printed(self):
        """The token from the environment is sent as PRIVATE-TOKEN and appears in no output."""
        self.write_pipeline_config(project="group/secured")
        code, out, err = self.run_script(token=TOKEN)
        self.assertEqual(code, 0, err)
        self.assertEqual(FakeGitLab.requests[0][2], TOKEN)
        self.assertNotIn(TOKEN, out + err)


class SetEnvironmentCase(ScriptCase):
    """set_environment.py: the value it writes, when it leaves the file alone, and the errors."""

    script = SET_SCRIPT

    def settings(self):
        """Return the GITLAB_* keys of the fake pipeline."""
        return {"GITLAB_URL": self.url, "GITLAB_PROJECT_ID": "7", "GITLAB_REF": "main"}

    def write_pipeline_config(self, variables=None):
        """Write the GITLAB_* keys and the given variables, indented by two spaces."""
        self.save_config(text=json.dumps({**self.settings(), "variables": variables or {}}, indent=2) + "\n")

    def current(self):
        """Return PIPELINE_RUNTIME_CONFIG of the config file."""
        config = json.loads(self.config_file().read_bytes().decode("utf-8-sig"))
        return config["variables"].get("PIPELINE_RUNTIME_CONFIG")

    def test_one_match_is_set_when_the_variable_is_absent_empty_or_different(self):
        """A text that one name contains sets environments/<filename>, whatever the file held."""
        for before in (None, "", "environments/prod.yaml"):
            self.write_pipeline_config({} if before is None else {"PIPELINE_RUNTIME_CONFIG": before})
            lines = self.lines("--name", "DYN-ci")
            self.assertEqual(self.current(), "environments/atp3prod_dyn-CI-Ivory.yaml", before)
            self.assertEqual(lines[0], 'The only environment that matches "DYN-ci" is `atp3prod_dyn-CI-Ivory`.')
            self.assertTrue(lines[1].startswith("Set PIPELINE_RUNTIME_CONFIG to "), lines[1])

    def test_exact_name_is_set_without_a_listing(self):
        """A full name is read directly and set, and the answer names the previous value."""
        self.write_pipeline_config({"PIPELINE_RUNTIME_CONFIG": "environments/prod.yaml"})
        lines = self.lines("--name", "dev-CI-Ivory")
        self.assertEqual(self.current(), "environments/dev-CI-Ivory.yaml")
        self.assertTrue(lines[0].endswith("It was `environments/prod.yaml`."), lines[0])
        self.assertEqual(len(FakeGitLab.requests), 1)

    def test_the_rest_of_the_file_and_its_format_stay(self):
        """The other keys, the non-ASCII text, the indentation, the CRLF ends, and the BOM are kept."""
        lines = ["{"]
        lines += [f'    "{key}": "{value}",' for key, value in self.settings().items()]
        lines += ['    "comment": "Окружение",', '    "variables": {', '        "A": "1",']
        lines += ['        "PIPELINE_RUNTIME_CONFIG": ""', "    }", "}"]
        text = "\ufeff" + "\r\n".join(lines) + "\r\n"
        self.save_config(text=text)
        self.lines("--name", "prod")
        expected = text.replace('CONFIG": ""', 'CONFIG": "environments/prod.yaml"')
        self.assertEqual(self.config_file().read_bytes(), expected.encode("utf-8"))
        self.assertEqual(list(self.config_file().parent.glob("*.tmp")), [])

    def test_a_config_without_variables_gets_them(self):
        """A config with only the GITLAB_* keys gets the object variables with the one value."""
        self.save_config(self.settings())
        self.assertTrue(self.lines("--name", "prod")[0].endswith("It was not set."))
        self.assertEqual(self.current(), "environments/prod.yaml")

    def test_the_same_value_leaves_the_file_alone(self):
        """When the variable already names the file, the file is not written."""
        variables = {"PIPELINE_RUNTIME_CONFIG": "environments/prod.yaml"}
        text = json.dumps({**self.settings(), "variables": variables})
        self.save_config(text=text)
        self.assertIn("Nothing changed.", self.lines("--name", "prod")[0])
        self.assertEqual(self.config_file().read_bytes(), text.encode("utf-8"))

    def test_none_or_several_matches_change_nothing(self):
        """Without one match, the file stays, and several names are listed for the user to choose."""
        self.write_pipeline_config({"PIPELINE_RUNTIME_CONFIG": "environments/prod.yaml"})
        before = self.config_file().read_bytes()
        lines = self.lines("--name", "ci-ivory")
        self.assertEqual(lines[2:4], ["- `atp3prod_dyn-CI-Ivory`", "- `dev-CI-Ivory`"])
        self.assertEqual(lines[-1], "PIPELINE_RUNTIME_CONFIG was not changed.")
        lines = self.lines("--name", "nothing-like-this")
        self.assertTrue(lines[0].startswith('No environment matches "nothing-like-this" in '), lines[0])
        self.assertEqual(self.config_file().read_bytes(), before)

    def test_missing_or_broken_config(self):
        """Without a usable config the script fails before it asks GitLab."""
        self.assertEqual(self.error_of("--name", "prod")["error"], "config_missing")
        for text in ("[]", "{", '{"variables": []}'):
            self.save_config(text=text)
            self.assertEqual(self.error_of("--name", "prod")["error"], "config_unreadable", text)
        self.assertEqual(FakeGitLab.requests, [])

    def test_name_is_required(self):
        """An absent or blank --name is a usage error."""
        self.assertEqual(self.run_script()[0], 2)
        self.assertEqual(self.run_script("--name", " ")[0], 2)


class RepoUrlCase(unittest.TestCase):
    """Check how a repository URL turns into a GitLab base URL and a project path."""

    def setUp(self):
        sys.path.insert(0, str(SKILLS / "atp-common" / "scripts"))
        self.addCleanup(sys.path.pop, 0)
        import atp_common  # pylint: disable=import-outside-toplevel,import-error

        self.common = atp_common

    def test_forms_of_the_url(self):
        """An http(s) URL, an ssh URL, and a git@host:path address give the same kind of answer."""
        split = self.common.split_repo_url
        self.assertEqual(split("https://gitlab.example.com/g/s/p.git"), ("https://gitlab.example.com", "g/s/p"))
        self.assertEqual(
            split("https://user:pw@gitlab.example.com:8443/g/p"), ("https://gitlab.example.com:8443", "g/p")
        )
        self.assertEqual(split("git@gitlab.example.com:g/p.git"), ("https://gitlab.example.com", "g/p"))
        self.assertEqual(split("ssh://git@gitlab.example.com:2222/g/p.git"), ("https://gitlab.example.com", "g/p"))

    def test_configured_gitlab_url_keeps_its_prefix(self):
        """A repository under GITLAB_URL keeps that URL, with its path prefix, as the base."""
        split = self.common.split_repo_url
        self.assertEqual(
            split("https://host.example.com/gitlab/g/p.git", "https://host.example.com/gitlab/"),
            ("https://host.example.com/gitlab", "g/p"),
        )


def load_tests(loader, tests, _pattern):
    """Add the tests of the other test modules to the tests of this module."""
    for module in ("test_run", "test_config", "test_local"):
        tests.addTests(loader.loadTestsFromModule(importlib.import_module(module)))
    return tests


if __name__ == "__main__":
    unittest.main(verbosity=2)
