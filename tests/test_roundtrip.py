# -*- coding: utf-8 -*-
"""Verifica el revisor sense Streamlit: import net + round-trip lossless +
resum del linter sobre tots els .dvw reals."""
import os
import sys

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import partits
APP = os.path.join(ARREL, "revisor_dvw.py")

# import net: no ha de disparar cap crida a Streamlit (main() no es crida)
import revisor_dvw as R

ENC = R.ENC
fitxers = partits.camins()

print(f"{len(fitxers)} fitxers\n")
tot_ok = True
for f in fitxers:
    with open(f, "rb") as fh:
        raw = fh.read()
    text = raw.decode(ENC)
    parsed = R.parse_dvw(text)

    # 1) round-trip byte a byte
    reconstruit = R.rebuild(parsed).encode(ENC)
    lossless = (reconstruit == raw)
    tot_ok = tot_ok and lossless

    # 2) resum scout + linter
    n_skill = sum(1 for d in parsed["scout"] if d["kind"] == "skill")
    avisos = R.lint(parsed)
    n_err = sum(1 for a in avisos if a["grav"] == "error")
    n_av = sum(1 for a in avisos if a["grav"] == "avis")

    nom = os.path.basename(f)[:42]
    print(f"[{'OK ' if lossless else 'FAIL'}] {nom:44s} "
          f"scout={len(parsed['scout']):4d} skill={n_skill:4d} "
          f"err={n_err:3d} avis={n_av:3d}")

print("\nROUND-TRIP LOSSLESS TOTAL:", "OK" if tot_ok else "HI HA FALLADES")

# desglossament de motius del primer fitxer, per veure què detecta
print("\n--- Motius (primer fitxer) ---")
with open(fitxers[0], "rb") as fh:
    parsed = R.parse_dvw(fh.read().decode(ENC))
from collections import Counter
c = Counter()
for a in R.lint(parsed):
    # normalitza el motiu (treu números concrets)
    key = a["motiu"].split(".")[0][:60]
    c[(a["grav"], key)] += 1
for (g, k), n in c.most_common():
    print(f"  {g:5s} x{n:3d}  {k}")
