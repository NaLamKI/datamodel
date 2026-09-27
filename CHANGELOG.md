# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/), with the revision
of the Recommendation as a pre-release label until it is approved.

## 1.0.0-draft.3 — 2026-09-26

First release: the model of the draft Recommendation *Data model for digital
agriculture and farm management systems*, revision 3 of 2026-07-29, bound to
the agrifooddata ontology as of 2026-09-27 (`809c186`).

### Added

- **The model** under `model/`: 47 entities in 14 packages with the attributes
  of Annex A in its wording, the conventions of clause 5.1 as EntityBase, the
  enumerations of Annex B, the rules V01–V16 with where each is checked, the
  business keys of Table 3, the state models of Table 4, the derived views of
  clause 7.5.
- **JSON Schema 2020-12** per entity, closed, with every constraint a single
  record can carry: exclusive references (V03), positive quantities (V02),
  provenance (V04), the conditions of clause 8.
- **OpenAPI 3.1**: a reference REST binding — client-generated identifiers,
  JSON Merge Patch, synchronization by cursor over `updatedAt`, the
  correction path, problem details naming the violated rule, OGC API -
  Features for fields, regions and sites, derived stock levels.
- **JSON-LD 1.1 context** mapping every attribute onto the ontology's own
  property; references and records meet as `urn:uuid:` IRIs, enumeration
  values become the ontology's individuals.
- **SHACL shapes** for a single record and for a dataset: references,
  concept schemes, and V05, V07, V08, V09 across records.
- **Example dataset**: one fictitious farm through all 47 entities, from a
  risk model run to a submitted plant protection record and from the harvest
  to the sale.
- **Reference pages** for every entity, the API, the rules, the enumerations
  and the divergences, published through GitHub Pages at
  <https://datamodel.agrifooddata.org>.
- Checks, all without network access: the model against the Recommendation's
  tables, the binding against the pinned ontology, each rule against an
  example broken in exactly its way, the published files against the build.

### Decided

- **An address keeps its meaning.** Every artefact is published under the
  major version (`v1/`); a breaking change gets `v2/` next to it.
- **Optional attributes are omitted, never `null`**; UUIDs in lower case;
  timestamps checked for UTC by pattern; Decimal as a JSON number.
- **Every attribute maps onto the ontology's own property**, not onto a
  look-alike in DCMI Terms or PROV-O; the alignment belongs in the ontology.
- **The ontology is a git submodule, not a copy.** This repository records
  which commit of the ontology the model is checked against; its files stay
  in the ontology's repository, and the checks still run offline.
- **Record IRIs are `urn:uuid:`**, not HTTP addresses: in a federation the
  same record is served by more than one node.
- **The shapes are written as Turtle text**, not serialised by rdflib, whose
  blank-node output is not reproducible.
- Two attributes the tables of Annex A lack are included, with their source:
  `Machine.description` (clauses 5.1 f), 9) and `ProcessingService.typeUri`
  (clause 8.12, Annex B).

### Found

Recorded in `model/divergences.yaml`, each with the reading taken:

- In the ontology, and fixed there by its version of 2026-09-26: Address was missing from the domains of
  `organizationId` and `farmId`, Machine from that of `description`,
  ProcessingService from that of `typeUri`; `roleUris` was functional though a
  list; the three bindings of `observedPropertyUri` intersected; geometries
  and Decimal values had ranges that what JSON-LD makes of them contradicted;
  a comment on Lot contradicted V13; the term IRIs did not dereference; its
  own context mapped onto properties it does not constrain, and the alignment
  with PROV-O made every ProcessingJob an activity and an entity at once.
  What remains (O10): the schemes crops and pests are mapped to AGROVOC only
  in part, phenology not at all, although clause 7.2 asks for the mapping.
- In the Recommendation: four of the eight AGROVOC identifiers in Appendix III
  name other concepts; the Thing Description of Appendix II does not conform
  to WoT TD 1.1; Table 4 lets a rejected report be regenerated although V15
  makes it immutable; a stock level is defined per storage location, which a
  stock movement does not have; a budget scoped to a cost category has no
  attribute for it; Region.area has no unit.
- pyld 2.0.4 reuses a resolved scoped context across terms and turned each
  foreign key from the second on into a literal; every scoped context in the context
  therefore restates its own term, and the checks compare pyld with rdflib.
