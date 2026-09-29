# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import partits
APP = os.path.join(ARREL, "revisor_dvw.py")
import revisor_dvw as R
from streamlit.testing.v1 import AppTest

fhos = partits.cami("Demo VC vs Rival B.dvw")
f1 = partits.cami("Demo VC vs Rival D.dvw")

def check(nom, ok, extra=""):
    print(f"[{'OK ' if ok else 'FAIL'}] {nom} {extra}")

# --- A) nivell funció: sobre Rival B, 2 confiats (els saques -> 11) ---
parsed = R.parse_dvw(open(fhos, "rb").read().decode(R.ENC))
freq = R.build_freq(parsed)
by_idx = {d["idx"]: d for d in parsed["scout"]}
conf, amb = [], []
for a in R.lint(parsed):
    if a.get("codi") in ("dorsal_plantilla", "dorsal_pista"):
        scored, c = R.suggereix_dorsal(parsed, by_idx[a["idx"]], freq)
        (conf if c else amb).append((a["linia"], by_idx[a["idx"]]["skill"],
                                     scored[0][0] if scored else None))
print("confiats:", conf)
print("ambigus:", [(l, s) for l, s, _ in amb])
check("Rival B: 2 confiats", len(conf) == 2, str(conf))
check("confiats son saques -> 11", all(s == "S" and best == "11" for _, s, best in conf))

# --- B) render + desar sense editar: aplica els 2 auto i genera baixada ---
at = AppTest.from_file(APP, default_timeout=90)
at.run()
at.get("file_uploader")[0].upload("h.dvw", open(fhos, "rb").read())
at.run()
check("render sense excepció", not at.exception, str(at.exception))
at.get("button")[0].click()
at.run()
dl = at.get("download_button")
succ = [s.value for s in at.get("success")]
check("desar aplica auto i ofereix baixada", len(dl) == 1, str(succ))

# mostra les línies que s'auto-corregeixen
parsed2 = R.parse_dvw(open(fhos, "rb").read().decode(R.ENC))
freq2 = R.build_freq(parsed2)
for a in R.lint(parsed2):
    if a.get("codi") in ("dorsal_plantilla", "dorsal_pista"):
        d = {x["idx"]: x for x in parsed2["scout"]}[a["idx"]]
        scored, c = R.suggereix_dorsal(parsed2, d, freq2)
        if c:
            code = parsed2["lines"][a["idx"]].split(";")[0]
            print(f"  L{a['linia']}: {code} -> auto {scored[0][0]}")

# --- C) file 1: 0 confiats, desar sense editar -> sense canvis ---
at2 = AppTest.from_file(APP, default_timeout=90)
at2.run()
at2.get("file_uploader")[0].upload("f1.dvw", open(f1, "rb").read())
at2.run()
check("file1 render sense excepció", not at2.exception)
at2.get("button")[0].click()
at2.run()
check("file1 sense confiats -> sense baixada", len(at2.get("download_button")) == 0,
      str([s.value for s in at2.get("info")]))
