"""Whether the model says what the Recommendation says.

The model under model/ was written from the Recommendation (revision 3). These
checks hold it to the parts of the text that are easy to get wrong in a
thousand lines of YAML: which entity sits in which package, which attributes
are quantities, which references are exclusive, which entities describe
themselves. Where a check names a list, the list is the Recommendation's.
"""
from __future__ import annotations

import re

import pytest

from model import load_yaml

# Table 1 of the Recommendation.
TABLE_1 = {
    "P1": ["Organization", "User", "Worker", "Address", "Role", "AccessAssignment"],
    "P2": ["Farm", "Site"],
    "P3": ["Field", "Region"],
    "P4": ["CroppingPlan", "CroppingPlanEntry", "Stand", "CultivationPeriod"],
    "P5": ["Task", "Activity", "ActivityResource", "TimeRecord"],
    "P6": ["Product", "StorageLocation", "Lot", "StockMovement"],
    "P7": ["Machine", "MaintenanceRecord"],
    "P8": ["Animal", "AnimalGroup", "AnimalEvent", "FeedRation", "FeedRationComponent"],
    "P9": ["Device", "Observation", "Data", "DataType", "File"],
    "P10": ["InputOutput", "Economics", "Budget"],
    "P11": ["RegulatoryReport", "Certification", "AuditLog"],
    "P12": ["ServiceCatalogue", "ProcessingService", "ProcessingJob",
            "ProcessingJobInput", "Result"],
    "P13": ["SustainabilityIndicator"],
    "P14": ["CodeMapping"],
}


def test_the_model_holds_together(model):
    """No reference to an entity, enumeration, attribute or rule that does
    not exist — the slip YAML never complains about."""
    assert model.problems() == []


def test_fourteen_packages_with_the_entities_of_table_1(model):
    assert {p.id: p.entities for p in model.packages} == TABLE_1


def test_forty_seven_entities_in_the_order_of_annex_a(model):
    """Annex A numbers the entities A.1 to A.47 in the order of the packages."""
    annexes = [e.annex for e in model.ordered()]
    assert annexes == [f"A.{n}" for n in range(1, 48)]


def test_every_attribute_says_what_it_is(model):
    mute = [f"{e.name}.{a.name}" for e in model.ordered()
            for a in e.attributes.values() if not a.description.strip()]
    assert not mute


def test_names_follow_clause_5_1_k(model):
    """Entities in PascalCase, attributes in camelCase, foreign keys <entity>Id."""
    wrong = []
    for e in model.ordered():
        if not re.fullmatch(r"[A-Z][A-Za-z]+", e.name):
            wrong.append(e.name)
        for a in e.attributes.values():
            if not re.fullmatch(r"[a-z][A-Za-z]*", a.name):
                wrong.append(f"{e.name}.{a.name}")
            if a.references and not a.name.endswith("Id"):
                wrong.append(f"{e.name}.{a.name}: a reference ends in Id")
    assert not wrong


def test_every_uuid_ending_in_id_is_a_reference(model):
    """A UUID attribute named ...Id points somewhere: at one entity, or at
    the one another attribute names."""
    loose = [f"{e.name}.{a.name}" for e in model.ordered()
             for a in e.attributes.values()
             if a.type == "UUID" and a.name != "id" and not a.references
             and not a.referencesBy]
    assert not loose


def test_the_exclusive_references_of_rule_v03(model):
    """V03 names seven entities; each has its exclusive reference group."""
    named = {"InputOutput", "Observation", "Data", "Economics", "AnimalEvent",
             "ActivityResource", "ProcessingJobInput"}
    have = {e.name for e in model.ordered() for c in e.constraints
            if c.kind == "exactlyOne" and c.rule == "V03"}
    assert have == named


def test_the_quantities_of_rule_v02(model):
    """V02: amount, quantity, dosage, area, capacity and headCount are greater
    than zero — and nothing else, Economics.value least of all."""
    positive = {a.name for e in model.ordered() for a in e.attributes.values()
                if a.positive}
    assert positive == {"amount", "quantity", "dosage", "area", "capacity", "headCount"}
    assert not model.entities["Economics"].attributes["value"].positive


def test_the_self_describing_entities_of_clause_5_1_f(model):
    """Clause 5.1 f) lists eight entities whose description is a Thing
    Description; Annex A.13 adds Stand (divergence R3)."""
    listed = {"Field", "Region", "Site", "Machine", "Device", "Data",
              "ProcessingService", "Result"}
    have = {e.name for e in model.ordered()
            if "description" in e.attributes and e.attributes["description"].thingDescription}
    assert have == listed | {"Stand"}


def test_the_external_synchronization_pair_of_clause_5_1_g(model):
    listed = {"Organization", "Farm", "Field", "Machine", "Animal", "Product", "Device"}
    have = {e.name for e in model.ordered()
            if {"externalId", "externalProvider"} <= set(e.attributes)}
    assert have == listed


def test_every_entity_carries_the_attributes_of_clause_5_1(model):
    system = ["id", "createdAt", "updatedAt", "originType", "createdByUserId",
              "createdByJobId", "clientId"]
    for e in model.ordered():
        assert [n for n in e.attributes if n in system] == system, e.name


def test_the_state_models_of_table_4(model):
    assert set(model.states) == {
        "Task", "CultivationPeriod", "Activity", "ProcessingJob", "RegulatoryReport",
        "CroppingPlan", "Animal", "User", "Machine", "Device"}


def test_every_enumeration_is_used(model):
    used = {a.enum for e in model.ordered() for a in e.attributes.values() if a.enum}
    assert used == set(model.enumerations)


def test_the_enumerations_of_annex_b(model):
    """Annex B, Table B.1: the permitted values, spot-checked where the
    list is long."""
    assert model.enum_values("ProductCategory") == [
        "SEED", "PLANT_MATERIAL", "FERTILIZER", "PLANT_PROTECTION", "FEED",
        "VETERINARY_MEDICINE", "FUEL", "HARVEST_PRODUCT", "ANIMAL_PRODUCT", "OTHER"]
    assert model.enum_values("ServiceType")[-1] == "CUSTOM"
    assert model.enum_values("OriginType") == ["USER", "SERVICE", "DEVICE", "IMPORT", "SYSTEM"]


def test_paths_are_distinct_and_kebab_case(model):
    paths = [e.path for e in model.ordered()]
    assert len(paths) == len(set(paths))
    assert all(re.fullmatch(r"[a-z]+(-[a-z]+)*", p) for p in paths)


def test_the_loader_refuses_a_key_given_twice(tmp_path):
    """YAML keeps the second value of a duplicated key without a word. In an
    attribute list that silently replaces one attribute by another."""
    path = tmp_path / "twice.yaml"
    path.write_text("a:\n  type: String\na:\n  type: UUID\n", encoding="utf-8")
    import yaml
    with pytest.raises(yaml.constructor.ConstructorError):
        load_yaml(path)


def test_the_attributes_beyond_annex_a_name_their_source(model):
    """Two attributes come from clause text rather than the tables of Annex A
    (divergences R1 and R2); they say so."""
    extra = {f"{e.name}.{a.name}" for e in model.ordered()
             for a in e.own.values() if a.source}
    assert extra == {"Machine.description", "ProcessingService.typeUri"}
