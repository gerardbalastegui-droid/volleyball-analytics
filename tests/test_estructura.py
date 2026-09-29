# -*- coding: utf-8 -*-
"""Motor d'inserir/esborrar: context copiat, validació de coherència, ids
estables i que la resta del fitxer no es toca."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import partits
APP = os.path.join(ARREL, "revisor_dvw.py")
import revisor_dvw as R

F = partits.cami("Demo VC vs Rival D.dvw")
TEXT = open(F, "rb").read().decode(R.ENC)
REF = 691          # L692 = *25AH+


def check(nom, ok, extra=""):
    print(f"[{'OK ' if ok else 'FAIL'}] {nom} {extra}")


p0 = R.parse_dvw(TEXT)
print("línia de referència:", p0["lines"][REF].split(";")[0])
win = R.guanyador_rally(p0, REF)
print("guanyador del rally:", win, "(equip de la referència: *)")

# --- construcció de la línia nova ---
codi = R.construeix_codi("*", 9, "A", "#")
check("codi construït", codi == "*09AH#", codi)
nova = R.construeix_linia(p0["lines"][REF], codi)
f_nova, f_ref = nova.split(";"), p0["lines"][REF].split(";")
check("context copiat del veí", f_nova[7:] == f_ref[7:])
check("camps 1-6 buits", all(x == "" for x in f_nova[1:7]), str(f_nova[1:7]))

# --- validació de coherència amb el guanyador ---
perdedor = "a" if win == "*" else "*"
ok_g, _ = R.valida_accio(p0, REF, win, 11 if win == "*" else 1, "A", "#")
ok_p, motiu_p = R.valida_accio(p0, REF, perdedor, 1 if perdedor == "a" else 11, "A", "#")
check("punt per al guanyador: permès", ok_g)
check("punt per al perdedor: rebutjat", not ok_p, motiu_p)
ok_d, motiu_d = R.valida_accio(p0, REF, "*", 77, "A", "+")
check("dorsal fora de pista: rebutjat", not ok_d, motiu_d)
ok_nt, _ = R.valida_accio(p0, REF, perdedor, 1 if perdedor == "a" else 11, "A", "+")
check("marca NO terminal: sempre permesa", ok_nt)

# --- aplicar operacions ---
ops = [{"tipus": "insereix", "ref": REF, "on": "despres",
        "linia": nova, "id": "n0", "desc": ""}]
p1, ids = R.aplica_operacions(TEXT, ops)
check("una línia més", len(p1["lines"]) == len(p0["lines"]) + 1)
check("la nova és a la posició següent", p1["lines"][REF + 1].split(";")[0] == codi)
check("id estable de la nova", ids[REF + 1] == "n0")
check("la referència no s'ha mogut", p1["lines"][REF] == p0["lines"][REF])
resta_igual = (p1["lines"][:REF + 1] == p0["lines"][:REF + 1]
               and p1["lines"][REF + 2:] == p0["lines"][REF + 1:])
check("la resta del fitxer intacta", resta_igual)

# la nova línia es parseja com a acció?
d_nova = {x["idx"]: x for x in p1["scout"]}.get(REF + 1)
check("la nova es llegeix com a acció", d_nova is not None and d_nova["kind"] == "skill"
      and d_nova["player"] == "09" and d_nova["skill"] == "A" and d_nova["eval"] == "#",
      str(d_nova and (d_nova["kind"], d_nova["player"], d_nova["skill"], d_nova["eval"])))

# --- esborrar ---
ops2 = [{"tipus": "esborra", "ref": REF, "desc": ""}]
p2, ids2 = R.aplica_operacions(TEXT, ops2)
check("una línia menys", len(p2["lines"]) == len(p0["lines"]) - 1)
check("la línia esborrada ja no hi és", p2["lines"][REF].split(";")[0] != "*25AH+")

# --- insert + delete combinats, i ids coherents ---
ops3 = ops + ops2
p3, ids3 = R.aplica_operacions(TEXT, ops3)
check("insert+delete: mateix nombre de línies", len(p3["lines"]) == len(p0["lines"]))
check("la nova sobreviu a l'esborrat de la referència", "n0" in ids3)

# --- sense operacions: round-trip intacte ---
p4, ids4 = R.aplica_operacions(TEXT, [])
check("sense ops: round-trip lossless", R.rebuild(p4).encode(R.ENC) == open(F, "rb").read())
check("sense ops: ids = índexs", ids4 == list(range(len(p4["lines"]))))
