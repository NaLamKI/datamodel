#!/usr/bin/env python3
"""Build `docs/` in full — what GitHub Pages serves.

    python3 tool/build.py

Everything under docs/ is generated from model/, ontology/, examples/ and
BINDINGS.md, and the directory is wiped on every run. CI builds it and then
demands `git diff --exit-code`: a hand-edited file, or a change to the model
without a rebuild, shows up there. That only works if the build is
byte-for-byte reproducible, so nothing here depends on the time, the machine
or the order of a set.

    docs/
      index.html, style.css, CNAME, .nojekyll, repo/
      v1/
        index.html, <Entity>.html, api.html, rules.html, enumerations.html,
        bindings.html, divergences.html, problems/<type>.html
        openapi.yaml, openapi.json      the REST binding (OpenAPI 3.1)
        schema/<Entity>.json            JSON Schema 2020-12
        context.jsonld                  JSON-LD 1.1 context
        shapes.ttl, shapes-dataset.ttl  SHACL
        model.json                      the model in one document
        examples/<Entity>.json          the example dataset
"""
from __future__ import annotations

import json
import shutil
import sys
from urllib.parse import urlsplit

import yaml

from model import DOCS, EXAMPLES, ROOT, Model, Ontology, json_text, text
import context
import openapi
import pages
import schemas
import shapes
from page import CSS


class _Dumper(yaml.SafeDumper):
    """No anchors, and multi-line strings as literal blocks."""

    def ignore_aliases(self, data):
        return True


def _str(dumper: yaml.SafeDumper, value: str):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str)


def yaml_text(value) -> str:
    return yaml.dump(value, Dumper=_Dumper, sort_keys=False, allow_unicode=True,
                     width=100, default_flow_style=False)


def model_document(model: Model, ontology: Ontology) -> dict:
    """The whole model in one JSON document, for generators of all kinds."""
    def attribute(entity: str, a) -> dict:
        out = {"name": a.name, "type": a.type, "required": a.required,
               "description": text(a.description)}
        if a.note:
            out["note"] = text(a.note)
        out["property"] = f"{model.ns}{a.term}"
        for key in ("references", "referencesBy", "enum", "format", "default",
                    "geometry", "json", "source"):
            value = getattr(a, key)
            if value is not None:
                out[key] = value
        for key in ("concept", "positive", "entityName", "thingDescription",
                    "readOnly", "immutable"):
            if getattr(a, key):
                out[key] = True
        schemes_ = ontology.bindings.get((entity, a.term))
        if schemes_:
            out["schemes"] = schemes_
        if a.term in ontology.notation_from:
            out["notationFrom"] = ontology.notation_from[a.term]
        if a.inherited:
            out["inherited"] = True
        return out

    def constraint(c) -> dict:
        out = {"kind": c.kind}
        if c.members:
            out["attributes"] = c.members
        if c.attribute:
            out["attribute"] = c.attribute
            out["when"] = c.when
        out["level"] = c.level
        if c.rule:
            out["rule"] = c.rule
        if c.source:
            out["source"] = c.source
        out["text"] = c.describe()
        return out

    entities = {}
    for e in model.ordered():
        entities[e.name] = {
            "package": e.package, "annex": e.annex, "path": f"/{e.path}",
            "class": f"{model.ns}{e.name}",
            "schema": f"{model.base_url}schema/{e.name}.json",
            "definition": e.definition,
            "attributes": [attribute(e.name, a) for a in e.attributes.values()],
            "constraints": [constraint(c) for c in e.all_constraints],
        }
        if e.systemManaged:
            entities[e.name]["systemManaged"] = True
        if e.name in model.states:
            entities[e.name]["states"] = model.states[e.name]
    meta = model.meta
    return {
        "id": meta["id"], "title": meta["title"], "version": model.version,
        "description": text(meta["description"]),
        "home": model.base_url, "repository": meta["repository"],
        "license": meta["license"]["url"],
        "recommendation": {k: text(str(v)) for k, v in meta["recommendation"].items()},
        "ontology": dict(meta["ontology"], snapshot={
            k: ontology.snapshot[k] for k in ("source", "commit", "version")}),
        "iri": model.iri,
        "conventions": [{"id": c["id"], "title": c["title"], "text": text(c["text"])}
                        for c in meta["conventions"]],
        "packages": [{"id": p.id, "title": p.title, "clause": p.clause,
                      "scope": p.scope, "summary": p.summary, "notes": p.notes,
                      "entities": p.entities} for p in model.packages],
        "entities": entities,
        "enumerations": {n: {"description": text(e["description"]),
                             "class": f"{model.ns}{n}",
                             "values": e["values"]}
                         for n, e in model.enumerations.items()},
        "rules": {rid: {k: (text(v) if isinstance(v, str) else v)
                        for k, v in r.items()} for rid, r in model.rules.items()},
        "businessKeys": model.business_keys,
        "derivedViews": [{k: (text(v) if isinstance(v, str) else v)
                          for k, v in v_.items()} for v_ in model.derived_views],
        "divergences": {part: [{k: (text(v) if isinstance(v, str) else v)
                                for k, v in d.items()} for d in items]
                        for part, items in model.divergences.items()},
    }


def write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    model = Model()
    problems = model.problems()
    if problems:
        print("The model does not hold together:\n  " + "\n  ".join(problems),
              file=sys.stderr)
        return 1
    ontology = Ontology(ns=model.ns)

    if DOCS.exists():
        shutil.rmtree(DOCS)
    v = DOCS / model.major
    v.mkdir(parents=True)

    # What GitHub Pages needs and what is not derived from the model. Without
    # .nojekyll, Jekyll would swallow anything starting with an underscore.
    write(DOCS / ".nojekyll", "")
    write(DOCS / "CNAME", urlsplit(model.home).netloc + "\n")
    write(DOCS / "style.css", CSS)
    write(DOCS / "index.html", pages.root_index(model))
    write(DOCS / "repo" / "index.html",
          pages.redirect(model.meta["repository"], "Source and history"))

    # JSON Schema.
    files = schemas.standalone(model, ontology)
    for name, schema in files.items():
        write(v / "schema" / name, json_text(schema))
    write(v / "schema" / "index.html",
          pages.listing(model, "JSON Schema", sorted(files), "../"))

    # OpenAPI.
    doc = openapi.build(model, ontology)
    write(v / "openapi.json", json_text(doc))
    write(v / "openapi.yaml", yaml_text(doc))

    # JSON-LD and SHACL.
    write(v / "context.jsonld", json_text(context.build(model)))
    write(v / "shapes.ttl", shapes.record_shapes(model, ontology))
    write(v / "shapes-dataset.ttl", shapes.dataset_shapes(model, ontology))

    # The model in one document.
    write(v / "model.json", json_text(model_document(model, ontology)))

    # Examples, as they are.
    examples = {}
    for e in model.ordered():
        source = EXAMPLES / f"{e.name}.json"
        records = json.loads(source.read_text(encoding="utf-8")) if source.exists() else []
        examples[e.name] = records
        if records:
            write(v / "examples" / source.name, source.read_text(encoding="utf-8"))
    write(v / "examples" / "index.html", pages.listing(
        model, "Examples", [f"{n}.json" for n, r in examples.items() if r], "../"))

    # Pages.
    write(v / "index.html", pages.version_index(model, ontology))
    for e in model.ordered():
        write(v / f"{e.name}.html", pages.entity_page(model, ontology, e, examples[e.name]))
    write(v / "api.html", pages.api_page(model, doc))
    write(v / "rules.html", pages.rules_page(model))
    write(v / "enumerations.html", pages.enumerations_page(model, ontology))
    write(v / "divergences.html", pages.divergences_page(model, ontology))
    write(v / "bindings.html", pages.markdown_page(
        model, "Bindings", (ROOT / "BINDINGS.md").read_text(encoding="utf-8")))
    for slug, status, title, body in openapi.PROBLEMS:
        write(v / "problems" / f"{slug}.html",
              pages.problem_page(model, slug, status, title, body))

    count = sum(1 for p in DOCS.rglob("*") if p.is_file())
    print(f"{len(model.entities)} entities, {sum(len(r) for r in examples.values())} "
          f"example records, {count} files -> {DOCS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
