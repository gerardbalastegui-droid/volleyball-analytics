# -*- coding: utf-8 -*-
"""Prova el camí d'escriptura: helpers de token + aplica_canvis simulat."""
import sys
import pandas as pd
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import partits
APP = os.path.join(ARREL, "revisor_dvw.py")
import revisor_dvw as R
t = R.t

def check(nom, got, exp):
    ok = got == exp
    print(f"[{'OK ' if ok else 'FAIL'}] {nom}: {got!r}" + ("" if ok else f"  esperava {exp!r}"))
    return ok

# --- helpers de token (posicions fixes, preserven extres) ---
check("eval simple", R.set_code_eval("*08RT#", "+"), "*08RT+")
check("eval amb extres", R.set_code_eval("*11ST#K1C", "+"), "*11ST+K1C")
check("dorsal", R.set_code_player("*25AH+", 9), "*09AH+")
check("dorsal 2 dig", R.set_code_player("a01ST-", 30), "a30ST-")

# --- aplica_canvis end-to-end sobre el fitxer real ---
f = partits.cami("Demo VC vs Rival D.dvw")
parsed = R.parse_dvw(open(f, "rb").read().decode(R.ENC))

# Localitza les dues línies d'error conegudes (idx = línia-1)
i413, i692 = 412, 691
assert parsed["lines"][i413].split(";")[0] == "*08RT#"
assert parsed["lines"][i692].split(";")[0] == "*25AH+"

cols_base = {
    "_idx": [i413, i692, i413],
    t("col_dorsal"): [8, 25, 8],
    t("col_aval"): ["#", "+", "#"],
}
# fila 0: canvi d'avaluació segur (#->+ recepció, no terminal)
# fila 1: canvi de dorsal 25->9 (9 és a pista a L692: 2,90,11,9,26,4) -> OK
# (repetim idx413 a fila 2 només per comprovar que no peta amb duplicats? no)
base = pd.DataFrame({"_idx": [i413, i692], t("col_dorsal"): [8, 25], t("col_aval"): ["#", "+"]})
edit = pd.DataFrame({"_idx": [i413, i692], t("col_dorsal"): [8, 9],   t("col_aval"): ["+", "+"]})

canvis, ignorats = R.aplica_canvis(parsed, base, edit)
print(f"\naplica_canvis: {canvis} canvis, {len(ignorats)} ignorats")
for m in ignorats:
    print("  ignorat:", m)
check("L413 avaluació #->+", parsed["lines"][i413].split(";")[0], "*08RT+")
check("L692 dorsal 25->9",   parsed["lines"][i692].split(";")[0], "*09AH+")
check("num canvis", canvis, 2)

# la resta de la línia intacta?
orig_parsed = R.parse_dvw(open(f, "rb").read().decode(R.ENC))
orig_fields = orig_parsed["lines"][i413].split(";")
now_fields = parsed["lines"][i413].split(";")
check("resta de camps L413 intacta", now_fields[1:], orig_fields[1:])

# --- prova de bloqueig: avaluació terminal ---
parsed2 = R.parse_dvw(open(f, "rb").read().decode(R.ENC))
# busca un atac amb # (kill, terminal)
idx_kill = next(d["idx"] for d in parsed2["scout"]
                if d["kind"] == "skill" and d["skill"] == "A" and d["eval"] == "#")
base2 = pd.DataFrame({"_idx": [idx_kill], t("col_dorsal"): [0], t("col_aval"): ["#"]})
edit2 = pd.DataFrame({"_idx": [idx_kill], t("col_dorsal"): [0], t("col_aval"): ["+"]})
c2, ig2 = R.aplica_canvis(parsed2, base2, edit2)
check("canvi terminal bloquejat (0 canvis)", c2, 0)
check("terminal genera avís", len(ig2), 1)

# --- prova de bloqueig: dorsal fora de pista i no líbero ---
parsed3 = R.parse_dvw(open(f, "rb").read().decode(R.ENC))
base3 = pd.DataFrame({"_idx": [i692], t("col_dorsal"): [25], t("col_aval"): ["+"]})
edit3 = pd.DataFrame({"_idx": [i692], t("col_dorsal"): [7], t("col_aval"): ["+"]})  # 7 no és a pista home
c3, ig3 = R.aplica_canvis(parsed3, base3, edit3)
check("dorsal fora de pista bloquejat", c3, 0)
print("  ", ig3)
