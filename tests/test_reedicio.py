# -*- coding: utf-8 -*-
"""Reprodueix el bug reportat: editar un dorsal i tornar-lo a editar.
Abans: el nom canviava però el dorsal tornava al valor per defecte."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import partits
APP = os.path.join(ARREL, "revisor_dvw.py")
import revisor_dvw as R
from streamlit.testing.v1 import AppTest

F = partits.cami("Demo VC vs Rival D.dvw")
LINIA = 692            # *25AH+ : dorsal 25 inexistent


def taula(at):
    for e in (at.get("data_editor") or at.get("dataframe")):
        v = getattr(e, "value", None)
        if v is not None and hasattr(v, "columns") and "Zona" in list(v.columns):
            return v
    return None


def check(nom, ok, extra=""):
    print(f"[{'OK ' if ok else 'FAIL'}] {nom} {extra}")


at = AppTest.from_file(APP, default_timeout=90)
at.run()
at.get("file_uploader")[0].upload("f.dvw", open(F, "rb").read())
at.run()

tbl = taula(at)
pos = list(tbl.index).index(tbl[tbl["Línia"] == LINIA].index[0])
ini = tbl[tbl["Línia"] == LINIA][["Dorsal", "Jugador"]].to_dict("records")[0]
print("inicial:", ini)


def edita(dorsal):
    at.session_state["editor"] = {"edited_rows": {pos: {"Dorsal": dorsal}},
                                  "added_rows": [], "deleted_rows": []}
    at.run()
    return taula(at)[taula(at)["Línia"] == LINIA][
        ["Dorsal", "Jugador", "Zona"]].to_dict("records")[0]


r1 = edita(2)
print("després d'escriure 2: ", r1)
check("1a edició: dorsal 2", r1["Dorsal"] == 2, str(r1))

r2 = edita(9)
print("després d'escriure 9: ", r2)
check("2a edició: dorsal 9 (no torna a 25)", r2["Dorsal"] == 9, str(r2))
check("2a edició: nom coherent amb 9", r2["Jugador"] not in ("?", r1["Jugador"]),
      str(r2["Jugador"]))

# tercera edició, i desar: ha d'escriure l'últim valor
r3 = edita(11)
check("3a edició: dorsal 11", r3["Dorsal"] == 11, str(r3))

at.get("button")[0].click()
at.run()
succ = [s.value for s in at.get("success")]
check("desa amb l'últim valor", len(at.get("download_button")) == 1, str(succ))

# comprova el contingut escrit realment
parsed = R.parse_dvw(open(F, "rb").read().decode(R.ENC))
print("línia original:", parsed["lines"][LINIA - 1].split(";")[0])
