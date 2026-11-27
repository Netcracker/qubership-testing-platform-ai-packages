"""Build links to the objects behind the business identifiers that run_tests.py finds.

BUSINESS_IDS_AS_LINKS of the config, false by default, switches the links on. Each entry
of BUSINESS_ID_LINK_TEMPLATES then gives one link for each identifier:

  get_property('<system>','<connection type>','<property>')  a value of the file below
  $ID                                                       the identifier, URL-encoded

The values come from the JSON file environment-configuration/<name> of the test
repository, where EXTRA_VARS of the pipeline variables names it as
ENV_CONFIGURATION_TEMPLATE_FILENAME=<name>. EXTRA_VARS holds name=value pairs separated
by commas, where "\\," is a comma inside a value:

  {"systems": [{"<system>": {"connections": [{"<connection type>": {"<property>": ...}}]}}]}

The file holds passwords, so only the properties that a template names are taken from
it, and a property that looks like a secret is refused. The file is read for every run.
Python 3.9+, standard library only.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass

FOLDER = "environment-configuration"
EXTRA_VARS_KEY = "EXTRA_VARS"
FILE_NAME_KEY = "ENV_CONFIGURATION_TEMPLATE_FILENAME"
REPO_KEY = "ATP_TESTS_GIT_REPO_URL"
BRANCH_KEY = "ATP_TESTS_GIT_REPO_BRANCH"
RUNTIME_KEY = "PIPELINE_RUNTIME_CONFIG"
PLACEHOLDER = "$ID"
UNESCAPED_COMMA = re.compile(r"(?<!\\),")
CALL = "get_property("
PROPERTY = re.compile(r"get_property\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*\)")
SECRET_PROPERTY = re.compile(r"pass|pwd|secret|token|credential|private_?key|api_?key", re.IGNORECASE)
# The characters of a URL that stay as they are; a space or a parenthesis would break a Markdown link.
URL_SAFE = ":/?#[]@!$&'*+,;=%-._~"


class LinkError(ValueError):
    """A link that cannot be built, with the error code to report.

    templates is empty, or holds the outcome of every template as resolve() describes it.
    """

    def __init__(self, code, message, templates=()):
        super().__init__(message)
        self.code, self.templates = code, list(templates)


@dataclass(frozen=True)
class Links:
    """The links of a run before the identifiers are known.

    file is the path of the environment configuration in the test repository. outcomes
    holds {"template": ..., "link": ...} for each template, where only $ID is left in the
    link. warning is empty or says that the name of the file differs from the one of the
    pipeline environment.
    """

    file: str
    outcomes: tuple
    warning: str = ""

    def make(self, value):
        """Return the links to one identifier, in the order of the templates."""
        quoted = urllib.parse.quote(value, safe="")
        return [outcome["link"].replace(PLACEHOLDER, quoted) for outcome in self.outcomes]

    def plan(self):
        """Return the fields that describe the links before the run."""
        warning = {"warning": self.warning} if self.warning else {}
        return {"file": self.file, "templates": list(self.outcomes), **warning}


def check_templates(templates):
    """Return the templates as a tuple, or raise LinkError for one that cannot be used."""
    if not isinstance(templates, (list, tuple)) or not templates:
        raise LinkError("invalid_link_template", "it must be a list with at least one template")
    for number, template in enumerate(templates, 1):
        if not isinstance(template, str) or PLACEHOLDER not in template:
            problem = f"template {number} must be a string that holds {PLACEHOLDER}"
        elif CALL in PROPERTY.sub("", template):
            problem = f"template {number} has a get_property that is not get_property('system','type','property')"
        elif any(SECRET_PROPERTY.search(call[2]) for call in PROPERTY.findall(template)):
            problem = f"template {number} names a property that looks like a secret; a link would show it"
        else:
            continue
        raise LinkError("invalid_link_template", problem)
    return tuple(templates)


def find_file_name(extra_vars):
    """Return the filename that EXTRA_VARS gives.

    EXTRA_VARS holds name=value pairs separated by commas. A comma inside a value is
    written as "\\,".
    """
    for pair in UNESCAPED_COMMA.split(str(extra_vars or "")):
        name, _, value = pair.replace("\\,", ",").partition("=")
        if name.strip() == FILE_NAME_KEY and value.strip():
            filename = value.strip()
            if ".." in filename.split("/") or filename.startswith("/"):
                raise LinkError("env_config_unresolved", f"{FILE_NAME_KEY} must be a filename, not '{filename}'.")
            return filename
    raise LinkError(
        "env_config_unresolved",
        f"No {FILE_NAME_KEY}=<name>.json in {EXTRA_VARS_KEY} of the pipeline variables.",
    )


def names_differ(runtime_config, filename):
    """Tell whether the pipeline environment and the configuration file have different names.

    The extensions and the case are ignored. A name that is the other one after a prefix
    ending in '-' or '_' is the same name.
    """
    environment = re.sub(r"\.ya?ml$", "", str(runtime_config).rsplit("/", 1)[-1], flags=re.IGNORECASE)
    configuration = re.sub(r"\.json$", "", filename.rsplit("/", 1)[-1], flags=re.IGNORECASE)
    if not environment:
        return False
    short, long = sorted((environment.lower(), configuration.lower()), key=len)
    return not (long == short or long.endswith((f"-{short}", f"_{short}")))


def as_dicts(value):
    """Return the objects of a JSON array, or an empty list when the value is not one."""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def find_property(document, system, connection, name):
    """Return the text of one property of a connection of a system, or "" when there is none."""
    root = document if isinstance(document, dict) else {}
    for entry in as_dicts(root.get("systems")):
        described = entry.get(system)
        if not isinstance(described, dict):
            continue
        for connections in as_dicts(described.get("connections")):
            properties = connections.get(connection)
            value = properties.get(name) if isinstance(properties, dict) else None
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip():
                return str(value).strip()
    return ""


def without_user(url):
    """Return the URL without the user and the password before its host."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    if "@" not in parts.netloc:
        return url
    return urllib.parse.urlunsplit(parts._replace(netloc=parts.netloc.rsplit("@", 1)[1]))


def fill(template, document, missing):
    """Return the template with each get_property replaced by its value.

    A property that the document does not hold is added to missing. A value that ends in
    '/' loses it where the template goes on with '/'.
    """

    def replace(match):
        value = find_property(document, *match.groups())
        if not value:
            missing.append(".".join(match.groups()))
        if template.startswith("/", match.end()):
            value = value.rstrip("/")
        return without_user(value)

    return PROPERTY.sub(replace, template)


def is_web_link(link):
    """Tell whether the link is an http or https URL with a host."""
    try:
        parts = urllib.parse.urlsplit(link)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def outcome_of(template, document):
    """Return the outcome of one template, as resolve() describes it."""
    missing: list[str] = []
    filled = fill(template, document, missing)
    if missing:
        return {"template": template, "missing": list(dict.fromkeys(missing))}
    link = urllib.parse.quote(filled, safe=URL_SAFE)
    if not is_web_link(link):
        return {"template": template, "problem": "not an http or https link"}
    return {"template": template, "link": link}


def resolve(templates, text, path):
    """Return the outcome of every template with the text of the configuration file.

    An outcome is {"template": ..., "link": ...}. When a template gives no link, LinkError
    is raised, and its templates hold all outcomes: a failed one has "missing", the list
    of <system>.<connection type>.<property> without a value, or "problem" in the place
    of "link". The messages name the file and the properties, and never quote the
    content.
    """
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise LinkError("env_config_unresolved", f"{path} is not JSON.") from exc
    outcomes = [outcome_of(template, document) for template in templates]
    problems = []
    for number, outcome in enumerate(outcomes, 1):
        if "missing" in outcome:
            problems.append(f"template {number}: no value for {', '.join(outcome['missing'])}")
        elif "problem" in outcome:
            problems.append(f"template {number}: {outcome['problem']}")
    if problems:
        message = f"Not every template gives a link with {path}: {'; '.join(problems)}."
        raise LinkError("env_config_unresolved", message, outcomes)
    return tuple(outcomes)


def load_links(templates, variables, read_file):
    """Return the Links of a run, or raise LinkError.

    templates is the value of BUSINESS_ID_LINK_TEMPLATES, and variables holds the pipeline
    variables of this run. read_file(repository URL, branch, path) returns the text of a
    file and raises LinkError.
    """
    checked = check_templates(templates)
    filename = find_file_name(variables.get(EXTRA_VARS_KEY))
    path = f"{FOLDER}/{filename}"
    text = read_file(variables.get(REPO_KEY, ""), variables.get(BRANCH_KEY, "").strip(), path)
    runtime = variables.get(RUNTIME_KEY, "")
    warning = ""
    if names_differ(runtime, filename):
        warning = (
            f"The names differ: {RUNTIME_KEY} is {runtime}, and the links come from {path}. "
            f"Check {FILE_NAME_KEY} in {EXTRA_VARS_KEY}."
        )
    return Links(path, resolve(checked, text, path), warning)
