"""Shared access to the model, the ontology and the examples — read once.

The checks run without network access. Everything they need is in the
repository: the model under model/, the ontology under ontology/ (a git
submodule), the example dataset under examples/. The JSON-LD context and the shapes are
built in memory from the model, not read from docs/, so that a check of the
model does not depend on a build having been run; tests/test_docs.py checks
the published files separately.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tool"))

from model import EXAMPLES, Model, Ontology  # noqa: E402


@pytest.fixture(scope="session")
def model() -> Model:
    return Model()


@pytest.fixture(scope="session")
def ontology(model) -> Ontology:
    return Ontology(ns=model.ns)


@pytest.fixture(scope="session")
def examples(model) -> dict[str, list[dict]]:
    """Entity -> its example records."""
    out = {}
    for e in model.ordered():
        path = EXAMPLES / f"{e.name}.json"
        out[e.name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return out


@pytest.fixture(scope="session")
def records(model, examples) -> dict[str, tuple[str, dict]]:
    """id -> (entity, record), across the whole example dataset."""
    out = {}
    for name, recs in examples.items():
        for r in recs:
            out[r["id"]] = (name, r)
    return out


@pytest.fixture(scope="session")
def context_document(model) -> dict:
    import context
    return context.build(model)


@pytest.fixture(scope="session")
def standalone_schemas(model, ontology) -> dict[str, dict]:
    import schemas
    return schemas.standalone(model, ontology)


@pytest.fixture(scope="session")
def validator_for(standalone_schemas):
    """Entity name -> a JSON Schema validator that resolves its references
    offline, against the schemas as generated."""
    from jsonschema import Draft202012Validator, FormatChecker
    from referencing import Registry, Resource

    registry = Registry().with_resources(
        (s["$id"], Resource.from_contents(s)) for s in standalone_schemas.values())

    def make(name: str):
        return Draft202012Validator(standalone_schemas[f"{name}.json"],
                                    registry=registry,
                                    format_checker=FormatChecker())
    return make


@pytest.fixture(scope="session")
def dataset_graph(model, examples, context_document):
    """The example dataset as RDF, read with the context (pyld)."""
    from pyld import jsonld
    from rdflib import Graph

    import context

    g = Graph(bind_namespaces="none")
    for e in model.ordered():
        for rec in examples[e.name]:
            doc = context.representation(model, e, rec,
                                         context=context_document["@context"])
            g.parse(data=jsonld.to_rdf(doc, {"format": "application/n-quads"}),
                    format="nt")
    return g
