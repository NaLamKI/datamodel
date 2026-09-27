"""The model and the ontology, as every generator and every check sees them.

Everything under `model/` is YAML written by people, and YAML forgives too
much: a key written twice silently keeps the second value, and a misspelt
`requierd: true` is just another key. The loader here refuses the first, and
`Model.problems()` names the second kind of slip — a reference to an entity,
an enumeration or an attribute that does not exist — before any artefact is
generated from it.

The ontology is read from `ontology/`, a git submodule of the ontology's own
repository pinned at one commit — never from the network: the checks run
offline, and a model checked against a moving target proves nothing. What is
read is what the ontology publishes, its `docs/`; nothing of it is copied into
this repository.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import yaml
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, SKOS

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "model"
ONTOLOGY = ROOT / "ontology"
EXAMPLES = ROOT / "examples"
DOCS = ROOT / "docs"

TYPES = ("UUID", "String", "Integer", "Decimal", "Boolean", "Date",
         "DateTime", "JSON", "Enum")
CONSTRAINTS = ("exactlyOne", "atMostOne", "atLeastOne", "requiredWhen",
               "requiredTogether", "order")


class _Loader(yaml.SafeLoader):
    """SafeLoader that rejects a key given twice in one mapping."""


def _mapping(loader: _Loader, node: yaml.MappingNode, deep: bool = False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark)
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                        _mapping)


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_Loader) or {}


def text(value: str | None) -> str:
    """Folded YAML keeps single spaces; a trailing one is noise."""
    return " ".join(str(value).split()) if value else ""


def json_text(value, indent: int = 0, width: int = 88) -> str:
    """JSON as people read it: indented, but a short list stays on one line.

    `json.dumps(indent=2)` puts every coordinate of a polygon on a line of its
    own, and a field boundary becomes a page. The output is still plain JSON,
    and deterministic, which is what the guard on docs/ needs.
    """
    def flat(v) -> bool:
        return not isinstance(v, dict) and not (
            isinstance(v, list) and any(isinstance(x, dict) for x in v))

    def render(v, level: int) -> str:
        pad = "  " * level
        if isinstance(v, list) and flat(v):
            inline = json.dumps(v, ensure_ascii=False, separators=(", ", ": "))
            if len(inline) + len(pad) <= width:
                return inline
        if isinstance(v, dict):
            if not v:
                return "{}"
            items = [f'{pad}  {json.dumps(k, ensure_ascii=False)}: {render(x, level + 1)}'
                     for k, x in v.items()]
            return "{\n" + ",\n".join(items) + "\n" + pad + "}"
        if isinstance(v, list):
            if not v:
                return "[]"
            items = [f"{pad}  {render(x, level + 1)}" for x in v]
            return "[\n" + ",\n".join(items) + "\n" + pad + "]"
        return json.dumps(v, ensure_ascii=False)

    return render(value, indent) + "\n"


# --- The model ------------------------------------------------------------

@dataclass
class Attribute:
    name: str
    entity: str
    type: str
    description: str
    required: bool = False
    references: str | None = None
    referencesBy: dict | None = None
    enum: str | None = None
    concept: bool = False
    prop: str | None = None      # `property:` in YAML — the ontology term
    format: str | None = None
    default: object = None
    geometry: object = None
    json: str | None = None
    positive: bool = False
    entityName: bool = False
    thingDescription: bool = False
    readOnly: bool = False
    immutable: bool = False
    note: str | None = None
    source: str | None = None

    @property
    def term(self) -> str:
        """The local name of the ontology property the attribute maps onto."""
        return self.prop or self.name

    @property
    def inherited(self) -> bool:
        return self.entity == "EntityBase"

    @property
    def multivalued(self) -> bool:
        """A JSON list whose members become one statement each."""
        return self.json == "concepts"

    @property
    def writable(self) -> bool:
        """May a client change it after creation?"""
        return not (self.readOnly or self.immutable or self.name == "id")

    def summary(self) -> str:
        """Description and note, as one sentence sequence."""
        parts = [text(self.description)]
        if self.note:
            parts.append(text(self.note))
        return ". ".join(p.rstrip(".") for p in parts if p) + "."


@dataclass
class Constraint:
    kind: str
    members: list = field(default_factory=list)
    attribute: str | None = None
    when: dict | None = None
    level: str = "shall"
    rule: str | None = None
    source: str | None = None

    @property
    def cites(self) -> str:
        return self.rule or self.source or ""

    def attributes(self) -> list[str]:
        """Every attribute the constraint mentions."""
        out: list[str] = []
        for m in self.members:
            out.extend(m if isinstance(m, list) else [m])
        if self.attribute:
            out.append(self.attribute)
        for key in (self.when or {}):
            out.append(key)
        return out

    def describe(self) -> str:
        """The constraint in a sentence, for pages and messages."""
        def names(ms):
            return ", ".join(" and ".join(m) if isinstance(m, list) else m
                             for m in ms)
        if self.kind == "exactlyOne":
            s = f"Exactly one of {names(self.members)} is set"
        elif self.kind == "atMostOne":
            s = f"At most one of {names(self.members)} is set"
        elif self.kind == "atLeastOne":
            s = f"At least one of {names(self.members)} is set"
        elif self.kind == "requiredTogether":
            s = f"{names(self.members)} are set together or not at all"
        elif self.kind == "order":
            s = f"{self.members[1]} is not earlier than {self.members[0]}"
        else:
            (key, values), = self.when.items()
            s = (f"{self.attribute} is set where {key} is "
                 + " or ".join(values))
        if self.level == "should":
            s = s.replace(" is set", " should be set", 1)
        return s


@dataclass
class Entity:
    name: str
    package: str
    annex: str
    path: str
    definition: str
    own: dict[str, Attribute]
    constraints: list[Constraint]
    base: dict[str, Attribute]
    base_constraints: list[Constraint]
    systemManaged: bool = False

    @property
    def attributes(self) -> dict[str, Attribute]:
        """id first, then the entity's own attributes, then the system ones."""
        out = {"id": self.base["id"]}
        out.update(self.own)
        out.update({k: v for k, v in self.base.items() if k != "id"})
        return out

    @property
    def all_constraints(self) -> list[Constraint]:
        return self.base_constraints + self.constraints

    @property
    def plural(self) -> str:
        """`cropping-plan-entries` -> `CroppingPlanEntries`."""
        return "".join(p.capitalize() for p in self.path.split("-"))

    @property
    def permission(self) -> str:
        """The entity part of a permission identifier (`entity:action`)."""
        return self.name[0].lower() + self.name[1:]


@dataclass
class Package:
    id: str
    slug: str
    title: str
    clause: str
    scope: str
    summary: str
    notes: list[str]
    entities: list[str]

    @property
    def number(self) -> int:
        return int(self.id[1:])


def _attribute(name: str, entity: str, raw: dict) -> Attribute:
    raw = dict(raw)
    if "property" in raw:
        raw["prop"] = raw.pop("property")
    known = set(Attribute.__dataclass_fields__) - {"name", "entity"}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"{entity}.{name}: unknown keys {sorted(unknown)}")
    return Attribute(name=name, entity=entity, **raw)


def _constraint(where: str, raw: dict) -> Constraint:
    kinds = [k for k in CONSTRAINTS if k in raw]
    if len(kinds) != 1:
        raise ValueError(f"{where}: a constraint names exactly one of "
                         f"{', '.join(CONSTRAINTS)}; got {sorted(raw)}")
    kind = kinds[0]
    rest = {k: v for k, v in raw.items() if k != kind}
    unknown = set(rest) - {"level", "rule", "source"}
    if unknown:
        raise ValueError(f"{where}: unknown keys {sorted(unknown)}")
    if kind == "requiredWhen":
        body = raw[kind]
        return Constraint(kind=kind, attribute=body["attribute"],
                          when=body["when"], **rest)
    return Constraint(kind=kind, members=list(raw[kind]), **rest)


class Model:
    """Everything under model/, loaded and cross-referenced."""

    def __init__(self, root: Path = MODEL):
        self.root = root
        self.meta = load_yaml(root / "model.yaml")
        self.enumerations: dict[str, dict] = load_yaml(root / "enumerations.yaml")
        rules = load_yaml(root / "rules.yaml")
        self.rules: dict[str, dict] = rules["rules"]
        self.business_keys: list[dict] = rules["businessKeys"]
        self.derived_views: list[dict] = rules["derivedViews"]
        self.states: dict[str, dict] = load_yaml(root / "states.yaml")
        self.divergences: dict[str, list] = load_yaml(root / "divergences.yaml")

        base = self.meta["entityBase"]
        self.base = {n: _attribute(n, "EntityBase", a)
                     for n, a in base["attributes"].items()}
        self.base_constraints = [_constraint("EntityBase", c)
                                 for c in base.get("constraints", [])]

        self.packages: list[Package] = []
        self.entities: dict[str, Entity] = {}
        for path in sorted((root / "packages").glob("P*.yaml")):
            raw = load_yaml(path)
            slug = path.stem.split("-", 1)[1]
            pkg = Package(id=raw["package"], slug=slug, title=raw["title"],
                          clause=str(raw["clause"]), scope=raw["scope"],
                          summary=text(raw["summary"]),
                          notes=[text(n) for n in raw.get("notes", [])],
                          entities=list(raw["entities"]))
            self.packages.append(pkg)
            for name, e in raw["entities"].items():
                unknown = set(e) - {"annex", "path", "definition", "attributes",
                                    "constraints", "systemManaged"}
                if unknown:
                    raise ValueError(f"{name}: unknown keys {sorted(unknown)}")
                if name in self.entities:
                    raise ValueError(f"{name} is defined twice")
                self.entities[name] = Entity(
                    name=name, package=pkg.id, annex=e["annex"], path=e["path"],
                    definition=text(e["definition"]),
                    own={n: _attribute(n, name, a)
                         for n, a in e["attributes"].items()},
                    constraints=[_constraint(name, c)
                                 for c in e.get("constraints", [])],
                    base=self.base, base_constraints=self.base_constraints,
                    systemManaged=bool(e.get("systemManaged")))
        self.packages.sort(key=lambda p: p.number)

    # -- addresses ---------------------------------------------------------

    @property
    def version(self) -> str:
        return self.meta["version"]

    @property
    def major(self) -> str:
        return self.meta["major"]

    @property
    def home(self) -> str:
        return self.meta["home"]

    @property
    def base_url(self) -> str:
        """Where the artefacts of this major version are published."""
        return f"{self.home}{self.major}/"

    @property
    def ns(self) -> str:
        return self.meta["ontology"]["namespace"]

    @property
    def iri(self) -> str:
        return self.meta["iri"]

    def package(self, pid: str) -> Package:
        return next(p for p in self.packages if p.id == pid)

    def ordered(self) -> list[Entity]:
        """Entities in the order of the packages, as Annex A has them."""
        return [self.entities[n] for p in self.packages for n in p.entities]

    def enum_values(self, name: str) -> list[str]:
        return list(self.enumerations[name]["values"])

    def inbound(self, target: str) -> list[tuple[Entity, Attribute]]:
        """Who refers to this entity, and through which attribute."""
        return [(e, a) for e in self.ordered() for a in e.attributes.values()
                if a.references == target]

    def v01_pairs(self, entity: Entity) -> list[tuple[str, str]]:
        """The period pairs of rule V01 that this entity carries."""
        names = entity.attributes
        return [(a, b) for a, b in self.rules["V01"]["pairs"]
                if a in names and b in names]

    # -- consistency -------------------------------------------------------

    def problems(self) -> list[str]:
        """Every dangling reference in the model, as one sentence each."""
        out: list[str] = []
        entity_names = set(self.entities)
        paths: dict[str, str] = {}
        for e in self.ordered():
            if e.path in paths:
                out.append(f"{e.name}: path {e.path} already used by "
                           f"{paths[e.path]}")
            paths[e.path] = e.name
            clash = set(e.own) & set(self.base)
            if clash:
                out.append(f"{e.name}: repeats base attributes {sorted(clash)}")
            for a in e.attributes.values():
                where = f"{e.name}.{a.name}"
                if a.type not in TYPES:
                    out.append(f"{where}: unknown type {a.type}")
                if a.references and a.references not in entity_names:
                    out.append(f"{where}: references unknown {a.references}")
                if a.references and a.type != "UUID":
                    out.append(f"{where}: a reference is a UUID")
                if a.type == "Enum" and a.enum not in self.enumerations:
                    out.append(f"{where}: unknown enumeration {a.enum}")
                if a.enum and a.type != "Enum":
                    out.append(f"{where}: enum on a {a.type}")
                if a.concept and a.type not in ("String", "JSON"):
                    out.append(f"{where}: a concept is a String")
                if a.name.endswith("Uri") != bool(a.concept) and a.json != "concepts":
                    out.append(f"{where}: names ending in Uri are concepts "
                               "and vice versa (clause 5.1 e))")
                if a.geometry and a.type != "JSON":
                    out.append(f"{where}: geometry is JSON")
                if a.referencesBy:
                    by = a.referencesBy["attribute"]
                    if by not in e.attributes:
                        out.append(f"{where}: referencesBy unknown {by}")
                    for value, target in (a.referencesBy.get("targets") or {}).items():
                        enum = e.attributes[by].enum if by in e.attributes else None
                        if enum and value not in self.enum_values(enum):
                            out.append(f"{where}: {value} is not a {enum}")
                        if target is not None and target not in entity_names:
                            out.append(f"{where}: unknown target {target}")
            for c in e.all_constraints:
                for name in c.attributes():
                    if name not in e.attributes:
                        out.append(f"{e.name}: constraint names unknown "
                                   f"attribute {name}")
                if c.rule and c.rule not in self.rules:
                    out.append(f"{e.name}: constraint cites unknown rule {c.rule}")
                if c.when:
                    for key, values in c.when.items():
                        attr = e.attributes.get(key)
                        if attr and attr.enum:
                            bad = set(values) - set(self.enum_values(attr.enum))
                            if bad:
                                out.append(f"{e.name}: {sorted(bad)} are not "
                                           f"{attr.enum} values")
        for name, st in self.states.items():
            if name not in self.entities:
                out.append(f"states: unknown entity {name}")
                continue
            attr = self.entities[name].attributes.get(st["attribute"])
            if attr is None or not attr.enum:
                out.append(f"states: {name}.{st['attribute']} is no enumeration")
                continue
            values = set(self.enum_values(attr.enum))
            used = {v for t in st["transitions"] for v in t} | set(st["terminal"])
            if used - values:
                out.append(f"states: {name} uses {sorted(used - values)}")
            for a, b in st["transitions"]:
                if a in st["terminal"]:
                    out.append(f"states: {name} leaves terminal state {a}")
        for key in self.business_keys:
            e = self.entities.get(key["entity"])
            if e is None:
                out.append(f"businessKeys: unknown entity {key['entity']}")
                continue
            for name in key.get("attributes", []) + key.get("within", []):
                if name not in e.attributes:
                    out.append(f"businessKeys: {e.name} has no {name}")
        for view in self.derived_views:
            for name in view["from"]:
                if name not in entity_names:
                    out.append(f"derivedViews: {view['id']} names {name}")
        return out


# --- The ontology ---------------------------------------------------------

def bound_schemes(graph: Graph, ns: str) -> list[str]:
    """The concept schemes the schema binds a property to, by identifier.

    Read from the schema itself — `owl:hasValue` on `skos:inScheme`, and
    `agfoda:notationFrom` — not from a list kept here that could go stale.
    """
    base = "https://w3id.org/agrifooddata/"
    schemes = {str(graph.value(r, OWL.hasValue))
               for r in graph.subjects(OWL.onProperty, SKOS.inScheme)
               if graph.value(r, OWL.hasValue) is not None}
    schemes |= {str(s) for s in graph.objects(None, URIRef(ns + "notationFrom"))}
    stray = sorted(s for s in schemes if not s.startswith(base))
    if stray:
        raise SystemExit(f"schemes outside {base}: {stray}")
    return sorted(s[len(base):] for s in schemes)


class Ontology:
    """The ontology as `ontology/` holds it — the files it publishes, at the
    commit this repository pins — and what is asked of it."""

    def __init__(self, root: Path = ONTOLOGY, ns: str | None = None):
        self.root = root
        self.docs = root / "docs"
        if not (self.docs / "term.ttl").exists():
            raise SystemExit(
                f"{root}/ holds no ontology. It is a git submodule; fetch it "
                "with `git submodule update --init` (or clone with "
                "`--recurse-submodules`).")
        self.graph = Graph(bind_namespaces="none").parse(
            self.docs / "term.ttl", format="turtle")
        self.ns = ns or "https://w3id.org/agrifooddata/term/"
        self.schemes = Graph(bind_namespaces="none")
        for scheme in bound_schemes(self.graph, self.ns):
            self.schemes.parse(self.docs / f"{scheme}.ttl", format="turtle")
        # The mapping of the ontology's own schemes onto AGROVOC, which it
        # publishes apart from them.
        self.links = Graph(bind_namespaces="none")
        if (self.docs / "links" / "agrovoc.ttl").exists():
            self.links.parse(self.docs / "links" / "agrovoc.ttl", format="turtle")

    @cached_property
    def snapshot(self) -> dict[str, str]:
        """Which state of the ontology the model is checked against: its
        repository, the commit the submodule is at, and the version that
        commit publishes."""
        import subprocess

        def git(*args: str) -> str:
            return subprocess.run(["git", "-C", str(self.root), *args],
                                  capture_output=True, text=True).stdout.strip()

        entry = Graph(bind_namespaces="none").parse(
            self.docs / "agrifooddata.ttl", format="turtle")
        versions = sorted(str(v) for v in entry.objects(None, OWL.versionInfo))
        url = git("remote", "get-url", "origin")
        return {"source": url[:-4] if url.endswith(".git") else url,
                "commit": git("rev-parse", "HEAD"),
                "version": versions[-1] if versions else ""}

    def iri(self, local: str) -> URIRef:
        return URIRef(self.ns + local)

    def local(self, node) -> str:
        s = str(node)
        return s[len(self.ns):] if s.startswith(self.ns) else s

    def _members(self, node) -> set[str]:
        if isinstance(node, BNode):
            union = self.graph.value(node, OWL.unionOf)
            if union is not None:
                return {self.local(m) for m in Collection(self.graph, union)}
        return {self.local(node)} if node is not None else set()

    @cached_property
    def classes(self) -> set[str]:
        return {self.local(c) for c in self.graph.subjects(RDF.type, OWL.Class)
                if isinstance(c, URIRef) and str(c).startswith(self.ns)}

    @cached_property
    def enumerations(self) -> set[str]:
        """Classes defined by their individuals. A datatype of the ontology —
        agfoda:Decimal, the union of xsd:decimal and xsd:double — is defined
        by owl:equivalentClass too, and is no enumeration."""
        return {self.local(c) for c in self.graph.subjects(OWL.equivalentClass, None)
                if str(c).startswith(self.ns) and (c, RDF.type, OWL.Class) in self.graph}

    @cached_property
    def properties(self) -> dict[str, dict]:
        out = {}
        for kind, label in ((OWL.ObjectProperty, "object"),
                            (OWL.DatatypeProperty, "datatype")):
            for p in self.graph.subjects(RDF.type, kind):
                if not (isinstance(p, URIRef) and str(p).startswith(self.ns)):
                    continue
                rng = self.graph.value(p, RDFS.range)
                out[self.local(p)] = {
                    "kind": label,
                    "domain": self._members(self.graph.value(p, RDFS.domain)),
                    "range": str(rng) if rng is not None else None,
                    "functional": (p, RDF.type, OWL.FunctionalProperty) in self.graph,
                }
        return out

    @cached_property
    def mandatory(self) -> dict[str, set[str]]:
        """Class -> properties with an owl:minCardinality restriction."""
        out: dict[str, set[str]] = {}
        for cls, r in self.graph.subject_objects(RDFS.subClassOf):
            if isinstance(r, BNode) and self.graph.value(r, OWL.minCardinality) is not None:
                prop = self.graph.value(r, OWL.onProperty)
                out.setdefault(self.local(cls), set()).add(self.local(prop))
        return out

    def _restrictions(self) -> list[tuple[tuple[str, str], list[str]]]:
        """((class, property), schemes) per restriction binding a property to
        concept schemes — to one, or to several as a union."""
        out = []
        for cls, r in self.graph.subject_objects(RDFS.subClassOf):
            filler = self.graph.value(r, OWL.allValuesFrom)
            if filler is None:
                continue
            union = self.graph.value(filler, OWL.unionOf)
            parts = list(Collection(self.graph, union)) if union is not None else [filler]
            schemes = [str(self.graph.value(part, OWL.hasValue)) for part in parts
                       if self.graph.value(part, OWL.onProperty) == SKOS.inScheme]
            if schemes:
                prop = self.graph.value(r, OWL.onProperty)
                out.append(((self.local(cls), self.local(prop)), schemes))
        return out

    @cached_property
    def bindings(self) -> dict[tuple[str, str], list[str]]:
        """(class, property) -> the concept schemes its values come from,
        any one of them."""
        out: dict[tuple[str, str], list[str]] = {}
        for key, schemes in self._restrictions():
            out.setdefault(key, []).extend(schemes)
        return {k: sorted(v) for k, v in out.items()}

    @cached_property
    def intersecting(self) -> set[tuple[str, str]]:
        """(class, property) bound by more than one restriction. Restrictions
        intersect: a value would have to be a concept of every scheme at once,
        which the reading of `bindings` — any one of them — does not follow."""
        seen: dict[tuple[str, str], int] = {}
        for key, _ in self._restrictions():
            seen[key] = seen.get(key, 0) + 1
        return {k for k, n in seen.items() if n > 1}

    @cached_property
    def notation_from(self) -> dict[str, str]:
        """Property -> the scheme whose skos:notation its literal is."""
        return {self.local(p): str(s) for p, s in
                self.graph.subject_objects(self.iri("notationFrom"))}

    def individuals(self, enum: str) -> list[str]:
        """The values of an enumeration, as the ontology names them."""
        prefix = f"{enum}_"
        return sorted(self.local(i)[len(prefix):]
                      for i in self.graph.subjects(RDF.type, self.iri(enum))
                      if self.local(i).startswith(prefix))

    def concept(self, scheme: str, notation: str) -> str:
        """The identifier of the concept with this notation in this scheme."""
        base = "https://w3id.org/agrifooddata/"
        scheme_iri = URIRef(scheme if scheme.startswith("https://") else base + scheme)
        hits = [c for c in self.schemes.subjects(SKOS.notation, Literal(notation))
                if (c, SKOS.inScheme, scheme_iri) in self.schemes]
        if len(hits) != 1:
            raise KeyError(f"{scheme}#{notation}: {len(hits)} concepts")
        return str(hits[0])

    def in_scheme(self, concept: str) -> set[str]:
        return {str(s) for s in self.schemes.objects(URIRef(concept), SKOS.inScheme)}

    def notations(self, scheme: str) -> set[str]:
        return {str(n) for c in self.schemes.subjects(SKOS.inScheme, URIRef(scheme))
                for n in self.schemes.objects(c, SKOS.notation)}

    def scheme_label(self, scheme: str) -> str:
        """The English title of a scheme where it has one."""
        node = URIRef(scheme)
        labels = {o.language: str(o) for o in self.schemes.objects(node, SKOS.prefLabel)
                  if isinstance(o, Literal)}
        from rdflib.namespace import DCTERMS
        labels.update({o.language: str(o) for o in self.schemes.objects(node, DCTERMS.title)
                       if isinstance(o, Literal) and o.language not in labels})
        return labels.get("en") or labels.get("de") or scheme.rsplit("/", 1)[-1]


def schemes_of(ontology: Ontology, entity: Entity, attr: Attribute) -> list[str]:
    """The concept schemes an attribute takes its values from, if bound."""
    return ontology.bindings.get((entity.name, attr.term), [])
