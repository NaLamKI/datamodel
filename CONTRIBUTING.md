# Contributing

The model lives under `model/`. `docs/` is generated and never touched by
hand.

```bash
pip install -r requirements.txt
python3 tool/build.py          # rebuild docs/
python3 -m pytest              # check, without network access
```

## The one rule

**An address that has been published keeps meaning the same thing.** A JSON
Schema, the context and the shapes are referenced by URL from records, code
and other specifications; a record valid yesterday must be valid tomorrow.
Within `v1/`, changes are therefore additive — a new optional attribute, a new
enumeration value, a clarified description. Renaming or removing an attribute,
making one mandatory, narrowing a type: that is `v2/`, alongside `v1/`, which
stays where it is. `major` in `model/model.yaml` names the directory, and the
version says which it is.

Until the Recommendation is approved the version carries its revision as a
pre-release label (`1.0.0-draft.3`), and `v1/` may still follow the text.

## Changing the model

Each package is one file under `model/packages/`. An attribute:

```yaml
      farmId:
        type: UUID                  # UUID String Integer Decimal Boolean Date DateTime JSON Enum
        required: true              # M in Annex A; omit for O
        references: Farm            # a foreign key: the entity it points at
        description: Foreign key to the Farm entity   # the wording of Annex A
        note: >-                    # what clause 8 adds, with its clause
          ...
```

and where they apply:

| Key | For |
|---|---|
| `enum: TaskStatus` | an enumeration of `model/enumerations.yaml` |
| `concept: true` | a classification (`…Uri`); the ontology says which scheme |
| `property: taskStatus` | the ontology property, where its name differs |
| `format: currency` | `currency` `country` `language-tag` `time-zone` `ucum` `media-type` `gtin` `email` `uri` |
| `geometry: any` or `[Point, Polygon]` | a GeoJSON attribute |
| `json: object` | the shape of another JSON attribute |
| `positive: true` | a quantity greater than zero (rule V02) |
| `thingDescription: true` | a WoT Thing Description (clause 5.1 f)) |
| `referencesBy: {attribute: …}` | a reference whose target another attribute names |
| `source: …` | where the attribute is specified, if not in the tables of Annex A |

Constraints that span attributes go under the entity's `constraints`:
`exactlyOne`, `atMostOne`, `atLeastOne`, `requiredWhen`, `requiredTogether`,
`order`, each with the `rule` or the `source` it comes from, and
`level: should` where the Recommendation says "should". The generators turn
them into JSON Schema, SHACL and the reference pages; `tool/model.py` refuses a
key it does not know and a reference to anything that does not exist.

Then rebuild and run the checks. A change the Recommendation does not make
belongs in the Recommendation first, or in `model/divergences.yaml` with the
reading taken.

## The ontology

`ontology/` is a git submodule: the model is checked against the one commit of
the ontology's repository recorded here, never against the network. Clone with
`--recurse-submodules`, or run `git submodule update --init` once. When the
ontology publishes a new version:

```bash
git submodule update --remote ontology        # its current main
python3 -m pytest
python3 tool/build.py                         # the pages name the ontology's commit
git add ontology docs                         # then commit the new pointer
```

A failing check then says what changed — a property renamed, a domain fixed. A
divergence the ontology has fixed fails its check until it is removed from
`model/divergences.yaml`; a new one fails until it is listed there. Nothing
under `ontology/` is edited here: a change to the ontology belongs in its own
repository, and the checks fail on a local edit.

## The examples

`examples/<Entity>.json` holds one consistent dataset. A new record needs a
new UUID in lower case, references only to records in these files, and concept
identifiers taken from the ontology under `ontology/` — never typed from memory.
Everything else is fictitious and has to look it: `example.org` for addresses,
no real persons.

## Language

The repository is English: documentation, comments, field names, commit
messages. The exceptions are data — German field names and product names in
the examples, the BVL attribution in its prescribed wording.

## Network runs

Not part of a pull request:

```bash
git -C ontology fetch origin main
git -C ontology diff --stat HEAD FETCH_HEAD -- docs/   # published since the pinned commit
```

`.github/workflows/external.yml` asks the same every Monday.
