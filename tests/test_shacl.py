"""Whether the SHACL shapes accept the example dataset and catch what they
are meant to catch.

As for the JSON Schemas: a shape that accepts everything proves nothing. Each
negative check breaks one record of the example dataset the way a rule
forbids and demands a result naming that rule.
"""
from __future__ import annotations

import copy

import pytest
from pyld import jsonld
from pyshacl import validate
from rdflib import Graph, Literal, URIRef

import context
import shapes


@pytest.fixture(scope="session")
def record_shapes(model, ontology) -> Graph:
    return Graph().parse(data=shapes.record_shapes(model, ontology), format="turtle")


@pytest.fixture(scope="session")
def dataset_shapes(model, ontology) -> Graph:
    return Graph().parse(data=shapes.dataset_shapes(model, ontology), format="turtle")


def _graph(model, examples, context_document) -> Graph:
    g = Graph(bind_namespaces="none")
    for e in model.ordered():
        for rec in examples[e.name]:
            doc = context.representation(model, e, rec, context=context_document["@context"])
            g.parse(data=jsonld.to_rdf(doc, {"format": "application/n-quads"}), format="nt")
    return g


def _results(data: Graph, shapes_graph: Graph) -> tuple[list[str], list[str]]:
    """(violations, warnings), each as the messages of the results."""
    _, report, _ = validate(data, shacl_graph=shapes_graph, advanced=True)
    q = """
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        SELECT ?severity ?message WHERE {
            ?r a sh:ValidationResult ; sh:resultSeverity ?severity .
            OPTIONAL { ?r sh:resultMessage ?message }
        }"""
    violations, warnings = [], []
    for severity, message in report.query(q):
        (warnings if str(severity).endswith("Warning") else violations).append(str(message))
    return violations, warnings


def _change(examples, entity: str, pick, change) -> dict:
    """A copy of the dataset with one record of `entity` changed: the first
    that has every attribute in `pick`, or for which `pick` holds."""
    out = copy.deepcopy(examples)
    test = pick if callable(pick) else (lambda r: all(k in r for k in pick))
    rec = next(r for r in out[entity] if test(r))
    change(rec, out)
    return out


def test_the_example_dataset_conforms_record_by_record(dataset_graph, record_shapes):
    violations, warnings = _results(dataset_graph, record_shapes)
    assert not violations and not warnings, (violations + warnings)[:5]


def test_the_example_dataset_holds_together(dataset_graph, dataset_shapes, ontology):
    violations, warnings = _results(dataset_graph + ontology.schemes, dataset_shapes)
    assert not violations and not warnings, (violations + warnings)[:5]


# (entity, attributes the record must have, how to break it, what the result names)
RECORD_CASES = [
    ("InputOutput", ["activityId"],
     lambda r, ex: r.update(cultivationPeriodId=r["activityId"]), "V03"),
    ("Activity", ["endsAt"], lambda r, ex: r.update(endsAt="2026-05-12T04:00:00Z"), "V01"),
    ("StockMovement", [], lambda r, ex: r.update(quantity=-5), None),
    ("Task", ["createdByUserId"], lambda r, ex: r.pop("createdByUserId"), "V04"),
    ("Stand", [], lambda r, ex: r.update(clearingDate="2018-01-01"), "V08"),
    ("Lot", ["originCultivationPeriodId"],
     lambda r, ex: r.update(originAnimalGroupId=r["originCultivationPeriodId"]), "V13"),
    ("Product", ["registrationNumber"], lambda r, ex: r.pop("registrationNumber"),
     "registrationNumber"),
]


@pytest.mark.parametrize("entity,needs,change,expect", RECORD_CASES,
                         ids=[f"{e} {x or 'V02'}" for e, _, _, x in RECORD_CASES])
def test_the_record_shapes_catch(model, examples, context_document, record_shapes,
                                 entity, needs, change, expect):
    data = _graph(model, _change(examples, entity, needs, change), context_document)
    violations, _ = _results(data, record_shapes)
    assert violations, "nothing caught"
    if expect:
        assert any(expect in v for v in violations), violations[:3]


def test_a_closed_shape_rejects_an_unknown_property(model, examples, dataset_graph,
                                                   record_shapes):
    data = Graph(bind_namespaces="none") + dataset_graph
    field = URIRef(model.iri + examples["Field"][0]["id"])
    data.add((field, URIRef(model.ns + "colour"), Literal("green")))
    violations, _ = _results(data, record_shapes)
    assert violations


def test_a_should_is_a_warning(model, examples, context_document, record_shapes):
    """A task without operational context: clause 8.5 says "should"."""
    def strip(r, ex):
        for k in ("cultivationPeriodId", "regionId", "siteId", "animalGroupId"):
            r.pop(k, None)
    violations, warnings = _results(
        _graph(model, _change(examples, "Task", [], strip), context_document),
        record_shapes)
    assert not violations and warnings


def _region(ex, name_part: str) -> str:
    return next(r["id"] for r in ex["Region"] if name_part in r["name"])


def _product(ex, category: str) -> str:
    return next(r["id"] for r in ex["Product"] if r["category"] == category)


DATASET_CASES = [
    # The orchard loses its default region.
    ("V05", "Region", lambda r: "Obstwiese" in r["name"],
     lambda r, ex: r.update(typeUri="https://w3id.org/agrifooddata/crops#TRZAW"), "V05"),
    ("V08", "CultivationPeriod", ["standId"],
     lambda r, ex: r.update(regionId=_region(ex, "Nordschlag")), "V08"),
    ("V09", "InputOutput", ["activityId", "lotId"],
     lambda r, ex: r.update(productId=_product(ex, "FERTILIZER")), "V09"),
    ("V07", "CultivationPeriod", ["planEntryId"],
     lambda r, ex: r.update(typeUri="https://w3id.org/agrifooddata/crops#MABSD"), "V07"),
    ("scheme", "CultivationPeriod", ["planEntryId"],
     lambda r, ex: r.update(typeUri="http://aims.fao.org/aos/agrovoc/c_5978"), "scheme"),
    ("notation", "Activity", ["bbchStage"], lambda r, ex: r.update(bbchStage="999"),
     "notation"),
    ("reference", "Task", ["farmId"], lambda r, ex: r.update(farmId=r["id"]),
     "reference points at a record"),
]


@pytest.mark.parametrize("case,entity,pick,change,expect", DATASET_CASES,
                         ids=[c[0] for c in DATASET_CASES])
def test_the_dataset_shapes_catch(model, ontology, examples, context_document,
                                  dataset_shapes, case, entity, pick, change, expect):
    data = _graph(model, _change(examples, entity, pick, change), context_document)
    violations, warnings = _results(data + ontology.schemes, dataset_shapes)
    found = violations + warnings
    assert any(expect in v for v in found), found[:3] or "nothing caught"
