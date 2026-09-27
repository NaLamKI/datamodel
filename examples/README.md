# Example dataset

One farm, told through every entity of the model at least once. The files are
JSON arrays of records as the API serves them (`application/json`); the
checks validate each record against its schema, read the whole dataset as RDF
with the JSON-LD context and validate it against both sets of SHACL shapes.

**Lindenhof**, a fictitious mixed farm, harvest year 2026:

- **Plant protection, documented** (Appendix I.5 of the Recommendation). A
  risk model run (`ProcessingJob`, `Result`) recommends a fungicide against
  Septoria on the field *Nordschlag*; the recommendation becomes a `Task`,
  the task an `Activity` at BBCH 32 with tractor, sprayer and operator
  (`ActivityResource`, the operator holding her certificate of competence in
  `Worker.certifications`), the product used an `InputOutput` of
  *DOMARK 10 EC* with its registration number. A report-generation run
  produces the `RegulatoryReport`, submitted — its `originType` is `SERVICE`
  and `createdByJobId` names the run.
- **Harvest, lot, sale** (Appendix I.8). The harvest `Activity` yields an
  `InputOutput`, the intake into store a `StockMovement` of a `Lot` whose
  origin is the cultivation period; the sale a second movement and the
  proceeds an `Economics` record.
- **Plan and outcome** (clause 7.4). A `CroppingPlanEntry` for winter wheat,
  the `CultivationPeriod` that carried it out, a planned fertilizer quantity,
  a `Budget`, a nitrogen balance as `SustainabilityIndicator`.
- **Perennial crop.** An apple `Stand` on the orchard and its 2026
  `CultivationPeriod`.
- **Dairy.** A cow, her group, a milk recording, a ration and the feed booked.
- **Sensing and data.** Weather station, soil moisture probe with a Thing
  Description, GNSS on the tractor; soil moisture, precipitation, a scouting
  record and a soil pH from a laboratory report (`Data`, `File`).

All names, numbers, e-mail addresses and identifiers are fictitious, except
the concept identifiers — resolved from the ontology under `ontology/`, never
typed by hand — and the product *DOMARK 10 EC* with registration number `004329-00`,
taken from the code list of the German Federal Office of Consumer Protection
and Food Safety (BVL): BUNDESAMT FÜR VERBRAUCHERSCHUTZ UND
LEBENSMITTELSICHERHEIT (BVL) 2026: [https://psm-api.bvl.bund.de/], Stand
2026-09-02. Nothing here is an agronomic recommendation.

The identifiers are UUIDs in lower case; any version will do. A new record
needs a new one, and every reference must point at a record in these files —
`tests/test_examples.py` checks that.
