"""Share the config, token, and GitLab code of the scripts of the atp-tests-assistant skills.

A script imports this module after adding the folder that holds it to sys.path:

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "atp-tests-common" / "scripts"))
    common = importlib.import_module("atp_tests_common")

The module reads the files that the tdm-test-data-assistant package defines, and works
without them: .tdm-assistant/config.json (found from the working directory up), the
variables file that its key GENERATE_VARIABLES_FILE names, and the token. Every file is
optional. A script prints its result on stdout and an error on stderr, as one JSON object
{"ok": false, "error": "<code>", "message": "<text>"}, and exits with 1.
Python 3.9+, standard library only.
"""

import fnmatch
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NoReturn

CONFIG_PATH = Path(".tdm-assistant") / "config.json"
TOKEN_FILE = "gitlab-token"
DEFAULT_TOKEN_ENV = "GITLAB_TOKEN"
REQUEST_TIMEOUT = 30
MAX_PAGES = 500
LINK_NEXT = re.compile(r'<([^>]+)>\s*;\s*rel="next"')
SCP_URL = re.compile(r"[\w.-]+@([\w.-]+):(.+)")
ENVIRONMENTS_FOLDER = "environments"
ENVIRONMENT_SUFFIX = ".yaml"
PIPELINE_SETTINGS = (("url", "GITLAB_URL"), ("project", "GITLAB_PROJECT_ID"), ("ref", "GITLAB_REF"))


class GitLabError(Exception):
    """A failed GitLab request: its error code, the HTTP status, and the start of the body."""

    def __init__(self, code, message, status=None, body=""):
        super().__init__(message)
        self.code, self.message, self.status, self.body = code, message, status, body


def fail(code, message, **extra) -> NoReturn:
    """Print an error object on stderr and exit with status 1."""
    print(json.dumps({"ok": False, "error": code, "message": message, **extra}, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


def use_utf8_output():
    """Make stdout UTF-8 whatever the console code page is."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def find_config():
    """Return the path of config.json found from the working directory up, or None."""
    here = Path.cwd().resolve()
    for folder in [here, *here.parents]:
        candidate = folder / CONFIG_PATH
        if candidate.is_file():
            return candidate
    return None


def load_config():
    """Return the config, or an empty dict when there is no config file.

    CONFIG_DIR holds the folder of the config file, the .tdm-assistant folder.
    """
    path = find_config()
    if path is None:
        return {}
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail("config_unreadable", f"Cannot read {path}: {exc}")
    if not isinstance(config, dict):
        fail("config_unreadable", f"{path} must hold a JSON object.")
    config["CONFIG_DIR"] = str(path.parent)
    return config


def read_variables(config):
    """Return the variables object of the file that GENERATE_VARIABLES_FILE names.

    A relative path is taken from the project folder, the parent of the .tdm-assistant
    folder. The result is empty when the config has no such key.
    """
    name = config.get("GENERATE_VARIABLES_FILE")
    if not name:
        return {}
    path = Path(name)
    if not path.is_absolute():
        path = Path(config["CONFIG_DIR"]).parent / path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail("variables_file_unreadable", f"Cannot read the variables file {path}: {exc}")
    variables = data.get("variables") if isinstance(data, dict) else None
    if not isinstance(variables, dict):
        fail("variables_file_unreadable", f"The variables file {path} has no 'variables' object.")
    return variables


def read_token(config):
    """Return the GitLab token from the environment variable or the token file, or "".

    The variable is named by GITLAB_TOKEN_ENV in the config and is GITLAB_TOKEN by default.
    The token file is .tdm-assistant/gitlab-token, and only its first line counts.
    """
    token = (os.environ.get(config.get("GITLAB_TOKEN_ENV") or DEFAULT_TOKEN_ENV) or "").strip()
    if token or "CONFIG_DIR" not in config:
        return token
    token_path = Path(config["CONFIG_DIR"]) / TOKEN_FILE
    if not token_path.is_file():
        return ""
    lines = token_path.read_text(encoding="utf-8").strip().splitlines()
    return lines[0].strip() if lines else ""


def make_name_filter(text):
    """Return a function that tells whether a name passes the --name filter.

    TEXT is a substring of the name, ignoring case. TEXT with * or ? is a mask for the whole
    name, ignoring case.
    """
    if not text:
        return lambda name: True
    low = text.lower()
    if "*" in low or "?" in low:
        mask = re.compile(fnmatch.translate(low.replace("[", "[[]")))
        return lambda name: bool(mask.match(name.lower()))
    return lambda name: low in name.lower()


def split_repo_url(repo, gitlab_url=""):
    """Return the base URL of the GitLab service and the path of the project in it.

    A repository under gitlab_url, the GITLAB_URL of the config, keeps that URL as the
    base, which covers a GitLab served under a path prefix. Otherwise the base comes from
    the host of the repository URL: an ssh address (ssh://... or git@host:path) is
    reached over https, and a user name or password in the URL is dropped.
    """
    repo = repo.strip()
    base = (gitlab_url or "").rstrip("/")
    if base and repo.lower().startswith(base.lower() + "/"):
        start = len(base) + 1
        path = repo[start:]
    elif SCP_URL.fullmatch(repo):
        host, path = SCP_URL.fullmatch(repo).groups()
        base = f"https://{host}"
    else:
        parts = urllib.parse.urlsplit(repo)
        if parts.scheme not in ("http", "https", "ssh") or not parts.hostname:
            fail("repo_url_invalid", f"Cannot read the repository URL '{repo}'. Use http(s)://host/group/project.git.")
        port = f":{parts.port}" if parts.port and parts.scheme != "ssh" else ""
        base = f"{'https' if parts.scheme == 'ssh' else parts.scheme}://{parts.hostname}{port}"
        path = parts.path
    path = path.strip("/")
    path = path.removesuffix(".git")
    path = path.strip("/")
    if "/" not in path:
        fail("repo_url_invalid", f"The repository URL '{repo}' has no group and project path.")
    return base, path


def send(url, token):
    """Send one GET request and return the body and the Link header; raise GitLabError."""
    headers = {"PRIVATE-TOKEN": token} if token else {}
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return response.read(), response.headers.get("Link") or ""
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        raise GitLabError("http_error", f"HTTP {exc.code} from GitLab", status=exc.code, body=body) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GitLabError("server_unreachable", f"Cannot reach GitLab: {exc}") from exc
    except ValueError as exc:
        raise GitLabError("http_error", f"Cannot send the request to GitLab: {exc}") from exc


def get_page(url, token):
    """Send one GET request and return the decoded JSON and the Link header; raise GitLabError."""
    body, link = send(url, token)
    try:
        return json.loads(body.decode("utf-8")), link
    except ValueError as exc:
        raise GitLabError("http_error", f"The GitLab response is not JSON: {exc}") from exc


def project_url(base, project_path, endpoint, query):
    """Return the API URL of a project endpoint; the project is a numeric ID or a path."""
    quoted = urllib.parse.quote(project_path, safe="")
    return f"{base}/api/v4/projects/{quoted}{endpoint}?{urllib.parse.urlencode(query)}"


def get_file(base, project_path, file_path, ref, token):
    """Return the text of one file of the repository on the branch ref; raise GitLabError.

    The text is read as UTF-8 without the byte order mark, and a byte that is not UTF-8
    becomes the replacement character.
    """
    endpoint = f"/repository/files/{urllib.parse.quote(file_path, safe='')}/raw"
    body, _ = send(project_url(base, project_path, endpoint, {"ref": ref}), token)
    return body.decode("utf-8-sig", "replace")


def get_all(base, project_path, endpoint, query, token):
    """Return the items of every page of a project endpoint, following the Link header.

    The token goes only to the host of base: a next link to another host is refused.
    Raises GitLabError.
    """
    url = project_url(base, project_path, endpoint, query)
    host = urllib.parse.urlsplit(base).netloc.lower()
    items = []
    for _ in range(MAX_PAGES):
        page, link = get_page(url, token)
        items.extend(page)
        match = LINK_NEXT.search(link)
        if not match:
            return items
        url = match.group(1)
        if urllib.parse.urlsplit(url).netloc.lower() != host:
            raise GitLabError(
                "http_error", "GitLab sent a next-page link to another host; the script did not follow it."
            )
    raise GitLabError("too_many_pages", f"The answer has more than {MAX_PAGES} pages.")


def add_pipeline_arguments(parser):
    """Add --url, --project, and --ref, which name the pipeline repository."""
    parser.add_argument("--url", help="base URL of GitLab; overrides GITLAB_URL")
    parser.add_argument("--project", help="numeric ID or path of the pipeline project; overrides GITLAB_PROJECT_ID")
    parser.add_argument("--ref", help="branch to read; overrides GITLAB_REF")


def resolve_pipeline(args, config):
    """Return the GitLab URL, the project, and the branch of the pipeline, or fail naming what is missing."""
    values = {key: str(getattr(args, option) or config.get(key) or "").strip() for option, key in PIPELINE_SETTINGS}
    missing = [key for key, value in values.items() if not value]
    if missing:
        fail(
            "gitlab_settings_missing",
            "Missing: " + ", ".join(missing) + ". Set them in .tdm-assistant/config.json, "
            "or give --url, --project, and --ref.",
        )
    return values["GITLAB_URL"].rstrip("/"), values["GITLAB_PROJECT_ID"], values["GITLAB_REF"]


def fail_request(exc, where, token) -> NoReturn:
    """Fail for a GitLabError of a pipeline request; 401, 403, and 404 become repo_inaccessible."""
    if exc.status in (401, 403, 404):
        remedy = "Check the token." if token else "Set GITLAB_TOKEN or fill .tdm-assistant/gitlab-token."
        fail("repo_inaccessible", f"GitLab answered HTTP {exc.status} for {where}. {remedy}")
    fail(exc.code, f"{exc.message} ({where}) {exc.body}".strip())


def read_environments(base, project, ref, token):
    """Return {name: filename} of the YAML files in the environments folder, sorted by name ignoring case.

    The name is the filename without .yaml. Fails with a message for the user when the
    folder cannot be read.
    """
    query = {"path": ENVIRONMENTS_FOLDER, "ref": ref, "per_page": "100"}
    try:
        entries = get_all(base, project, "/repository/tree", query, token)
    except GitLabError as exc:
        where = f"{base}, project {project}"
        if exc.status == 404 and "Tree Not Found" in exc.body:
            fail(
                "environments_folder_missing",
                f"The folder {ENVIRONMENTS_FOLDER} does not exist in {where}, branch {ref}, "
                "or the branch does not exist.",
            )
        fail_request(exc, where, token)
    files = {
        entry["name"][: -len(ENVIRONMENT_SUFFIX)]: entry["name"]
        for entry in entries
        if entry.get("type") == "blob" and entry.get("name", "").lower().endswith(ENVIRONMENT_SUFFIX)
    }
    return {name: files[name] for name in sorted(files, key=lambda name: (name.lower(), name))}
