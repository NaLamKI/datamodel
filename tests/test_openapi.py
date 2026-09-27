"""Whether the OpenAPI description is valid and says the same as the schemas."""
from __future__ import annotations

import json
import re

import pytest


@pytest.fixture(scope="session")
def api(model, ontology) -> dict:
    import openapi
    return openapi.build(model, ontology)


def test_the_description_is_valid_openapi_3_1(api):
    from openapi_spec_validator import validate
    validate(json.loads(json.dumps(api)))


def test_every_entity_has_its_operations(model, api):
    """Five operations per entity; the audit log, written by the system and
    append-only, is read only."""
    for e in model.ordered():
        collection = api["paths"][f"/{e.path}"]
        item = api["paths"][f"/{e.path}/{{id}}"]
        methods = {m for m in item if m in ("get", "put", "patch", "delete")}
        assert "get" in collection, e.name
        if e.systemManaged:
            assert methods == {"get"}, e.name
        else:
            assert methods == {"get", "put", "patch", "delete"}, e.name


def test_operation_ids_are_unique(api):
    ids = [op["operationId"] for item in api["paths"].values()
           for m, op in item.items() if m in ("get", "put", "patch", "delete")]
    assert len(ids) == len(set(ids))


def test_the_components_are_the_published_schemas(model, ontology, api, standalone_schemas):
    """The OpenAPI description embeds the schemas under v1/schema/: same
    content, references pointed elsewhere."""
    def to_openapi(schema):
        text = json.dumps(schema)
        text = re.sub(r'"(common|enumerations)\.json#/\$defs/', '"#/components/schemas/', text)
        return json.loads(text)

    for e in model.ordered():
        published = dict(standalone_schemas[f"{e.name}.json"])
        published.pop("$schema")
        published.pop("$id")
        assert api["components"]["schemas"][e.name] == to_openapi(published), e.name


def test_every_operation_names_its_permission(model, api):
    """`entity:action`, the pattern of Role.permissions (clause 8.1)."""
    entities = {e.permission for e in model.ordered()}
    for path, item in api["paths"].items():
        for m, op in item.items():
            if m not in ("get", "put", "patch", "delete"):
                continue
            if "x-agfoda-permission" not in op:
                # Only the landing pages of the Features binding name none.
                assert path in ("/features", "/features/conformance",
                                "/features/collections",
                                "/features/collections/{collectionId}"), path
                continue
            perms = op["x-agfoda-permission"]
            for perm in perms if isinstance(perms, list) else [perms]:
                entity, _, action = perm.partition(":")
                assert entity in entities and action in (
                    "read", "create", "update", "delete"), f"{m} {path}: {perm}"


def test_a_patch_cannot_touch_the_system_attributes(model, api):
    for e in model.ordered():
        if e.systemManaged:
            continue
        props = api["components"]["schemas"][f"{e.name}Patch"]["properties"]
        assert not {"id", "createdAt", "updatedAt", "originType", "createdByUserId",
                    "createdByJobId", "clientId"} & set(props), e.name


def test_the_geospatial_entities_are_feature_collections(api):
    """Clause 9: Field, Region and Site as OGC API - Features."""
    for path in ("/features", "/features/conformance", "/features/collections",
                 "/features/collections/fields/items", "/features/collections/regions/items",
                 "/features/collections/sites/items"):
        assert path in api["paths"], path


def test_every_problem_type_is_described(model, api):
    import openapi
    table = api["info"]["description"]
    for slug, status, _, _ in openapi.PROBLEMS:
        assert f"`{slug}` | {status}" in table


def test_every_reference_resolves(api):
    """A dangling $ref is found here rather than by the first client."""
    refs = set(re.findall(r'"\$ref": "#/([^"]+)"', json.dumps(api)))
    for ref in refs:
        node = api
        for part in ref.split("/"):
            assert part in node, ref
            node = node[part]
