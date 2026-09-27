"""The JSON-LD 1.1 context: the canonical JSON, read as RDF (clause 9).

Every attribute lands on the property of the ontology it corresponds to —
not on a look-alike from another vocabulary — so that the data meet the
ontology's domains, ranges and concept scheme bindings. The alignment with
PROV-O and DCMI Terms is the ontology's, stated as rdfs:subPropertyOf where it
holds; the ontology's own context.jsonld refers to this one.

Four things the plain JSON cannot say by itself, and how the context says it:

* **References.** A foreign key holds a bare UUID. Its term is typed `@vocab`
  and carries a scoped `@vocab` of `urn:uuid:`, so `"farmId": "9971…"`
  becomes the IRI `urn:uuid:9971…` — the same IRI the farm's own
  representation carries as `@id`. The two meet in one node.
* **Enumerations.** `"status": "PLANNED"` on a task becomes the individual
  `agfoda:TaskStatus_PLANNED`, by the same device with the enumeration's
  prefix as `@vocab`.
* **One name, several properties.** `status`, `scopeType` and `validFrom`
  are one attribute name in JSON and a different property per class in the
  ontology (`taskStatus`, `userStatus` …). A type-scoped context per entity
  resolves them; a representation read as JSON-LD therefore carries `@type`.
* **Numbers.** Decimal attributes are left untyped. JSON-LD turns a number
  with a fraction into xsd:double, and typing the term xsd:decimal would make
  it write lexical forms such as "1.55E1"^^xsd:decimal, which are invalid.
  The ontology's range for them, agfoda:Decimal, admits xsd:double as well.

A list response reads as RDF too: `items` is an alias of `@included`, and the
paging members map to nothing.
"""
from __future__ import annotations

from collections import Counter

from model import Attribute, Entity, Model

XSD = "http://www.w3.org/2001/XMLSchema#"


def _vocab(name: str, prop: str, vocab: str) -> dict:
    """A term whose string value is a name in the vocabulary `vocab`.

    The scoped context restates the term itself. That changes nothing in
    meaning — the value is expanded against `vocab` either way — but it makes
    the scoped context of every such term distinct. Some processors resolve a
    scoped context once and reuse the result for the next term that carries
    an identical one; pyld 2.0.4 does, and from the second foreign key on the
    reference then came out as a literal instead of an IRI. The checks compare
    pyld's output with rdflib's for every example record.
    """
    return {"@id": prop, "@type": "@vocab",
            "@context": {"@vocab": vocab,
                         name: {"@id": prop, "@type": "@vocab"}}}


def term_definition(model: Model, attr: Attribute):
    """The term definition an attribute needs, independent of its entity."""
    prop = f"agfoda:{attr.term}"
    if attr.references:
        return _vocab(attr.name, prop, model.iri)
    if attr.type == "Enum":
        return _vocab(attr.name, prop, f"{model.ns}{attr.enum}_")
    if attr.concept:
        d = {"@id": prop, "@type": "@id"}
        if attr.multivalued:
            d["@container"] = "@set"
        return d
    if attr.type == "JSON":
        return {"@id": prop, "@type": "@json"}
    if attr.type == "DateTime":
        return {"@id": prop, "@type": "xsd:dateTime"}
    if attr.type == "Date":
        return {"@id": prop, "@type": "xsd:date"}
    return prop


def _key(definition) -> str:
    import json
    return json.dumps(definition, sort_keys=True)


def build(model: Model) -> dict:
    """The context document, deterministic in content and order."""
    uses: dict[str, list[tuple[Entity, object]]] = {}
    for e in model.ordered():
        for attr in e.attributes.values():
            uses.setdefault(attr.name, []).append((e, term_definition(model, attr)))

    shared: dict[str, object] = {}
    scoped: dict[str, dict[str, object]] = {e.name: {} for e in model.ordered()}
    for name, pairs in uses.items():
        counts = Counter(_key(d) for _, d in pairs)
        ranked = counts.most_common()
        # One definition for everyone, or one most entities share: that one
        # is global and the rest override it per type. Without a majority
        # there is no sensible default, and the name stays type-scoped only.
        winner = ranked[0][0] if len(ranked) == 1 or ranked[0][1] > ranked[1][1] else None
        for e, d in pairs:
            if winner is not None and _key(d) == winner:
                shared.setdefault(name, d)
            else:
                scoped[e.name][name] = d

    ctx: dict[str, object] = {
        "@version": 1.1,
        "@vocab": model.ns,
        "agfoda": model.ns,
        "xsd": XSD,
        # Paging: the members of a list become nodes, the rest is not data.
        "items": "@included",
        "nextCursor": None,
        "hasMore": None,
    }
    for e in model.ordered():
        definition: dict[str, object] = {"@id": f"agfoda:{e.name}"}
        if scoped[e.name]:
            definition["@context"] = dict(sorted(scoped[e.name].items()))
        ctx[e.name] = definition
    for name in sorted(shared):
        ctx[name] = shared[name]
    return {"@context": ctx}


def representation(model: Model, entity: Entity, record: dict,
                   context: object | None = None) -> dict:
    """A record as an `application/ld+json` representation carries it.

    The attributes are unchanged; the three JSON-LD keywords are added in
    front: the context, the record's IRI and its entity.
    """
    out = {"@context": context or f"{model.base_url}context.jsonld",
           "@id": f"{model.iri}{record['id']}",
           "@type": entity.name}
    out.update({k: v for k, v in record.items() if not k.startswith("@")})
    return out
