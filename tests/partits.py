# -*- coding: utf-8 -*-
"""On són els .dvw de proves.

`Partits/` està organitzada per `<temporada>/<club>/<equip>/`, o sigui que cap prova
pot llistar-la amb un `listdir` pla ni construir camins a mà. Es resol aquí i
tothom els agafa d'aquí: si algun dia canvia l'arbre, només es toca aquest
arxiu.
"""
import os

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTITS = os.path.join(ARREL, "Partits")


def camins():
    """Tots els .dvw de Partits/ (a qualsevol subcarpeta), ordenats per nom."""
    out = []
    for arrel, _dirs, noms in os.walk(PARTITS):
        out += [os.path.join(arrel, n) for n in noms
                if n.lower().endswith(".dvw")]
    return sorted(out, key=os.path.basename)


def cami(nom):
    """El camí d'un partit concret pel seu nom d'arxiu."""
    for c in camins():
        if os.path.basename(c) == nom:
            return c
    raise FileNotFoundError(f"no trobo {nom} dins de {PARTITS}")
