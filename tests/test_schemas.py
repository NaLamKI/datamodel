"""Whether the JSON Schemas accept what is right and refuse what is wrong.

A schema that accepts the examples proves little: an empty schema does too.
Most checks here therefore take a valid example, break it in one specific
way — the way a rule of the Recommendation forbids — and demand that the
schema refuses it.
"""
from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator


def test_every_schema_is_valid_json_schema_2020_12(standalone_schemas):
    for name, schema in standalone_schemas.items():
        Draft202012Validator.check_schema(schema)


def test_every_entity_has_an_example(model, examples):
    missing = [e.name for e in model.ordered() if not examples[e.name]]
    assert not missing


def test_every_example_conforms_to_its_schema(model, examples, validator_for):
    errors = []
    for e in model.ordered():
        v = validator_for(e.name)
        for rec in examples[e.name]:
            errors += [f"{e.name} {rec['id']}: {err.json_path} {err.message}"
                       for err in v.iter_errors(rec)]
    assert not errors, errors[:5]


def test_a_json_ld_representation_conforms_too(model, examples, validator_for):
    """`application/ld+json` adds @context, @id and @type in front; the
    schema admits exactly those."""
    import context
    e = model.entities["Task"]
    doc = context.representation(model, e, examples["Task"][0])
    assert not list(validator_for("Task").iter_errors(doc))
    doc["@type"] = "Activity"
    assert list(validator_for("Task").iter_errors(doc))


def test_every_property_names_its_ontology_term(model, standalone_schemas):
    for e in model.ordered():
        props = standalone_schemas[f"{e.name}.json"]["properties"]
        for a in e.attributes.values():
            assert props[a.name]["x-agfoda-property"] == f"{model.ns}{a.term}"


def _first(examples, entity: str, needs=()) -> dict:
    """A copy of the first example that has every attribute in `needs`."""
    for rec in examples[entity]:
        if all(k in rec for k in needs):
            return copy.deepcopy(rec)
    raise LookupError(entity, needs)


def _drop(rec, *keys):
    for k in keys:
        rec.pop(k, None)
    return rec


# (entity, attributes the example must have, how to break it, what forbids it)
BROKEN = [
    ("Task", ["farmId"], lambda r: _drop(r, "farmId"), "a mandatory attribute is missing"),
    ("Task", [], lambda r: r.update(colour="red"), "an attribute the model does not have"),
    ("Task", [], lambda r: r.update(status="DONE"), "a value outside the enumeration"),
    ("Task", [], lambda r: r.update(typeUri="urn:example:spraying"),
     "a classification that is not a dereferenceable URI (clause 5.1 e))"),
    ("Task", [], lambda r: r.update(dueAt="2026-05-14T20:00:00+02:00"),
     "a timestamp not in UTC (clause 5.1 c))"),
    ("Task", [], lambda r: r.update(farmId=r["farmId"].upper()), "a UUID not in lower case"),
    ("InputOutput", ["activityId"], lambda r: r.update(cultivationPeriodId=r["activityId"]),
     "two exclusive references (V03)"),
    ("InputOutput", ["activityId"], lambda r: _drop(r, "activityId"),
     "no exclusive reference (V03)"),
    ("Observation", ["regionId"], lambda r: r.update(fieldId=r["regionId"]),
     "two features of interest (V03)"),
    ("Economics", ["inputOutputId"], lambda r: _drop(r, "inputOutputId"),
     "nothing valued (V03)"),
    ("StockMovement", [], lambda r: r.update(quantity=-1), "a negative quantity (V02)"),
    ("Field", ["area"], lambda r: r.update(area=0), "an area of zero (V02)"),
    ("Task", ["createdByUserId"], lambda r: _drop(r, "createdByUserId"),
     "originType USER without createdByUserId (V04)"),
    ("Result", ["createdByJobId"], lambda r: _drop(r, "createdByJobId"),
     "originType SERVICE without createdByJobId (V04)"),
    ("Product", ["registrationNumber"], lambda r: _drop(r, "registrationNumber"),
     "a plant protection product without registration number (clause 8.6)"),
    ("ActivityResource", ["machineId"], lambda r: r.update(resourceType="WORKER"),
     "a machine deployment declared as a worker (clause 8.5)"),
    ("Lot", ["originCultivationPeriodId"],
     lambda r: r.update(originAnimalGroupId=r["originCultivationPeriodId"]),
     "two origins of own production (V13)"),
    ("Device", ["regionId"], lambda r: r.update(siteId=r["regionId"]),
     "a device mounted in two places (clause 8.9)"),
    ("ProcessingJobInput", ["entityId"], lambda r: _drop(r, "entityId"),
     "entityType without entityId (clause 8.12)"),
    ("Activity", ["cultivationPeriodId"], lambda r: _drop(r, "cultivationPeriodId"),
     "an operation without context (clause 8.5)"),
    ("Site", ["geometry"], lambda r: r.update(geometry={
        "type": "LineString", "coordinates": [[13.4, 52.5], [13.5, 52.5]]}),
     "a site that is neither Point nor Polygon (clause 8.2)"),
    ("Field", [], lambda r: r.update(geometry={"type": "Point", "coordinates": [200, 52.5]}),
     "a longitude outside WGS 84"),
    ("Farm", [], lambda r: r.update(defaultCurrency="euro"), "a currency not in ISO 4217"),
    ("Address", [], lambda r: r.update(country="Germany"), "a country not in ISO 3166-1"),
    ("Role", [], lambda r: r.update(permissions=["read everything"]),
     "a permission not in the entity:action pattern"),
    ("AuditLog", [], lambda r: r.update(entityType="Tractor"),
     "an entity the model does not have"),
]


@pytest.mark.parametrize("entity,needs,breaks,reason", BROKEN,
                         ids=[f"{e}: {why}" for e, _, _, why in BROKEN])
def test_a_broken_record_is_refused(examples, validator_for, entity, needs, breaks, reason):
    rec = _first(examples, entity, needs)
    assert not list(validator_for(entity).iter_errors(rec)), "the example itself is invalid"
    breaks(rec)
    assert list(validator_for(entity).iter_errors(rec)), f"accepted: {reason}"


def test_a_should_is_not_an_error(examples, validator_for):
    """Clause 12: a rule expressed with "should" raises a warning. A task
    without operational context is therefore valid JSON (the shapes warn)."""
    rec = _first(examples, "Task")
    _drop(rec, "cultivationPeriodId", "regionId", "siteId", "animalGroupId")
    assert not list(validator_for("Task").iter_errors(rec))


def test_a_custom_service_without_type_is_valid_but_warned(examples, validator_for):
    rec = _first(examples, "ProcessingService")
    rec["serviceType"] = "CUSTOM"
    assert not list(validator_for("ProcessingService").iter_errors(rec))
