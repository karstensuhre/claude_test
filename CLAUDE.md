# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A personal "playground" repo whose substantial artifacts are **homogenized, link-checked rebuilds of the metabolomix.com GWAS catalogs**, one for **metabolomics** and one for **proteomics**, each regenerated from a Python pipeline into self-contained static HTML. `index.html` is the landing page. There is no server, build system, or test suite.

- **Metabolomics:** `gwas_table.html` (98 existing studies) + `candidates.html` (15 auto-discovered 2024–2026 papers pending review).
- **Proteomics:** `pgwas_table.html` (93 existing pQTL studies) + `pgwas_candidates.html` (49 new 2023–2026 pGWAS, keep + borderline, pending review).

## Architecture: pipeline → generated static HTML

The committed `*.html` files are **generated output**. The source of truth is `source/gwas_original.html` + the `scripts/` + the curated `data/*.csv`. Two independent data tracks feed the renderer:

**Track A — the 98 existing studies** (each step's output feeds the next):
```
source/gwas_original.html
  → parse.py            → data/gwas_existing.csv      (8 raw cols + reference URLs)
  → resolve_ids.py      → data/gwas_ids.csv           (PMID/DOI via Europe PMC)
  → resolve_fallback.py → data/gwas_ids.csv (in place; writes .bak)   (author+year fallback match)
  → verify_ids.py       → data/gwas_ids.csv (in place) (demote false matches, derive MDPI DOIs)
  → homogenize.py       → data/gwas_homogenized.csv + homogenize_changelog.csv
  (linkcheck.py         → data/linkcheck.csv          QA only: liveness of every link)
```

**Track B — new candidate papers** (mostly independent of Track A):
```
harvest.py        → data/harvest_candidates.csv   (Europe PMC 2024–2026, deduped vs the 98)
refine_pool.py    → data/pool_refined.csv         (tighten precision, score, drop MR/PRS/reviews)
  → [external multi-agent verification produces data/agent_out/slice_*.jsonl]
consolidate_candidates.py → data/candidates.csv   (merge slices, drop preprint twins, flag overlaps)
```

**Renderer:** `build_html.py` reads `data/gwas_homogenized.csv` → `gwas_table.html` and `data/candidates.csv` → `candidates.html`. CSS/JS are inlined as Python string constants (`CSS`, `SORT_JS`).

**Proteomics pipeline (`*_prot.py`)** mirrors the metabolomics one step-for-step on `source/pgwas_original.html`, with proteomics-specific deltas: a 4-class platform taxonomy (aptamer/SomaScan, PEA/Olink, mass spec, immunoassay) + cis/trans/total pQTL parsing in `homogenize_prot.py`; `verify_ids_prot.py` applies hand-verified ID corrections; candidate verification is 6 parallel agents writing `data/pgwas_agent_out/slice_*.jsonl`, consolidated by `consolidate_candidates_prot.py` into `data/pgwas_candidates.csv` + an auditable `data/pgwas_rejections.md`; `build_html_prot.py` renders both proteomics pages (its `CSS`/`SORT_JS` are copied from `build_html.py` so each builder stays standalone). The candidate filter is the key intent: keep only de-novo proteome-measurement pGWAS, exclude papers that reuse published pQTLs (MR/PWAS/coloc/drug-target/PheWAS/meta).

## Commands

All scripts are **bare `python3 scripts/<name>.py` with no arguments**; each computes paths from `__file__`, so the working directory doesn't matter. Requires Python 3.6+ (3.11 available); **stdlib only — nothing to `pip install`, no requirements.txt/Makefile.**

- **Regenerate the site after editing a CSV** (the common task): `python3 scripts/build_html.py`
- **View locally:** open the `.html` files directly, or `python3 -m http.server` from the repo root.
- Re-running the full pipeline from `source/` requires running Track A in the order above, then `build_html.py`.

## Conventions and constraints

- **Network calls go through `curl` as a subprocess** (not `requests`/`urllib`), with a hardcoded browser User-Agent and 0.2–0.4 s rate-limit sleeps, hitting Europe PMC and publisher pages. So `resolve_ids.py`, `resolve_fallback.py`, `verify_ids.py`, `harvest.py`, `linkcheck.py` are **slow, network-dependent, and non-deterministic** — avoid re-running them unless re-resolving data. The pure offline scripts are `parse.py`, `homogenize.py`, `refine_pool.py`, `consolidate_candidates.py`, `build_html.py`.
- **HTML must stay fully self-contained** — inline CSS/JS, no external CDN or framework. New pages should match `index.html`'s look and link from its experiments grid.
- **Homogenization is deliberately conservative:** only labels/formatting are normalized; original values are preserved in the `notes` column and in the untouched `source/gwas_original.html`. Changes are logged row-by-row to `data/homogenize_changelog.csv`. Preserve this when touching `homogenize.py`.
- **Candidate approval workflow:** a reviewer sets `approve=y` in `data/candidates.csv`. **Note:** the README describes `scripts/merge_candidates.py` as merging approved rows into the main table, but **that script does not yet exist** — no script currently reads the `approve` column. Write it if asked to wire up approval.
- **Not committed (`.gitignore`):** `data/harvest_candidates.csv` and `data/agent_out/`. Since `consolidate_candidates.py` reads `data/agent_out/slice_*.jsonl`, regenerating `candidates.csv` from scratch needs those agent slices, which are not in the repo.
