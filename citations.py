r"""Citations in the notebook's markdown cells, from content/references.bib.

Write a citation in a markdown cell like this (pandoc's syntax, or LaTeX's):

    [@anderson2017]              \cite{anderson2017}              -> [1]
    [@anderson2017, p. 12]       \cite[p.~12]{anderson2017}       -> [1, p. 12]
    [@a; @b; @c]                 \cite{a,b,c}                     -> [1-3]

The page numbers them in order of first citation, and adds a References
section at the end. The look follows biblatex's numeric-comp style with:
sorting=none, maxbibnames=minbibnames=3, doi=true, isbn=false, eprint=false.
Colab and JupyterLite show the citation as written.
"""
import codecs
import html
import re

import latexcodec  # noqa: F401  (registers the "ulatex" codec)
from pybtex.database import parse_file

KEY = r"[\w:.#$%&+?<>~/-]+"
PANDOC_RE = re.compile(r"\[([^\[\]]*@[^\[\]]*)\](?!\()")
PANDOC_PART_RE = re.compile(rf"^@({KEY})(?:\s*,\s*(.+))?$", re.S)
LATEX_RE = re.compile(r"\\(?:auto|paren|text)?cite(?:\[([^\]]*)\])?\{([^}]*)\}")
# Parts of markdown where a citation is left as written: fenced blocks, inline code
VERBATIM_RE = re.compile(r"^(```|~~~).*?^\1[ \t]*$|`[^`\n]+`", re.M | re.S)
MAX_NAMES = 3

MONTHS = "January February March April May June July August September October November December".split()


# ---- turning BibTeX field text into HTML ------------------------------------

def tex(text):
    r"""A BibTeX field as HTML: {\"o} -> ö, -- -> en dash, braces dropped, $...$ kept for MathJax."""
    out = []
    for i, piece in enumerate(re.split(r"(\$[^$]*\$)", text)):
        if i % 2:  # maths
            out.append(html.escape(piece))
            continue
        piece = piece.replace("---", "\u2014").replace("--", "\u2013").replace("~", "\u00a0")
        piece = re.sub(r"\\(emph|textit|textbf|mkbibemph)\s*\{([^{}]*)\}", r"\2", piece)
        try:
            piece = codecs.decode(piece, "ulatex")
        except (UnicodeDecodeError, ValueError):
            pass
        out.append(html.escape(piece.replace("{", "").replace("}", "").replace("\\", "")))
    return re.sub(r"\s+", " ", "".join(out)).strip()


def name(person):
    """'Given von Family Jr.' with given names in full, as biblatex does by default."""
    parts = person.first_names + person.middle_names + person.prelast_names + person.last_names
    full = " ".join(tex(p) for p in parts)
    return " ".join([full] + [tex(p) for p in person.lineage_names])  # "John D. Anderson Jr."


def names(people):
    """'A', 'A and B', 'A, B, and C', and past three names 'A, B, C, et al.'"""
    shown = [name(p) for p in people[:MAX_NAMES]]
    if len(people) > MAX_NAMES:
        return ", ".join(shown) + ", et al."
    if len(shown) <= 2:
        return " and ".join(shown)
    return ", ".join(shown[:-1]) + ", and " + shown[-1]


def pages(text):
    text = tex(text)
    return ("pp. " if re.search("[\u2013,-]", text) else "p. ") + text


def ordinal_edition(text):
    text = tex(text)
    if not text.isdigit():
        return text
    n = int(text)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix} ed."


def date(fields):
    year = tex(fields.get("year", fields.get("date", "")))
    month = fields.get("month", "").strip()
    if month.isdigit() and 1 <= int(month) <= 12:
        month = MONTHS[int(month) - 1]
    return f"{tex(month)} {year}".strip() if month else year


def join(*pieces, sep=". "):
    """Join the non-empty pieces; like biblatex, no second full stop after an abbreviation ("ed.")."""
    out = ""
    for p in filter(None, pieces):
        if out:
            out += sep[1:] if sep.startswith(".") and out.endswith(".") else sep
        out += p
    return out


def reference(entry):
    """One bibliography entry as HTML, laid out like biblatex's standard style."""
    f = entry.fields
    kind = entry.type.lower()
    who = names(entry.persons["author"]) if "author" in entry.persons else ""
    editors = entry.persons.get("editor", [])
    title = tex(f.get("title", ""))
    year = date(f)
    pub = join(tex(f.get("address", f.get("location", ""))),
               tex(f.get("publisher", f.get("institution", f.get("school", f.get("organization", ""))))),
               sep=": ")
    pp = pages(f["pages"]) if "pages" in f else ""
    ed = ordinal_edition(f["edition"]) if "edition" in f else ""
    eds = f"Ed. by {names(editors)}" if editors else ""
    if not who and editors:
        who = names(editors) + (", eds." if len(editors) > 1 else ", ed.")
        eds = ""

    if kind == "article":
        journal = f"<i>{tex(f.get('journaltitle', f.get('journal', '')))}</i>"
        vol = tex(f.get("volume", "")) + ("." + tex(f["number"]) if "number" in f else "")
        where = join(f"In: {journal} {vol}".strip() + (f" ({year})" if year else ""), pp, sep=", ")
        body = join(f"\u201c{title}\u201d", where)
    elif kind in ("inproceedings", "incollection", "inbook", "conference"):
        book = f"<i>{tex(f.get('booktitle', ''))}</i>"
        body = join(f"\u201c{title}\u201d", f"In: {book}", eds, ed, join(join(pub, year, sep=", "), pp, sep=", "))
    elif kind in ("phdthesis", "mastersthesis", "thesis"):
        what = {"phdthesis": "PhD thesis", "mastersthesis": "MA thesis"}.get(kind, tex(f.get("type", "Thesis")))
        body = join(f"\u201c{title}\u201d", what, join(pub, year, sep=", "))
    elif kind in ("techreport", "report"):
        what = join(tex(f.get("type", "Tech. rep.")), tex(f.get("number", "")), sep=" ")
        body = join(f"<i>{title}</i>", what, join(pub, year, sep=", "))
    else:  # book, misc, online, manual, ...
        body = join(f"<i>{title}</i>", eds, ed, join(pub, year, sep=", "))

    tail = []
    if "doi" in f:
        doi = f["doi"].strip()
        tail.append(f'doi: <a href="https://doi.org/{html.escape(doi)}">{html.escape(doi)}</a>')
    elif "url" in f:  # biblatex shows the URL too; skip it when a DOI says the same
        url = f["url"].strip()
        tail.append(f'url: <a href="{html.escape(url)}">{html.escape(url)}</a>')
    text = join(who, body, *tail)
    return text if text.endswith(".") else text + "."


def plain(fragment):
    """HTML as plain text, for a tooltip."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


# ---- citations in the text ---------------------------------------------------

def compress(numbers):
    """[1, 2, 3, 5] -> '1\u20133, 5'; two in a row stay apart: [1, 2] -> '1, 2'."""
    numbers = sorted(set(numbers))
    out, i = [], 0
    while i < len(numbers):
        j = i
        while j + 1 < len(numbers) and numbers[j + 1] == numbers[j] + 1:
            j += 1
        if j - i >= 2:
            out.append(f"{numbers[i]}\u2013{numbers[j]}")
        else:
            out.extend(str(n) for n in numbers[i:j + 1])
        i = j + 1
    return out


class Citations:
    def __init__(self, bib_path):
        self.entries = parse_file(str(bib_path), bib_format="bibtex").entries if bib_path.exists() else {}
        self.order = []  # keys, in order of first citation

    def number(self, key):
        if key not in self.entries:
            raise SystemExit(f"citation [@{key}]: no entry '{key}' in content/references.bib")
        if key not in self.order:
            self.order.append(key)
        return self.order.index(key) + 1

    def html(self, keys, locator=""):
        nums = [self.number(k) for k in keys]
        label = ", ".join(compress(nums) + ([tex(locator)] if locator else []))
        links = []
        for part in label.split(", "):  # each number (or range) links to its entry
            first = part.split("\u2013")[0]
            if first.isdigit():
                tip = html.escape(plain(reference(self.entries[self.order[int(first) - 1]])))
                links.append(f'<a href="#ref-{first}" title="{tip}">{part}</a>')
            else:
                links.append(part)
        return f'<span class="cite">[{", ".join(links)}]</span>'

    def _pandoc(self, m):
        parts = [p.strip() for p in m.group(1).split(";")]
        found = [PANDOC_PART_RE.match(p) for p in parts]
        if not all(found):
            return m.group(0)  # not a citation, e.g. an email in brackets
        locators = [f.group(2) for f in found if f.group(2)]
        return self.html([f.group(1) for f in found], locators[-1] if locators else "")

    def _latex(self, m):
        return self.html([k.strip() for k in m.group(2).split(",") if k.strip()], m.group(1) or "")

    def replace(self, src):
        """Markdown with its citations replaced by numbered links (code left alone)."""
        out, last = [], 0
        for m in VERBATIM_RE.finditer(src):
            out.append(self._replace_text(src[last:m.start()]))
            out.append(m.group(0))
            last = m.end()
        out.append(self._replace_text(src[last:]))
        return "".join(out)

    def _replace_text(self, text):
        return LATEX_RE.sub(self._latex, PANDOC_RE.sub(self._pandoc, text))

    def bibliography(self):
        """The References list, or '' when nothing was cited."""
        if not self.order:
            return ""
        rows = "".join(f'<li id="ref-{n}"><span class="label">[{n}]</span>'
                       f'<span>{reference(self.entries[k])}</span></li>'
                       for n, k in enumerate(self.order, 1))
        return f'<ol class="references">{rows}</ol>'
