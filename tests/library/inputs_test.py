#!/usr/bin/env python3
"""Checks that the library holds no deployment's values and that a deployment
supplies every input.

A deployment sets each input once, in the root ApplicationSet's generator
values; the library refers to it as @<name>@. The root's templatePatch replaces
those tokens in every generated Application. Directories that hold nested
ApplicationSets or input-dependent manifests are kustomizations with a
local-config ConfigMap library-inputs (values REQUIRED-<name>) and
replacements, which the owning application.yaml patches with the same tokens.

Checks, each reported as ok or FAIL:
  static-revision  no upstream URL and no HEAD revision under apps/, bootstrap/,
                   cluster-config/ (Markdown, tests and upstream's legacy lab
                   roots excepted)
  static-catalog   no lab catalog repository under those directories
  components       each apps/*/application.yaml and cluster-config/application.yaml,
                   with sample-inputs.yaml substituted the way the root does it,
                   resolves: no @token@ or REQUIRED- left, every git source is the
                   library, the deployment, the catalog or a known external
                   repository at the matching revision, and every kustomization
                   it reads builds with the Application's own patches
  bare-inputs      each directory with an inputs.yaml builds without patches and
                   shows its inputs as REQUIRED-<name>
  root             bootstrap/hub/applicationset.yaml lists every component, marks
                   its repository, revision and every input REQUIRED-, and the
                   library has no self-syncing root
  root-render      each listed component through the root's templatePatch,
                   rendered as the ApplicationSet controller does
                   (tests/library/templatepatch, needs Go), passes the
                   components checks; an input left out or left REQUIRED- fails
                   with "missing input: <name>"

Run: bash tests/library/inputs-test.sh   (needs python3 with PyYAML, kustomize)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample-inputs.yaml")

STATIC_DIRS = ("apps", "bootstrap", "cluster-config")
# Upstream's self-syncing lab roots. They predate inputs and stay until the
# lab moves to its own deployment repository.
LEGACY_ROOTS = {"bootstrap/applicationset.yaml", "bootstrap/dedicated-hub/applicationset.yaml"}
REVISION_PATTERNS = [
    re.compile(r"ai-grid-cloud/ai-grid-cluster-gitops"),
    re.compile(r"\b(target)?[rR]evision:\s*['\"]?HEAD\b"),
]
CATALOG_PATTERNS = [re.compile(r"ai-grid-shared-catalog")]
# Repositories a component may read that no deployment chooses: products and
# charts the library pins itself.
EXTERNAL_PREFIXES = (
    "https://github.com/opendatahub-io/",
    "https://github.com/ai-grid-cloud/ai-grid-provider-console",
    "oci://",
)
TOKEN = re.compile(r"@[a-zA-Z]+@")

failures = []
results = []


def check(name):
    def wrap(fn):
        def run(*args):
            before = len(failures)
            fn(*args)
            new = failures[before:]
            results.append((name, not new))
            print(("   ok   " if not new else "   FAIL ") + name)
            for item in new:
                print("          - " + item)
        return run
    return wrap


def fail(message):
    failures.append(message)


def rel(path):
    return os.path.relpath(path, ROOT)


def library_files(dirs):
    for top in dirs:
        for base, subdirs, files in os.walk(os.path.join(ROOT, top)):
            subdirs[:] = [d for d in subdirs if d not in (".git", "tests")]
            for name in sorted(files):
                yield os.path.join(base, name)


def load_inputs():
    with open(SAMPLE) as handle:
        return yaml.safe_load(handle)


def substitute(text, inputs):
    for key, value in inputs.items():
        text = text.replace("@%s@" % key, str(value))
    return text


def grep(patterns, label):
    for path in library_files(STATIC_DIRS):
        relative = rel(path)
        if relative.endswith(".md") or relative in LEGACY_ROOTS:
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                lines = handle.readlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            if any(p.search(line) for p in patterns):
                fail("%s:%d: %s: %s" % (relative, number, label, line.strip()))


@check("static-revision")
def static_revision():
    grep(REVISION_PATTERNS, "upstream self-reference")


@check("static-catalog")
def static_catalog():
    grep(CATALOG_PATTERNS, "lab catalog")


def classify(repo, inputs):
    if repo == inputs["libraryRepoURL"]:
        return "library", inputs["libraryRevision"]
    if repo == inputs["deploymentRepoURL"]:
        return "deployment", inputs["deploymentRevision"]
    if repo == inputs["catalogRepoURL"]:
        return "catalog", inputs["catalogRevision"]
    if repo.startswith(EXTERNAL_PREFIXES):
        return "external", None
    return None, None


def check_repo(where, repo, revision, inputs):
    kind, expected = classify(repo, inputs)
    if kind is None:
        fail("%s: repository %s is not an input or a known external repository" % (where, repo))
    elif expected is not None and revision != expected:
        fail("%s: %s repository at revision %r, not the %s input" % (where, kind, revision, kind + "Revision"))
    return kind


def sources_of(spec):
    if "source" in spec:
        return [spec["source"]]
    return spec.get("sources") or []


def walk_generators(generators):
    for generator in generators or []:
        for kind, body in generator.items():
            if not isinstance(body, dict):
                continue
            if kind == "git":
                yield body
            if kind in ("matrix", "merge"):
                yield from walk_generators(body.get("generators"))


def check_nested(where, documents, inputs):
    """Repositories that nested ApplicationSets and Applications name."""
    for doc in documents:
        if not isinstance(doc, dict) or doc.get("apiVersion", "").split("/")[0] != "argoproj.io":
            continue
        name = "%s %s/%s" % (where, doc.get("kind"), doc.get("metadata", {}).get("name"))
        if doc.get("kind") == "ApplicationSet":
            for git in walk_generators(doc.get("spec", {}).get("generators")):
                check_repo(name + " git generator", git.get("repoURL", ""), git.get("revision"), inputs)
            spec = doc.get("spec", {}).get("template", {}).get("spec", {})
        elif doc.get("kind") == "Application":
            spec = doc.get("spec", {})
        else:
            continue
        for source in sources_of(spec):
            kind = check_repo(name + " source", source.get("repoURL", ""), source.get("targetRevision"), inputs)
            path = source.get("path")
            if kind == "library" and path and "{{" not in path and not os.path.isdir(os.path.join(ROOT, path)):
                fail("%s: library path %s does not exist" % (name, path))


def scan_text(where, text):
    for token in sorted(set(TOKEN.findall(text))):
        fail("%s: input %s left unresolved" % (where, token))
    if "REQUIRED-" in text:
        names = sorted(set(re.findall(r"REQUIRED-[A-Za-z]+", text)))
        fail("%s: input not supplied: %s" % (where, ", ".join(names)))


def kustomize_build(directory, patches=None):
    """Builds directory as Argo CD does: Application patches appended to the
    kustomization's own patches, in a copy of the tree."""
    work = tempfile.mkdtemp(prefix="inputs-test-")
    try:
        copy = os.path.join(work, "tree")
        shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", ".worktrees"))
        target = os.path.join(copy, rel(directory))
        kfile = os.path.join(target, "kustomization.yaml")
        if patches:
            with open(kfile) as handle:
                kustomization = yaml.safe_load(handle)
            kustomization["patches"] = (kustomization.get("patches") or []) + patches
            with open(kfile, "w") as handle:
                yaml.safe_dump(kustomization, handle, sort_keys=False)
        result = subprocess.run(["kustomize", "build", target], capture_output=True, text=True)
        if result.returncode != 0:
            return None, result.stderr.strip()
        return result.stdout, None
    finally:
        shutil.rmtree(work, ignore_errors=True)


def read_directory(directory, recurse):
    texts = []
    for base, subdirs, files in os.walk(directory):
        if not recurse:
            subdirs[:] = []
        for name in sorted(files):
            if name.endswith((".yaml", ".yml", ".json")):
                with open(os.path.join(base, name)) as handle:
                    texts.append(handle.read())
    return "\n---\n".join(texts)


def component_files():
    paths = sorted(
        os.path.join("apps", name, "application.yaml")
        for name in os.listdir(os.path.join(ROOT, "apps"))
        if os.path.isfile(os.path.join(ROOT, "apps", name, "application.yaml"))
    )
    # Components one level deeper, such as apps/object-storage/<option>.
    for name in sorted(os.listdir(os.path.join(ROOT, "apps"))):
        group = os.path.join(ROOT, "apps", name)
        if os.path.isdir(group) and not os.path.isfile(os.path.join(group, "application.yaml")):
            for option in sorted(os.listdir(group)):
                if os.path.isfile(os.path.join(group, option, "application.yaml")):
                    paths.append(os.path.join("apps", name, option, "application.yaml"))
    paths.append(os.path.join("cluster-config", "application.yaml"))
    return paths


def check_application(where, app, inputs):
    """One Application's sources, and what each library source renders."""
    scan_text(where, yaml.safe_dump(app))
    for index, source in enumerate(sources_of(app.get("spec", {}))):
        source_where = "%s source %d" % (where, index)
        kind = check_repo(source_where, source.get("repoURL", ""), source.get("targetRevision"), inputs)
        if kind != "library" or not source.get("path"):
            continue
        directory = os.path.join(ROOT, source["path"])
        if not os.path.isdir(directory):
            fail("%s: library path %s does not exist" % (source_where, source["path"]))
            continue
        if os.path.isfile(os.path.join(directory, "Chart.yaml")):
            continue
        kustomize = source.get("kustomize")
        if os.path.isfile(os.path.join(directory, "kustomization.yaml")):
            if "directory" in source:
                fail("%s: a kustomize source can't use directory include or exclude" % source_where)
            output, error = kustomize_build(directory, (kustomize or {}).get("patches"))
            if error:
                fail("%s: kustomize build %s failed: %s" % (source_where, source["path"], error.splitlines()[-1]))
                continue
        else:
            if kustomize:
                fail("%s: kustomize options on %s, which has no kustomization.yaml" % (source_where, source["path"]))
            output = read_directory(directory, (source.get("directory") or {}).get("recurse", False))
        scan_text("%s (%s)" % (source_where, source["path"]), output)
        check_nested("%s (%s)" % (source_where, source["path"]), list(yaml.safe_load_all(output)), inputs)


@check("components")
def components(inputs):
    for path in component_files():
        with open(os.path.join(ROOT, path)) as handle:
            text = substitute(handle.read(), inputs)
        check_application(path, yaml.safe_load(text), inputs)


ROOT_APPSET = os.path.join("bootstrap", "hub", "applicationset.yaml")
ODF = os.path.join("apps", "odf", "application.yaml")


def load_root():
    with open(os.path.join(ROOT, ROOT_APPSET)) as handle:
        return yaml.safe_load(handle)


def check_generator(where, git, inputs):
    if git.get("repoURL") != "REQUIRED-libraryRepoURL" or git.get("revision") != "REQUIRED-libraryRevision":
        fail("%s: repoURL and revision must be REQUIRED-libraryRepoURL and REQUIRED-libraryRevision" % where)
    values = git.get("values") or {}
    if set(values) != set(inputs):
        fail("%s: values keys %s, not the inputs %s" % (where, sorted(values), sorted(inputs)))
    for key, value in values.items():
        if value != "REQUIRED-" + key:
            fail("%s: values.%s is %r, not REQUIRED-%s" % (where, key, value, key))


@check("root")
def root(inputs):
    if os.path.exists(os.path.join(ROOT, "bootstrap", "dedicated-hub", "application.yaml")):
        fail("bootstrap/dedicated-hub/application.yaml still makes the library's root sync itself")
    if not os.path.isfile(os.path.join(ROOT, ROOT_APPSET)):
        fail("%s is missing" % ROOT_APPSET)
        return
    with open(os.path.join(ROOT, "bootstrap", "hub", "kustomization.yaml")) as handle:
        if "applicationset.yaml" not in (yaml.safe_load(handle).get("resources") or []):
            fail("bootstrap/hub/kustomization.yaml does not list applicationset.yaml")
    generators = load_root()["spec"]["generators"]
    first = generators[0]["git"]
    check_generator("generator 0", first, inputs)
    listed = {item["path"] for item in first.get("files", [])}
    expected = set(component_files()) - {ODF}
    if listed != expected:
        fail("generator 0 files: missing %s, extra %s" % (sorted(expected - listed), sorted(listed - expected)))
    odf = generators[1]["matrix"]["generators"][0]["git"]
    check_generator("generator 1 (ODF)", odf, inputs)
    if [item["path"] for item in odf.get("files", [])] != [ODF]:
        fail("generator 1 must list only %s" % ODF)


def template_patch_renderer():
    """Builds tests/library/templatepatch, which renders a templatePatch as the
    ApplicationSet controller does. None if Go isn't installed."""
    if not shutil.which("go"):
        return None
    out = os.path.join(tempfile.mkdtemp(prefix="templatepatch-"), "templatepatch")
    source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templatepatch")
    env = dict(os.environ, GOFLAGS="-mod=mod")
    result = subprocess.run(["go", "build", "-o", out, "."], cwd=source, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        fail("go build tests/library/templatepatch: %s" % result.stderr.strip())
        return None
    return out


def render_patch(renderer, appset, params):
    request = {"templatePatch": appset["spec"]["templatePatch"],
               "options": appset["spec"].get("goTemplateOptions", []), "params": params}
    result = subprocess.run([renderer], input=json.dumps(request), capture_output=True, text=True)
    if result.returncode != 0:
        return None, result.stderr.strip()
    return yaml.safe_load(result.stdout), None


def root_params(path, values):
    with open(os.path.join(ROOT, path)) as handle:
        params = yaml.safe_load(handle)
    if path == ODF:
        # The matrix's clusters generator adds the hub's labels.
        params["metadata"]["labels"] = {"openshiftVersion-major-minor": "4.21"}
    params["path"] = {"path": os.path.dirname(path), "filename": os.path.basename(path)}
    params["values"] = dict(values)
    return params


@check("root-render")
def root_render(inputs):
    if not os.path.isfile(os.path.join(ROOT, ROOT_APPSET)):
        fail("%s is missing" % ROOT_APPSET)
        return
    renderer = template_patch_renderer()
    if renderer is None:
        if not failures or "go build" not in failures[-1]:
            print("          (skipped: go is not installed)")
        return
    appset = load_root()
    first = appset["spec"]["generators"][0]["git"]
    paths = [item["path"] for item in first["files"]] + [ODF]
    for path in paths:
        patch, error = render_patch(renderer, appset, root_params(path, inputs))
        if error:
            fail("%s: templatePatch failed: %s" % (path, error))
            continue
        check_application("%s through the root" % path, {"spec": patch["spec"]}, inputs)
    # A deployment that leaves out an input, or leaves its REQUIRED- default,
    # gets an error naming it and no Application.
    for name, values in (("left out", {k: v for k, v in inputs.items() if k != "libraryRevision"}),
                         ("not set", dict(inputs, libraryRevision="REQUIRED-libraryRevision"))):
        _, error = render_patch(renderer, appset, root_params("apps/acm/application.yaml", values))
        if not error or "missing input: libraryRevision" not in error:
            fail("an input %s must fail with 'missing input: libraryRevision', got %r" % (name, error))


@check("bare-inputs")
def bare_inputs():
    found = 0
    for path in library_files(STATIC_DIRS):
        if os.path.basename(path) != "inputs.yaml":
            continue
        found += 1
        directory = os.path.dirname(path)
        output, error = kustomize_build(directory)
        if error:
            fail("%s: kustomize build failed: %s" % (rel(directory), error.splitlines()[-1]))
        elif "REQUIRED-" not in output:
            fail("%s: a bare build shows no REQUIRED- input" % rel(directory))
    if not found:
        fail("no directory declares its inputs (inputs.yaml)")


def main():
    inputs = load_inputs()
    static_revision()
    static_catalog()
    components(inputs)
    bare_inputs()
    root(inputs)
    root_render(inputs)
    failed = sum(1 for _, ok in results if not ok)
    print("inputs tests: %d ok, %d failed" % (len(results) - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
