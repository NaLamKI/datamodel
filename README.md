# agrifooddata-datamodel

The machine-readable specification of the **AgriFoodData model** — the data
model of the draft Recommendation *Data model for digital agriculture and farm
management systems* — published at

**<https://datamodel.agrifooddata.org>**

47 entities in 14 packages, from organizations, farms and fields to
cultivation periods, operations, animals, observations, economics, regulatory
reports and processing runs. Every entity is a class of the
[agrifooddata ontology](https://ontology.agrifooddata.org), every attribute
one of its properties, every classification a concept of one of its schemes —
and that is checked, not asserted.

```json
{
  "id": "069a9d2c-0d5c-5eda-b447-1eb9d3791f7e",
  "name": "Fungizidbehandlung Septoria, Nordschlag",
  "farmId": "997142c3-14cf-5cb4-b260-048af4b57a76",
  "status": "COMPLETED",
  "typeUri": "http://aims.fao.org/aos/agrovoc/c_5978",
  "createdAt": "2026-05-10T07:00:00Z",
  "updatedAt": "2026-05-12T06:20:00Z",
  "originType": "USER",
  "createdByUserId": "b630da76-9ec3-5faa-a1d7-e66d56bc5db4"
}
```

A task. The same record reads as `agfoda:Task` with `agfoda:taskStatus
agfoda:TaskStatus_COMPLETED` and `agfoda:farmId <urn:uuid:9971…>` through the
JSON-LD context — see [BINDINGS.md](BINDINGS.md).

## What lives here

Under `https://datamodel.agrifooddata.org/v1/`:

| | | |
|---|---|---|
| `openapi.yaml`, `openapi.json` | OpenAPI 3.1 | The REST binding: every entity as a collection, offline synchronization, OGC API - Features for fields, regions and sites |
| `schema/<Entity>.json` | JSON Schema 2020-12 | One schema per entity, for records as stored and exchanged |
| `context.jsonld` | JSON-LD 1.1 | Reads the JSON as RDF, on the ontology's own properties |
| `shapes.ttl` | SHACL | Checks a single record in RDF |
| `shapes-dataset.ttl` | SHACL | Checks a dataset: references, concept schemes, rules across records |
| `model.json` | JSON | The whole model in one document, for generators |
| `examples/<Entity>.json` | JSON | One consistent, fictitious farm |
| `<Entity>.html` | HTML | The reference page of each entity |

Next to them: the integrity rules V01–V16 with where each is checked, the state
models, the business keys, the enumerations, and the
[divergences](https://datamodel.agrifooddata.org/v1/divergences.html) —
where the Recommendation, the ontology and this specification part ways.

## Using it

Validate a record against its schema:

```python
import json, urllib.request
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

base = "https://datamodel.agrifooddata.org/v1/schema/"
def fetch(uri):
    return Resource.from_contents(json.load(urllib.request.urlopen(uri)))

registry = Registry(retrieve=fetch)
schema = fetch(base + "Task.json").contents
Draft202012Validator(schema, registry=registry).validate(task)
```

Read it as RDF, and check it:

```bash
# with the context, any JSON-LD processor turns a record into triples
riot --syntax=jsonld task.jsonld > task.ttl
pyshacl -s https://datamodel.agrifooddata.org/v1/shapes.ttl task.ttl
```

The API description loads into any OpenAPI 3.1 tool. It is a reference
binding: the Recommendation specifies the data and the requirements of its
clauses 9 and 10, and [BINDINGS.md](BINDINGS.md) says how they became paths,
headers and status codes.

## How it is made

```
model/       the source: model.yaml (conventions, EntityBase), packages/
             (one file per package, attributes in the wording of Annex A),
             enumerations, rules, state models, divergences
ontology/    the agrifooddata ontology as a git submodule, pinned at one commit
             of github.com/NaLamKI/ontology — referenced, not copied
examples/    the example dataset
tool/        build.py and the generators
tests/       run without network access
docs/        what GitHub Pages serves — generated in full
```

**`docs/` is not edited by hand.** It is generated from `model/`,
`ontology/`, `examples/` and `BINDINGS.md`. `ontology/` is a submodule, so
clone with `--recurse-submodules`, or run `git submodule update --init` once
in an existing clone:

```bash
git clone --recurse-submodules https://github.com/NaLamKI/datamodel.git
pip install -r requirements.txt
python3 tool/build.py
python3 -m pytest
```

`python3 -m http.server 8000 --directory docs` serves the result at
<http://localhost:8000/v1/>.

The build is byte-for-byte reproducible; CI rebuilds and demands
`git diff --exit-code`, so a hand-edited page or a forgotten rebuild shows up
there. The checks hold every artefact to the Recommendation and to the
ontology: every attribute maps onto a declared property whose domain and range
fit, mandatory attributes are the ontology's minimum cardinalities, the
enumerations are its individuals, every example record reads as RDF on
declared properties only, and each rule the schemas and shapes enforce is
proven by breaking an example in exactly that way.

## Publishing

`.github/workflows/pages.yml` runs the checks on every push to `main` and
deploys `docs/` to GitHub Pages only when they pass. Once, in the repository
settings:

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. **Custom domain:** `datamodel.agrifooddata.org`, then *Enforce HTTPS*.
3. At the DNS provider of `agrifooddata.org`: a `CNAME` record from
   `datamodel` to `nalamki.github.io`.

`docs/CNAME` records the same domain, so that deploying from the branch
instead (`main`, `/docs`) works as well.

`.github/workflows/external.yml` checks weekly whether the ontology has
published changes since the commit the model is pinned at, and whether Pages
serves the right media types. Neither runs on a pull request: somebody else's outage
should not block a contribution.

## The Recommendation, the ontology and this repository

The Recommendation is the authority; in the event of a discrepancy its text
takes precedence (clause 8). The ontology formalizes its entities and
attributes as classes and properties; this repository formalizes the rest —
constraints, rules, state models, representation, interface — and binds both.
Where the three differ, [model/divergences.yaml](model/divergences.yaml) names
the difference and the reading taken, so that it is fixed where it belongs.

Contributing: [CONTRIBUTING.md](CONTRIBUTING.md). Changes:
[CHANGELOG.md](CHANGELOG.md).

## Licence

The model and everything generated from it under [CC BY 4.0](LICENSE), the
tooling under [MIT](LICENSE-CODE). The ontology is not part of this repository
but a submodule with its own licence; the BVL data the examples draw on carry
their own attribution — see [LICENSE](LICENSE).
