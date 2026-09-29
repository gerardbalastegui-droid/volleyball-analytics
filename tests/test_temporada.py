# -*- coding: utf-8 -*-
"""Data del partit i ordre cronològic, sobre els 14 partits reals.

L'ordre de temporada és una invariant silenciosa: si la data es llegeix
malament, el desglossament per partit i l'evolució surten ordenats de
qualsevol manera i les taules continuen semblant correctes. Per això es
comprova aquí i no a ull.

  1. Els 14 partits porten data a [3MATCH], i cauen dins de la temporada.
  2. ordena_per_data() deixa la llista en ordre estrictament creixent, i els
     partits sense data van al final conservant l'ordre de pujada.
  3. La tendència compara les dues meitats de la sèrie i ignora els forats.
"""
import os
import sys
import types
import datetime
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ARREL, "app_dvw.py")
sys.path.insert(0, ARREL)

import partits
PARTITS = partits.PARTITS

_ok = _ko = 0


def check(nom, cond, extra=""):
    global _ok, _ko
    if cond:
        _ok += 1
    else:
        _ko += 1
    print(f"[{'OK ' if cond else 'FAIL'}] {nom} {extra}")


def carrega_app_sense_ui():
    """Igual que a test_metriques.py: executa app_dvw.py fins al banner de la
    interfície, que llegeix st.session_state i peta fora de Streamlit."""
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
check("app_dvw exposa la lectura de data i l'ordre",
      all(hasattr(A, f) for f in ("data_partit", "ordena_per_data",
                                  "_tendencia", "_data_curta")))

fitxers = []
for c in partits.camins():
    with open(c, "rb") as f:
        fitxers.append((os.path.basename(c), f.read()))
check("hi ha partits per provar", len(fitxers) > 0, f"{len(fitxers)} arxius")

# ---------------------------------------------------------------------------
# 1. Tots els partits porten data, i és plausible
# ---------------------------------------------------------------------------
dates = [(n, A.data_partit(b)) for n, b in fitxers]
sense = [n for n, d in dates if d is None]
check("tots els partits porten data a [3MATCH]", not sense,
      f"{len(dates) - len(sense)}/{len(dates)}"
      + (f" — sense data: {sense}" if sense else ""))

totes = [d for _, d in dates if d]
check("les dates són datetime.date", all(isinstance(d, datetime.date) for d in totes))
check("cap data és al futur llunyà ni abans del 2000",
      all(datetime.date(2000, 1, 1) < d < datetime.date(2100, 1, 1) for d in totes))

# Una temporada de volei va de tardor a primavera: si totes caiguessin al
# mateix mes voldria dir que s'està llegint un camp fix i no la data real.
check("les dates cobreixen mesos diferents (no és un camp fix)",
      len({d.month for d in totes}) > 1,
      f"{len({d.month for d in totes})} mesos, {len(set(totes))} dates diferents")

# ---------------------------------------------------------------------------
# 2. L'ordre cronològic
# ---------------------------------------------------------------------------
ordenats = A.ordena_per_data(fitxers)
check("ordena_per_data no perd ni duplica arxius",
      sorted(n for n, _ in ordenats) == sorted(n for n, _ in fitxers),
      f"{len(ordenats)} de {len(fitxers)}")

seq = [A.data_partit(b) for _, b in ordenats]
creixent = all(a <= b for a, b in zip(seq, seq[1:]) if a and b)
check("la llista queda en ordre de calendari", creixent,
      f"{A._data_curta(seq[0], anys=True)} → {A._data_curta(seq[-1], anys=True)}")

# El nom d'arxiu NO serveix per ordenar: "Demo VC vs Rival I" (06/11/22) va
# després de "Demo VC vs Rival H" (15/01/23) alfabèticament. Aquesta prova falla si
# algú torna a confiar en l'ordre de pujada.
check("l'ordre per data no coincideix amb l'alfabètic (calia ordenar)",
      [n for n, _ in ordenats] != [n for n, _ in fitxers])

# Un partit sense data ha d'anar al final, no petar ni colar-se al principi
fals = [("zzz sense data.dvw", b"[3MATCH]\n;;;;\n[3SET]\n")] + fitxers
ord_fals = A.ordena_per_data(fals)
check("els partits sense data van al final",
      ord_fals[-1][0] == "zzz sense data.dvw")

# ---------------------------------------------------------------------------
# 3. La tendència
# ---------------------------------------------------------------------------
check("tendència: sèrie curta no en té", A._tendencia([10.0, 20.0]) is None)
check("tendència: millora clara és positiva",
      A._tendencia([10.0, 10.0, 20.0, 20.0]) == 10.0)
check("tendència: empitjorament clar és negatiu",
      A._tendencia([20.0, 20.0, 10.0, 10.0]) == -10.0)
check("tendència: sèrie plana és zero",
      A._tendencia([15.0, 15.0, 15.0, 15.0]) == 0.0)
check("tendència: els forats (None) no compten",
      A._tendencia([10.0, None, 20.0, 20.0]) == 10.0)
check("tendència: una meitat buida no dóna número",
      A._tendencia([None, None, 20.0, 20.0]) is None)
# Senar: el tall va a len//2, o sigui que el partit del mig cau a la segona
# meitat. Amb 5 partits, 2 contra 3.
check("tendència: amb sèrie senar el partit del mig va a la segona meitat",
      A._tendencia([10.0, 10.0, 20.0, 20.0, 20.0]) == 10.0)

# El color de la tendència és el semàfor de sempre amb objectiu 0: la franja
# ambre evita que un +0.2 (temporada plana) es pinti de verd com si millorés.
check("color: una tendència clarament amunt és verda",
      A.color_semafor(5.0, 0) == A.C_VERD)
check("color: una tendència clarament avall és roja",
      A.color_semafor(-5.0, 0) == A.C_ROIG)
check("color: una temporada plana és ambre", A.color_semafor(0.2, 0) == A.C_AMBRE)
check("color: el marge ambre arriba just fins a ±2.5",
      A.color_semafor(2.5, 0) == A.C_AMBRE and A.color_semafor(-2.5, 0) == A.C_AMBRE
      and A.color_semafor(2.6, 0) == A.C_VERD and A.color_semafor(-2.6, 0) == A.C_ROIG)

# ---------------------------------------------------------------------------
# 4. Carpeta Partits/: l'arbre <temporada>/<club>/<equip>/
#    D'aquí surten els desplegables de "Carregar Partits". Que l'equip sigui
#    una carpeta no és cosmètic: l'app exigeix un equip comú a tots els arxius
#    carregats, o sigui que barrejar dos clubs petaria. I el club és un
#    nivell a part perquè d'un mateix club en porto més d'un equip: sense ell,
#    triar el club carregaria el femení i el masculí alhora.
# ---------------------------------------------------------------------------
temporades = A.subcarpetes(PARTITS)
check("hi ha temporades a Partits/", bool(temporades), str(temporades))
check("les temporades tenen forma d'aa-aa",
      all(len(x) == 5 and x[2] == "-" for x in temporades), str(temporades))
check("les temporades surten ordenades (la darrera va primer a l'app)",
      temporades == sorted(temporades), str(temporades))

clubs = {temp: A.subcarpetes(os.path.join(PARTITS, temp)) for temp in temporades}
check("cada temporada té almenys una carpeta de club",
      all(clubs.values()), str(clubs))

# Un club sense cap carpeta d'equip NO és un error: és el club amb qui encara no
# he jugat aquesta temporada. L'app hi obre el desplegable
# per defecte a un altre que sí tingui partits.
equips = {(temp, cl): A.subcarpetes(os.path.join(PARTITS, temp, cl))
          for temp in temporades for cl in clubs[temp]}

# Tots els .dvw han de quedar dins d'una carpeta d'equip: un partit deixat solt
# a Partits/, a <temporada>/ o a <temporada>/<club>/ no sortiria a cap
# desplegable. Aquesta és la prova que hauria cantat la migració a mitges.
per_equip = {}
for (temp, cl), eqs in equips.items():
    for eq in eqs:
        per_equip[(temp, cl, eq)] = A.escaneja_carpeta(
            os.path.join(PARTITS, temp, cl, eq))
check("tots els partits són dins d'una carpeta d'equip",
      sum(len(v) for v in per_equip.values()) == len(fitxers),
      f"{sum(len(v) for v in per_equip.values())} de {len(fitxers)}")

def equips_de(b):
    """Els dos equips de la secció [3TEAMS], sense parsejar l'arxiu sencer."""
    raw = b.decode("latin-1", errors="ignore")
    j = raw.find("[3TEAMS]")
    noms = set()
    for linia in raw[j:].splitlines()[1:3] if j >= 0 else []:
        parts = linia.split(";")
        if len(parts) > 1 and parts[1].strip():
            noms.add(parts[1].strip())
    return noms


# Un cop triada la carpeta, l'equip és el mateix a tots els arxius: si no,
# l'app avisaria de "cap equip comú" just després de carregar.
for (temp, cl, eq), fs in per_equip.items():
    if not fs:
        continue
    check(f"{temp}/{cl}/{eq}: els arxius comparteixen un equip",
          bool(set.intersection(*[equips_de(b) for _, b in fs])),
          f"{len(fs)} arxius")

# Una carpeta que no existeix no ha de petar: el desplegable es queda buit.
check("una carpeta inexistent no peta",
      A.subcarpetes(os.path.join(PARTITS, "no-hi-es")) == [])

print(f"\n{_ok} correctes, {_ko} fallides")
sys.exit(1 if _ko else 0)
