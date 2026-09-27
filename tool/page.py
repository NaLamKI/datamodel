"""How the published pages look — in one place.

The look is the ontology's (ontology.agrifooddata.org): plain, no scripts, no
fonts from elsewhere. Whoever arrives here holds a record, a schema or an API
response and wants to know what an attribute means — not to look at a brand.
"""
from __future__ import annotations

import html

CSS = """:root { color-scheme: light dark; --rule: #d8d8d2; --muted: #6b6b66; }
body { font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
       max-width: 68rem; margin: 0 auto; padding: 1.2rem 1rem 5rem; }
nav { font-size: .88rem; color: var(--muted); margin-bottom: 1.6rem; }
h1 { font-size: 1.6rem; margin-bottom: .2rem; }
h2 { font-size: 1.15rem; margin-top: 2.4rem; }
h3 { font-size: 1rem; margin-top: 1.8rem; }
.sub { color: var(--muted); margin-top: 0; }
table { border-collapse: collapse; width: 100%; margin: 1.4rem 0; }
th, td { text-align: left; padding: .45rem .6rem;
         border-bottom: 1px solid var(--rule); vertical-align: top; }
th { position: sticky; top: 0; background: Canvas; }
code { font-size: .92em; overflow-wrap: anywhere; }
pre { overflow-x: auto; padding: .8rem 1rem; border: 1px solid var(--rule);
      border-radius: 6px; font-size: .86rem; line-height: 1.45; }
pre code { overflow-wrap: normal; }
blockquote { margin: 1.2rem 0; padding: .1rem 1rem; border-left: 3px solid var(--rule);
             color: var(--muted); }
.code { white-space: nowrap; }
.muted { color: var(--muted); }
.note { color: var(--muted); font-size: .92rem; }
.footnote { margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--rule);
            color: var(--muted); font-size: .9rem; }
a { color: inherit; }
@media (max-width: 40rem) { table { font-size: .9rem; } }
"""


def esc(s) -> str:
    return html.escape(str(s))


def header(title: str, sub: str = "", *, crumbs: str = "", links: str = "",
           css: str = "style.css") -> str:
    """The page header. `sub`, `crumbs` and `links` may contain HTML."""
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n"
        f'<link rel="stylesheet" href="{css}">\n'
        f"{links}"
        + (f"<nav>{crumbs}</nav>\n" if crumbs else "")
        + f"<h1>{esc(title)}</h1>\n"
        + (f'<p class="sub">{sub}</p>\n' if sub else "")
    )


def table(head: list[str], rows: list[list[str]]) -> str:
    """A table; the cells are HTML already."""
    out = ["<table><thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in head)
           + "</tr></thead><tbody>"]
    for r in rows:
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)
