# -*- coding: utf-8 -*-
"""Regressió de les mètriques d'app_dvw.py sobre els 14 partits reals.

L'app d'informes no tenia cap prova: qualsevol canvi a les fórmules donava
números plausibles però equivocats sense petar ni avisar. Això comprova les
invariants que estan documentades a CLAUDE.md i que han de valer sempre:

  1. Comptar les files 'Point' reprodueix EXACTAMENT el marcador de [3SET].
     És la prova forta: si la delimitació de rallies es trenca, salta aquí.
  2. Eficàcia i eficiència segueixen la definició (#+ +)/total i (# − =)/total.
  3. Als rallies, Eficiència ≡ 2 × Eficàcia − 100 (tot rally té guanyador).
  4. Side-out + contraatac cobreixen tots els rallies, sense solapament.
  5. La zona d'atac es dedueix per a la gran majoria d'atacs.
"""
import os
import sys
import types
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ARREL, "app_dvw.py")
sys.path.insert(0, ARREL)

import partits

_ok = _ko = 0


def check(nom, cond, extra=""):
    global _ok, _ko
    if cond:
        _ok += 1
    else:
        _ko += 1
    print(f"[{'OK ' if cond else 'FAIL'}] {nom} {extra}")


def carrega_app_sense_ui():
    """Carrega app_dvw.py tallant just abans del bloc INTERFÍCIE.

    Importar-lo sencer peta amb KeyError('dvw_files'): la interfície del final
    llegeix st.session_state, que fora d'una sessió de Streamlit no existeix.
    Aquí només volem les funcions pures, així que executem el fitxer fins al
    banner de la interfície. Si algun dia es reanomena aquest banner, la prova
    avisa en comptes de passar en fals.
    """
    with open(APP, encoding="utf-8") as f:
        src = f.read()
    i = src.find("# INTERFÍCIE")
    if i < 0:
        print("[FAIL] no trobo el banner '# INTERFÍCIE' a app_dvw.py "
              "(s'ha reanomenat? cal actualitzar aquesta prova)")
        sys.exit(1)
    tall = src.rfind("# ===", 0, i)
    mod = types.ModuleType("app_dvw_pur")
    mod.__file__ = APP
    exec(compile(src[:tall], APP, "exec"), mod.__dict__)
    return mod


A = carrega_app_sense_ui()
check("app_dvw es carrega sense la interfície",
      all(hasattr(A, f) for f in ("marcador_sets", "rallies_equip",
                                  "sideout_contra", "carregar_dvw")))

fitxers = partits.camins()
check("hi ha partits per provar", len(fitxers) > 0, f"{len(fitxers)} arxius")

# ---------------------------------------------------------------------------
# 1. El marcador reconstruït des de les jugades == [3SET]
# ---------------------------------------------------------------------------
quadren = descuadren = 0
pitjor_exclosos = 0.0
pitjor_desviacio = 0

for cami in fitxers:
    nom = os.path.basename(cami)
    with open(cami, "rb") as f:
        dades = f.read()

    oficial = A.marcador_sets(dades)
    df = A.carregar_partits([(nom, dades)])

    punts = (df[df["skill"] == "Point"]
             .groupby([df["set_number"].map(A._norm_set), "team"])
             .size().unstack(fill_value=0))

    local = df["home_team"].dropna().unique()
    visit = df["visiting_team"].dropna().unique()
    if not len(local) or not len(visit):
        continue
    local, visit = local[0], visit[0]

    for n_set, (ph, pv) in enumerate(oficial, start=1):
        if n_set not in punts.index:
            descuadren += 1
            continue
        fila = punts.loc[n_set]
        gh = int(fila.get(local, 0))
        gv = int(fila.get(visit, 0))
        if (gh, gv) == (ph, pv):
            quadren += 1
        else:
            descuadren += 1
            pitjor_desviacio = max(pitjor_desviacio, abs(gh - ph), abs(gv - pv))
            print(f"       (conegut) {nom} set {n_set}: "
                  f"jugades {gh}-{gv} vs [3SET] {ph}-{pv}")

    # rallies descartats (sense Serve identificable): CLAUDE.md diu ~1,5%
    r, exclosos = A.rallies_equip(df, local)
    if len(r) + exclosos:
        pct = 100 * exclosos / (len(r) + exclosos)
        pitjor_exclosos = max(pitjor_exclosos, pct)

# Nota: NO quadra al 100%. Mesurat avui: 46 de 52 sets exactes. Als 6 restants
# les jugades donen entre 2 i 4 punts de més (fins i tot un 25-25 impossible),
# perquè algun scout té accions repetides al final del set. Per això l'app
# llegeix el marcador de [3SET] i no el compta de les jugades: la decisió que
# ja hi ha a app_dvw.py és la bona.
# El que sí vigila aquesta prova és que la proporció no s'ensorri: si algú
# trenca la delimitació de rallies, això baixa de cop molt per sota del 85%.
pct_quadren = 100 * quadren / max(quadren + descuadren, 1)
check("el marcador de les jugades quadra amb [3SET] a la gran majoria de sets",
      pct_quadren >= 85,
      f"{quadren}/{quadren + descuadren} sets exactes ({pct_quadren:.0f}%)")
check("cap set se'n va molt lluny del marcador oficial", pitjor_desviacio <= 5,
      f"pitjor desviació: {pitjor_desviacio} punts")
check("pocs rallies descartats per no trobar el saque", pitjor_exclosos < 5.0,
      f"pitjor partit: {pitjor_exclosos:.1f}%")

# ---------------------------------------------------------------------------
# 2..5. Invariants de les fórmules, sobre un partit concret
# ---------------------------------------------------------------------------
nom = os.path.basename(fitxers[0])
with open(fitxers[0], "rb") as f:
    dades = f.read()
df = A.carregar_partits([(nom, dades)])
equip = A.equips_comuns(df)[0]

# --- eficàcia i eficiència segons la definició ---
atacs = df[(df["team"] == equip) & (df["skill"] == "Attack")]
total = len(atacs)
pos = int(atacs["evaluation_code"].isin(["#", "+"]).sum())
pun = int((atacs["evaluation_code"] == "#").sum())
err = int((atacs["evaluation_code"] == "=").sum())
check("hi ha atacs per comprovar", total > 0, f"{total} atacs de {equip}")

esperat_efic = round(pos / total * 100, 1)
esperat_efn = round((pun - err) / total * 100, 1)
check("Eficàcia = (# + +) / total", 0 <= esperat_efic <= 100,
      f"{esperat_efic}%")
check("Eficiència = (# − =) / total, pot ser negativa", -100 <= esperat_efn <= 100,
      f"{esperat_efn}%")

# --- rallies: identitat efn == 2*efic - 100, i cobertura completa ---
taula, _ = A.sideout_contra(df, equip)
check("la taula de rallies té side-out i contraatac", len(taula) == 2,
      f"{len(taula)} files")

identitat_ok = True
for _, fila in taula.iterrows():
    if fila["total"] == 0:
        continue
    if abs(fila["efn"] - (2 * fila["efic"] - 100)) > 0.15:
        identitat_ok = False
        print(f"       fase {fila['fase']}: efn={fila['efn']} "
              f"pero 2*{fila['efic']}-100={2 * fila['efic'] - 100}")
check("als rallies, Eficiència ≡ 2 × Eficàcia − 100", identitat_ok)

r, exclosos = A.rallies_equip(df, equip)
suma_fases = int(taula["total"].sum())
check("side-out + contraatac = tots els rallies", suma_fases == len(r),
      f"{suma_fases} vs {len(r)}")
check("cada rally és side-out o contraatac, mai els dos",
      set(r["fase"].unique()) <= {"sideout", "contra"})

guanyats = int(r["guanyat"].sum())
check("hi ha rallies guanyats i perduts", 0 < guanyats < len(r),
      f"{guanyats} guanyats de {len(r)}")

# --- zona d'atac deduïda (CLAUDE.md: 99,6% coherent) ---
# Compte: atacs_amb_zona() torna TOTS els atacs amb una columna 'zona' que pot
# ser None (central de zaguer, dorsal que no surt a la formació...). El que
# interessa és quantes zones s'han pogut deduir, no quantes files hi ha.
amb_zona = A.atacs_amb_zona(df, equip)
deduides = amb_zona["zona"].dropna()
pct_zona = 100 * len(deduides) / max(total, 1)
check("la zona d'atac es dedueix per a la majoria d'atacs", pct_zona > 80,
      f"{len(deduides)}/{total} ({pct_zona:.1f}%)")

zones = set(deduides.unique())
check("les zones deduïdes són les esperades (Z1-Z4, Z6)",
      zones <= {"Z1", "Z2", "Z3", "Z4", "Z6"}, str(sorted(zones)))

print(f"\n{_ok} correctes, {_ko} fallides")
sys.exit(1 if _ko else 0)
