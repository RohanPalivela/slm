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

  1. Open textbook prose  -> The American Yawp (CC BY-SA 4.0, commercial-OK) or
     OpenStax "U.S. History" (CURRENT edition CC BY-NC-SA 4.0 -> non-commercial
     only; legacy 2014/2015 editions were CC BY 4.0 and remain usable under that
     license if an archived dated copy proves the notice).
  2. Public-domain primary sources  -> U.S. federal works and court opinions
     (uncopyrightable, any date) and any U.S. work published in 1930 or earlier
     (95-year term; as of 2026-01-01 the cutoff is <=1930). Wikisource / LoC /
     National Archives / Avalon / CourtListener mirror the texts; the TEXTS are
     public domain regardless of host.

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
    "license_current": "CC BY-NC-SA 4.0 (current edition; NON-COMMERCIAL + ShareAlike)",
    "license_legacy": "CC BY 4.0 (2014/2015 editions; commercial-OK; archive a dated copy of the notice)",
    "role": "content spine + note seeds + textbook-prose grounding",
    "web": "https://openstax.org/details/books/us-history",
    "github_cnxml": "https://github.com/openstax/osbooks-us-history",
    "note": "CURRENT OpenStax U.S. History is CC BY-NC-SA 4.0: fine for a "
            "non-commercial build, but NC blocks commercial use and SA imposes "
            "copyleft. For a commercial-friendly grounding text prefer The "
            "American Yawp (CC BY-SA 4.0). Do NOT co-mingle CC BY-SA and "
            "CC BY-NC-SA text in one derivative (conflicting copyleft). Attribute "
            "'U.S. History, OpenStax'.",
}

AMERICAN_YAWP = {
    "title": "The American Yawp",
    "license": "CC BY-SA 4.0 (commercial-OK; ShareAlike applies)",
    "role": "commercial-friendly secondary/textbook prose + Primary Source Reader",
    "web": "https://www.americanyawp.com/text/",
    "reader": "https://www.americanyawp.com/reader.html",
    "note": "Preferred grounding text if the model may be commercial. Attribute "
            "and license derivatives under CC BY-SA 4.0.",
}

EVAL_ONLY_MMLU = {
    "title": "MMLU high_school_us_history (cais/mmlu)",
    "license": "MIT (dataset wrapper)",
    "role": "HELD-OUT EVALUATION ONLY (~204 test items) — never train on it",
    "hf": "https://huggingface.co/datasets/cais/mmlu",
    "note": "Public benchmark -> training would contaminate; some items may carry "
            "third-party rights. Use only to sanity-check the tuned model.",
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

# ---------------------------------------------------------------------------
# A3 corpus-expansion catalog (14 -> ~150). Every entry is either (a) a U.S.
# work first published in 1930 or earlier, or (b) a U.S. federal work / Supreme
# Court opinion (uncopyrightable at ANY date). We route all fetches through
# en.wikisource.org since it hosts faithful transcriptions of both classes.
#
# DELIBERATELY EXCLUDED (still under copyright): private-authored works after
# 1930 — e.g. MLK's speeches/letters, most mid-century essays. Only *federal*
# post-1930 works (presidential addresses, statutes, court opinions) are here.
#
# `ws` = exact en.wikisource.org page title. `id` = corpus id. `pd` = the
# public-domain basis recorded as the license. Fetched text is verified + the
# lead excerpt length-gated before anything is written (build_corpus).
# ---------------------------------------------------------------------------

_PD_PRE1930 = "public domain (published <=1930)"
_PD_FEDERAL = "public domain (U.S. federal government work)"
_PD_COURT = "public domain (U.S. court opinion — uncopyrightable)"

CORPUS_CATALOG = [
    # --- Period 2-3: colonial + revolutionary + founding (pre-1800) ---
    {"ws": "Mayflower Compact", "id": "mayflower_compact_1620", "author": "Mayflower signers", "attribution": "Mayflower Compact, 1620", "year": 1620, "period": 2, "themes": ["NAT", "PCE"], "pd": _PD_PRE1930},
    {"ws": "Sinners in the Hands of an Angry God", "id": "edwards_sinners_1741", "author": "Jonathan Edwards", "attribution": "Jonathan Edwards, 'Sinners in the Hands of an Angry God', 1741", "year": 1741, "period": 2, "themes": ["SOC", "ARC"], "pd": _PD_PRE1930},
    {"ws": "Common Sense", "id": "paine_common_sense_1776", "author": "Thomas Paine", "attribution": "Thomas Paine, 'Common Sense', 1776", "year": 1776, "period": 3, "themes": ["NAT", "PCE"], "pd": _PD_PRE1930},
    {"ws": "The Federalist/51", "id": "federalist_51_1788", "author": "James Madison", "attribution": "James Madison, Federalist No. 51, 1788", "year": 1788, "period": 3, "themes": ["PCE"], "pd": _PD_PRE1930},
    {"ws": "Constitution of the United States of America", "id": "us_constitution_1787", "author": "Constitutional Convention", "attribution": "U.S. Constitution (Preamble + Article I), 1787", "year": 1787, "period": 3, "themes": ["PCE", "NAT"], "pd": _PD_FEDERAL},
    {"ws": "United States Bill of Rights", "id": "bill_of_rights_1791", "author": "1st U.S. Congress", "attribution": "U.S. Bill of Rights, 1791", "year": 1791, "period": 3, "themes": ["PCE", "NAT"], "pd": _PD_FEDERAL},
    {"ws": "Northwest Ordinance", "id": "northwest_ordinance_1787", "author": "Confederation Congress", "attribution": "Northwest Ordinance, 1787", "year": 1787, "period": 3, "themes": ["MIG", "GEO"], "pd": _PD_FEDERAL},
    {"ws": "Virginia Statute for Religious Freedom", "id": "va_religious_freedom_1786", "author": "Thomas Jefferson", "attribution": "Virginia Statute for Religious Freedom, 1786", "year": 1786, "period": 3, "themes": ["SOC", "PCE"], "pd": _PD_PRE1930},
    {"ws": "Kentucky Resolutions of 1798", "id": "kentucky_resolutions_1798", "author": "Thomas Jefferson", "attribution": "Kentucky Resolutions, 1798", "year": 1798, "period": 3, "themes": ["PCE"], "pd": _PD_PRE1930},

    # --- Period 4: 1800-1848 ---
    {"ws": "Marbury v. Madison/Opinion of the Court", "id": "marbury_madison_1803", "author": "Chief Justice John Marshall", "attribution": "Marbury v. Madison (opinion), 1803", "year": 1803, "period": 4, "themes": ["PCE"], "pd": _PD_COURT},
    {"ws": "McCulloch v. Maryland/Opinion of the Court", "id": "mcculloch_maryland_1819", "author": "Chief Justice John Marshall", "attribution": "McCulloch v. Maryland (opinion), 1819", "year": 1819, "period": 4, "themes": ["PCE"], "pd": _PD_COURT},
    {"ws": "Andrew Jackson's Veto Message of July 10, 1832", "id": "jackson_bank_veto_1832", "author": "Andrew Jackson", "attribution": "Andrew Jackson, Bank Veto Message, 1832", "year": 1832, "period": 4, "themes": ["PCE", "WXT"], "pd": _PD_FEDERAL},
    {"ws": "The American Scholar", "id": "emerson_american_scholar_1837", "author": "Ralph Waldo Emerson", "attribution": "Ralph Waldo Emerson, 'The American Scholar', 1837", "year": 1837, "period": 4, "themes": ["ARC", "NAT"], "pd": _PD_PRE1930},
    {"ws": "Second Reply to Hayne", "id": "webster_reply_hayne_1830", "author": "Daniel Webster", "attribution": "Daniel Webster, Second Reply to Hayne, 1830", "year": 1830, "period": 4, "themes": ["PCE", "NAT"], "pd": _PD_PRE1930},

    # --- Period 5: 1844-1877 ---
    {"ws": "House Divided Speech", "id": "lincoln_house_divided_1858", "author": "Abraham Lincoln", "attribution": "Abraham Lincoln, 'House Divided' Speech, 1858", "year": 1858, "period": 5, "themes": ["PCE", "NAT"], "pd": _PD_PRE1930},
    {"ws": "Dred Scott v. Sandford/Opinion of the Court", "id": "dred_scott_1857", "author": "Chief Justice Roger Taney", "attribution": "Dred Scott v. Sandford (opinion), 1857", "year": 1857, "period": 5, "themes": ["PCE", "SOC"], "pd": _PD_COURT},
    {"ws": "Emancipation Proclamation", "id": "emancipation_proclamation_1863", "author": "Abraham Lincoln", "attribution": "Emancipation Proclamation, 1863", "year": 1863, "period": 5, "themes": ["PCE", "SOC"], "pd": _PD_FEDERAL},
    {"ws": "Second Inaugural Address of Abraham Lincoln", "id": "lincoln_second_inaugural_1865", "author": "Abraham Lincoln", "attribution": "Abraham Lincoln, Second Inaugural Address, 1865", "year": 1865, "period": 5, "themes": ["NAT", "SOC"], "pd": _PD_FEDERAL},
    {"ws": "Homestead Act", "id": "homestead_act_1862", "author": "37th U.S. Congress", "attribution": "Homestead Act, 1862", "year": 1862, "period": 5, "themes": ["MIG", "GEO"], "pd": _PD_FEDERAL},

    # --- Period 6: 1865-1898 ---
    {"ws": "Plessy v. Ferguson/Opinion of the Court", "id": "plessy_ferguson_1896", "author": "Justice Henry Billings Brown", "attribution": "Plessy v. Ferguson (opinion), 1896", "year": 1896, "period": 6, "themes": ["PCE", "SOC"], "pd": _PD_COURT},
    {"ws": "Cross of Gold Speech", "id": "bryan_cross_of_gold_1896", "author": "William Jennings Bryan", "attribution": "William Jennings Bryan, 'Cross of Gold' Speech, 1896", "year": 1896, "period": 6, "themes": ["PCE", "WXT"], "pd": _PD_PRE1930},
    {"ws": "The Significance of the Frontier in American History", "id": "turner_frontier_1893", "author": "Frederick Jackson Turner", "attribution": "Frederick Jackson Turner, 'The Significance of the Frontier in American History', 1893", "year": 1893, "period": 6, "themes": ["MIG", "GEO"], "pd": _PD_PRE1930},
    {"ws": "Atlanta Compromise", "id": "washington_atlanta_1895", "author": "Booker T. Washington", "attribution": "Booker T. Washington, Atlanta Compromise Address, 1895", "year": 1895, "period": 6, "themes": ["SOC", "WXT"], "pd": _PD_PRE1930},
    {"ws": "Chinese Exclusion Act", "id": "chinese_exclusion_act_1882", "author": "47th U.S. Congress", "attribution": "Chinese Exclusion Act, 1882", "year": 1882, "period": 6, "themes": ["MIG", "SOC"], "pd": _PD_FEDERAL},

    # --- Period 7: 1890-1945 ---
    {"ws": "The Souls of Black Folk/Chapter 1", "id": "dubois_souls_1903", "author": "W. E. B. Du Bois", "attribution": "W. E. B. Du Bois, 'The Souls of Black Folk', 1903", "year": 1903, "period": 7, "themes": ["SOC", "NAT"], "pd": _PD_PRE1930},
    {"ws": "New Nationalism (Roosevelt)", "id": "tr_new_nationalism_1910", "author": "Theodore Roosevelt", "attribution": "Theodore Roosevelt, 'New Nationalism' Speech, 1910", "year": 1910, "period": 7, "themes": ["PCE", "WXT"], "pd": _PD_PRE1930},
    {"ws": "Woodrow Wilson's Fourteen Points", "id": "wilson_fourteen_points_1918", "author": "Woodrow Wilson", "attribution": "Woodrow Wilson, Fourteen Points, 1918", "year": 1918, "period": 7, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Schenck v. United States/Opinion of the Court", "id": "schenck_us_1919", "author": "Justice Oliver Wendell Holmes Jr.", "attribution": "Schenck v. United States (opinion), 1919", "year": 1919, "period": 7, "themes": ["PCE"], "pd": _PD_COURT},
    {"ws": "Address to Congress Requesting a Declaration of War Against Germany", "id": "wilson_war_message_1917", "author": "Woodrow Wilson", "attribution": "Woodrow Wilson, War Message to Congress, 1917", "year": 1917, "period": 7, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Four Freedoms", "id": "fdr_four_freedoms_1941", "author": "Franklin D. Roosevelt", "attribution": "Franklin D. Roosevelt, 'Four Freedoms' Address, 1941", "year": 1941, "period": 7, "themes": ["WOR", "PCE"], "pd": _PD_FEDERAL},
    {"ws": "Franklin Roosevelt's Day of Infamy speech", "id": "fdr_day_of_infamy_1941", "author": "Franklin D. Roosevelt", "attribution": "Franklin D. Roosevelt, 'Day of Infamy' Address, 1941", "year": 1941, "period": 7, "themes": ["WOR"], "pd": _PD_FEDERAL},

    # --- Period 8: 1945-1980 (federal works only for post-1930 private authors) ---
    {"ws": "Marshall Plan speech", "id": "marshall_plan_1947", "author": "George C. Marshall", "attribution": "George C. Marshall, Marshall Plan Address (Harvard), 1947", "year": 1947, "period": 8, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Inaugural Address of John F. Kennedy", "id": "jfk_inaugural_1961", "author": "John F. Kennedy", "attribution": "John F. Kennedy, Inaugural Address, 1961", "year": 1961, "period": 8, "themes": ["WOR", "NAT"], "pd": _PD_FEDERAL},
    {"ws": "Eisenhower's farewell address", "id": "eisenhower_farewell_1961", "author": "Dwight D. Eisenhower", "attribution": "Dwight D. Eisenhower, Farewell Address, 1961", "year": 1961, "period": 8, "themes": ["WOR", "PCE"], "pd": _PD_FEDERAL},
    {"ws": "Gulf of Tonkin Resolution", "id": "gulf_of_tonkin_1964", "author": "88th U.S. Congress", "attribution": "Gulf of Tonkin Resolution, 1964", "year": 1964, "period": 8, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Civil Rights Act of 1964", "id": "civil_rights_act_1964", "author": "88th U.S. Congress", "attribution": "Civil Rights Act of 1964 (Title II/VII)", "year": 1964, "period": 8, "themes": ["SOC", "PCE"], "pd": _PD_FEDERAL},

    # --- Batch 2: single-page PD speeches / essays / documents (higher fetch yield) ---
    # Period 3 — revolution & early republic
    {"ws": "Give Me Liberty or Give Me Death", "id": "henry_liberty_1775", "author": "Patrick Henry", "attribution": "Patrick Henry, 'Give Me Liberty or Give Me Death', 1775", "year": 1775, "period": 3, "themes": ["NAT", "PCE"], "pd": _PD_PRE1930},
    {"ws": "Thomas Jefferson's First Inaugural Address", "id": "jefferson_first_inaugural_1801", "author": "Thomas Jefferson", "attribution": "Thomas Jefferson, First Inaugural Address, 1801", "year": 1801, "period": 3, "themes": ["PCE", "NAT"], "pd": _PD_FEDERAL},
    # Period 4 — 1800-1848
    {"ws": "Andrew Jackson's First Inaugural Address", "id": "jackson_first_inaugural_1829", "author": "Andrew Jackson", "attribution": "Andrew Jackson, First Inaugural Address, 1829", "year": 1829, "period": 4, "themes": ["PCE"], "pd": _PD_FEDERAL},
    {"ws": "Slavery a Positive Good", "id": "calhoun_positive_good_1837", "author": "John C. Calhoun", "attribution": "John C. Calhoun, 'Slavery a Positive Good', 1837", "year": 1837, "period": 4, "themes": ["SOC", "PCE"], "pd": _PD_PRE1930},
    {"ws": "Civil Disobedience (Thoreau)", "id": "thoreau_civil_disobedience_1849", "author": "Henry David Thoreau", "attribution": "Henry David Thoreau, 'Civil Disobedience', 1849", "year": 1849, "period": 4, "themes": ["SOC", "ARC"], "pd": _PD_PRE1930},
    {"ws": "The Great Nation of Futurity", "id": "osullivan_futurity_1839", "author": "John L. O'Sullivan", "attribution": "John L. O'Sullivan on Manifest Destiny, 1839", "year": 1839, "period": 4, "themes": ["MIG", "WOR"], "pd": _PD_PRE1930},
    # Period 5 — 1844-1877
    {"ws": "Ain't I a Woman?", "id": "truth_aint_i_a_woman_1851", "author": "Sojourner Truth", "attribution": "Sojourner Truth, 'Ain't I a Woman?', 1851", "year": 1851, "period": 5, "themes": ["SOC"], "pd": _PD_PRE1930},
    {"ws": "Gettysburg Address", "id": "gettysburg_address_1863", "author": "Abraham Lincoln", "attribution": "Abraham Lincoln, Gettysburg Address, 1863", "year": 1863, "period": 5, "themes": ["NAT"], "pd": _PD_FEDERAL},
    {"ws": "Abraham Lincoln's First Inaugural Address", "id": "lincoln_first_inaugural_1861", "author": "Abraham Lincoln", "attribution": "Abraham Lincoln, First Inaugural Address, 1861", "year": 1861, "period": 5, "themes": ["PCE", "NAT"], "pd": _PD_FEDERAL},
    {"ws": "Cooper Union Address", "id": "lincoln_cooper_union_1860", "author": "Abraham Lincoln", "attribution": "Abraham Lincoln, Cooper Union Address, 1860", "year": 1860, "period": 5, "themes": ["PCE"], "pd": _PD_PRE1930},
    # Period 6 — 1865-1898
    {"ws": "The New Colossus", "id": "lazarus_new_colossus_1883", "author": "Emma Lazarus", "attribution": "Emma Lazarus, 'The New Colossus', 1883", "year": 1883, "period": 6, "themes": ["MIG"], "pd": _PD_PRE1930},
    {"ws": "Southern Horrors: Lynch Law in All Its Phases", "id": "wells_southern_horrors_1892", "author": "Ida B. Wells", "attribution": "Ida B. Wells, 'Southern Horrors', 1892", "year": 1892, "period": 6, "themes": ["SOC"], "pd": _PD_PRE1930},
    {"ws": "The Talented Tenth", "id": "dubois_talented_tenth_1903", "author": "W. E. B. Du Bois", "attribution": "W. E. B. Du Bois, 'The Talented Tenth', 1903", "year": 1903, "period": 7, "themes": ["SOC"], "pd": _PD_PRE1930},
    # Period 7 — 1890-1945
    {"ws": "Woodrow Wilson's First Inaugural Address", "id": "wilson_first_inaugural_1913", "author": "Woodrow Wilson", "attribution": "Woodrow Wilson, First Inaugural Address, 1913", "year": 1913, "period": 7, "themes": ["PCE"], "pd": _PD_FEDERAL},
    {"ws": "The Man with the Muck-Rake", "id": "tr_muckrake_1906", "author": "Theodore Roosevelt", "attribution": "Theodore Roosevelt, 'The Man with the Muck-Rake', 1906", "year": 1906, "period": 7, "themes": ["PCE"], "pd": _PD_FEDERAL},
    {"ws": "Quarantine Speech", "id": "fdr_quarantine_1937", "author": "Franklin D. Roosevelt", "attribution": "Franklin D. Roosevelt, Quarantine Speech, 1937", "year": 1937, "period": 7, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Address to Congress on the State of the Union (January 11, 1944)", "id": "fdr_second_bill_of_rights_1944", "author": "Franklin D. Roosevelt", "attribution": "Franklin D. Roosevelt, 'Second Bill of Rights' (1944 State of the Union)", "year": 1944, "period": 7, "themes": ["PCE", "WXT"], "pd": _PD_FEDERAL},
    # Period 8-9 — 1945-present (federal works only)
    {"ws": "Address at the Brandenburg Gate", "id": "reagan_brandenburg_1987", "author": "Ronald Reagan", "attribution": "Ronald Reagan, Address at the Brandenburg Gate, 1987", "year": 1987, "period": 9, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Ronald Reagan's First Inaugural Address", "id": "reagan_first_inaugural_1981", "author": "Ronald Reagan", "attribution": "Ronald Reagan, First Inaugural Address, 1981", "year": 1981, "period": 9, "themes": ["PCE", "WXT"], "pd": _PD_FEDERAL},
    {"ws": "We Shall Overcome (speech)", "id": "lbj_we_shall_overcome_1965", "author": "Lyndon B. Johnson", "attribution": "Lyndon B. Johnson, 'We Shall Overcome' Address, 1965", "year": 1965, "period": 8, "themes": ["SOC", "PCE"], "pd": _PD_FEDERAL},
]

# Presidential inaugural addresses: all U.S. federal works (public domain at any
# date), single-page prose on Wikisource, spanning every APUSH period — the
# highest-yield way to scale the stimulus corpus. (president, ordinal, year,
# period). Ones already in the corpus/catalog by another id are omitted.
_INAUGURALS = [
    ("George Washington", "First", 1789, 3), ("George Washington", "Second", 1793, 3),
    ("John Adams", "", 1797, 3), ("Thomas Jefferson", "Second", 1805, 4),
    ("James Madison", "First", 1809, 4), ("James Madison", "Second", 1813, 4),
    ("James Monroe", "First", 1817, 4), ("James Monroe", "Second", 1821, 4),
    ("John Quincy Adams", "", 1825, 4), ("Andrew Jackson", "Second", 1833, 4),
    ("Martin Van Buren", "", 1837, 4), ("William Henry Harrison", "", 1841, 4),
    ("James K. Polk", "", 1845, 5), ("Zachary Taylor", "", 1849, 5),
    ("Franklin Pierce", "", 1853, 5), ("James Buchanan", "", 1857, 5),
    ("Ulysses S. Grant", "First", 1869, 5), ("Ulysses S. Grant", "Second", 1873, 6),
    ("Rutherford B. Hayes", "", 1877, 6), ("James A. Garfield", "", 1881, 6),
    ("Grover Cleveland", "First", 1885, 6), ("Benjamin Harrison", "", 1889, 6),
    ("Grover Cleveland", "Second", 1893, 6), ("William McKinley", "First", 1897, 7),
    ("William McKinley", "Second", 1901, 7), ("Theodore Roosevelt", "", 1905, 7),
    ("William Howard Taft", "", 1909, 7), ("Woodrow Wilson", "Second", 1917, 7),
    ("Warren G. Harding", "", 1921, 7), ("Calvin Coolidge", "", 1925, 7),
    ("Herbert Hoover", "", 1929, 7), ("Franklin D. Roosevelt", "Second", 1937, 7),
    ("Franklin D. Roosevelt", "Third", 1941, 7), ("Franklin D. Roosevelt", "Fourth", 1945, 7),
    ("Harry S. Truman", "", 1949, 8), ("Dwight D. Eisenhower", "First", 1953, 8),
    ("Dwight D. Eisenhower", "Second", 1957, 8), ("Lyndon B. Johnson", "", 1965, 8),
    ("Richard Nixon", "First", 1969, 8), ("Richard Nixon", "Second", 1973, 8),
    ("Jimmy Carter", "", 1977, 8), ("Ronald Reagan", "Second", 1985, 9),
    ("George H. W. Bush", "", 1989, 9), ("Bill Clinton", "First", 1993, 9),
    ("Bill Clinton", "Second", 1997, 9),
]


def _inaugural_entries():
    out = []
    for name, ordinal, year, period in _INAUGURALS:
        last = re.sub(r"[^a-z]", "", name.split()[-1].lower())
        ord_slug = (ordinal.lower() + "_") if ordinal else ""
        title = f"{name}'s {ordinal} Inaugural Address" if ordinal else f"{name}'s Inaugural Address"
        label = f"{name}, {ordinal} Inaugural Address, {year}" if ordinal else f"{name}, Inaugural Address, {year}"
        out.append({"ws": title, "id": f"{last}_{ord_slug}inaugural_{year}",
                    "author": name, "attribution": label, "year": year,
                    "period": period, "themes": ["PCE", "NAT"], "pd": _PD_FEDERAL})
    return out


CORPUS_CATALOG += _inaugural_entries()

# Batch 3: high-relevance APUSH speeches/documents (federal at any date, or <=1930).
CORPUS_CATALOG += [
    {"ws": "The American Crisis/I", "id": "paine_american_crisis_1776", "author": "Thomas Paine", "attribution": "Thomas Paine, 'The American Crisis' No. I, 1776", "year": 1776, "period": 3, "themes": ["NAT", "PCE"], "pd": _PD_PRE1930},
    {"ws": "President Jackson's Message to Congress On Indian Removal", "id": "jackson_indian_removal_1830", "author": "Andrew Jackson", "attribution": "Andrew Jackson, Message on Indian Removal, 1830", "year": 1830, "period": 4, "themes": ["MIG", "GEO"], "pd": _PD_FEDERAL},
    {"ws": "Theodore Roosevelt's Fourth Annual Message", "id": "tr_roosevelt_corollary_1904", "author": "Theodore Roosevelt", "attribution": "Theodore Roosevelt, Roosevelt Corollary (Annual Message), 1904", "year": 1904, "period": 7, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "The Fourteen Points", "id": "wilson_fourteen_points_speech_1918", "author": "Woodrow Wilson", "attribution": "Woodrow Wilson, Fourteen Points, 1918", "year": 1918, "period": 7, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Farewell address (Eisenhower)", "id": "eisenhower_farewell_address_1961", "author": "Dwight D. Eisenhower", "attribution": "Dwight D. Eisenhower, Farewell Address (military-industrial complex), 1961", "year": 1961, "period": 8, "themes": ["WOR", "PCE"], "pd": _PD_FEDERAL},
    {"ws": "Address to the Nation on the War in Vietnam (November 3, 1969)", "id": "nixon_silent_majority_1969", "author": "Richard Nixon", "attribution": "Richard Nixon, 'Silent Majority' Address, 1969", "year": 1969, "period": 8, "themes": ["WOR", "PCE"], "pd": _PD_FEDERAL},
    {"ws": "Crisis of Confidence", "id": "carter_crisis_confidence_1979", "author": "Jimmy Carter", "attribution": "Jimmy Carter, 'Crisis of Confidence' Address, 1979", "year": 1979, "period": 8, "themes": ["PCE", "WXT"], "pd": _PD_FEDERAL},
    {"ws": "Address to the Nation Announcing Steps to Lower the Rate of Inflation", "id": "reagan_evil_empire_1983", "author": "Ronald Reagan", "attribution": "Ronald Reagan, 'Evil Empire' Speech, 1983", "year": 1983, "period": 9, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Address at Rice University on the Nation's Space Effort", "id": "jfk_rice_moon_1962", "author": "John F. Kennedy", "attribution": "John F. Kennedy, Rice University 'Moon' Speech, 1962", "year": 1962, "period": 8, "themes": ["WOR", "WXT"], "pd": _PD_FEDERAL},
    {"ws": "Cuban Missile Crisis Address to the Nation", "id": "jfk_cuban_missile_1962", "author": "John F. Kennedy", "attribution": "John F. Kennedy, Cuban Missile Crisis Address, 1962", "year": 1962, "period": 8, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Arsenal of Democracy", "id": "fdr_arsenal_democracy_1940", "author": "Franklin D. Roosevelt", "attribution": "Franklin D. Roosevelt, 'Arsenal of Democracy' Fireside Chat, 1940", "year": 1940, "period": 7, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Brutus I", "id": "antifederalist_brutus_1_1787", "author": "Brutus (Anti-Federalist)", "attribution": "Anti-Federalist 'Brutus' No. I, 1787", "year": 1787, "period": 3, "themes": ["PCE"], "pd": _PD_PRE1930},
    {"ws": "The Federalist/78", "id": "federalist_78_1788", "author": "Alexander Hamilton", "attribution": "Alexander Hamilton, Federalist No. 78, 1788", "year": 1788, "period": 3, "themes": ["PCE"], "pd": _PD_PRE1930},
    {"ws": "Address Accepting the Presidential Nomination (1932)", "id": "fdr_new_deal_nomination_1932", "author": "Franklin D. Roosevelt", "attribution": "Franklin D. Roosevelt, 'New Deal' Nomination Address, 1932", "year": 1932, "period": 7, "themes": ["WXT", "PCE"], "pd": _PD_FEDERAL},
    {"ws": "Nixon's resignation speech", "id": "nixon_resignation_1974", "author": "Richard Nixon", "attribution": "Richard Nixon, Resignation Address, 1974", "year": 1974, "period": 8, "themes": ["PCE"], "pd": _PD_FEDERAL},
    {"ws": "Special Message to the Congress on Greece and Turkey", "id": "truman_doctrine_speech_1947", "author": "Harry S. Truman", "attribution": "Harry S. Truman, Special Message on Greece and Turkey, 1947", "year": 1947, "period": 8, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Old Soldiers Never Die", "id": "macarthur_old_soldiers_1951", "author": "Douglas MacArthur", "attribution": "Douglas MacArthur, 'Old Soldiers Never Die' Address, 1951", "year": 1951, "period": 8, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "The Chance for Peace", "id": "eisenhower_chance_peace_1953", "author": "Dwight D. Eisenhower", "attribution": "Dwight D. Eisenhower, 'Chance for Peace', 1953", "year": 1953, "period": 8, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Speech to the Second Virginia Convention", "id": "henry_virginia_convention_1775", "author": "Patrick Henry", "attribution": "Patrick Henry, Speech to the Virginia Convention, 1775", "year": 1775, "period": 3, "themes": ["NAT"], "pd": _PD_PRE1930},
    {"ws": "The Significance of the Frontier in American History", "id": "turner_frontier_thesis_1893", "author": "Frederick Jackson Turner", "attribution": "Frederick Jackson Turner, Frontier Thesis, 1893", "year": 1893, "period": 6, "themes": ["MIG", "GEO"], "pd": _PD_PRE1930},
    {"ws": "Cross of Gold speech", "id": "bryan_cross_gold_speech_1896", "author": "William Jennings Bryan", "attribution": "William Jennings Bryan, 'Cross of Gold', 1896 (full)", "year": 1896, "period": 6, "themes": ["PCE", "WXT"], "pd": _PD_PRE1930},
    {"ws": "Declaration of War against Japan", "id": "fdr_declaration_war_1941", "author": "Franklin D. Roosevelt", "attribution": "Franklin D. Roosevelt, Request for Declaration of War, 1941", "year": 1941, "period": 7, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Kennedy's Berlin Wall speech", "id": "jfk_ich_bin_berliner_1963", "author": "John F. Kennedy", "attribution": "John F. Kennedy, 'Ich bin ein Berliner', 1963", "year": 1963, "period": 8, "themes": ["WOR"], "pd": _PD_FEDERAL},
    {"ws": "Watergate/Address to the Nation about the Watergate Investigations", "id": "nixon_watergate_1973", "author": "Richard Nixon", "attribution": "Richard Nixon, Address on Watergate, 1973", "year": 1973, "period": 8, "themes": ["PCE"], "pd": _PD_FEDERAL},
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
WIKISOURCE_SEARCH = "https://en.wikisource.org/w/rest.php/v1/search/page?q={q}&limit=3"
USER_AGENT = "apush-slm-seed-corpus/1.0 (research; contact: project maintainer)"


def _http_json(url: str, timeout: int = 25):
    """GET JSON with polite retry/backoff on 429/5xx. Returns dict or None."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                time.sleep(3 * (attempt + 1))
                continue
            return None
        except Exception:  # noqa: BLE001
            time.sleep(1.5)
    return None


def _ws_page_source(page_key: str) -> str | None:
    data = _http_json(WIKISOURCE_REST.format(title=urllib.parse.quote(page_key)))
    src = (data or {}).get("source")
    return _strip_wikitext(src) if src else None


def _ws_resolve(query: str) -> str | None:
    """Resolve a human title to an exact Wikisource page key via search — avoids
    the brittle exact-title guessing that 404s."""
    data = _http_json(WIKISOURCE_SEARCH.format(q=urllib.parse.quote(query)))
    pages = (data or {}).get("pages") or []
    return pages[0].get("key") if pages else None


def _strip_wikitext(s: str) -> str:
    """Best-effort wikitext -> plain text for excerpting. Not exhaustive."""
    # Iteratively remove templates INNERMOST-first so nested {{header|...{{x}}...}}
    # blocks (which carry doc metadata, not prose) are fully stripped, not leaked.
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)  # refs
    s = re.sub(r"<ref[^>]*/\s*>", "", s)          # self-closing refs
    s = re.sub(r"<[^>]+>", "", s)                  # html tags
    s = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", s, flags=re.I)  # media
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)  # links -> label
    s = re.sub(r"'''?", "", s)                     # bold/italic
    s = re.sub(r"^[=*#:;].*$", "", s, flags=re.M)  # headings/lists
    s = re.sub(r"\n{2,}", "\n\n", s)
    return s.strip()


def _looks_like_markup(p: str) -> bool:
    """True if a 'paragraph' is actually leftover template/metadata, not prose.
    Targets template SYNTAX (braces, `|param=`) and Wikisource metadata keywords,
    so it won't reject ordinary historical prose."""
    return ("{{" in p or "}}" in p
            or re.search(r"\|\s*[\w ]{1,24}=", p) is not None       # |param = ...
            or re.search(r"\b(commonscat|wikidata|statvolume|billtype|override_author|portal\s*=)\b", p, re.I) is not None)


def fetch_wikisource(title: str, timeout: int = 20) -> str | None:
    """Fetch a public-domain transcription: try the exact title, then fall back to
    a search-resolved page key. Returns plain text or None."""
    direct = _ws_page_source(title.replace(" ", "_"))
    if direct:
        return direct
    key = _ws_resolve(title)
    if key:
        return _ws_page_source(key)
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
            out.append({**src, "license": "public domain (published <=1930)",
                        "source_url": WIKISOURCE_REST.format(title=urllib.parse.quote(src["title"])),
                        "text_len": len(text), "text": text[:4000]})
        time.sleep(1.0)  # be polite
    with open(FETCHED_PATH, "w", encoding="utf-8") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} fetched sources -> {FETCHED_PATH}")
    return 0


def _lead_excerpt(text: str, lo: int = 200, hi: int = 1000) -> str | None:
    """Pull a clean, coherent stimulus excerpt from a fetched document: the first
    substantive prose paragraph(s), skipping short header/metadata lines, trimmed
    to a sentence boundary. Returns None if nothing usable is found."""
    if not text:
        return None
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n{2,}", text)]
    # a real prose paragraph: long enough, has sentence punctuation, not a heading,
    # and not leftover template/metadata markup
    good = [p for p in paras
            if len(p) >= 120 and p.count(" ") >= 15 and re.search(r"[.!?]", p)
            and not p.isupper() and not _looks_like_markup(p)]
    if not good:
        return None
    buf = ""
    for p in good:
        buf = p if not buf else f"{buf} {p}"
        if len(buf) >= lo:
            break
    if len(buf) < lo:
        return None
    if len(buf) > hi:
        cut = buf[:hi]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        buf = cut[:end + 1] if end > lo else cut.rsplit(" ", 1)[0]
    return buf.strip()


def _existing_seed_ids() -> set:
    ids = set()
    if os.path.exists(SEED_PATH):
        with open(SEED_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        ids.add(json.loads(line).get("id"))
                    except json.JSONDecodeError:
                        pass
    return ids


def cmd_build_corpus() -> int:
    """A3 corpus expansion: fetch every catalog entry from Wikisource, extract a
    length-gated lead excerpt, and STAGE the results (full seed schema) to
    fetched_primary_sources.jsonl for review. Nothing is written to the
    source-of-truth seed_stimuli.jsonl here — run --promote-fetched after eyeing
    the staged file. Idempotent: skips ids already in the seed corpus."""
    have = _existing_seed_ids()
    staged, skipped, failed = [], [], []
    for src in CORPUS_CATALOG:
        if src["id"] in have:
            skipped.append((src["id"], "already in seed corpus"))
            continue
        print(f"fetching: {src['ws']}")
        raw = fetch_wikisource(src["ws"])
        excerpt = _lead_excerpt(raw or "")
        if not excerpt:
            failed.append((src["id"], "no usable excerpt (404 or unparseable)"))
            time.sleep(0.5)
            continue
        staged.append({
            "id": src["id"], "stimulus_type": "primary_text",
            "attribution": src["attribution"], "author": src["author"],
            "year": src["year"], "period": src["period"], "themes": src["themes"],
            "text": excerpt, "license": src["pd"],
            "source_url": WIKISOURCE_REST.format(title=urllib.parse.quote(src["ws"].replace(" ", "_"))),
            "provenance": "fetched from en.wikisource.org (A3); lead excerpt, length-gated",
        })
        time.sleep(1.0)  # be polite
    with open(FETCHED_PATH, "w", encoding="utf-8") as f:
        for o in staged:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(f"\nstaged {len(staged)} sources -> {FETCHED_PATH}")
    if skipped:
        print(f"skipped {len(skipped)} (already present)")
    if failed:
        print(f"FAILED {len(failed)} (fix the ws title or drop from catalog):")
        for fid, why in failed:
            print(f"  - {fid}: {why}")
    print("\nreview the staged file, then:  python build_seed_corpus.py --promote-fetched")
    return 0


def cmd_promote_fetched() -> int:
    """Append staged sources (fetched_primary_sources.jsonl) that pass validation
    into the source-of-truth seed_stimuli.jsonl, de-duplicating by id."""
    if not os.path.exists(FETCHED_PATH):
        print("no staged file; run --build-corpus first", file=sys.stderr)
        return 1
    have = _existing_seed_ids()
    added = 0
    with open(FETCHED_PATH, encoding="utf-8") as f, open(SEED_PATH, "a", encoding="utf-8") as out:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("id") in have:
                continue
            if len(obj.get("text", "")) < 150:
                print(f"  skip {obj.get('id')}: excerpt too short", file=sys.stderr)
                continue
            out.write(json.dumps(obj, ensure_ascii=False) + "\n")
            have.add(obj["id"])
            added += 1
    print(f"appended {added} sources to {SEED_PATH}")
    print("now run:  python build_seed_corpus.py --validate")
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
        "american_yawp": AMERICAN_YAWP,
        "eval_only": EVAL_ONLY_MMLU,
        "wikisource_pd_sources": WIKISOURCE_PD_SOURCES,
        "federal_pd_sources": FEDERAL_PD_SOURCES,
        "pd_cutoff": "U.S. works published <=1930 are public domain (as of 2026-01-01); federal works and court opinions are uncopyrightable at any date",
        "excluded_by_policy": [
            "College Board CED sample items / released FRQs / secure MCQs (copyright; their terms explicitly forbid AI training; taxonomy is hand-derived from the public framework and CED examples are analysis-only, never ingested)",
            "test-prep proprietary question banks",
            "Gilder Lehrman (revocable license; paid permission)",
            "third-party HF question sets with ambiguous/NC-SA-tainted provenance (regenerate our own instead)",
        ],
        "risk_flags": [
            "ShareAlike collision: never blend CC BY-SA (American Yawp / Wikisource notes) with CC BY-NC-SA (current OpenStax) in one derivative; keep per-chunk provenance",
            "Teacher-model ToS is a separate gate: confirm the frontier teacher's terms permit generating training data for another model BEFORE distilling",
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
    p.add_argument("--fetch-wikisource", action="store_true", help="fetch the original 9 PD primary sources")
    p.add_argument("--build-corpus", action="store_true", help="A3: fetch the full catalog + stage length-gated excerpts for review")
    p.add_argument("--promote-fetched", action="store_true", help="append staged sources into seed_stimuli.jsonl")
    p.add_argument("--openstax-info", action="store_true", help="print OpenStax CC BY pointers")
    p.add_argument("--manifest", action="store_true", help="write provenance manifest")
    args = p.parse_args()
    if args.validate:
        return cmd_validate()
    if args.fetch_wikisource:
        return cmd_fetch_wikisource()
    if args.build_corpus:
        return cmd_build_corpus()
    if args.promote_fetched:
        return cmd_promote_fetched()
    if args.openstax_info:
        return cmd_openstax_info()
    if args.manifest:
        return cmd_manifest()
    p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
