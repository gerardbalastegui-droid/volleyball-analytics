# -*- coding: utf-8 -*-
"""Regla del linter: el marcador ha de pujar d'un punt, i d'un de sol.

Detecta les correccions que vaig fer en directe (donar un punt a qui no
tocava i desfer-ho): el marcador retrocedeix i queden files fantasma.
Als 14 partits n'hi ha exactament 7, en 6 sets — comprovat de manera
independent llegint els .dvw amb el parser d'app_dvw.py.

El que ha de vigilar aquesta prova és sobretot que NO surtin falsos
positius: un linter que crida el llop cada dos per tres no el mira ningú.
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)

import partits

import revisor_dvw as R

_ok = _ko = 0


def check(nom, cond, extra=""):
    global _ok, _ko
    if cond:
        _ok += 1
    else:
        _ko += 1
    print(f"[{'OK ' if cond else 'FAIL'}] {nom} {extra}")


# --- lectura del codi de marcador -----------------------------------------
check("llegeix un marcador normal", R._marcador_codi("*p01:02") == (1, 2))
check("llegeix un marcador de dos dígits", R._marcador_codi("ap23:25") == (23, 25))
check("tolera espais", R._marcador_codi("*p 7: 9") == (7, 9))
check("no peta amb un codi sense marcador", R._marcador_codi("*pXX") is None)
check("no peta amb un codi buit", R._marcador_codi("*p") is None)

# --- els 7 casos reals, i cap més ------------------------------------------
fitxers = partits.camins()
check("hi ha partits per provar", len(fitxers) == 14, f"{len(fitxers)} arxius")

trobats = []
altres_avisos = 0
for cami in fitxers:
    nom = os.path.basename(cami)
    with open(cami, "rb") as f:
        text = f.read().decode("latin-1")
    avisos = R.lint(R.parse_dvw(text))
    for a in avisos:
        if a.get("codi") == "marcador_salt":
            trobats.append((nom, a["linia"], a["motiu"]))
        else:
            altres_avisos += 1

check("troba exactament els 7 salts de marcador coneguts", len(trobats) == 7,
      f"{len(trobats)} trobats")

# Els 6 sets afectats, identificats abans amb el parser d'app_dvw.py.
esperats = {
    "Demo VC vs Rival D.dvw": 3,
    "Demo VC vs Rival A.dvw": 1,
    "Demo VC vs Rival C.dvw": 2,
    "Demo VC vs Rival K 2.dvw": 1,
}
per_fitxer = {}
for nom, _, _ in trobats:
    per_fitxer[nom] = per_fitxer.get(nom, 0) + 1
check("els salts són als partits esperats", per_fitxer == esperats,
      f"{per_fitxer}")

check("cap salt als altres 10 partits",
      all(n in esperats for n in per_fitxer))

# Tots els casos reals són retrocessos d'un punt: si algun dia en surt un
# d'un altre tipus (un salt endavant de 2, per exemple), val la pena mirar-lo.
retrocessos = 0
for _, _, motiu in trobats:
    a, b = motiu.split(" de ")[1].split(" (")[0].split(" a ")
    ah, av = (int(x) for x in a.split(":"))
    bh, bv = (int(x) for x in b.split(":"))
    if bh < ah or bv < av:
        retrocessos += 1
check("els 7 casos són retrocessos del marcador", retrocessos == 7,
      f"{retrocessos}/7")

# --- cap fals positiu en una seqüència neta --------------------------------
# El linter no ha d'inventar-se avisos en un set que puja bé de l'1 al 25.
net = R.parse_dvw("\n".join(
    ["[3SCOUT]"] +
    [f"*p{i:02d}:00;;;;;;;;1;;;;;;;;;;;;;;;;;;" for i in range(1, 26)]))
salts_nets = [a for a in R.lint(net) if a.get("codi") == "marcador_salt"]
check("cap avís en un set que puja d'un en un", len(salts_nets) == 0,
      f"{len(salts_nets)} avisos")

# I sí que n'ha de sortir un si el marcador fa un salt de 2.
trencat = R.parse_dvw("\n".join(
    ["[3SCOUT]"] +
    [f"*p{i:02d}:00;;;;;;;;1;;;;;;;;;;;;;;;;;;" for i in (1, 2, 4, 5)]))
salts_trencats = [a for a in R.lint(trencat) if a.get("codi") == "marcador_salt"]
check("avisa d'un salt endavant de 2 punts", len(salts_trencats) == 1,
      f"{len(salts_trencats)} avisos")

# --- el set torna a començar a zero ----------------------------------------
# Entre sets el marcador cau de 25 a 1: si no es reinicia per set, això
# semblaria un retrocés i sortirien avisos falsos a cada canvi de set.
dos_sets = R.parse_dvw("\n".join(
    ["[3SCOUT]"] +
    [f"*p{i:02d}:00;;;;;;;;1;;;;;;;;;;;;;;;;;;" for i in (24, 25)] +
    [f"*p{i:02d}:00;;;;;;;;2;;;;;;;;;;;;;;;;;;" for i in (1, 2)]))
salts_sets = [a for a in R.lint(dos_sets) if a.get("codi") == "marcador_salt"]
check("el canvi de set no genera avisos falsos", len(salts_sets) == 0,
      f"{len(salts_sets)} avisos")

# --- l'avís arriba a la interfície -----------------------------------------
# Aquest avís s'enganxa a una línia de marcador, i la TAULA només conté línies
# d'acció. Cal comprovar que això no peta i que surt igualment a la revisió.
from streamlit.testing.v1 import AppTest

F = partits.cami("Demo VC vs Rival D.dvw")
at = AppTest.from_file(os.path.join(ARREL, "revisor_dvw.py"), default_timeout=90)
at.run()
at.get("file_uploader")[0].upload("f.dvw", open(F, "rb").read())
at.run()
check("el revisor renderitza sense excepció", not at.exception, str(at.exception))

taula_avisos = None
for e in (at.get("dataframe") or []):
    v = getattr(e, "value", None)
    if v is not None and hasattr(v, "columns") and any(
            "otiu" in str(c) or "rund" in str(c) for c in v.columns):
        taula_avisos = v
        break
check("la taula d'avisos es troba", taula_avisos is not None)

if taula_avisos is not None:
    col_motiu = [c for c in taula_avisos.columns
                 if "otiu" in str(c) or "rund" in str(c)][0]
    marcador = [m for m in taula_avisos[col_motiu] if "marcador" in str(m).lower()]
    check("els 3 avisos de marcador surten a la revisió", len(marcador) == 3,
          f"{len(marcador)} de 3")

print(f"\n{_ok} correctes, {_ko} fallides")
sys.exit(1 if _ko else 0)
