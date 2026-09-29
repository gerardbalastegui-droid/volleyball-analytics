# -*- coding: utf-8 -*-
"""Saltar al panell des de la taula (casella →) i des de la revisió (clic)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import partits
APP = os.path.join(ARREL, "revisor_dvw.py")
import revisor_dvw as R
from streamlit.testing.v1 import AppTest

F = partits.cami("Demo VC vs Rival D.dvw")


def check(nom, ok, extra=""):
    print(f"[{'OK ' if ok else 'FAIL'}] {nom} {extra}")


def ss(a, k, default=None):
    try:
        return a.session_state[k]
    except (KeyError, AttributeError):
        return default


def taula(a):
    for e in (a.get("data_editor") or a.get("dataframe")):
        v = getattr(e, "value", None)
        if v is not None and hasattr(v, "columns") and "Zona" in list(v.columns):
            return v


at = AppTest.from_file(APP, default_timeout=120)
at.run()
at.get("file_uploader")[0].upload("f.dvw", open(F, "rb").read())
at.run()
check("render amb salts, sense excepció", not at.exception, str(at.exception))

tbl = taula(at)
check("la taula té la columna de salt", "Anar" in list(tbl.columns), str(list(tbl.columns)))

# ---- 1) salt des de la taula: marca la casella d'una fila concreta ----
objectiu = 692
pos = list(tbl.index).index(tbl[tbl["Línia"] == objectiu].index[0])
at.session_state["editor"] = {"edited_rows": {pos: {"Anar": True}},
                              "added_rows": [], "deleted_rows": []}
at.run()
check("la taula porta el panell a la línia",
      ss(at, "ins_linia_val") == objectiu,
      f"ins_linia_val={ss(at, 'ins_linia_val')}")
check("el tic no queda enganxat", not (ss(at, "editor") or {}).get("edited_rows"),
      str(ss(at, "editor")))
txt = " ".join(e.value for e in at.get("text") if isinstance(e.value, str))
check("el panell mostra aquest rally", "*25AH+" in txt)

# ---- 2) el salt no perd les correccions fetes a la taula ----
at.session_state["editor"] = {"edited_rows": {pos: {"Dorsal": 11}},
                              "added_rows": [], "deleted_rows": []}
at.run()
altra = 75
pos2 = list(taula(at).index).index(taula(at)[taula(at)["Línia"] == altra].index[0])
at.session_state["editor"] = {"edited_rows": {pos2: {"Anar": True}},
                              "added_rows": [], "deleted_rows": []}
at.run()
check("saltar no perd la correcció anterior",
      (ss(at, "correccions") or {}).get(objectiu - 1, {}).get("dorsal") == 11,
      str(ss(at, 'correccions')))
t2 = taula(at)
fila = t2[t2["Línia"] == objectiu][["Dorsal", "Jugador"]].to_dict("records")
check("i segueix pintada a la taula", fila and fila[0]["Dorsal"] == 11, str(fila))
check("i ha saltat a la nova línia", ss(at, "ins_linia_val") == altra)

# ---- 3) salt des de la revisió automàtica ----
at.session_state["taula_avisos"] = {"selection": {"rows": [1], "columns": []}}
at.run()
avisos = R.lint(R.parse_dvw(open(F, "rb").read().decode(R.ENC)))
esperat = avisos[1]["linia"]
check("clicar un avís porta el panell a la seva línia",
      ss(at, "ins_linia_val") == esperat,
      f"esperat L{esperat}, obtingut L{ss(at, 'ins_linia_val')}")
