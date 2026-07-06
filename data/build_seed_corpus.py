#!/usr/bin/env python3
"""
build_seed_corpus.py — legal stimulus-corpus builder for the APUSH notes->questions SLM.

WHY THIS EXISTS
---------------
APUSH multiple-choice items are stimulus-based: every question hangs on a source
(primary text, historian excerpt, image, map, chart). We generate synthetic
questions by DISTILLING from a frontier teacher model, but the *stimuli* those
questions hang on must be legally reusable. This script assembles a
legally-clean stimulus corpus from two source classes only:

  1. CC BY 4.0 open textbook prose  -> OpenStax "U.S. History"
  2. Public-domain primary sources  -> U.S. federal works (any date) and any
     U.S. work published before 1929 (Wikisource / LoC / National Archives /
     Avalon Project mirror the texts; the TEXTS are public domain).

WHAT WE DELIBERATELY DO NOT SCRAPE
----------------------------------
  - College Board exam questions (CED sample items, released FRQs, secure MCQs)
    are copyrighted. We analyze them for the taxonomy (fair use) and MAY hold a
    few aside as an eval reference, but we never ingest them as training data.
  - Any test-prep site's proprietary question banks.
  - Anything under an NC / SA / ND license that is incompatible with reuse.

Full legal analysis + citations: docs/05_data_sourcing_and_legal.md.

USAGE
-----
  python build_seed_corpus.py --validate           # check seed_stimuli.jsonl
  python build_seed_corpus.py --fetch-wikisource    # pull PD primary sources
  python build_seed_corpus.py --openstax-info       # print CC BY book pointers
  python build_seed_corpus.py --manifest            # write provenance manifest

Fetching is optional and rate-limited; the hand-curated seed_stimuli.jsonl is
sufficient to run the litmus test without any live network calls.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SEED_PATH = os.path.join(HERE, "seed_stimuli.jsonl")
FETCHED_PATH = os.path.join(HERE, "fetched_primary_sources.jsonl")
MANIFEST_PATH = os.path.join(HERE, "corpus_manifest.json")

# ---------------------------------------------------------------------------
# Legal source catalog. Each entry documents license + provenance so every
# downstream artifact is auditable. period/theme use the CED grid.
# ---------------------------------------------------------------------------

OPENSTAX = {
    "title": "U.S. History (OpenStax)",
    "license": "CC BY 4.0",
    "role": "content spine + note seeds + textbook-prose secondary source",
    "web": "https://openstax.org/details/books/us-history",
    "github_cnxml": "https://github.com/openstax/osbooks-u-s-history",
    "archive_api": "https://openstax.org/apps/archive/  (per-page JSON; see repo README)",
    "note": "CC BY 4.0 permits reuse and redistribution WITH attribution. Ideal "
            "for study-note seeds and for grounding factual claims. Attribute: "
            "'U.S. History, OpenStax, CC BY 4.0'.",
}

# Public-domain primary sources. Wikisource hosts faithful transcriptions of
# public-domain texts; the TEXT is public domain regardless of the host.
# (title on en.wikisource.org, metadata for tagging)
WIKISOURCE_PD_SOURCES = [
    {"title": "United States Declaration of Independence", "year": 1776, "period": 3, "themes": ["NAT", "PCE"]},
    {"title": "The Federalist/10", "year": 1787, "period": 3, "themes": ["PCE"]},
    {"title": "Seventh Annual Message (Monroe)", "year": 1823, "period": 4, "themes": ["WOR"]},
    {"title": "Declaration of Sentiments", "year": 1848, "period": 4, "themes": ["SOC"]},
    {"title": "What to the Slave Is the Fourth of July?", "year": 1852, "period": 5, "themes": ["SOC", "NAT"]},
    {"title": "Gettysburg Address", "year": 1863, "period": 5, "themes": ["NAT"]},
    {"title": "Omaha Platform", "year": 1892, "period": 6, "themes": ["PCE", "WXT"]},
    {"title": "The Gospel of Wealth", "year": 1889, "period": 6, "themes": ["WXT", "SOC"]},
    {"title": "The March of the Flag", "year": 1898, "period": 7, "themes": ["WOR", "NAT"]},
]

# Public-domain U.S. federal works (any date) — official repositories.
FEDERAL_PD_SOURCES = [
    {"title": "FDR First Inaugural Address", "year": 1933, "period": 7, "themes": ["WXT", "PCE"],
     "url": "https://www.archives.gov/milestone-documents/president-franklin-roosevelts-first-inaugural-address"},
    {"title": "Truman Doctrine (Address to Congress)", "year": 1947, "period": 8, "themes": ["WOR"],
     "url": "https://www.archives.gov/milestone-documents/truman-doctrine"},
    {"title": "Brown v. Board of Education (opinion)", "year": 1954, "period": 8, "themes": ["PCE", "SOC"],
     "url": "https://www.archives.gov/milestone-documents/brown-v-board-of-education"},
]

WIKISOURCE_REST = "https://en.wikisource.org/w/rest.php/v1/page/{title}"
USER_AGENT = "apush-slm-seed-corpus/1.0 (research; contact: project maintainer)"


def _strip_wikitext(s: str) -> str:
    """Best-effort wikitext -> plain text for excerpting. Not exhaustive."""
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)          # templates
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)  # refs
    s = re.sub(r"<[^>]+>", "", s)                  # html tags
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)  # links
    s = re.sub(r"'''?", "", s)                     # bold/italic
    s = re.sub(r"^[=*#:;].*$", "", s, flags=re.M)  # headings/lists
    s = re.sub(r"\n{2,}", "\n\n", s)
    return s.strip()


def fetch_wikisource(title: str, timeout: int = 20) -> str | None:
    url = WIKISOURCE_REST.format(title=urllib.parse.quote(title.replace(" ", "_")))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        return _strip_wikitext(data.get("source", ""))
    except Exception as e:  # noqa: BLE001
        print(f"  ! fetch failed for {title!r}: {e}", file=sys.stderr)
        return None


def cmd_validate() -> int:
    if not os.path.exists(SEED_PATH):
        print("seed_stimuli.jsonl not found", file=sys.stderr)
        return 1
    required = {"id", "stimulus_type", "attribution", "year", "period", "themes", "text", "license"}
    n, bad = 0, 0
    seen = set()
    with open(SEED_PATH, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            n += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  line {i}: invalid JSON: {e}", file=sys.stderr)
                bad += 1
                continue
            missing = required - obj.keys()
            if missing:
                print(f"  line {i} ({obj.get('id','?')}): missing {missing}", file=sys.stderr)
                bad += 1
            if obj.get("id") in seen:
                print(f"  line {i}: duplicate id {obj.get('id')}", file=sys.stderr)
                bad += 1
            seen.add(obj.get("id"))
            if not (1 <= int(obj.get("period", 0)) <= 9):
                print(f"  line {i}: period out of range", file=sys.stderr)
                bad += 1
    print(f"validated {n} stimuli, {bad} problems")
    return 0 if bad == 0 else 2


def cmd_fetch_wikisource() -> int:
    out = []
    for src in WIKISOURCE_PD_SOURCES:
        print(f"fetching: {src['title']}")
        text = fetch_wikisource(src["title"])
        if text:
            out.append({**src, "license": "public domain (pre-1929)",
                        "source_url": WIKISOURCE_REST.format(title=urllib.parse.quote(src["title"])),
                        "text_len": len(text), "text": text[:4000]})
        time.sleep(1.0)  # be polite
    with open(FETCHED_PATH, "w", encoding="utf-8") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} fetched sources -> {FETCHED_PATH}")
    return 0


def cmd_openstax_info() -> int:
    print(json.dumps(OPENSTAX, indent=2))
    print("\nTo ingest OpenStax at scale: clone the CC BY CNXML repo and parse "
          "collection XML into (period, theme)-tagged prose sections; attribute "
          "'U.S. History, OpenStax, CC BY 4.0'.")
    return 0


def cmd_manifest() -> int:
    manifest = {
        "openstax": OPENSTAX,
        "wikisource_pd_sources": WIKISOURCE_PD_SOURCES,
        "federal_pd_sources": FEDERAL_PD_SOURCES,
        "excluded_by_policy": [
            "College Board CED sample items / released FRQs / secure MCQs (copyright; analysis-only)",
            "test-prep proprietary question banks",
            "NC/SA/ND-licensed content incompatible with reuse",
        ],
        "legal_basis_doc": "docs/05_data_sourcing_and_legal.md",
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote provenance manifest -> {MANIFEST_PATH}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--validate", action="store_true", help="validate seed_stimuli.jsonl")
    p.add_argument("--fetch-wikisource", action="store_true", help="fetch public-domain primary sources")
    p.add_argument("--openstax-info", action="store_true", help="print OpenStax CC BY pointers")
    p.add_argument("--manifest", action="store_true", help="write provenance manifest")
    args = p.parse_args()
    if args.validate:
        return cmd_validate()
    if args.fetch_wikisource:
        return cmd_fetch_wikisource()
    if args.openstax_info:
        return cmd_openstax_info()
    if args.manifest:
        return cmd_manifest()
    p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
