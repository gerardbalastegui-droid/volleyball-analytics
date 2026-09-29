# -*- coding: utf-8 -*-
"""Cap text de l'app d'informes es queda sense traduir.

Si una clau de TXT, NOMS o COLS no té les tres llengües, `t()` no peta: torna
la clau o cau a una altra llengua, i la interfície surt barrejada sense que
ningú ho vegi. Aquesta prova ho fa visible.
"""
import os
import sys
import types
import warnings

warnings.filterwarnings("ignore")
ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ARREL, "app_dvw.py")


def check(nom, cond, extra=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {nom} {extra}")


with open(APP, encoding="utf-8") as f:
    src = f.read()
i = src.find("# INTERFÍCIE")
mod = types.ModuleType("app_dvw_pur")
mod.__file__ = APP
exec(compile(src[:src.rfind("# ===", 0, i)], APP, "exec"), mod.__dict__)

llengues = set(mod.IDIOMES)
check("hi ha tres llengües", llengues == {"en", "ca", "de"}, str(sorted(llengues)))
check("la llengua per defecte és una de les disponibles", mod.IDIOMA_DEF in llengues)

falten = {k: sorted(llengues - set(v)) for k, v in mod.TXT.items()
          if llengues - set(v)}
check("totes les claus de TXT tenen les tres llengües", not falten, str(falten))

buides = [(k, l) for k, v in mod.TXT.items() for l, text in v.items() if not text.strip()]
check("cap traducció buida", not buides, str(buides))

# Els {} s'omplen amb .format(): una traducció amb un nombre diferent de forats
# petaria només en aquella llengua.
forats = {k: {l: text.count("{}") for l, text in v.items()}
          for k, v in mod.TXT.items()}
diferents = {k: n for k, n in forats.items() if len(set(n.values())) > 1}
check("les tres llengües tenen els mateixos {}", not diferents, str(diferents))

check("NOMS té les tres llengües i les mateixes accions",
      set(mod.NOMS) == llengues
      and len({frozenset(v) for v in mod.NOMS.values()}) == 1)
check("COLS té les tres llengües",
      all(set(v) == llengues for v in mod.COLS.values()))
