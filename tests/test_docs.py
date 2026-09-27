"""Whether docs/ is what the build makes of the model — and nothing else.

CI rebuilds docs/ and demands `git diff --exit-code`; these checks catch the
same thing locally, and a few the diff cannot: a broken link, a local path
that leaked into a published file, a page for an entity that no longer
exists.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml

from model import DOCS, ROOT, json_text

V1 = DOCS / "v1"

pytestmark = pytest.mark.skipif(not (V1 / "index.html").exists(),
                                reason="docs/ not built – run python3 tool/build.py")


def test_every_artefact_is_published(model):
    expected = ["index.html", "style.css", "CNAME", ".nojekyll", "repo/index.html",
                "v1/index.html", "v1/api.html", "v1/rules.html", "v1/enumerations.html",
                "v1/divergences.html", "v1/bindings.html", "v1/openapi.yaml",
                "v1/openapi.json", "v1/context.jsonld", "v1/shapes.ttl",
                "v1/shapes-dataset.ttl", "v1/model.json", "v1/schema/common.json",
                "v1/schema/enumerations.json", "v1/schema/EntityBase.json"]
    for e in model.ordered():
        expected += [f"v1/{e.name}.html", f"v1/schema/{e.name}.json",
                     f"v1/examples/{e.name}.json"]
    missing = [p for p in expected if not (DOCS / p).exists()]
    assert not missing


def test_nothing_is_published_that_the_model_does_not_know(model):
    """A page for an entity that was renamed would keep a dead name alive."""
    pages = {p.stem for p in V1.glob("*.html")} - {
        "index", "api", "rules", "enumerations", "divergences", "bindings"}
    assert pages == set(model.entities)


def test_the_published_schemas_are_the_generated_ones(standalone_schemas):
    for name, schema in standalone_schemas.items():
        assert (V1 / "schema" / name).read_text(encoding="utf-8") == json_text(schema), name


def test_the_published_context_is_the_generated_one(context_document):
    assert json.loads((V1 / "context.jsonld").read_text(encoding="utf-8")) == context_document


def test_openapi_yaml_and_json_say_the_same():
    as_json = json.loads((V1 / "openapi.json").read_text(encoding="utf-8"))
    as_yaml = yaml.safe_load((V1 / "openapi.yaml").read_text(encoding="utf-8"))
    assert as_json == as_yaml


def test_the_examples_are_published_as_they_are():
    for source in (ROOT / "examples").glob("*.json"):
        assert (V1 / "examples" / source.name).read_bytes() == source.read_bytes()


def test_the_shapes_parse_and_carry_the_version(model):
    from rdflib import Graph, Literal
    from rdflib.namespace import OWL
    for name in ("shapes.ttl", "shapes-dataset.ttl"):
        g = Graph().parse(V1 / name, format="turtle")
        assert (None, OWL.versionInfo, Literal(model.version)) in g, name


def test_model_json_describes_every_entity(model):
    doc = json.loads((V1 / "model.json").read_text(encoding="utf-8"))
    assert doc["version"] == model.version
    assert list(doc["entities"]) == [e.name for e in model.ordered()]


def test_the_custom_domain_is_the_home(model):
    assert (DOCS / "CNAME").read_text(encoding="utf-8").strip() == urlsplit(model.home).netloc


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("href", "src") and v:
                self.links.append(v)
            if k == "id" and v:
                self.ids.add(v)


def _parse(path: Path) -> _Links:
    p = _Links()
    p.feed(path.read_text(encoding="utf-8"))
    return p


def test_every_local_link_resolves():
    """A link into the site points at a file that exists — and, with a
    fragment, at an anchor on that page."""
    broken = []
    for page in DOCS.rglob("*.html"):
        for link in _parse(page).links:
            parts = urlsplit(link)
            if parts.scheme or link.startswith("//") or link.startswith("mailto:"):
                continue
            target = (page.parent / parts.path).resolve() if parts.path else page
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                broken.append(f"{page.relative_to(DOCS)} -> {link}")
            elif parts.fragment and target.suffix == ".html":
                if parts.fragment not in _parse(target).ids:
                    broken.append(f"{page.relative_to(DOCS)} -> {link} (no anchor)")
    assert not broken, broken[:10]


def test_no_local_path_leaked():
    """A build run on somebody's machine must not publish that machine."""
    leaked = []
    for path in DOCS.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if re.search(r"/Users/|/home/[a-z]|file://|[A-Z]:\\\\", text):
                leaked.append(str(path.relative_to(DOCS)))
    assert not leaked


def test_the_bindings_table_is_the_model(model):
    """BINDINGS.md lists where attribute and property names differ. The table
    is written out for readers on GitHub; this check keeps it true."""
    text = (ROOT / "BINDINGS.md").read_text(encoding="utf-8")
    listed = set()
    for name, on, prop in re.findall(r"^\| `(\w+)` \| ([^|]+) \| `agfoda:(\w+)` \|$",
                                     text, re.M):
        for entity in [e.strip() for e in on.split(",")]:
            listed.add((name, entity, prop))
    actual = set()
    every = len(model.entities)
    renamed: dict[tuple[str, str], list[str]] = {}
    for e in model.ordered():
        for a in e.attributes.values():
            if a.term != a.name:
                renamed.setdefault((a.name, a.term), []).append(e.name)
    for (name, term), entities in renamed.items():
        for entity in (["every entity"] if len(entities) == every else entities):
            actual.add((name, entity, term))
    assert listed == actual


def test_every_term_link_names_a_term_of_the_ontology(ontology):
    """The pages link each class, property and enumeration value to its row
    on the ontology's schema page, which carries an anchor for every term it
    declares. A link to a name the ontology does not declare lands at the top
    of a long page instead."""
    from rdflib import URIRef

    declared = {ontology.local(s) for s in ontology.graph.subjects()
                if isinstance(s, URIRef) and str(s).startswith(ontology.ns)}
    linked = set()
    for page in DOCS.rglob("*.html"):
        linked |= set(re.findall(r'https://ontology\.agrifooddata\.org/term\.html#([^"]+)"',
                                 page.read_text(encoding="utf-8")))
    assert linked, "no term linked – was docs/ built?"
    assert not linked - declared, sorted(linked - declared)[:8]
