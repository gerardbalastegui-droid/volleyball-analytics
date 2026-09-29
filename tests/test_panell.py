# -*- coding: utf-8 -*-
"""El panell d'inserir/esborrar dins de la UI real."""
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


def boto(at, etiqueta):
    return next((b for b in at.get("button") if b.label == etiqueta), None)


def taula(at):
    for e in (at.get("data_editor") or at.get("dataframe")):
        v = getattr(e, "value", None)
        if v is not None and hasattr(v, "columns") and "Zona" in list(v.columns):
            return v


at = AppTest.from_file(APP, default_timeout=120)
at.run()
at.get("file_uploader")[0].upload("f.dvw", open(F, "rb").read())
at.run()
check("render amb panell, sense excepció", not at.exception, str(at.exception))
print("botons:", [b.label for b in at.get("button")])
n_files_ini = len(taula(at))

# apunta a la L692 (*25AH+), rally guanyat pel visitant
at.session_state["ins_linia_val"] = 692
at.run()
txt = " ".join(e.value for e in at.get("text") if isinstance(e.value, str))
check("previsualització mostra el rally", "*25AH+" in txt, txt[:80].replace("\n", " | "))

# --- intent incoherent: punt per al LOCAL, que va perdre el rally ---
at.get("selectbox")[1].set_value("Demo VC")   # equip (0 = filtre)
at.run()
sb = at.get("selectbox")
at.get("number_input")[1].set_value(9)                 # dorsal (0 = línia ref)
at.run()
# gest = Atac, marca = #
for s in at.get("selectbox"):
    if "Atac" in (s.options or []):
        s.set_value("Atac")
    if "#" in (s.options or []):
        s.set_value("#")
at.run()
b = boto(at, "Afegir operació")
b.click()
at.run()
errs = [e.value for e in at.get("error")]
check("insert incoherent bloquejat", len(errs) == 1, str(errs))

# --- intent vàlid: marca no terminal ---
for s in at.get("selectbox"):
    if "+" in (s.options or []):
        s.set_value("+")
at.run()
boto(at, "Afegir operació").click()
at.run()
check("insert vàlid acceptat", not at.get("error"), str([e.value for e in at.get("error")]))
taula2 = taula(at)
check("la taula té una acció més", len(taula2) == n_files_ini + 1,
      f"{n_files_ini} -> {len(taula2)}")
noves = taula2[taula2["_avis"] == "+"]
check("la nova surt marcada", len(noves) == 1,
      str(noves[["Línia", "Dorsal", "Jugador", "Gest", "Aval."]].to_dict("records")))

# --- desar: ha d'incloure l'operació ---
boto(at, "Desar còpia corregida").click()
at.run()
check("desar ofereix baixada", len(at.get("download_button")) == 1,
      str([s.value for s in at.get("success")]))
