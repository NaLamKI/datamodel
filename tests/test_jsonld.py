"""Whether the JSON-LD context reads the JSON as the ontology means it.

The strongest check is the synthetic one: a record of every entity with every
attribute set, expanded, must produce exactly the ontology property each
attribute maps onto — for all of them, not only for those the examples
happen to use. The example dataset then shows that real records land on
declared properties only, and that references meet the records they name.
"""
from __future__ import annotations

import json

import pytest
from pyld import jsonld
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

import context

UUID = "0f0e0d0c-0b0a-4908-8706-050403020100"
SAMPLE = {"Integer": 1, "Decimal": 1.5, "Boolean": True, "Date": "2026-01-01",
          "DateTime": "2026-01-01T00:00:00Z", "String": "x"}


def _value(model, ontology, entity, a):
    if a.type == "UUID":
        return UUID
    if a.type == "Enum":
        return model.enum_values(a.enum)[0]
    if a.multivalued:
        return ["https://example.org/a", "https://example.org/b"]
    if a.concept:
        return "https://example.org/concept"
    if a.type == "JSON":
        return {"type": "Point", "coordinates": [13.4, 52.5]} if a.geometry else {"k": "v"}
    return SAMPLE[a.type]


def _expand(doc) -> Graph:
    g = Graph(bind_namespaces="none")
    g.parse(data=jsonld.to_rdf(doc, {"format": "application/n-quads"}), format="nt")
    return g


def test_the_context_is_json_ld_1_1_on_the_ontology(model, context_document):
    ctx = context_document["@context"]
    assert ctx["@version"] == 1.1
    assert ctx["@vocab"] == model.ns


def test_the_context_uses_only_terms_the_ontology_declares(model, ontology, context_document):
    """Every `agfoda:` IRI in the context is a declared class or property."""
    found = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "@id" and isinstance(v, str) and v.startswith("agfoda:"):
                    found.add(v[len("agfoda:"):])
                walk(v)
        elif isinstance(node, str) and node.startswith("agfoda:"):
            found.add(node[len("agfoda:"):])
    walk(context_document["@context"])
    unknown = found - set(ontology.properties) - ontology.classes
    assert not unknown


@pytest.mark.parametrize("name", [
    "Organization", "User", "Worker", "Address", "Role", "AccessAssignment", "Farm",
    "Site", "Field", "Region", "CroppingPlan", "CroppingPlanEntry", "Stand",
    "CultivationPeriod", "Task", "Activity", "ActivityResource", "TimeRecord", "Product",
    "StorageLocation", "Lot", "StockMovement", "Machine", "MaintenanceRecord", "Animal",
    "AnimalGroup", "AnimalEvent", "FeedRation", "FeedRationComponent", "Device",
    "Observation", "Data", "DataType", "File", "InputOutput", "Economics", "Budget",
    "RegulatoryReport", "Certification", "AuditLog", "ServiceCatalogue",
    "ProcessingService", "ProcessingJob", "ProcessingJobInput", "Result",
    "SustainabilityIndicator", "CodeMapping"])
def test_every_attribute_lands_on_its_ontology_property(model, ontology, context_document, name):
    e = model.entities[name]
    record = {a.name: _value(model, ontology, e, a) for a in e.attributes.values()}
    record["id"] = UUID
    doc = context.representation(model, e, record, context=context_document["@context"])
    g = _expand(doc)
    subject = URIRef(model.iri + UUID)
    assert (subject, RDF.type, URIRef(model.ns + name)) in g
    predicates = {p for p in g.predicates(subject, None)} - {RDF.type}
    expected = {URIRef(model.ns + a.term) for a in e.attributes.values()}
    assert predicates == expected, sorted(map(str, predicates ^ expected))
    for a in e.attributes.values():
        objects = list(g.objects(subject, URIRef(model.ns + a.term)))
        if a.references:
            assert objects == [URIRef(model.iri + UUID)], a.name
        elif a.type == "Enum":
            assert objects == [URIRef(f"{model.ns}{a.enum}_{record[a.name]}")], a.name
        elif a.concept:
            assert all(isinstance(o, URIRef) for o in objects) and objects, a.name
            assert len(objects) == (2 if a.multivalued else 1), a.name
        else:
            assert len(objects) == 1 and isinstance(objects[0], Literal), a.name


def test_the_examples_land_on_declared_properties_only(ontology, dataset_graph):
    undeclared = {str(p) for p in dataset_graph.predicates()
                  if p != RDF.type and ontology.local(p) not in ontology.properties}
    assert not undeclared


def test_references_meet_the_records_they_name(model, dataset_graph, records):
    """A foreign key and the record it points at are one node: `urn:uuid:`."""
    typed = {s: o for s, o in dataset_graph.subject_objects(RDF.type)}
    dangling = []
    for e in model.ordered():
        for a in e.attributes.values():
            if not a.references:
                continue
            for s, o in dataset_graph.subject_objects(URIRef(model.ns + a.term)):
                if typed.get(s) != URIRef(model.ns + e.name):
                    continue
                if typed.get(o) != URIRef(model.ns + a.references):
                    dangling.append(f"{e.name}.{a.name} -> {o}")
    assert not dangling


def test_pyld_and_rdflib_read_every_example_alike(model, examples, context_document):
    """Two processors, one meaning. pyld once disagreed on every second
    foreign key (see tool/context.py)."""
    differ = []
    for e in model.ordered():
        for rec in examples[e.name]:
            doc = context.representation(model, e, rec, context=context_document["@context"])
            a = set(_expand(doc))
            b = set(Graph(bind_namespaces="none").parse(data=json.dumps(doc), format="json-ld"))
            if a != b:
                differ.append(f"{e.name} {rec['id']}: {sorted(map(str, a ^ b))[:2]}")
    assert not differ


def test_classifications_are_concepts_of_their_scheme(model, ontology, examples):
    """The values the ontology binds to a scheme come from that scheme."""
    wrong = []
    for e in model.ordered():
        for a in e.attributes.values():
            schemes = set(ontology.bindings.get((e.name, a.term), []))
            if not schemes:
                continue
            for rec in examples[e.name]:
                if a.name in rec and not ontology.in_scheme(rec[a.name]) & schemes:
                    wrong.append(f"{e.name}.{a.name} = {rec[a.name]}")
    assert not wrong


def test_growth_stages_are_notations_of_the_phenology_scheme(ontology, examples):
    notations = ontology.notations(ontology.notation_from["bbchStage"])
    stages = {r["bbchStage"] for r in examples["Activity"] if "bbchStage" in r}
    assert stages and stages <= notations


def test_a_page_of_a_collection_reads_as_rdf(model, examples, context_document):
    """`items` is `@included`; the paging members are not data."""
    e = model.entities["Field"]
    items = [{k: v for k, v in context.representation(model, e, r).items()
              if k != "@context"} for r in examples["Field"]]
    page = {"@context": context_document["@context"], "items": items,
            "nextCursor": "opaque", "hasMore": False}
    g = _expand(page)
    subjects = set(g.subjects(RDF.type, URIRef(model.ns + "Field")))
    assert subjects == {URIRef(model.iri + r["id"]) for r in examples["Field"]}
    assert not any("nextCursor" in str(p) or "hasMore" in str(p) for p in g.predicates())
