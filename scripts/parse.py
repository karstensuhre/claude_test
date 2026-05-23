#!/usr/bin/env python3
"""Parse the metabolomix mGWAS table from source/gwas_original.html into data/gwas_existing.csv.

Stdlib-only (html.parser). Extracts the 8 original columns plus the reference
link(s) found in the last (Reference) cell of each data row.
"""
import csv, os, re
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source", "gwas_original.html")
OUT = os.path.join(ROOT, "data", "gwas_existing.csv")

COLS = ["Biofluid", "Metabolic_traits", "Platform", "Study_population",
        "N_Traits", "Cohort_size", "N_Loci", "Reference"]


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = 0
        self.in_cell = False
        self.rows = []          # list of rows; each row is list of (text, [hrefs])
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

    # unescape common entities in cell text
    def handle_entityref(self, name):
        if self.in_cell:
            self.buf.append({"amp": "&", "ndash": "-", "rsquo": "'",
                             "nbsp": " ", "lt": "<", "gt": ">"}.get(name, ""))

    def handle_charref(self, name):
        if self.in_cell:
            try:
                self.buf.append(chr(int(name[1:], 16) if name.lower().startswith("x") else int(name)))
            except ValueError:
                pass


def main():
    html = open(SRC, encoding="utf-8", errors="replace").read()
    p = TableParser()
    p.feed(html)
    rows = p.rows
    # first row is the header
    header = [t for t, _ in rows[0]]
    data = rows[1:]
    print(f"header: {header}")
    print(f"data rows: {len(data)}")

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row_id"] + COLS + ["Ref_URLs"])
        for i, r in enumerate(data, 1):
            cells = [t for t, _ in r]
            # pad/trim to 8 columns
            cells = (cells + [""] * 8)[:8]
            ref_urls = r[-1][1] if r else []
            w.writerow([i] + cells + [" ; ".join(ref_urls)])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
