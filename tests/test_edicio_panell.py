# -*- coding: utf-8 -*-
"""Edició de línies des del panell: també les que no tenen cap error, i també
marques terminals (que a la taula estan bloquejades)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import partits
APP = os.path.join(ARREL, "revisor_dvw.py")
import revisor_dvw as R
from streamlit.testing.v1 import AppTest

F = partits.cami("Demo VC vs Rival D.dvw")
TEXT = open(F, "rb").read().decode(R.ENC)


def check(nom, ok, extra=""):
    print(f"[{'OK ' if ok else 'FAIL'}] {nom} {extra}")


# ---------- nivell funció: operació d'edició ----------
p0 = R.parse_dvw(TEXT)
# busca una acció SENSE cap error (una recepció normal) i una de terminal
idx_ok = next(d["idx"] for d in p0["scout"]
              if d["kind"] == "skill" and d["skill"] == "R" and d["eval"] == "+")
idx_term = next(d["idx"] for d in p0["scout"]
                if d["kind"] == "skill" and d["skill"] == "A" and d["eval"] == "#")
print("acció sense error :", p0["lines"][idx_ok].split(";")[0], f"(L{idx_ok+1})")
print("acció terminal    :", p0["lines"][idx_term].split(";")[0], f"(L{idx_term+1})")

ops = [{"tipus": "edita", "ref": idx_ok, "codi": "*05RT!", "desc": ""}]
p1, ids = R.aplica_operacions(TEXT, ops)
check("edita el token", p1["lines"][idx_ok].split(";")[0] == "*05RT!",
      p1["lines"][idx_ok].split(";")[0])
check("context intacte",
      p1["lines"][idx_ok].split(";")[1:] == p0["lines"][idx_ok].split(";")[1:])
check("mateix nombre de línies", len(p1["lines"]) == len(p0["lines"]))
check("cap altra línia tocada",
      [l for i, l in enumerate(p1["lines"]) if i != idx_ok]
      == [l for i, l in enumerate(p0["lines"]) if i != idx_ok])

# guarda del guanyador en EDITAR una terminal
d_term = {x["idx"]: x for x in p0["scout"]}[idx_term]
win = R.guanyador_rally(p0, idx_term)
check("el kill és de qui guanya el rally", d_term["team"] == win)
perd = "a" if win == "*" else "*"
ok1, _ = R.valida_accio(p0, idx_term, d_term["team"], int(d_term["player"]), "A", "=")
check("kill -> error del mateix equip: rebutjat", not ok1)
ok2, _ = R.valida_accio(p0, idx_term, d_term["team"], int(d_term["player"]), "A", "+")
check("kill -> marca no terminal: permès", ok2)

# ---------- nivell UI ----------
at = AppTest.from_file(APP, default_timeout=120)
at.run()
at.get("file_uploader")[0].upload("f.dvw", open(F, "rb").read())
at.run()


def boto(a, et):
    return next((b for b in a.get("button") if b.label == et), None)


def taula(a):
    for e in (a.get("data_editor") or a.get("dataframe")):
        v = getattr(e, "value", None)
        if v is not None and hasattr(v, "columns") and "Zona" in list(v.columns):
            return v


# 1) editar una línia de MARCADOR ha d'estar prohibit
idx_pt = next(d["idx"] for d in p0["scout"] if d["kind"] == "point")
at.session_state["ins_linia_val"] = idx_pt + 1
at.run()
at.get("radio")[0].set_value("Editar aquesta línia")
at.run()
infos = [i.value for i in at.get("info")]
check("editar una línia de marcador: bloquejat",
      any("línies d'acció" in i for i in infos), str(infos))

# 2) editar una acció normal (sense error)
at.session_state["ins_linia_val"] = idx_ok + 1
at.run()
at.get("radio")[0].set_value("Editar aquesta línia")
at.run()
caps = [c.value for c in at.get("caption")]
check("pre-omple amb el codi actual",
      any(p0["lines"][idx_ok].split(";")[0] in c for c in caps), str(caps[-1:]))
# canvia la marca de + a !
for s in at.get("selectbox"):
    if "!" in (s.options or []) and "#" in (s.options or []):
        s.set_value("!")
at.run()
boto(at, "Desar el canvi").click()
at.run()
check("edició acceptada", not at.get("error"), str([e.value for e in at.get("error")]))
tbl = taula(at)
fila = tbl[tbl["Línia"] == idx_ok + 1][["Dorsal", "Aval."]].to_dict("records")
check("la taula reflecteix la marca nova", fila and fila[0]["Aval."] == "!", str(fila))

# 3) desar
boto(at, "Desar còpia corregida").click()
at.run()
check("desa amb l'edició", len(at.get("download_button")) == 1,
      str([s.value for s in at.get("success")]))
