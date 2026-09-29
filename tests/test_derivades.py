# -*- coding: utf-8 -*-
"""Columnes derivades del dorsal: (1) la Zona no s'ha de perdre pel zero-padding
i (2) en canviar el dorsal, Jugador i Zona s'han de recalcular."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import partits
APP = os.path.join(ARREL, "revisor_dvw.py")
import revisor_dvw as R
from streamlit.testing.v1 import AppTest

F = partits.cami("Demo VC vs Rival D.dvw")
LINIA = 692          # *25AH+ (dorsal inexistent, atac)


def check(nom, ok, extra=""):
    print(f"[{'OK ' if ok else 'FAIL'}] {nom} {extra}")


def taula(a):
    for e in (a.get("data_editor") or a.get("dataframe")):
        v = getattr(e, "value", None)
        if v is not None and hasattr(v, "columns") and "Zona" in list(v.columns):
            return v


at = AppTest.from_file(APP, default_timeout=90)
at.run()
at.get("file_uploader")[0].upload("f.dvw", open(F, "rb").read())
at.run()
check("render sense excepció", not at.exception, str(at.exception))

tbl = taula(at)
check("la taula es troba", tbl is not None)

# --- (1) zero-padding: els dorsals d'1 xifra també han de tenir zona ---
# La formació guarda "9" i el token "09": si no es normalitza, es perdien 109
# de 111 zones. Amb l'arreglo han de sortir gairebé totes.
atacs = tbl[tbl["Gest"] == "Atac"]
amb_zona = int((atacs["Zona"] != "").sum())
pct = 100 * amb_zona / max(len(atacs), 1)
check("la majoria d'atacs tenen zona deduïda", pct > 90,
      f"{amb_zona}/{len(atacs)} ({pct:.1f}%)")

# els dorsals d'una xifra no poden quedar-se sense zona sistemàticament
curts = atacs[atacs["Dorsal"] < 10]
amb_zona_curts = int((curts["Zona"] != "").sum())
check("els dorsals d'1 xifra també tenen zona", amb_zona_curts > 0,
      f"{amb_zona_curts}/{len(curts)}")

# --- (2) recàlcul en canviar el dorsal ---
fila = tbl[tbl["Línia"] == LINIA]
abans = fila[["Dorsal", "Jugador", "Zona"]].to_dict("records")[0]
check("de partida, dorsal desconegut i sense zona",
      abans["Jugador"] == "?" and abans["Zona"] == "", str(abans))

pos = list(tbl.index).index(fila.index[0])
at.session_state["editor"] = {"edited_rows": {pos: {"Dorsal": 2}},
                              "added_rows": [], "deleted_rows": []}
at.run()
despres = taula(at)[taula(at)["Línia"] == LINIA][
    ["Dorsal", "Jugador", "Zona"]].to_dict("records")[0]
check("el nom es recalcula amb el dorsal nou",
      despres["Jugador"] not in ("?", ""), str(despres))
check("la zona es recalcula amb el dorsal nou",
      despres["Zona"] != "", str(despres))
