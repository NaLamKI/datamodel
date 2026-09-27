"""The reference pages: one per entity, and the tables around them.

An attribute found in a record, an operation found in a log, a rule cited in
an error — each should lead to a page that says what it means, where it comes
from in the Recommendation and which ontology term carries it. That is what
these pages are for; the machine-readable artefacts next to them say the same
for programs.
"""
from __future__ import annotations

import markdown

from model import Attribute, Entity, Model, Ontology, json_text, text
from page import esc, header, table

ONTOLOGY_PAGES = "https://ontology.agrifooddata.org/"

FORMAT_LABELS = {
    "currency": "ISO 4217 currency code", "country": "ISO 3166-1 country code",
    "language-tag": "BCP 47 language tag", "time-zone": "IANA time zone",
    "ucum": "unit, should be UCUM", "media-type": "media type",
    "gtin": "GTIN", "email": "e-mail address", "uri": "URI",
}
JSON_LABELS = {
    "map": "object of strings, keyed by scheme",
    "concepts": "list of concept URIs",
    "permissions": "list of permission identifiers (entity:action)",
    "certificates": "list of certificates: type, number, validFrom, validTo",
    "change-set": "object: before, after",
    "object": "JSON object",
    "any": "any JSON value",
}


def md(source: str) -> str:
    return markdown.markdown(source, extensions=["tables", "fenced_code"])


def crumbs(*parts: tuple[str, str]) -> str:
    return " › ".join(f'<a href="{href}">{esc(label)}</a>' if href else esc(label)
                      for label, href in parts)


def term_link(local: str) -> str:
    """A class, property or individual of the ontology, linked to its row on
    the ontology's schema page — each term has an anchor there."""
    return (f'<a href="{ONTOLOGY_PAGES}term.html#{esc(local)}">'
            f"<code>agfoda:{esc(local)}</code></a>")


def scheme_link(scheme: str) -> str:
    sid = scheme.rsplit("/", 1)[-1]
    return f'<a href="{ONTOLOGY_PAGES}{sid}.html">{esc(sid)}</a>'


def domain_gaps(model: Model) -> dict[tuple[str, str], str]:
    """(entity, attribute) -> divergence id, for the flagged attributes."""
    out = {}
    for d in model.divergences["ontology"]:
        if d["kind"] in ("domain", "multiplicity"):
            for cls in d.get("classes", []):
                attr = next((a.name for a in model.entities[cls].attributes.values()
                             if a.term == d["property"]), d["property"])
                out[(cls, attr)] = d["id"]
    return out


def values_cell(model: Model, ontology: Ontology, entity: Entity, a: Attribute) -> str:
    parts = []
    if a.references:
        parts.append(f'→ <a href="{a.references}.html">{esc(a.references)}</a>')
    if a.referencesBy:
        by = a.referencesBy["attribute"]
        targets = a.referencesBy.get("targets")
        if targets:
            parts.append(f"→ by <code>{esc(by)}</code>: " + ", ".join(
                f"{esc(k)} → " + (f'<a href="{t}.html">{esc(t)}</a>' if t else "none")
                for k, t in targets.items()))
        else:
            parts.append(f"→ the entity named in <code>{esc(by)}</code>")
    if a.enum:
        parts.append(f'<a href="enumerations.html#{a.enum}">{esc(a.enum)}</a>: '
                     f'<code>{esc(", ".join(model.enum_values(a.enum)))}</code>')
    if a.concept:
        schemes = ontology.bindings.get((entity.name, a.term), [])
        if schemes:
            parts.append("concept of " + " or ".join(scheme_link(s) for s in schemes))
        else:
            parts.append("concept URI, AGROVOC primary")
    if a.term in ontology.notation_from:
        parts.append("notation of " + scheme_link(ontology.notation_from[a.term]))
    if a.format:
        parts.append(esc(FORMAT_LABELS[a.format]))
    if a.geometry:
        parts.append("GeoJSON: " + ("any geometry" if a.geometry == "any"
                                    else " or ".join(a.geometry)))
    elif a.json and a.json in JSON_LABELS:
        parts.append(esc(JSON_LABELS[a.json]))
    if a.thingDescription:
        parts.append("WoT Thing Description")
    if a.entityName:
        parts.append("name of an entity")
    if a.positive:
        parts.append("greater than zero (V02)")
    if a.default is not None:
        parts.append(f"default <code>{esc(a.default)}</code>")
    if a.readOnly:
        parts.append("set by the system")
    elif a.immutable:
        parts.append("not changed after creation")
    return "<br>".join(parts)


def attribute_rows(model: Model, ontology: Ontology, e: Entity) -> list[list[str]]:
    gaps = domain_gaps(model)
    rows = []
    for a in e.attributes.values():
        name = f"<code>{esc(a.name)}</code>"
        if a.inherited:
            name += ' <span class="muted">(EntityBase)</span>'
        if a.source:
            name += f'<br><span class="note">{esc(a.source)}</span>'
        desc = esc(text(a.description))
        if a.note:
            desc += f'<br><span class="note">{esc(text(a.note))}</span>'
        term = term_link(a.term)
        gap = gaps.get((e.name, a.name))
        if gap:
            term += f' <a href="divergences.html#{gap}">({gap})</a>'
        rows.append([name, esc(a.type), "M" if a.required else "O", desc, term,
                     values_cell(model, ontology, e, a)])
    return rows


def entity_page(model: Model, ontology: Ontology, e: Entity, examples: list[dict]) -> str:
    pkg = model.package(e.package)
    sub = (f"{esc(pkg.id)} {esc(pkg.title)} · Annex {esc(e.annex)} · "
           f"{term_link(e.name)} · "
           f'<a href="schema/{e.name}.json">JSON Schema</a> · '
           f"<code>/{esc(e.path)}</code>")
    out = [header(e.name, sub, css="../style.css",
                  crumbs=crumbs(("AgriFoodData model", "../"), (model.major, "./"),
                                (f"{pkg.id} {pkg.title}", f"./#{pkg.id}"), (e.name, "")),
                  links=f'<link rel="describedby" type="application/schema+json" '
                        f'href="schema/{e.name}.json">\n')]
    out.append(f"<p>{esc(e.definition)}</p>")
    if e.systemManaged:
        out.append('<p class="note">Written by the system on every change, '
                   "append-only; the interface offers it for reading only.</p>")

    out.append("<h2>Attributes</h2>")
    out.append(table(["Attribute", "Type", "", "Description", "Ontology", "Values"],
                     attribute_rows(model, ontology, e)))

    constraints = list(e.constraints)
    pairs = model.v01_pairs(e)
    if constraints or pairs:
        out.append("<h2>Constraints</h2><ul>")
        for c in constraints:
            cite = f" ({esc(c.cites)})" if c.cites else ""
            out.append(f"<li>{esc(c.describe())}{cite}.</li>")
        for first, second in pairs:
            out.append(f"<li>{esc(second)} is not earlier than {esc(first)} "
                       '(<a href="rules.html#V01">V01</a>).</li>')
        out.append("</ul>")
        out.append('<p class="note">In addition, for every entity: createdByUserId '
                   "is set where originType is USER, createdByJobId where it is "
                   'SERVICE (<a href="rules.html#V04">V04</a>).</p>')

    st = model.states.get(e.name)
    if st:
        out.append(f"<h2>State model of <code>{esc(st['attribute'])}</code></h2>")
        out.append(table(["From", "To"], [[f"<code>{esc(a)}</code>", f"<code>{esc(b)}</code>"]
                                          for a, b in st["transitions"]]))
        terminal = ", ".join(st["terminal"]) or "none"
        out.append(f'<p class="note">Terminal: <code>{esc(terminal)}</code>. '
                   "Transitions not listed are rejected (clause 13).</p>")

    keys = [k for k in model.business_keys if k["entity"] == e.name]
    if keys:
        out.append("<h2>Unique</h2><ul>")
        for k in keys:
            if "attributes" in k:
                s = ", ".join(k["attributes"])
                scope = (" within " + ", ".join(k["within"])) if k.get("within") else ""
                scope += f" ({k['scope']})" if k.get("scope") else ""
                extra = f"; {text(k['text'])}" if k.get("text") else ""
                out.append(f"<li><code>{esc(s)}</code>{esc(scope)}{esc(extra)}.</li>")
            else:
                out.append(f"<li>{esc(text(k['text']))}</li>")
        out.append("</ul>")

    inbound = model.inbound(e.name)
    if inbound:
        out.append("<h2>Referenced by</h2><p>" + ", ".join(
            f'<a href="{src.name}.html">{esc(src.name)}</a>.<code>{esc(a.name)}</code>'
            for src, a in inbound) + "</p>")

    if examples:
        out.append("<h2>Example</h2>")
        out.append(f'<p class="note">From the example dataset '
                   f'(<a href="examples/{e.name}.json">{e.name}.json</a>); '
                   "all names and numbers are fictitious.</p>")
        out.append(f"<pre><code>{esc(json_text(examples[0]).rstrip())}</code></pre>")
    out.append(footnote(model))
    return "\n".join(out) + "\n"


def footnote(model: Model) -> str:
    rec = model.meta["recommendation"]
    return ('<p class="footnote">'
            f"{esc(model.meta['title'])} {esc(model.version)} · machine-readable "
            f"specification of the Recommendation <em>{esc(rec['title'])}</em> "
            f"({esc(text(rec['status']))}, {esc(rec['date'])}). "
            f"{esc(text(rec['precedence']))} "
            f'Published under <a href="{model.meta["license"]["url"]}">CC BY 4.0</a> · '
            f'<a href="{model.meta["repository"]}">source</a>.</p>')


def version_index(model: Model, ontology: Ontology) -> str:
    snap = ontology.snapshot
    sub = (f"{esc(model.version)} · {len(model.entities)} entities in "
           f"{len(model.packages)} packages · <code>{esc(model.base_url)}</code>")
    out = [header(f"{model.meta['title']} {model.major}", sub, css="../style.css",
                  crumbs=crumbs(("AgriFoodData model", "../"), (model.major, "")),
                  links='<link rel="alternate" type="application/ld+json" '
                        'href="context.jsonld">\n')]
    out.append(f"<p>{esc(text(model.meta['description']))} Every entity is a class "
               f'of the <a href="{model.meta["ontology"]["home"]}">agrifooddata '
               f"ontology</a>, every attribute one of its properties; this "
               f"version is checked against the ontology as of "
               f"{esc(snap.get('version', ''))} "
               f"(<code>{esc(snap.get('commit', '')[:7])}</code>). Where the "
               f'two part ways, <a href="divergences.html">Divergences</a> says '
               "so.</p>")

    out.append("<h2>Artefacts</h2>")
    rows = [
        ['<a href="openapi.yaml">openapi.yaml</a>, <a href="openapi.json">.json</a>',
         "OpenAPI 3.1", 'The REST binding: every entity as a collection, '
                         'synchronization, OGC API - Features. <a href="api.html">Overview</a>'],
        ['<a href="schema/">schema/</a><code>&lt;Entity&gt;.json</code>',
         "JSON Schema 2020-12", "One schema per entity, for records as stored and exchanged."],
        ['<a href="context.jsonld">context.jsonld</a>', "JSON-LD 1.1",
         "Reads the JSON of the model as RDF on the ontology's properties."],
        ['<a href="shapes.ttl">shapes.ttl</a>', "SHACL",
         "Checks a single record in RDF, closed."],
        ['<a href="shapes-dataset.ttl">shapes-dataset.ttl</a>', "SHACL",
         "Checks a dataset: references, concept schemes, rules across records."],
        ['<a href="model.json">model.json</a>', "JSON",
         "The whole model in one document, for generators."],
        ['<a href="examples/">examples/</a>', "JSON",
         "One consistent, fictitious farm: every entity at least once."],
    ]
    out.append(table(["File", "Format", "For"], rows))
    out.append('<p>Also: <a href="rules.html">rules, state models and business keys</a> · '
               '<a href="enumerations.html">enumerations</a> · '
               '<a href="bindings.html">how the model becomes JSON, RDF and HTTP</a> · '
               '<a href="divergences.html">divergences</a>.</p>')

    out.append("<h2>Packages</h2>")
    for p in model.packages:
        out.append(f'<h3 id="{p.id}">{esc(p.id)} {esc(p.title)} '
                   f'<span class="muted">(clause {esc(p.clause)})</span></h3>')
        out.append(f"<p>{esc(p.summary)}</p>")
        rows = []
        for name in p.entities:
            e = model.entities[name]
            rows.append([f'<a href="{e.name}.html">{esc(e.name)}</a>', esc(e.annex),
                         esc(e.definition.split(". ")[0].rstrip(".") + "."),
                         f"<code>/{esc(e.path)}</code>"])
        out.append(table(["Entity", "Annex", "Definition", "API"], rows))
        if p.notes:
            out.append("<ul>" + "".join(f'<li class="note">{esc(n)}</li>' for n in p.notes)
                       + "</ul>")

    out.append("<h2>Conventions for every entity</h2>")
    out.append('<p class="note">Clause 5.1 of the Recommendation. The attributes '
               "they introduce are listed with every entity as EntityBase.</p>")
    out.append("<dl>" + "".join(
        f"<dt><strong>{esc(c['id'])}) {esc(c['title'])}</strong></dt>"
        f"<dd>{esc(text(c['text']))}</dd>" for c in model.meta["conventions"]) + "</dl>")
    out.append(footnote(model))
    return "\n".join(out) + "\n"


def root_index(model: Model) -> str:
    sub = esc(text(model.meta["description"]))
    out = [header(model.meta["title"], sub,
                  crumbs="AgriFoodData model")]
    rec = model.meta["recommendation"]
    out.append(f"<p>The machine-readable specification of the data model of the "
               f"Recommendation <em>{esc(rec['title'])}</em> "
               f"({esc(text(rec['status']))}, {esc(rec['date'])}): its "
               "entities, attributes and relationships, the rules and state "
               "models they obey, and a REST binding — as OpenAPI, JSON Schema, "
               "JSON-LD and SHACL, bound to the "
               f'<a href="{model.meta["ontology"]["home"]}">agrifooddata ontology</a>.</p>')
    out.append(table(["Version", "Status", "Address"], [[
        f'<a href="{model.major}/">{esc(model.major)}</a>', esc(model.version),
        f"<code>{esc(model.base_url)}</code>"]]))
    out.append("<p>An address, once published, keeps meaning the same thing: a change "
               "that would break existing records or clients gets a new major "
               "version, and the old one stays where it is.</p>")
    out.append(footnote(model))
    return "\n".join(out) + "\n"


def api_page(model: Model, doc: dict) -> str:
    out = [header("AgriFoodData API", f"OpenAPI 3.1 · {esc(model.version)} · "
                  '<a href="openapi.yaml">openapi.yaml</a> · '
                  '<a href="openapi.json">openapi.json</a>', css="../style.css",
                  crumbs=crumbs(("AgriFoodData model", "../"), (model.major, "./"),
                                ("API", "")))]
    out.append(md(doc["info"]["description"]))
    by_tag: dict[str, list[list[str]]] = {}
    for path, item in doc["paths"].items():
        for method in ("get", "put", "patch", "delete"):
            op = item.get(method)
            if not op:
                continue
            perm = op.get("x-agfoda-permission", "")
            perm = " / ".join(perm) if isinstance(perm, list) else perm
            by_tag.setdefault(op["tags"][0], []).append([
                f'<span class="code">{method.upper()}</span>',
                f"<code>{esc(path)}</code>", esc(op["summary"]),
                f"<code>{esc(perm)}</code>" if perm else ""])
    for tag in (t["name"] for t in doc["tags"]):
        if tag in by_tag:
            out.append(f"<h2>{esc(tag)}</h2>")
            out.append(table(["", "Path", "Operation", "Permission"], by_tag[tag]))
    out.append(footnote(model))
    return "\n".join(out) + "\n"


def rules_page(model: Model) -> str:
    out = [header("Rules, state models and business keys",
                  "Clauses 12 and 13 of the Recommendation", css="../style.css",
                  crumbs=crumbs(("AgriFoodData model", "../"), (model.major, "./"),
                                ("Rules", "")))]
    out.append("<p>Where each rule is checked: <em>JSON Schema</em> and "
               "<em>SHACL</em> on a single record, <em>SHACL dataset</em> on a "
               "dataset holding the records referred to and the concept "
               "schemes, <em>interface</em> only in the persistence or interface "
               "layer, because the rule needs history, sums over many records, "
               "geometry or time. A rule expressed with “should” raises a "
               "warning.</p>")
    labels = {"json-schema": "JSON Schema", "shacl": "SHACL",
              "shacl-dataset": "SHACL dataset", "interface": "interface"}
    rows = [[f'<span id="{rid}"><strong>{esc(rid)}</strong></span>', esc(r["level"]),
             esc(text(r["text"])), esc(", ".join(labels[x] for x in r["enforcement"]))]
            for rid, r in model.rules.items()]
    out.append(table(["Rule", "Level", "Text", "Checked by"], rows))
    out.append('<p class="note">V01 is applied to these pairs, wherever an entity '
               "carries both: " + ", ".join(
                   f"<code>{esc(a)}</code> ≤ <code>{esc(b)}</code>"
                   for a, b in model.rules["V01"]["pairs"]) + ".</p>")

    out.append('<h2 id="unique">Business keys</h2>')
    rows = []
    for k in model.business_keys:
        attrs = ", ".join(k.get("attributes", [])) or "—"
        scope = " ".join(filter(None, [
            ("within " + ", ".join(k["within"])) if k.get("within") else "",
            k.get("scope", ""), text(k.get("text", ""))]))
        rows.append([f'<a href="{k["entity"]}.html">{esc(k["entity"])}</a>',
                     f"<code>{esc(attrs)}</code>", esc(scope)])
    out.append(table(["Entity", "Unique", "Scope"], rows))

    out.append('<h2 id="states">State models</h2>')
    for name, st in model.states.items():
        out.append(f'<h3><a href="{name}.html">{esc(name)}</a>.{esc(st["attribute"])}</h3>')
        out.append("<p>" + ", ".join(f"<code>{esc(a)} → {esc(b)}</code>"
                                     for a, b in st["transitions"]) + ". Terminal: "
                   + (", ".join(f"<code>{esc(t)}</code>" for t in st["terminal"]) or "none")
                   + ".</p>")
        if st.get("note"):
            out.append(f'<p class="note">{esc(text(st["note"]))}</p>')

    out.append('<h2 id="derived">Derived views</h2>')
    for v in model.derived_views:
        out.append(f'<h3 id="{v["id"]}">{esc(v["title"])} '
                   f'<span class="muted">({esc(v["source"])})</span></h3>')
        out.append(f"<p>{esc(text(v['text']))}</p>")
        if v.get("rule"):
            out.append(f'<p class="note">{esc(text(v["rule"]))}</p>')
    out.append(footnote(model))
    return "\n".join(out) + "\n"


def enumerations_page(model: Model, ontology: Ontology) -> str:
    out = [header("Enumerations", "Annex B of the Recommendation", css="../style.css",
                  crumbs=crumbs(("AgriFoodData model", "../"), (model.major, "./"),
                                ("Enumerations", "")))]
    out.append("<p>Each enumeration is a class of the ontology, each value one of "
               "its named individuals; the JSON-LD context turns the value into "
               "the individual.</p>")
    used: dict[str, list[str]] = {}
    for e in model.ordered():
        for a in e.own.values():
            if a.enum:
                used.setdefault(a.enum, []).append(
                    f'<a href="{e.name}.html">{esc(e.name)}</a>.{esc(a.name)}')
    used.setdefault("OriginType", []).insert(0, "every entity.originType")
    for name, en in model.enumerations.items():
        out.append(f'<h2 id="{name}">{esc(name)}</h2>')
        out.append(f"<p>{esc(text(en['description']))} · used by "
                   + ", ".join(used.get(name, [])) + "</p>")
        out.append(table(["Value", "Individual"], [
            [f"<code>{esc(v)}</code>", term_link(f"{name}_{v}")]
            for v in en["values"]]))
    out.append(footnote(model))
    return "\n".join(out) + "\n"


def divergences_page(model: Model, ontology: Ontology) -> str:
    snap = ontology.snapshot
    out = [header("Divergences", "Where the Recommendation, the ontology and this "
                  "specification part ways", css="../style.css",
                  crumbs=crumbs(("AgriFoodData model", "../"), (model.major, "./"),
                                ("Divergences", "")))]
    out.append("<p>The Recommendation takes precedence (clause 8). A difference is "
               "named here so that it is fixed where it belongs, instead of being "
               "papered over in a generator. The ontology is checked as of "
               f"{esc(snap.get('version', ''))}, commit "
               f"<code>{esc(snap.get('commit', ''))}</code>.</p>")
    out.append("<h2>Ontology</h2>")
    rows = []
    for d in model.divergences["ontology"]:
        subject = " ".join(filter(None, [
            ", ".join(d.get("classes", [])),
            f"agfoda:{d['property']}" if d.get("property") and not d["property"].startswith("(")
            else d.get("property", "")]))
        body = esc(text(d["finding"]))
        if d.get("consequence"):
            body += f"<br><em>Consequence:</em> {esc(text(d['consequence']))}"
        rows.append([f'<span id="{d["id"]}"><strong>{esc(d["id"])}</strong></span>',
                     f"<code>{esc(subject)}</code>", body, esc(text(d["resolution"]))])
    out.append(table(["", "Subject", "Finding", "Resolution"], rows))
    out.append("<h2>Recommendation</h2>")
    rows = [[f'<span id="{d["id"]}"><strong>{esc(d["id"])}</strong></span>',
             f"<code>{esc(d['subject'])}</code>", esc(text(d["finding"])),
             esc(text(d["resolution"]))] for d in model.divergences["recommendation"]]
    out.append(table(["", "Subject", "Finding", "Resolution"], rows))
    out.append(footnote(model))
    return "\n".join(out) + "\n"


def markdown_page(model: Model, title: str, source: str) -> str:
    body = md(source)
    # The document's own first heading is the page title.
    if body.startswith("<h1>"):
        body = body[body.index("</h1>") + 5:]
    out = [header(title, "", css="../style.css",
                  crumbs=crumbs(("AgriFoodData model", "../"), (model.major, "./"),
                                (title, "")))]
    out.append(body)
    out.append(footnote(model))
    return "\n".join(out) + "\n"


def problem_page(model: Model, slug: str, status: int, title: str, body: str) -> str:
    out = [header(title, f"Problem type · HTTP {status} · "
                  f"<code>{esc(model.base_url)}problems/{esc(slug)}</code>",
                  css="../../style.css",
                  crumbs=crumbs(("AgriFoodData model", "../../"), (model.major, "../"),
                                ("API", "../api.html"), (slug, "")))]
    out.append(f"<p>{esc(body)}</p>")
    out.append('<p class="note">Reported as RFC 9457 problem details '
               "(<code>application/problem+json</code>); <code>violations</code> "
               "names the rules and attributes concerned.</p>")
    out.append(footnote(model))
    return "\n".join(out) + "\n"


def redirect(url: str, what: str) -> str:
    return ("<!doctype html>\n"
            '<html lang="en">\n<meta charset="utf-8">\n'
            f'<meta http-equiv="refresh" content="0; url={esc(url)}">\n'
            f'<link rel="canonical" href="{esc(url)}">\n'
            f"<title>{esc(what)}</title>\n"
            # A static page cannot send a 301; the link is spelled out as well.
            f'<p>{esc(what)}: <a href="{esc(url)}">{esc(url)}</a>.</p>\n')


def listing(model: Model, title: str, files: list[str], up: str) -> str:
    """An index for a directory — GitHub Pages lists none by itself."""
    out = [header(title, "", css="../../style.css",
                  crumbs=crumbs(("AgriFoodData model", "../../"), (model.major, up),
                                (title, "")))]
    out.append("<ul>" + "".join(f'<li><a href="{esc(f)}">{esc(f)}</a></li>'
                                for f in files) + "</ul>")
    out.append(footnote(model))
    return "\n".join(out) + "\n"
