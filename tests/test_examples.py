"""Whether the example dataset is one farm, not 47 unrelated records.

The examples serve the reference pages and every other check here. They are
worth something only if they hold together: every reference resolves, the
story adds up, and the rules the schemas cannot check hold as well.
"""
from __future__ import annotations

import re
from collections import defaultdict

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def test_identifiers_are_unique_and_canonical(examples):
    ids = [r["id"] for recs in examples.values() for r in recs]
    assert len(ids) == len(set(ids))
    assert all(UUID.match(i) for i in ids)


def test_every_reference_resolves_to_a_record_of_the_named_entity(model, examples, records):
    dangling = []
    for e in model.ordered():
        for rec in examples[e.name]:
            for a in e.attributes.values():
                if a.references and a.name in rec:
                    target = records.get(rec[a.name])
                    if target is None or target[0] != a.references:
                        dangling.append(f"{e.name}.{a.name} = {rec[a.name]}")
                if a.referencesBy and a.name in rec:
                    by = rec.get(a.referencesBy["attribute"])
                    targets = a.referencesBy.get("targets")
                    expected = targets.get(by) if targets else by
                    target = records.get(rec[a.name])
                    if expected and (target is None or target[0] != expected):
                        dangling.append(f"{e.name}.{a.name} = {rec[a.name]} ({by})")
    assert not dangling


def test_periods_are_in_order(model, examples):
    """V01 and V08, which JSON Schema cannot compare."""
    wrong = []
    for e in model.ordered():
        pairs = model.v01_pairs(e) + ([("plantingDate", "clearingDate")]
                                      if e.name == "Stand" else [])
        for rec in examples[e.name]:
            for a, b in pairs:
                if a in rec and b in rec and rec[b] < rec[a]:
                    wrong.append(f"{e.name} {rec['id']}: {b} < {a}")
    assert not wrong


def test_stock_levels_do_not_go_negative(examples):
    """V12, over the derived view of rules.yaml: in at the destination, out
    at the origin, per product, lot, storage location and unit."""
    levels: dict[tuple, float] = defaultdict(float)
    for m in sorted(examples["StockMovement"], key=lambda m: m["occurredAt"]):
        key = (m["productId"], m.get("lotId"), m["unit"])
        if "toStorageLocationId" in m:
            levels[key + (m["toStorageLocationId"],)] += m["quantity"]
        if "fromStorageLocationId" in m:
            levels[key + (m["fromStorageLocationId"],)] -= m["quantity"]
        if m["movementType"] != "ADJUSTMENT":
            assert all(v >= -1e-9 for v in levels.values()), m["id"]


def test_every_record_created_by_a_user_or_a_run_says_by_whom(examples, records):
    """V04, and that the user or the run exists."""
    for recs in examples.values():
        for r in recs:
            if r["originType"] == "USER":
                assert records[r["createdByUserId"]][0] == "User"
            if r["originType"] == "SERVICE":
                assert records[r["createdByJobId"]][0] == "ProcessingJob"


def test_the_digital_twin_loop_is_closed(examples, records):
    """Clause 7.1: a Result gives rise to a Task, the Task is carried out as
    an Activity, whose input is documented."""
    task = next(t for t in examples["Task"] if "sourceResultId" in t)
    assert records[task["sourceResultId"]][0] == "Result"
    activity = next(a for a in examples["Activity"] if a.get("taskId") == task["id"])
    assert any(io.get("activityId") == activity["id"] for io in examples["InputOutput"])


def test_the_regulated_application_is_documented(examples, records, model, ontology):
    """Appendix I.5: operator with certificate, product with authorization
    number, quantity, growth stage — and a submitted report produced by a
    service run."""
    spray = ontology.concept(**model.rules["V09"]["concepts"]["application"])
    act = next(a for a in examples["Activity"] if a["typeUri"] == spray)
    assert "bbchStage" in act
    worker = next(records[r["workerId"]][1] for r in examples["ActivityResource"]
                  if r["activityId"] == act["id"] and r["resourceType"] == "WORKER")
    assert worker["certifications"]
    io = next(i for i in examples["InputOutput"] if i.get("activityId") == act["id"])
    assert records[io["productId"]][1]["registrationNumber"]
    report = examples["RegulatoryReport"][0]
    assert report["status"] == "SUBMITTED" and report["originType"] == "SERVICE"


def test_the_harvest_is_traceable_to_the_sale(examples, records):
    """Appendix I.8: harvest, lot, intake, sale, proceeds."""
    lot = next(l for l in examples["Lot"] if "originCultivationPeriodId" in l)
    moves = [m for m in examples["StockMovement"] if m.get("lotId") == lot["id"]]
    assert {m["movementType"] for m in moves} >= {"HARVEST_INTAKE", "SALE"}
    sale = next(m for m in moves if m["movementType"] == "SALE")
    assert any(e.get("stockMovementId") == sale["id"] for e in examples["Economics"])


def test_names_are_fictitious(examples):
    """No real e-mail domains: the examples are published."""
    for r in examples["User"]:
        assert r["email"].endswith("@example.org")
