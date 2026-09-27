# How the model becomes JSON, RDF and HTTP

The Recommendation specifies entities, attributes, rules and state models, and
for their representation a small number of requirements: JSON as the canonical
form, a JSON-LD context onto referenced vocabularies, OGC API - Features for
the geospatial entities, synchronization over `updatedAt` (clause 9). This
document says how this repository turns that into files a program can use —
and where it had to decide something the Recommendation leaves open. Each
decision is stated with its reason, so that it can be argued with.

---

## 0. One source, four views

| | Answers | Generated from `model/` by |
|---|---|---|
| **JSON Schema** (`v1/schema/`) | Is this JSON a well-formed record? | `tool/schemas.py` |
| **OpenAPI** (`v1/openapi.yaml`) | How is it read, written and synchronized over HTTP? | `tool/openapi.py` |
| **JSON-LD context** (`v1/context.jsonld`) | What does it mean, in the terms of the ontology? | `tool/context.py` |
| **SHACL** (`v1/shapes.ttl`, `v1/shapes-dataset.ttl`) | Does its RDF, and a dataset of such records, hold together? | `tool/shapes.py` |

The four cannot drift apart: the OpenAPI description embeds the very schemas
under `v1/schema/`, the context and the shapes are derived from the same
attribute list, and the checks under `tests/` hold each of them against the
example dataset and against the ontology.

---

## 1. JSON

Clause 9 fixes the essentials: camelCase attribute names, timestamps in
ISO 8601 and UTC, GeoJSON geometries, enumerations in upper case, identifiers
as strings, the system attributes on every record. Where it says nothing, this
specification decides:

| Question | Decision | Why |
|---|---|---|
| An optional attribute that is not set | omitted, never `null` | "Exactly one of these references is set" (clause 5.1 h)) is then a question of presence, and JSON Schema and SHACL can check it. `null` appears only in a JSON Merge Patch, where it means "remove". |
| The form of a UUID | lower case | Clause 9 turns every reference into an IRI (§ 2); `urn:uuid:ABC…` and `urn:uuid:abc…` are different IRIs, and a reference would miss its record. |
| A timestamp | `…Z` or `…+00:00` | "Coordinated universal time" (clause 5.1 c)), checked by pattern, not merely by `format`. |
| A Decimal | a JSON number | The natural reading of clause 9, and what every client expects. See § 2 for what that costs in RDF. |
| A unit | a string, UCUM recommended | Clause 5.1 j) says *should*; the schema describes UCUM but does not reject other units. Currencies (ISO 4217), countries (ISO 3166-1) and languages (BCP 47) are *shall* and are checked. |
| A country code | alpha-2, alpha-3 or numeric | ISO 3166-1 defines all three and the Recommendation names none; alpha-2 is recommended. |
| A Thing Description | a string, `contentMediaType: application/td+json` | Annex A gives `description` the type String; the content is a WoT Thing Description in JSON-LD. |
| An attribute the model does not have | rejected | The schemas are closed (`additionalProperties: false`), so that a misspelt attribute is found. A client reading responses should nevertheless ignore what it does not know. |

Two attributes are in the schemas although the tables of Annex A lack them:
`Machine.description` (clauses 5.1 f) and 9) and `ProcessingService.typeUri`
(clause 8.12, Annex B). Both are marked with their source.

---

## 2. RDF

`v1/context.jsonld` makes any record readable as RDF. It maps every attribute
onto the property the ontology declares for it — `agfoda:farmId`, not
`dct:isPartOf`; `agfoda:typeUri`, not `dct:type` — because those are the
properties the ontology binds to its classes and concept schemes. A look-alike
from another vocabulary would carry the same words and none of the
constraints.

A task, in JSON, as the server sends it for `application/ld+json`:

```json
{
  "@context": "https://datamodel.agrifooddata.org/v1/context.jsonld",
  "@id": "urn:uuid:069a9d2c-0d5c-5eda-b447-1eb9d3791f7e",
  "@type": "Task",
  "id": "069a9d2c-0d5c-5eda-b447-1eb9d3791f7e",
  "name": "Fungizidbehandlung Septoria, Nordschlag",
  "farmId": "997142c3-14cf-5cb4-b260-048af4b57a76",
  "status": "COMPLETED",
  "typeUri": "http://aims.fao.org/aos/agrovoc/c_5978",
  "createdAt": "2026-05-10T07:00:00Z",
  "originType": "USER",
  "createdByUserId": "b630da76-9ec3-5faa-a1d7-e66d56bc5db4"
}
```

and the same record in Turtle:

```turtle
<urn:uuid:069a9d2c-0d5c-5eda-b447-1eb9d3791f7e> a agfoda:Task ;
    agfoda:id "069a9d2c-0d5c-5eda-b447-1eb9d3791f7e" ;
    agfoda:name "Fungizidbehandlung Septoria, Nordschlag" ;
    agfoda:farmId <urn:uuid:997142c3-14cf-5cb4-b260-048af4b57a76> ;
    agfoda:taskStatus agfoda:TaskStatus_COMPLETED ;
    agfoda:typeUri <http://aims.fao.org/aos/agrovoc/c_5978> ;
    agfoda:createdAt "2026-05-10T07:00:00Z"^^xsd:dateTime ;
    agfoda:originType agfoda:OriginType_USER ;
    agfoda:createdByUser <urn:uuid:b630da76-9ec3-5faa-a1d7-e66d56bc5db4> .
```

The attributes are unchanged; the three JSON-LD keywords in front are all the
server adds. What the context does with them:

- **Records and references meet in one node.** A record's IRI is `urn:uuid:`
  and its id. A foreign key holds a bare UUID; its term carries a scoped
  `@vocab` of `urn:uuid:`, so `farmId` becomes the IRI of the farm's own node.
  `urn:uuid:` rather than an HTTP address, because the model is meant for a
  federation of nodes (clause 7.3): the same record is served by more than one
  of them, and its identity must not depend on which.
- **Enumerations are individuals.** `"status": "COMPLETED"` on a task becomes
  `agfoda:TaskStatus_COMPLETED`, the named individual the ontology declares.
- **Where the names differ.** The ontology names some properties differently
  from the attribute, and for `status`, `scopeType` and `validFrom` it has one
  property per class where JSON has one name. The context maps each; a name
  that depends on the class is resolved by a context scoped to the entity —
  the reason a representation read as JSON-LD carries `@type`.

| Attribute | On | Property |
|---|---|---|
| `description` | Device | `agfoda:thingDescription` |
| `iamResourceId` | Farm, Data | `agfoda:accessResourceId` |
| `scopeType` | Budget | `agfoda:budgetScopeType` |
| `scopeType` | SustainabilityIndicator | `agfoda:sustainabilityIndicatorScopeType` |
| `status` | Activity | `agfoda:activityStatus` |
| `status` | Animal | `agfoda:animalStatus` |
| `status` | CroppingPlan | `agfoda:croppingPlanStatus` |
| `status` | CultivationPeriod | `agfoda:cultivationPeriodStatus` |
| `status` | Device | `agfoda:deviceStatus` |
| `status` | Machine | `agfoda:machineStatus` |
| `status` | ProcessingJob | `agfoda:processingJobStatus` |
| `status` | RegulatoryReport | `agfoda:regulatoryReportStatus` |
| `status` | Task | `agfoda:taskStatus` |
| `status` | User | `agfoda:userStatus` |
| `validFrom` | Certification | `agfoda:certificationValidFrom` |
| `validFrom` | CodeMapping | `agfoda:codeMappingValidFrom` |
| `validFrom` | FeedRation | `agfoda:feedRationValidFrom` |
| `validFrom` | Result | `agfoda:resultValidFrom` |
| `createdByJobId` | every entity | `agfoda:createdByJob` |
| `createdByUserId` | every entity | `agfoda:createdByUser` |

- **JSON stays JSON.** Attributes of type JSON become `rdf:JSON` literals
  (`@type: @json`). That includes geometries: JSON-LD cannot produce a
  `geo:geoJSONLiteral` from an embedded GeoJSON object, and the ontology's
  range for geometries, `agfoda:GeoJSON`, admits both; the lexical form is the
  same GeoJSON text.
- **Numbers are not typed.** JSON-LD turns a number with a fraction into
  `xsd:double`; typing the terms `xsd:decimal` would make JSON-LD write
  lexical forms such as `"1.55E1"^^xsd:decimal`, which are invalid. The
  ontology's range for Decimal attributes, `agfoda:Decimal`, admits
  `xsd:decimal` and `xsd:double`, and the shapes accept all three numeric
  datatypes.
- **Lists read as RDF too.** In a page of a collection, `items` is an alias of
  `@included`; `nextCursor` and `hasMore` map to nothing.

One processor detail is worth knowing: a property-scoped
context that is identical across terms is resolved once by some JSON-LD
processors and the result reused for the next term — pyld 2.0.4 does, and from
the second foreign key on, references came out as literals. Every scoped
context in `context.jsonld` therefore restates its own term, which changes
nothing in meaning and makes each one distinct; `tests/test_jsonld.py`
compares pyld's output with rdflib's for every example record.

---

## 3. The ontology

The model is bound to the ontology, not merely named after it. Every entity is
a class (`agfoda:Task`), every attribute a property (`agfoda:farmId`), every
enumeration a class with one individual per value. The classifications
(`typeUri`, `cropUri`, `speciesUri` …) take their values from the concept
schemes the ontology binds them to: a cultivation period's `typeUri` is a
concept of `crops`, an activity's of `activity-types`; `bbchStage` holds the
notation of a concept of `phenology`.

That binding is checked, offline, against the ontology under `ontology/` — a
git submodule pinned at one commit of the ontology's repository:

- every entity is a class and every attribute a declared property whose domain
  includes the entity and whose range fits its type;
- an attribute is mandatory exactly where the ontology states a minimum
  cardinality;
- the values of every enumeration are the ontology's individuals;
- every record of the example dataset, read with the context, lands on
  declared properties only.

Where the ontology and the Recommendation differ, the Recommendation takes
precedence (clause 8) and the difference is listed in
[divergences](https://datamodel.agrifooddata.org/v1/divergences.html). Of the
twelve found while binding the model, the ontology fixed eleven in its version
of 2026-09-26; what remains is the mapping to AGROVOC that clause 7.2 asks
for, which the ontology has made for part of its crops and pests only. A check
fails as soon as such a difference appears, and again once it is fixed
upstream but still listed.

Every class, property and enumeration value links to its row on the
ontology's [schema page](https://ontology.agrifooddata.org/term.html); its
identifier, `https://w3id.org/agrifooddata/term/<name>`, is redirected there
by the ontology's w3id rules.

---

## 4. HTTP

`v1/openapi.yaml` is a reference binding, not text of the Recommendation. It
maps its requirements onto HTTP as follows.

| Requirement | Binding |
|---|---|
| Identifiers generated by the client (clause 9) | `PUT /{collection}/{id}` creates a record under its own identifier; `If-None-Match: *` makes it create-only, so that a repeated request after a lost response cannot overwrite anything. |
| Per-attribute last-write-wins (clause 5.1 b)) | `PATCH` with JSON Merge Patch (RFC 7396) changes only the attributes it names; of two changes to the same attribute the later wins. `If-Match` with the `ETag` is available where a client prefers to fail. |
| Correction path for reported documentation | A change to a record that a RegulatoryReport in status `SUBMITTED` or later refers to needs `Change-Reason`, which the server records as `AuditLog.reason`. A submitted report itself is immutable (V15). |
| Provenance (clause 5.1 l)) | The server sets `createdAt`, `updatedAt`, `createdByUserId`, `createdByJobId` and `clientId` from the authenticated caller. A processing run names its ProcessingJob in `Processing-Job-Id`; `originType` may be declared on creation and is checked against the caller. |
| Synchronization by a cursor over `updatedAt` (clause 9) | Every collection lists by `updatedAt`, then `id`. `updatedAfter` starts a synchronization, `nextCursor` continues it — returned on the last page too, so that the next poll resumes exactly there. |
| Withdrawal and deletion propagated | Withdrawal is a status change and arrives with the record; a deletion arrives as a `DELETE` entry of `/audit-logs`, which is read-only. |
| State models (clause 13) | A status change not in the state model is refused with `409` and the problem type `invalid-transition`. |
| Integrity rules (clause 12) | Violations are reported as RFC 9457 problem details whose `violations` name the rule (`V01` … `V16`) and the attribute. |
| Authentication and authorization (clause 10) | OpenID Connect against the external IAM system. `x-agfoda-permission` names the permission an operation requires, in the `entity:action` pattern of `Role.permissions`, evaluated per farm in addition to the IAM's policies. |
| OGC API - Features for Field, Region, Site (clause 9) | `/features` with landing page, conformance, collections and items as GeoJSON. |
| Derived stock levels (clauses 7.5, 8.6) | `GET /stock-levels`, computed from the stock movements, never stored. |

Deliberately not specified: how a client obtains its token, rate limits,
bulk import, the transfer of file contents (a File refers to object storage
through `storageUrl`), and the interfaces of external services — SensorThings
endpoints are referenced, not described. The exchange formats clause 9 names
besides the model's own JSON — task data conforming to ISO 11783-10, an export
to an agricultural data exchange profile — are formats of their own; the model
carries what they need (`Activity.isobusTaskRef`, `Machine.isobusDeviceId`,
the ISOBUS codes bound through CodeMapping).

---

## 5. Which artefact checks what

A rule is checked where it can be checked. `model/rules.yaml` records this for
each rule, and the [rules page](https://datamodel.agrifooddata.org/v1/rules.html) shows it.

| Check | JSON Schema | SHACL, record | SHACL, dataset | Interface |
|---|---|---|---|---|
| Types, mandatory attributes, enumerations, formats | ✓ | ✓ | | |
| Exclusive references (V03), positive quantities (V02), provenance (V04) | ✓ | ✓ | | |
| Conditions of clause 8 (registration number, resource type …) | ✓ | ✓ | | |
| Period order (V01, V08) | | ✓ | | ✓ |
| References point at a record of the right entity | | | ✓ | ✓ |
| Classifications are concepts of the bound scheme | | | ✓ | ✓ |
| One default region per field (V05), stand on the same region (V08), planned crop (V07), plant protection product behind an application (V09) | | | ✓ | ✓ |
| Business keys, state models, withdrawal periods (V11), stock levels (V12), immutability (V15), overlapping assignments (V16) | | | | ✓ |

A rule expressed with "should" is a warning, not an error (clause 12): the
JSON Schemas leave it out, the shapes report it with `sh:severity sh:Warning`.

---

## 6. What deliberately does not live here

- **Usage policies.** Clause 11 places them in the data space or IAM layer,
  expressed in a policy language such as ODRL; the model records only the
  resource identifiers (`iamResourceId`) they are bound through.
- **Time series.** High-frequency data remain in a time series backend or a
  SensorThings service (clause 8.9); `Device.sensorThingsUrl` points there.
- **The vocabulary.** Concepts and code lists live in the ontology and are
  referenced by identifier, never copied into the schemas — a schema that
  listed the crops would be out of date with the next BVL extract.
- **A provenance export.** Clause 11 asks that provenance, audit log and
  the chain from ProcessingJob to Result be exportable as PROV-O. The
  attributes map onto ontology properties that are subproperties of PROV-O
  where the ontology says so (`createdByUser`, `createdByJob`,
  `changedByUserId`, `changedByJobId`); an export endpoint is an
  implementation matter.
- **An application's own fields.** They belong in the application's own
  namespace, not in the model; the closed schemas reject them on purpose.
