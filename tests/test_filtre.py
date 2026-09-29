# -*- coding: utf-8 -*-
"""El filtre 'només línies amb avís' ha de sobreviure a un salt al panell."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import partits
APP = os.path.join(ARREL, "revisor_dvw.py")
from streamlit.testing.v1 import AppTest

F = partits.cami("Demo VC vs Rival D.dvw")


def check(nom, ok, extra=""):
    print(f"[{'OK ' if ok else 'FAIL'}] {nom} {extra}")


def ss(a, k, d=None):
    try:
        return a.session_state[k]
    except (KeyError, AttributeError):
        return d


def taula(a):
    for e in (a.get("data_editor") or a.get("dataframe")):
        v = getattr(e, "value", None)
        if v is not None and hasattr(v, "columns") and "Zona" in list(v.columns):
            return v


def casella(a):
    return next(c for c in a.get("checkbox") if "avís" in c.label)


at = AppTest.from_file(APP, default_timeout=120)
at.run()
at.get("file_uploader")[0].upload("f.dvw", open(F, "rb").read())
at.run()

n_total = len(taula(at))
casella(at).set_value(True)
at.run()
n_filtrat = len(taula(at))
print(f"files: totes={n_total}  filtrades={n_filtrat}")
check("el filtre redueix la llista", n_filtrat < n_total)
check("la casella queda marcada", casella(at).value)

# ara salta al panell des d'una fila filtrada (casella →)
tbl = taula(at)
pos = 0
linia_obj = int(tbl.iloc[pos]["Línia"])
at.session_state["editor"] = {"edited_rows": {pos: {"Anar": True}},
                              "added_rows": [], "deleted_rows": []}
at.run()

print(f"després del salt: files={len(taula(at))}  casella={casella(at).value}  "
      f"ins_linia_val={ss(at, 'ins_linia_val')}")
check("ha saltat a la línia", ss(at, "ins_linia_val") == linia_obj)
check("LA CASELLA SEGUEIX MARCADA", casella(at).value)
check("I LA LLISTA SEGUEIX FILTRADA", len(taula(at)) == n_filtrat,
      f"{n_filtrat} -> {len(taula(at))}")

# el mateix saltant des de la revisió automàtica
at.session_state["taula_avisos"] = {"selection": {"rows": [0], "columns": []}}
at.run()
print(f"després del salt des del linter: files={len(taula(at))} "
      f"casella={casella(at).value}")
check("filtre viu després del salt des del linter",
      casella(at).value and len(taula(at)) == n_filtrat,
      f"{n_filtrat} -> {len(taula(at))}")

