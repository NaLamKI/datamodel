"""JSON Schema (2020-12) for every entity — the canonical JSON of clause 9.

One function builds a schema, and a `ref` callback decides where its
references point: at `common.json` and `enumerations.json` for the standalone
files under `v1/schema/`, at `#/components/schemas/` inside the OpenAPI
description. The two cannot drift apart because they are the same schema.

The schemas are flat: every entity lists the attributes it inherits from
EntityBase itself. `allOf` with `unevaluatedProperties` would say the same
more elegantly, and half of the tooling that reads an OpenAPI description
would render it wrongly.

What a schema can check on a single record, it checks: types, mandatory
attributes, formats, enumerations, exclusive references (rule V03), positive
quantities (V02), provenance (V04), conditional requirements. What needs a
comparison between two attributes (V01) or other records is left to the SHACL
shapes and to the interface layer; see `enforcement` in model/rules.yaml.
"""
from __future__ import annotations

from typing import Callable

from model import Attribute, Constraint, Entity, Model, Ontology

DIALECT = "https://json-schema.org/draft/2020-12/schema"

Ref = Callable[[str, str], str]   # (kind, name) -> URI reference


def file_ref(kind: str, name: str) -> str:
    """References between the standalone files under v1/schema/."""
    if kind == "common":
        return f"common.json#/$defs/{name}"
    if kind == "enum":
        return f"enumerations.json#/$defs/{name}"
    return f"{name}.json"


def openapi_ref(kind: str, name: str) -> str:
    return f"#/components/schemas/{name}"


UUID = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

FORMATS = {
    "currency": "CurrencyCode", "country": "CountryCode",
    "language-tag": "LanguageTag", "time-zone": "TimeZone", "ucum": "UcumCode",
    "media-type": "MediaType", "gtin": "Gtin",
}

GEOMETRY_TYPES = ("Point", "MultiPoint", "LineString", "MultiLineString",
                  "Polygon", "MultiPolygon", "GeometryCollection")


def common(model: Model) -> dict[str, dict]:
    """The shared definitions: identifiers, time, codes, GeoJSON, JSON-LD."""
    iri = model.iri
    defs: dict[str, dict] = {
        "Uuid": {
            "type": "string", "format": "uuid", "pattern": UUID,
            "description": "A UUID in its canonical lower-case form, so that a "
                           "reference and the record it points at yield the "
                           f"same IRI ({iri}...).",
        },
        "DateTime": {
            "type": "string", "format": "date-time",
            "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$",
            "description": "ISO 8601-1 timestamp in coordinated universal "
                           "time (clause 5.1 c)).",
        },
        "Date": {
            "type": "string", "format": "date", "pattern": r"^\d{4}-\d{2}-\d{2}$",
            "description": "ISO 8601-1 calendar date.",
        },
        "Uri": {"type": "string", "format": "uri"},
        "ConceptUri": {
            "type": "string", "format": "uri", "pattern": "^https?://",
            "description": "Dereferenceable URI of a concept in a canonical "
                           "vocabulary, AGROVOC being the primary one "
                           "(clause 5.1 e)).",
        },
        "CurrencyCode": {
            "type": "string", "pattern": "^[A-Z]{3}$",
            "description": "ISO 4217 currency code.", "examples": ["EUR"],
        },
        "CountryCode": {
            "type": "string", "pattern": "^([A-Z]{2}|[A-Z]{3}|[0-9]{3})$",
            "description": "ISO 3166-1 country code; alpha-2 is recommended.",
            "examples": ["DE"],
        },
        "LanguageTag": {
            "type": "string", "pattern": "^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$",
            "description": "IETF BCP 47 language tag.", "examples": ["de-DE"],
        },
        "TimeZone": {
            "type": "string",
            "pattern": "^[A-Za-z][A-Za-z0-9_+-]*(/[A-Za-z0-9_+-]+)*$",
            "description": "IANA time zone identifier.",
            "examples": ["Europe/Berlin"],
        },
        "UcumCode": {
            "type": "string",
            "description": "A unit, which should be a UCUM code (clause 5.1 j)).",
            "examples": ["kg", "t/har", "L/har", "%"],
        },
        "MediaType": {
            "type": "string",
            "pattern": r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*(\s*;.*)?$",
            "description": "Media type (RFC 6838).",
            "examples": ["application/pdf"],
        },
        "Gtin": {
            "type": "string", "pattern": r"^(\d{8}|\d{12}|\d{13}|\d{14})$",
            "description": "GS1 Global Trade Item Number (GTIN-8, -12, -13 or -14).",
        },
        "ThingDescription": {
            "type": "string", "contentMediaType": "application/td+json",
            "description": "A W3C WoT Thing Description 1.1, serialized as "
                           "JSON-LD; where present, its content conforms to "
                           "WoT-TD (clause 5.1 f)).",
        },
        "EntityName": {
            "type": "string", "enum": [e.name for e in model.ordered()],
            "description": "The name of an entity of the model.",
        },
        "Permission": {
            "type": "string", "pattern": r"^[^:\s]+:[^:\s]+$",
            "description": "Permission identifier following the entity:action "
                           "pattern (clause 8.1).",
            "examples": ["activity:create"],
        },
        "Certificate": {
            "type": "object",
            "description": "A certificate of competence: its type, number and "
                           "validity (clause 8.1).",
            "properties": {
                "type": {"type": "string", "description": "Type of certificate"},
                "number": {"type": "string", "description": "Certificate number"},
                "validFrom": {"$ref": "#/$defs/Date"},
                "validTo": {"$ref": "#/$defs/Date"},
            },
            "required": ["type"],
        },
        "ChangeSet": {
            "type": "object",
            "description": "The values before and after a change (clause 8.11).",
            "properties": {
                "before": {"type": "object"},
                "after": {"type": "object"},
            },
        },
        "JsonLdContext": {
            "description": "JSON-LD context of the representation: "
                           f"{model.base_url}context.jsonld.",
            "anyOf": [{"type": "string", "format": "uri"}, {"type": "object"},
                      {"type": "array"}],
        },
        "JsonLdId": {
            "type": "string", "pattern": f"^{iri}{UUID[1:]}",
            "description": f"The record's IRI in JSON-LD: {iri} followed by its id.",
        },
    }
    # GeoJSON (RFC 7946), in WGS 84 (clause 5.1 d)).
    defs.update({
        "Position": {
            "type": "array", "minItems": 2, "maxItems": 3,
            "prefixItems": [{"type": "number", "minimum": -180, "maximum": 180},
                            {"type": "number", "minimum": -90, "maximum": 90},
                            {"type": "number"}],
            "items": {"type": "number"},
            "description": "Longitude, latitude and optionally altitude, WGS 84.",
        },
        "BoundingBox": {"type": "array", "minItems": 4, "items": {"type": "number"}},
        "Point": _geometry("Point", {"$ref": "#/$defs/Position"}),
        "MultiPoint": _geometry("MultiPoint", {"type": "array",
                                               "items": {"$ref": "#/$defs/Position"}}),
        "LineString": _geometry("LineString", {"type": "array", "minItems": 2,
                                               "items": {"$ref": "#/$defs/Position"}}),
        "MultiLineString": _geometry("MultiLineString", {
            "type": "array", "items": {"type": "array", "minItems": 2,
                                       "items": {"$ref": "#/$defs/Position"}}}),
        "Polygon": _geometry("Polygon", {
            "type": "array", "items": {"$ref": "#/$defs/LinearRing"}}),
        "MultiPolygon": _geometry("MultiPolygon", {
            "type": "array", "items": {"type": "array",
                                       "items": {"$ref": "#/$defs/LinearRing"}}}),
        "LinearRing": {
            "type": "array", "minItems": 4, "items": {"$ref": "#/$defs/Position"},
            "description": "A closed ring: at least four positions, the first "
                           "and the last identical.",
        },
        "GeometryCollection": {
            "type": "object", "required": ["type", "geometries"],
            "properties": {
                "type": {"const": "GeometryCollection"},
                "geometries": {"type": "array", "items": {"$ref": "#/$defs/Geometry"}},
                "bbox": {"$ref": "#/$defs/BoundingBox"},
            },
        },
        "Geometry": {
            "description": "A GeoJSON geometry object (RFC 7946) in WGS 84.",
            "oneOf": [{"$ref": f"#/$defs/{t}"} for t in GEOMETRY_TYPES],
        },
    })
    return defs


def _geometry(kind: str, coordinates: dict) -> dict:
    return {
        "type": "object", "required": ["type", "coordinates"],
        "properties": {"type": {"const": kind}, "coordinates": coordinates,
                       "bbox": {"$ref": "#/$defs/BoundingBox"}},
    }


def enumerations(model: Model) -> dict[str, dict]:
    return {name: {"type": "string", "enum": list(e["values"]),
                   "description": " ".join(e["description"].split()),
                   "x-agfoda-class": f"{model.ns}{name}"}
            for name, e in model.enumerations.items()}


def property_schema(model: Model, ontology: Ontology, entity: str,
                    attr: Attribute, ref: Ref) -> dict:
    """The schema of one attribute, with what it means attached."""
    t = attr.type
    if t == "UUID":
        s = {"$ref": ref("common", "Uuid")}
    elif t == "Enum":
        s = {"$ref": ref("enum", attr.enum)}
    elif t == "Date":
        s = {"$ref": ref("common", "Date")}
    elif t == "DateTime":
        s = {"$ref": ref("common", "DateTime")}
    elif t == "Integer":
        s = {"type": "integer"}
    elif t == "Decimal":
        s = {"type": "number"}
    elif t == "Boolean":
        s = {"type": "boolean"}
    elif t == "JSON":
        s = _json_schema(attr, ref)
    elif attr.concept:
        s = {"$ref": ref("common", "ConceptUri")}
    elif attr.thingDescription:
        s = {"$ref": ref("common", "ThingDescription")}
    elif attr.entityName:
        s = {"$ref": ref("common", "EntityName")}
    elif attr.format in FORMATS:
        s = {"$ref": ref("common", FORMATS[attr.format])}
    elif attr.format in ("email", "uri"):
        s = {"type": "string", "format": attr.format}
    else:
        s = {"type": "string"}

    s["description"] = attr.summary()
    if attr.positive:
        s["exclusiveMinimum"] = 0
        s["$comment"] = "Rule V02: a quantity is greater than zero."
    if attr.default is not None:
        s["default"] = attr.default
    if attr.readOnly:
        s["readOnly"] = True
    s["x-agfoda-property"] = f"{model.ns}{attr.term}"
    if attr.references:
        s["x-agfoda-references"] = attr.references
    if attr.referencesBy:
        by = {"attribute": attr.referencesBy["attribute"]}
        if attr.referencesBy.get("targets"):
            by["targets"] = attr.referencesBy["targets"]
        s["x-agfoda-references-by"] = by
    schemes = ontology.bindings.get((entity, attr.term), [])
    if schemes:
        s["x-agfoda-schemes"] = schemes
    if attr.term in ontology.notation_from:
        s["x-agfoda-notation-from"] = ontology.notation_from[attr.term]
    return s


def _json_schema(attr: Attribute, ref: Ref) -> dict:
    if attr.geometry == "any":
        return {"$ref": ref("common", "Geometry")}
    if attr.geometry:
        kinds = list(attr.geometry)
        if len(kinds) == 1:
            return {"$ref": ref("common", kinds[0])}
        return {"oneOf": [{"$ref": ref("common", k)} for k in kinds]}
    kind = attr.json
    if kind == "map":
        return {"type": "object", "additionalProperties": {"type": "string"}}
    if kind == "concepts":
        return {"type": "array", "uniqueItems": True,
                "items": {"$ref": ref("common", "ConceptUri")}}
    if kind == "permissions":
        return {"type": "array", "uniqueItems": True,
                "items": {"$ref": ref("common", "Permission")}}
    if kind == "certificates":
        return {"type": "array", "items": {"$ref": ref("common", "Certificate")}}
    if kind == "change-set":
        return {"$ref": ref("common", "ChangeSet")}
    if kind == "object":
        return {"type": "object"}
    return {}


def constraint_schema(c: Constraint) -> dict | None:
    """One constraint as a subschema, or None where JSON Schema cannot say it.

    A "should" is not a schema error: clause 12 asks for a warning, which is
    what the SHACL shapes give it. A comparison of two attributes (`order`)
    is beyond JSON Schema altogether.
    """
    if c.level == "should" or c.kind == "order":
        return None
    comment = f"{c.cites}: {c.describe()}." if c.cites else f"{c.describe()}."

    def req(m):
        return {"required": m if isinstance(m, list) else [m]}

    if c.kind == "exactlyOne":
        body = {"oneOf": [req(m) for m in c.members]}
    elif c.kind == "atLeastOne":
        body = {"anyOf": [req(m) for m in c.members]}
    elif c.kind == "atMostOne":
        names = c.members
        pairs = [[a, b] for i, a in enumerate(names) for b in names[i + 1:]]
        body = {"not": {"anyOf": [{"required": p} for p in pairs]}}
    elif c.kind == "requiredTogether":
        body = {"dependentRequired": {m: [o for o in c.members if o != m]
                                      for m in c.members}}
    else:  # requiredWhen
        (key, values), = c.when.items()
        body = {"if": {"properties": {key: {"enum": list(values)}},
                       "required": [key]},
                "then": {"required": [c.attribute]}}
    return {"$comment": comment, **body}


def entity_schema(model: Model, ontology: Ontology, entity: Entity, ref: Ref,
                  *, standalone: bool) -> dict:
    """The schema of a record of this entity, as stored and exchanged."""
    props: dict[str, dict] = {
        "@context": {"$ref": ref("common", "JsonLdContext")},
        "@id": {"$ref": ref("common", "JsonLdId")},
        "@type": {"const": entity.name,
                  "description": "The entity, in a JSON-LD representation."},
    }
    for attr in entity.attributes.values():
        props[attr.name] = property_schema(model, ontology, entity.name, attr, ref)
    schema: dict = {}
    if standalone:
        schema["$schema"] = DIALECT
        schema["$id"] = f"{model.base_url}schema/{entity.name}.json"
    schema.update({
        "title": entity.name,
        "description": entity.definition,
        "type": "object",
        "properties": props,
        "required": [a.name for a in entity.attributes.values() if a.required],
        "additionalProperties": False,
    })
    checks = [s for s in (constraint_schema(c) for c in entity.all_constraints)
              if s]
    if checks:
        schema["allOf"] = checks
    schema["x-agfoda-class"] = f"{model.ns}{entity.name}"
    schema["x-agfoda-package"] = entity.package
    schema["x-agfoda-annex"] = entity.annex
    states = model.states.get(entity.name)
    if states:
        # Clause 13: transitions not listed are rejected.
        schema["x-agfoda-states"] = {"attribute": states["attribute"],
                                     "transitions": states["transitions"],
                                     "terminal": states["terminal"]}
    keys = [{k: v for k, v in key.items() if k != "entity"}
            for key in model.business_keys if key["entity"] == entity.name]
    if keys:
        # Table 3: unique in addition to the identifier.
        schema["x-agfoda-unique"] = [
            {k: (" ".join(v.split()) if isinstance(v, str) else v)
             for k, v in key.items()} for key in keys]
    return schema


def base_schema(model: Model, ontology: Ontology) -> dict:
    """EntityBase on its own: abstract, documented, inherited by copy."""
    props = {a.name: property_schema(model, ontology, "EntityBase", a, file_ref)
             for a in model.base.values()}
    schema = {
        "$schema": DIALECT,
        "$id": f"{model.base_url}schema/EntityBase.json",
        "title": "EntityBase",
        "description": " ".join(model.meta["entityBase"]["description"].split())
        + " Abstract: every entity schema carries these attributes itself.",
        "type": "object",
        "properties": props,
        "required": [a.name for a in model.base.values() if a.required],
        "allOf": [s for s in (constraint_schema(c) for c in model.base_constraints)
                  if s],
        "x-agfoda-class": f"{model.ns}EntityBase",
    }
    return schema


def standalone(model: Model, ontology: Ontology) -> dict[str, dict]:
    """File name -> schema, for v1/schema/."""
    out = {
        "common.json": {"$schema": DIALECT,
                        "$id": f"{model.base_url}schema/common.json",
                        "title": "Common definitions",
                        "$defs": common(model)},
        "enumerations.json": {"$schema": DIALECT,
                              "$id": f"{model.base_url}schema/enumerations.json",
                              "title": "Enumerations (Annex B)",
                              "$defs": enumerations(model)},
        "EntityBase.json": base_schema(model, ontology),
    }
    for e in model.ordered():
        out[f"{e.name}.json"] = entity_schema(model, ontology, e, file_ref,
                                              standalone=True)
    return out


def rebase(schema, target: str):
    """Point the `#/$defs/...` references of the common definitions elsewhere.

    Inside common.json the definitions refer to each other as `#/$defs/X`;
    moved into an OpenAPI document they have to say `#/components/schemas/X`.
    """
    if isinstance(schema, dict):
        return {k: (target + v[len("#/$defs/"):] if k == "$ref"
                    and isinstance(v, str) and v.startswith("#/$defs/")
                    else rebase(v, target)) for k, v in schema.items()}
    if isinstance(schema, list):
        return [rebase(v, target) for v in schema]
    return schema
