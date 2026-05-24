#!/usr/bin/env python3
"""Parse the metabolomix proteomics-GWAS table from source/pgwas_original.html
into data/pgwas_existing.csv.

Stdlib-only (html.parser). The source table has 6 columns:
  Reference | #Samples in study | Study population | #Proteins assayed | #pQTLs reported | Platform type
The Reference cell carries the PubMed / preprint / journal link(s). Raw pQTL and
platform strings are preserved verbatim; parsing/classification happens later in
homogenize_prot.py (conservative, like the metabolomics pipeline).
"""
import csv, os, re
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source", "pgwas_original.html")
OUT = os.path.join(ROOT, "data", "pgwas_existing.csv")

# source column order
COLS = ["Reference", "N_samples", "Study_population", "N_proteins", "N_pQTL_raw", "Platform_raw"]


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = 0
        self.in_cell = False
        self.rows = []
        self.cur = None
        self.buf = []
        self.cell_links = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table += 1
        if self.in_table and tag == "tr":
            self.cur = []
        if self.in_table and tag in ("td", "th"):
            self.in_cell = True
            self.buf = []
            self.cell_links = []
        if self.in_table and tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.cell_links.append(v.strip())

    def handle_endtag(self, tag):
        if self.in_table and tag in ("td", "th"):
            self.in_cell = False
            text = " ".join("".join(self.buf).split()).strip()
            self.cur.append((text, list(self.cell_links)))
        if self.in_table and tag == "tr" and self.cur is not None:
            if any(t for t, _ in self.cur):
                self.rows.append(self.cur)
            self.cur = None
        if tag == "table" and self.in_table:
            self.in_table -= 1

    def handle_data(self, data):
        if self.in_cell:
            self.buf.append(data)

    def handle_entityref(self, name):
        if self.in_cell:
            self.buf.append({"amp": "&", "ndash": "-", "rsquo": "'", "nbsp": " ",
                             "lt": "<", "gt": ">", "ge": ">=", "le": "<="}.get(name, ""))

    def handle_charref(self, name):
        if self.in_cell:
            try:
                self.buf.append(chr(int(name[1:], 16) if name.lower().startswith("x") else int(name)))
            except ValueError:
                pass


def main():
    html = open(SRC, encoding="utf-8", errors="replace").read()
    # repair malformed close tags (source has a stray "</a" without ">" in the Folkersen row)
    html = re.sub(r'</a(?![\s>])', '</a>', html)
    p = TableParser()
    p.feed(html)
    rows = p.rows
    header = [t for t, _ in rows[0]]
    data = rows[1:]
    print(f"header: {header}")
    print(f"data rows: {len(data)}")

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row_id"] + COLS + ["Ref_URLs"])
        for i, r in enumerate(data, 1):
            cells = [t for t, _ in r]
            cells = (cells + [""] * 6)[:6]
            ref_urls = r[0][1] if r else []          # links live in the Reference (col 0) cell
            w.writerow([i] + cells + [" ; ".join(ref_urls)])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
