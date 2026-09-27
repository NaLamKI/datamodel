"""The HTTP binding: an OpenAPI 3.1 description of the reference API.

The Recommendation specifies the data, and for the interface a handful of
requirements (clause 9): JSON as the canonical representation, synchronization
by a cursor over updatedAt, per-attribute last-write-wins, the correction path
for reported documentation, client-generated identifiers, OGC API - Features
for the geospatial entities, authentication and authorization through an
external IAM system (clause 10). How those requirements become paths, methods,
headers and status codes is this repository's binding, and `info.description`
says so.

The schemas are the ones under v1/schema/ — the same function builds both
(tool/schemas.py) — with their references pointed at `#/components/schemas/`.
"""
from __future__ import annotations

from model import Entity, Model, Ontology
from schemas import common, entity_schema, enumerations, openapi_ref, rebase

COMPONENTS = "#/components/schemas/"

# Problem types (RFC 9457) the model gives rise to. Status codes that need no
# explanation beyond themselves use `about:blank`.
PROBLEMS = [
    ("invalid-record", 422, "The record does not conform to its schema",
     "A mandatory attribute is missing, an attribute has the wrong type or "
     "format, or an attribute the entity does not have was sent."),
    ("rule-violation", 422, "An integrity rule is violated",
     "The record violates a rule of clause 12 of the Recommendation (V01 to "
     "V16) or a condition of clause 8. `violations` names the rule and the "
     "attributes concerned."),
    ("invalid-transition", 409, "The status change is not permitted",
     "The change of a status attribute is not listed in the state model of "
     "clause 13, or leaves a terminal state."),
    ("immutable-record", 409, "The record can no longer be changed",
     "A RegulatoryReport is immutable from SUBMITTED onwards (rule V15); a "
     "correction is a new report referencing it through supersedesReportId. "
     "Audit log entries are never changed."),
    ("duplicate-key", 409, "A business key is already taken",
     "The identifier or a business key of Table 3 — User.email, "
     "Farm.farmNumber, Field.name within the farm and the others — is already "
     "used by another record."),
    ("reason-required", 422, "A correction needs a reason",
     "The change affects documentation referenced by a RegulatoryReport whose "
     "status is SUBMITTED or later. Such a change is made through the "
     "correction path and needs a reason, sent as Change-Reason; it is "
     "recorded in the AuditLog (clause 5.1 b))."),
    ("dependent-records", 409, "Other records depend on this one",
     "The record cannot be deleted because other records refer to it. "
     "Operational records are withdrawn from use by a terminal status or an "
     "endsAt timestamp instead (clause 5.1 i))."),
]


def problem_uri(model: Model, slug: str) -> str:
    return f"{model.base_url}problems/{slug}"


def _problem_response(description: str) -> dict:
    return {"description": description,
            "content": {"application/problem+json": {
                "schema": {"$ref": f"{COMPONENTS}Problem"}}}}


def _content(schema_ref: str) -> dict:
    """JSON, and the same body read as JSON-LD."""
    return {"application/json": {"schema": {"$ref": schema_ref}},
            "application/ld+json": {"schema": {"$ref": schema_ref}}}


def _filters(model: Model, e: Entity) -> list[dict]:
    """Equality filters on references and enumerations."""
    out = []
    for a in e.attributes.values():
        if a.references and a.name not in ("createdByUserId", "createdByJobId"):
            out.append({"name": a.name, "in": "query", "required": False,
                        "description": f"Only records whose {a.name} is this "
                                       f"{a.references}.",
                        "schema": {"$ref": f"{COMPONENTS}Uuid"}})
        elif a.enum:
            out.append({"name": a.name, "in": "query", "required": False,
                        "description": f"Only records with this {a.name}.",
                        "schema": {"$ref": f"{COMPONENTS}{a.enum}"}})
        elif a.entityName or a.referencesBy and a.name == "entityId":
            out.append({"name": a.name, "in": "query", "required": False,
                        "description": f"Only records with this {a.name}.",
                        "schema": {"$ref": COMPONENTS + (
                            "EntityName" if a.entityName else "Uuid")}})
    return out


def _patch_schema(model: Model, e: Entity) -> dict:
    """JSON Merge Patch of a record: its writable attributes, all optional."""
    props = {}
    for a in e.attributes.values():
        if not a.writable:
            continue
        ref = {"$ref": f"{COMPONENTS}{e.name}/properties/{a.name}"}
        props[a.name] = ref if a.required else {"anyOf": [ref, {"type": "null"}]}
    return {"title": f"{e.name}Patch",
            "description": f"A JSON Merge Patch (RFC 7396) of a {e.name}: the "
                           "attributes present are changed, null removes an "
                           "optional one. The merged record must conform to "
                           f"{e.name}; the constraints are checked on it.",
            "type": "object", "properties": props, "additionalProperties": False}


def _page_schema(e: Entity) -> dict:
    return {"title": f"{e.name}Page",
            "description": f"A page of {e.name} records in synchronization "
                           "order (updatedAt, then id).",
            "type": "object",
            "properties": {
                "@context": {"$ref": f"{COMPONENTS}JsonLdContext"},
                "items": {"type": "array", "items": {"$ref": f"{COMPONENTS}{e.name}"}},
                "nextCursor": {"type": "string",
                               "description": "Resumes after the last record of "
                                              "this page — also on the last page, "
                                              "for the next poll."},
                "hasMore": {"type": "boolean",
                            "description": "Whether further records follow now."},
            },
            "required": ["items", "nextCursor", "hasMore"],
            "additionalProperties": False}


def _states_note(model: Model, e: Entity) -> str:
    st = model.states.get(e.name)
    if not st:
        return ""
    return (f" Changes of `{st['attribute']}` follow the state model of "
            "clause 13; any other is rejected with `invalid-transition`.")


def entity_paths(model: Model, e: Entity) -> dict:
    tag = _tag(model, e.package)
    perm = e.permission
    one = f"{COMPONENTS}{e.name}"
    std = {"401": {"$ref": "#/components/responses/Unauthorized"},
           "403": {"$ref": "#/components/responses/Forbidden"}}
    listing = {
        "get": {
            "tags": [tag], "operationId": f"list{e.plural}",
            "summary": f"List {e.name} records",
            "description": (
                "Records in synchronization order: by `updatedAt`, then `id` "
                "(clause 9). Start with `updatedAfter`, continue with the "
                "`nextCursor` of the previous page; the last page returns one "
                "too, so that the next poll resumes where this one ended. A "
                "record withdrawn from use appears with its terminal status or "
                "`endsAt`; a deleted one appears as a DELETE entry of the audit "
                "log."),
            "parameters": [{"$ref": "#/components/parameters/Limit"},
                           {"$ref": "#/components/parameters/Cursor"},
                           {"$ref": "#/components/parameters/UpdatedAfter"},
                           *_filters(model, e)],
            "responses": {
                "200": {"description": "A page of records.",
                        "content": _content(f"{COMPONENTS}{e.name}Page")},
                "400": {"$ref": "#/components/responses/BadRequest"}, **std},
            "x-agfoda-permission": f"{perm}:read",
        }
    }
    item: dict = {
        "parameters": [{"$ref": "#/components/parameters/Id"}],
        "get": {
            "tags": [tag], "operationId": f"get{e.name}",
            "summary": f"Read a {e.name}",
            "responses": {
                "200": {"description": "The record; `ETag` identifies its version.",
                        "headers": {"ETag": {"$ref": "#/components/headers/ETag"}},
                        "content": _content(one)},
                **std, "404": {"$ref": "#/components/responses/NotFound"}},
            "x-agfoda-permission": f"{perm}:read",
        },
    }
    if not e.systemManaged:
        immutable = (" From `SUBMITTED` onwards the report is immutable (rule "
                     "V15): a correction is a new report referencing it through "
                     "`supersedesReportId`." if e.name == "RegulatoryReport" else "")
        write_errors = {
            **std,
            "409": {"$ref": "#/components/responses/Conflict"},
            "412": {"$ref": "#/components/responses/PreconditionFailed"},
            "422": {"$ref": "#/components/responses/Unprocessable"},
        }
        item["put"] = {
            "tags": [tag], "operationId": f"put{e.name}",
            "summary": f"Create or replace a {e.name}",
            "description": (
                "Creates the record under the identifier its client generated "
                "(clause 9), or replaces it. `If-None-Match: *` creates only; "
                "`If-Match` replaces only the version read. The server sets "
                "`createdAt`, `updatedAt`, `createdByUserId`, `createdByJobId` "
                "and `clientId` (clause 5.1 l)). `originType` may be declared "
                "on creation and is checked against the caller: `USER` for a "
                "user, `SERVICE`, `DEVICE` or `IMPORT` for a processing run "
                "named in `Processing-Job-Id`; it cannot be changed afterwards."
                + _states_note(model, e) + immutable),
            "parameters": [{"$ref": "#/components/parameters/IfMatch"},
                           {"$ref": "#/components/parameters/IfNoneMatch"},
                           {"$ref": "#/components/parameters/ProcessingJobId"},
                           {"$ref": "#/components/parameters/ChangeReason"}],
            "requestBody": {"required": True, "content": _content(one)},
            "responses": {
                "200": {"description": "Replaced.",
                        "headers": {"ETag": {"$ref": "#/components/headers/ETag"}},
                        "content": _content(one)},
                "201": {"description": "Created.",
                        "headers": {"ETag": {"$ref": "#/components/headers/ETag"},
                                    "Location": {"$ref": "#/components/headers/Location"}},
                        "content": _content(one)},
                **write_errors},
            "x-agfoda-permission": [f"{perm}:create", f"{perm}:update"],
        }
        item["patch"] = {
            "tags": [tag], "operationId": f"patch{e.name}",
            "summary": f"Change attributes of a {e.name}",
            "description": (
                "JSON Merge Patch (RFC 7396). Changes to different attributes "
                "do not conflict; of two changes to the same attribute the "
                "later wins (clause 5.1 b)). A change to documentation that is "
                "referenced by a RegulatoryReport in status SUBMITTED or later "
                "goes through the correction path and needs `Change-Reason`, "
                "which is recorded in the AuditLog."
                + _states_note(model, e) + immutable),
            "parameters": [{"$ref": "#/components/parameters/IfMatch"},
                           {"$ref": "#/components/parameters/ProcessingJobId"},
                           {"$ref": "#/components/parameters/ChangeReason"}],
            "requestBody": {"required": True, "content": {
                "application/merge-patch+json": {
                    "schema": {"$ref": f"{COMPONENTS}{e.name}Patch"}}}},
            "responses": {
                "200": {"description": "Changed.",
                        "headers": {"ETag": {"$ref": "#/components/headers/ETag"}},
                        "content": _content(one)},
                **write_errors, "404": {"$ref": "#/components/responses/NotFound"}},
            "x-agfoda-permission": f"{perm}:update",
        }
        item["delete"] = {
            "tags": [tag], "operationId": f"delete{e.name}",
            "summary": f"Delete a {e.name}",
            "description": (
                "Operational records are withdrawn from use by a terminal "
                "status or `endsAt` rather than deleted (clause 5.1 i)). A "
                "deletion is recorded as a DELETE entry of the audit log, "
                "through which synchronizing clients learn of it (clause 9); "
                "one that other records depend on is refused."),
            "parameters": [{"$ref": "#/components/parameters/IfMatch"},
                           {"$ref": "#/components/parameters/ChangeReason"}],
            "responses": {
                "204": {"description": "Deleted."},
                **std, "404": {"$ref": "#/components/responses/NotFound"},
                "409": {"$ref": "#/components/responses/Conflict"},
                "412": {"$ref": "#/components/responses/PreconditionFailed"}},
            "x-agfoda-permission": f"{perm}:delete",
        }
    return {f"/{e.path}": listing, f"/{e.path}/{{id}}": item}


def _tag(model: Model, pid: str) -> str:
    p = model.package(pid)
    return f"{p.id} {p.title}"


FEATURE_ENTITIES = ("Field", "Region", "Site")


def feature_schemas(model: Model, entity_schemas: dict) -> dict:
    """GeoJSON features of the geospatial entities (OGC API - Features)."""
    out = {
        "Link": {"type": "object", "required": ["href", "rel"],
                 "properties": {"href": {"type": "string", "format": "uri-reference"},
                                "rel": {"type": "string"},
                                "type": {"type": "string"},
                                "title": {"type": "string"}}},
        "LandingPage": {"type": "object", "required": ["links"],
                        "properties": {"title": {"type": "string"},
                                       "description": {"type": "string"},
                                       "links": {"type": "array",
                                                 "items": {"$ref": f"{COMPONENTS}Link"}}}},
        "ConformanceDeclaration": {
            "type": "object", "required": ["conformsTo"],
            "properties": {"conformsTo": {"type": "array", "items": {
                "type": "string", "format": "uri"}}}},
        "Collection": {"type": "object", "required": ["id", "links"],
                       "properties": {"id": {"type": "string"},
                                      "title": {"type": "string"},
                                      "description": {"type": "string"},
                                      "itemType": {"type": "string", "const": "feature"},
                                      "links": {"type": "array",
                                                "items": {"$ref": f"{COMPONENTS}Link"}}}},
        "Collections": {"type": "object", "required": ["links", "collections"],
                        "properties": {"links": {"type": "array",
                                                 "items": {"$ref": f"{COMPONENTS}Link"}},
                                       "collections": {"type": "array",
                                                       "items": {"$ref": f"{COMPONENTS}Collection"}}}},
    }
    for name in FEATURE_ENTITIES:
        s = entity_schemas[name]
        props = {k: v for k, v in s["properties"].items()
                 if k not in ("id", "geometry") and not k.startswith("@")}
        out[f"{name}Properties"] = {
            "type": "object",
            "description": f"The attributes of a {name} other than id and geometry.",
            "properties": props,
            "required": [r for r in s["required"] if r not in ("id", "geometry")],
            "additionalProperties": False,
        }
        geometry = s["properties"]["geometry"]
        geometry = {k: v for k, v in geometry.items()
                    if k in ("$ref", "oneOf")}
        out[f"{name}Feature"] = {
            "type": "object", "required": ["type", "id", "geometry", "properties"],
            "description": f"A {name} as a GeoJSON Feature.",
            "properties": {
                "type": {"const": "Feature"},
                "id": {"$ref": f"{COMPONENTS}Uuid"},
                "geometry": {"oneOf": [geometry, {"type": "null"}]},
                "properties": {"$ref": f"{COMPONENTS}{name}Properties"},
                "links": {"type": "array", "items": {"$ref": f"{COMPONENTS}Link"}},
            },
        }
        out[f"{name}FeatureCollection"] = {
            "type": "object", "required": ["type", "features"],
            "properties": {
                "type": {"const": "FeatureCollection"},
                "features": {"type": "array",
                             "items": {"$ref": f"{COMPONENTS}{name}Feature"}},
                "links": {"type": "array", "items": {"$ref": f"{COMPONENTS}Link"}},
                "timeStamp": {"$ref": f"{COMPONENTS}DateTime"},
                "numberMatched": {"type": "integer", "minimum": 0},
                "numberReturned": {"type": "integer", "minimum": 0},
            },
        }
    return out


def feature_paths(model: Model) -> dict:
    tag = "Features (OGC API - Features)"
    geo = "application/geo+json"
    paths = {
        "/features": {"get": {
            "tags": [tag], "operationId": "getFeaturesLandingPage",
            "summary": "Landing page of the OGC API - Features binding",
            "responses": {"200": {"description": "Links to the API definition, "
                                                 "the conformance declaration and the collections.",
                                  "content": {"application/json": {"schema": {
                                      "$ref": f"{COMPONENTS}LandingPage"}}}}}}},
        "/features/conformance": {"get": {
            "tags": [tag], "operationId": "getFeaturesConformance",
            "summary": "Conformance classes implemented",
            "description": "At least Part 1 Core and GeoJSON.",
            "responses": {"200": {"description": "The conformance declaration.",
                                  "content": {"application/json": {"schema": {
                                      "$ref": f"{COMPONENTS}ConformanceDeclaration"}}}}}}},
        "/features/collections": {"get": {
            "tags": [tag], "operationId": "getFeatureCollections",
            "summary": "The feature collections: fields, regions and sites",
            "responses": {"200": {"description": "The collections.",
                                  "content": {"application/json": {"schema": {
                                      "$ref": f"{COMPONENTS}Collections"}}}}}}},
        "/features/collections/{collectionId}": {"get": {
            "tags": [tag], "operationId": "getFeatureCollection",
            "summary": "One feature collection",
            "parameters": [{"name": "collectionId", "in": "path", "required": True,
                            "schema": {"type": "string",
                                       "enum": [model.entities[n].path
                                                for n in FEATURE_ENTITIES]}}],
            "responses": {"200": {"description": "The collection.",
                                  "content": {"application/json": {"schema": {
                                      "$ref": f"{COMPONENTS}Collection"}}}},
                          "404": {"$ref": "#/components/responses/NotFound"}}}},
    }
    for name in FEATURE_ENTITIES:
        e = model.entities[name]
        paths[f"/features/collections/{e.path}/items"] = {"get": {
            "tags": [tag], "operationId": f"get{e.plural}Features",
            "summary": f"{e.name} records as GeoJSON features",
            "parameters": [{"$ref": "#/components/parameters/FeatureLimit"},
                           {"$ref": "#/components/parameters/Bbox"},
                           {"$ref": "#/components/parameters/Datetime"}],
            "responses": {"200": {"description": "A feature collection; a `next` "
                                                 "link continues it.",
                                  "content": {geo: {"schema": {
                                      "$ref": f"{COMPONENTS}{name}FeatureCollection"}}}},
                          "400": {"$ref": "#/components/responses/BadRequest"}},
            "x-agfoda-permission": f"{e.permission}:read"}}
        paths[f"/features/collections/{e.path}/items/{{featureId}}"] = {"get": {
            "tags": [tag], "operationId": f"get{e.name}Feature",
            "summary": f"A {e.name} as a GeoJSON feature",
            "parameters": [{"name": "featureId", "in": "path", "required": True,
                            "schema": {"$ref": f"{COMPONENTS}Uuid"}}],
            "responses": {"200": {"description": "The feature.",
                                  "content": {geo: {"schema": {
                                      "$ref": f"{COMPONENTS}{name}Feature"}}}},
                          "404": {"$ref": "#/components/responses/NotFound"}},
            "x-agfoda-permission": f"{e.permission}:read"}}
    return paths


def derived_paths(model: Model) -> dict:
    view = next(v for v in model.derived_views if v["id"] == "stock-level")
    return {view["api"]: {"get": {
        "tags": ["Derived views"], "operationId": "listStockLevels",
        "summary": "Stock levels, derived from stock movements",
        "description": " ".join((view["text"] + " " + view["rule"]).split())
        + " Stock levels are computed, never stored (clause 7.5).",
        "parameters": [
            {"name": n, "in": "query", "required": False,
             "schema": {"$ref": f"{COMPONENTS}Uuid"}}
            for n in ("productId", "lotId", "storageLocationId")],
        "responses": {"200": {"description": "The levels.",
                              "content": {"application/json": {"schema": {
                                  "$ref": f"{COMPONENTS}StockLevels"}}}},
                      "401": {"$ref": "#/components/responses/Unauthorized"}},
        "x-agfoda-permission": "stockMovement:read"}}}


def build(model: Model, ontology: Ontology) -> dict:
    schemas_: dict[str, dict] = {}
    for name, s in common(model).items():
        schemas_[name] = rebase(s, COMPONENTS)
    schemas_.update(enumerations(model))
    entity_schemas = {}
    for e in model.ordered():
        s = entity_schema(model, ontology, e, openapi_ref, standalone=False)
        entity_schemas[e.name] = s
        schemas_[e.name] = s
        if not e.systemManaged:
            schemas_[f"{e.name}Patch"] = _patch_schema(model, e)
        schemas_[f"{e.name}Page"] = _page_schema(e)
    schemas_["Problem"] = {
        "type": "object",
        "description": "Problem Details (RFC 9457).",
        "properties": {
            "type": {"type": "string", "format": "uri-reference",
                     "description": "One of the problem types under "
                                    f"{model.base_url}problems/, or about:blank."},
            "title": {"type": "string"}, "status": {"type": "integer"},
            "detail": {"type": "string"},
            "instance": {"type": "string", "format": "uri-reference"},
            "violations": {"type": "array", "items": {"$ref": f"{COMPONENTS}Violation"}},
        },
        "required": ["type", "title", "status"],
    }
    schemas_["Violation"] = {
        "type": "object", "required": ["message"],
        "properties": {
            "rule": {"type": "string", "pattern": "^V[0-9]{2}$",
                     "description": "Rule of clause 12 of the Recommendation."},
            "attribute": {"type": "string"},
            "message": {"type": "string"},
        },
    }
    schemas_["StockLevel"] = {
        "type": "object", "required": ["productId", "storageLocationId", "quantity", "unit"],
        "properties": {
            "productId": {"$ref": f"{COMPONENTS}Uuid"},
            "lotId": {"$ref": f"{COMPONENTS}Uuid"},
            "storageLocationId": {"$ref": f"{COMPONENTS}Uuid"},
            "quantity": {"type": "number",
                         "description": "The sum of the movements. It should not "
                                        "become negative; movements of type "
                                        "ADJUSTMENT are exempt (rule V12)."},
            "unit": {"$ref": f"{COMPONENTS}UcumCode"},
        },
        "additionalProperties": False,
    }
    schemas_["StockLevels"] = {
        "type": "object", "required": ["items"],
        "properties": {"items": {"type": "array",
                                 "items": {"$ref": f"{COMPONENTS}StockLevel"}}},
    }
    schemas_.update(feature_schemas(model, entity_schemas))

    paths: dict = {}
    for e in model.ordered():
        paths.update(entity_paths(model, e))
    paths.update(derived_paths(model))
    paths.update(feature_paths(model))

    problems = "\n".join(f"| `{slug}` | {status} | {title} |"
                         for slug, status, title, _ in PROBLEMS)
    description = f"""\
Reference REST binding of the **{model.meta['title']}** — the data model of the
Recommendation *{model.meta['recommendation']['title']}* ({' '.join(model.meta['recommendation']['status'].split())}, {model.meta['recommendation']['date']}).

The resources and their attributes are the entities of the model; each
attribute maps onto a property of the [agrifooddata ontology]({model.meta['ontology']['home']}).
The paths, headers and status codes are the binding of this repository — the
Recommendation specifies the data and the requirements of its clauses 9 and 10,
not a REST interface.

**Representations.** JSON as specified in clause 9: camelCase, UTC timestamps,
GeoJSON geometries, enumerations in upper case, identifiers as strings.
Optional attributes that are not set are omitted, never `null`. Asked for
`application/ld+json`, the server adds three JSON-LD keywords in front —
`@context` ({model.base_url}context.jsonld), `@id` (`{model.iri}` and the id) and
`@type` (the entity) — and leaves the attributes as they are.

**Identifiers** are UUIDs in lower case, generated by the client that creates
a record, so that records created while offline do not collide.

**Synchronization.** Every collection lists in the order of `updatedAt`, then
`id`; a client polls each collection with the cursor of its last page.
Withdrawals arrive as status changes, deletions as DELETE entries of
`/audit-logs`. Writes conflict per attribute, and the later write wins
(clause 5.1 b)); documentation already reported is corrected only with a
`Change-Reason` (correction path).

**Provenance** (clause 5.1 l)). The server sets `createdAt`, `updatedAt`,
`createdByUserId`, `createdByJobId` and `clientId` from the authenticated
caller. A processing run that writes names its ProcessingJob in the
`Processing-Job-Id` header; every automatic creation of data is such a run.

**Security** (clause 10). Every request is authenticated through the external
identity and access management system (OpenID Connect) and authorized against
its policies; the roles and access assignments of the model are evaluated in
addition, never instead. `x-agfoda-permission` names the permission, in the
`entity:action` pattern of `Role.permissions`, that an operation requires on
the farm concerned.

**Problems** are reported as RFC 9457 problem details; their `type` is
{problem_uri(model, "<type>")}:

| Type | Status | Meaning |
|---|---|---|
{problems}

The geospatial entities Field, Region and Site are also served as feature
collections conforming to OGC API - Features (`/features`).
"""
    doc = {
        "openapi": "3.1.0",
        "info": {
            "title": "AgriFoodData API",
            "version": model.version,
            "summary": "Reference REST binding of the AgriFoodData model",
            "description": description,
            "license": {"name": "CC BY 4.0",
                        "identifier": model.meta["license"]["id"]},
        },
        "externalDocs": {"description": "Reference documentation of the model",
                         "url": model.base_url},
        "servers": [{"url": "https://{host}/v1",
                     "description": "A deployment of the AgriFoodData API",
                     "variables": {"host": {"default": "fmis.example.org",
                                            "description": "Host of the deployment"}}}],
        "security": [{"oidc": []}],
        "tags": ([{"name": _tag(model, p.id), "description": p.summary}
                  for p in model.packages]
                 + [{"name": "Derived views",
                     "description": "Quantities computed from stored records, "
                                    "not stored as entities (clause 7.5)."},
                    {"name": "Features (OGC API - Features)",
                     "description": "Field, Region and Site as GeoJSON feature "
                                    "collections (clause 9)."}]),
        "paths": paths,
        "components": {
            "schemas": schemas_,
            "parameters": _parameters(),
            "headers": {
                "ETag": {"description": "Version of the record, for If-Match.",
                         "schema": {"type": "string"}},
                "Location": {"description": "Address of the record created.",
                             "schema": {"type": "string", "format": "uri"}},
            },
            "responses": {
                "BadRequest": _problem_response("The request is malformed."),
                "Unauthorized": _problem_response("Not authenticated."),
                "Forbidden": _problem_response(
                    "Not authorized for this farm and permission."),
                "NotFound": _problem_response("No such record."),
                "Conflict": _problem_response(
                    "invalid-transition, immutable-record, duplicate-key or "
                    "dependent-records."),
                "PreconditionFailed": _problem_response(
                    "The record has changed since the version named in "
                    "If-Match, or exists although If-None-Match: * was sent."),
                "Unprocessable": _problem_response(
                    "invalid-record, rule-violation or reason-required."),
            },
            "securitySchemes": {"oidc": {
                "type": "openIdConnect",
                "openIdConnectUrl": "https://iam.example.org/.well-known/openid-configuration",
                "description": "The external identity and access management "
                               "system of the deployment (clause 10)."}},
        },
    }
    return doc


def _parameters() -> dict:
    return {
        "Id": {"name": "id", "in": "path", "required": True,
               "description": "Identifier of the record.",
               "schema": {"$ref": f"{COMPONENTS}Uuid"}},
        "Limit": {"name": "limit", "in": "query", "required": False,
                  "description": "Maximum number of records on the page.",
                  "schema": {"type": "integer", "minimum": 1, "maximum": 1000,
                             "default": 100}},
        "Cursor": {"name": "cursor", "in": "query", "required": False,
                   "description": "The nextCursor of the previous page.",
                   "schema": {"type": "string"}},
        "UpdatedAfter": {"name": "updatedAfter", "in": "query", "required": False,
                         "description": "Start of a synchronization: records with "
                                        "a later updatedAt.",
                         "schema": {"$ref": f"{COMPONENTS}DateTime"}},
        "IfMatch": {"name": "If-Match", "in": "header", "required": False,
                    "description": "Act only on this version of the record.",
                    "schema": {"type": "string"}},
        "IfNoneMatch": {"name": "If-None-Match", "in": "header", "required": False,
                        "description": "`*`: create only, never replace.",
                        "schema": {"type": "string", "enum": ["*"]}},
        "ProcessingJobId": {
            "name": "Processing-Job-Id", "in": "header", "required": False,
            "description": "The ProcessingJob a processing run writes in; the "
                           "server sets createdByJobId (or "
                           "AuditLog.changedByJobId) from it.",
            "schema": {"$ref": f"{COMPONENTS}Uuid"}},
        "ChangeReason": {
            "name": "Change-Reason", "in": "header", "required": False,
            "description": "Reason for a correction of documentation already "
                           "reported; recorded as AuditLog.reason. Required on "
                           "that path, otherwise optional.",
            "schema": {"type": "string", "minLength": 1}},
        "FeatureLimit": {"name": "limit", "in": "query", "required": False,
                         "schema": {"type": "integer", "minimum": 1,
                                    "maximum": 10000, "default": 10}},
        "Bbox": {"name": "bbox", "in": "query", "required": False,
                 "style": "form", "explode": False,
                 "description": "Only features intersecting this bounding box "
                                "(WGS 84: min longitude, min latitude, max "
                                "longitude, max latitude).",
                 "schema": {"type": "array", "minItems": 4, "maxItems": 4,
                            "items": {"type": "number"}}},
        "Datetime": {"name": "datetime", "in": "query", "required": False,
                     "description": "Only features valid at this instant or "
                                    "within this interval (startsAt, endsAt).",
                     "schema": {"type": "string"}},
    }
