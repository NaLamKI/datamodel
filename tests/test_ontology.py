"""Whether the model and the ontology still fit — and where they do not.

Every entity is a class of the ontology and every attribute one of its
properties. The two are maintained in different repositories, so they drift;
these checks catch the drift against the ontology under ontology/, a git
submodule pinned at one commit of the ontology's repository.

A difference the Recommendation settles is not an error of the model: it is
listed in model/divergences.yaml. The checks demand that the list is exactly
right — a new difference fails, and so does one fixed upstream but still
listed.
"""
from __future__ import annotations

from rdflib import URIRef
from rdflib.namespace import SKOS

from model import ONTOLOGY

XSD = "http://www.w3.org/2001/XMLSchema#"
AGFODA = "https://w3id.org/agrifooddata/term/"
RDF_JSON = "http://www.w3.org/1999/02/22-rdf-syntax-ns#JSON"
CONCEPT = str(SKOS.Concept)

# Decimal and geometry have datatypes of the ontology's own: each the union of
# what JSON-LD makes of the value (xsd:double for a number with a fraction,
# rdf:JSON for an embedded GeoJSON object) and what the ontology names it
# (xsd:decimal, geo:geoJSONLiteral). A range of the latter alone made every
# such value a contradiction.
RANGES = {
    "String": {XSD + "string"}, "Integer": {XSD + "integer"},
    "Decimal": {AGFODA + "Decimal"}, "Boolean": {XSD + "boolean"},
    "Date": {XSD + "date"}, "DateTime": {XSD + "dateTime"},
    "JSON": {RDF_JSON, AGFODA + "GeoJSON"},
}


def test_the_ontology_is_the_commit_this_repository_pins():
    """ontology/ is a git submodule. The model is checked against the one
    commit of the ontology this repository records — not against whatever
    happens to be checked out there, and not against a file edited in it.
    Either would check the model against something no commit names."""
    import subprocess

    root = ONTOLOGY.parent
    status = subprocess.run(["git", "submodule", "status", "ontology"], cwd=root,
                            capture_output=True, text=True).stdout
    assert status.startswith(" "), (
        f"ontology/ is not at the commit recorded here: {status.strip()!r} – "
        "run `git submodule update --init`, or commit the new pointer")
    edited = subprocess.run(["git", "-C", str(ONTOLOGY), "status", "--porcelain"],
                            capture_output=True, text=True).stdout.strip()
    assert not edited, f"ontology/ has local changes: {edited[:200]}"


def test_every_entity_is_a_class_of_the_ontology(model, ontology):
    missing = [e.name for e in model.ordered() if e.name not in ontology.classes]
    assert not missing


def test_every_enumeration_is_a_class_with_the_same_values(model, ontology):
    wrong = []
    for name, enum in model.enumerations.items():
        if name not in ontology.enumerations:
            wrong.append(f"{name}: not an enumeration of the ontology")
        elif sorted(enum["values"]) != ontology.individuals(name):
            wrong.append(f"{name}: {sorted(enum['values'])} != {ontology.individuals(name)}")
    assert not wrong


def test_every_attribute_maps_onto_a_declared_property(model, ontology):
    missing = [f"{e.name}.{a.name} -> agfoda:{a.term}" for e in model.ordered()
               for a in e.attributes.values() if a.term not in ontology.properties]
    assert not missing


def test_the_ranges_fit_the_types(model, ontology):
    """A reference is an object property onto the entity it names, an
    enumeration one onto its class, a classification one onto skos:Concept;
    everything else a datatype property of the matching datatype."""
    wrong = []
    for e in model.ordered():
        for a in e.attributes.values():
            p = ontology.properties[a.term]
            rng = p["range"] or ""
            where = f"{e.name}.{a.name} ({a.type}) -> {rng}"
            if a.references:
                ok = p["kind"] == "object" and rng == str(ontology.iri(a.references))
            elif a.type == "UUID":
                ok = p["kind"] == "datatype" and rng == XSD + "string"
            elif a.type == "Enum":
                ok = p["kind"] == "object" and rng == str(ontology.iri(a.enum))
            elif a.concept:
                ok = p["kind"] == "object" and rng == CONCEPT
            else:
                ok = p["kind"] == "datatype" and rng in RANGES[a.type]
            if not ok:
                wrong.append(where)
    assert not wrong


def test_mandatory_attributes_are_the_ontologys_minimum_cardinalities(model, ontology):
    wrong = []
    for e in model.ordered():
        mandatory = ontology.mandatory.get(e.name, set()) | ontology.mandatory.get(
            "EntityBase", set())
        for a in e.attributes.values():
            if a.required != (a.term in mandatory):
                wrong.append(f"{e.name}.{a.name}: model {'M' if a.required else 'O'}")
    assert not wrong


def _domain_gaps(model, ontology) -> set[tuple[str, str]]:
    gaps = set()
    for e in model.ordered():
        for a in e.own.values():
            if e.name not in ontology.properties[a.term]["domain"]:
                gaps.add((e.name, a.term))
    return gaps


def _listed(model, kind: str) -> set[tuple[str, str]]:
    return {(cls, d["property"]) for d in model.divergences["ontology"]
            if d["kind"] == kind for cls in d["classes"]}


def test_the_domains_hold_except_where_listed(model, ontology):
    """An attribute outside its property's domain makes a reasoner classify
    the record as something it is not; with disjoint classes, the data become
    inconsistent. Each such gap is a divergence of kind `domain`."""
    assert _domain_gaps(model, ontology) == _listed(model, "domain")


def test_the_system_attributes_sit_on_entitybase(model, ontology):
    for a in model.base.values():
        assert "EntityBase" in ontology.properties[a.term]["domain"], a.name


def test_lists_are_not_functional_except_where_listed(model, ontology):
    """A list of values on an owl:FunctionalProperty lets a reasoner conclude
    that the values are one and the same."""
    clash = {(e.name, a.term) for e in model.ordered() for a in e.attributes.values()
             if a.multivalued and ontology.properties[a.term]["functional"]}
    assert clash == _listed(model, "multiplicity")


def test_several_schemes_are_bound_as_alternatives(ontology):
    """Where several schemes supply one property — an observation's observed
    property is a measured quantity, a pest or a soil property — the shapes and
    the schemas take the value from any one of them. That is the ontology's
    reading only while it states one restriction over their union: separate
    restrictions intersect, and the model would diverge again (formerly O6)."""
    assert len(ontology.bindings[("Observation", "observedPropertyUri")]) == 3
    assert not ontology.intersecting, sorted(ontology.intersecting)


def test_divergence_o10_holds_in_part(ontology):
    """Clause 7.2 admits the ontology's own schemes alongside AGROVOC provided
    their concepts are mapped to AGROVOC. The ontology maps crops and pests in
    part (links/agrovoc.ttl) and phenology not at all. Once every concept in
    use is mapped, this fails — and O10 is to go."""
    from rdflib import Literal
    from rdflib.namespace import OWL

    agrovoc = "http://aims.fao.org/aos/agrovoc/"
    mapped = {s for p in (SKOS.exactMatch, SKOS.closeMatch, SKOS.broadMatch)
              for s, o in ontology.links.subject_objects(p) if str(o).startswith(agrovoc)}
    unmapped = {}
    for scheme in ("crops", "pests", "phenology"):
        iri = URIRef(f"https://w3id.org/agrifooddata/{scheme}")
        in_use = {c for c in ontology.schemes.subjects(SKOS.inScheme, iri)
                  if (c, OWL.deprecated, Literal(True)) not in ontology.schemes}
        unmapped[scheme] = len(in_use - mapped)
    assert mapped, "no mapping onto AGROVOC – does the ontology still publish links/agrovoc.ttl?"
    assert any(unmapped.values()), "every concept is mapped – revisit divergence O10"


def test_every_divergence_names_something_that_exists(model, ontology):
    ids = [d["id"] for part in model.divergences.values() for d in part]
    assert len(ids) == len(set(ids))
    for d in model.divergences["ontology"]:
        prop = d.get("property", "")
        if prop and not prop.startswith("("):
            assert prop in ontology.properties, d["id"]
        for cls in d.get("classes", []):
            assert cls in model.entities, d["id"]


def test_every_bound_scheme_is_published(ontology):
    files = {p.stem for p in (ONTOLOGY / "docs").glob("*.ttl")}
    schemes = {s.rsplit("/", 1)[-1] for v in ontology.bindings.values() for s in v}
    schemes |= {s.rsplit("/", 1)[-1] for s in ontology.notation_from.values()}
    assert schemes <= files


def test_the_bindings_name_attributes_of_the_model(model, ontology):
    """A binding on a class and property the model does not pair would be a
    constraint nothing in the data can meet."""
    pairs = {(e.name, a.term) for e in model.ordered() for a in e.attributes.values()}
    assert set(ontology.bindings) <= pairs


def test_every_concept_the_rules_name_exists(model, ontology):
    for rid, rule in model.rules.items():
        for ref in (rule.get("concepts") or {}).values():
            assert ontology.concept(**ref), rid
