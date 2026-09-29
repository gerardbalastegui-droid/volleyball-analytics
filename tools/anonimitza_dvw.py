# -*- coding: utf-8 -*-
"""Anonimitza una carpeta de .dvw perquè es puguin publicar.

    python tools/anonimitza_dvw.py <carpeta_origen> <carpeta_desti>

Els .dvw de Partits/ d'aquest repositori han passat per aquí. Només es toquen
les capçaleres: les jugades ([3SCOUT]) no porten noms, només codis, hores i
dorsals, així que les estadístiques surten idèntiques abans i després.

Què canvia:
  - Jugadors: pseudònim estable a tota la carpeta (el mateix jugador és el
    mateix pseudònim a tots els partits), perquè l'acumulat de temporada no
    varii. L'equip comú rep l'alfabet OTAN; els rivals, "Opp A01", "Opp A02"...
  - Equips: l'equip comú passa a "Demo VC" i els rivals a "Rival A", "Rival
    B"..., per ordre alfabètic del nom original (no cronològic).
  - Fora: entrenadors, àrbitres, ciutat, pavelló, lliga, llicència de
    DataVolley i el camp numèric de [3MORE].
  - Dates: totes desplaçades DESPLACAMENT dies, també les que no es veuen (la
    de [3MATCH] en format sèrie d'Excel i les de GENERATOR/LASTCHANGE). Com que
    és un múltiple de 7, es conserven l'ordre, els intervals i el dia de la
    setmana.

Cada camp de text té una còpia "mirall" codificada: \\x0f + "2" + el text en
hexadecimal. Si només es canviés el text, el nom continuaria a la còpia. Per
això els miralls es regeneren a partir del text nou, i al final es busquen
tots els valors originals, en text i en hexadecimal, dins dels arxius nous.
Si en surt un, l'script falla sense escriure res.

La taula d'equivalències no es desa enlloc: amb aquest script i els arxius
publicats no es pot tornar enrere.
"""
import datetime
import os
import re
import sys

DESPLACAMENT = -1092          # 156 setmanes exactes
ANYS = 3                      # el que es resta a l'etiqueta de temporada
EQUIP_DEMO = "Demo VC"
CODI_DEMO = "DVC"
LLIGA = "Demo League"
OTAN = ["Alfa", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf",
        "Hotel", "India", "Juliett", "Kilo", "Lima", "Mike", "November",
        "Oscar", "Papa", "Quebec", "Romeo", "Sierra", "Tango", "Uniform",
        "Victor", "Whiskey", "Xray", "Yankee", "Zulu"]

MIRALL = "\x0f"
EXCEL_0 = datetime.date(1899, 12, 30)


def enc(text):
    """El mirall codificat que DataVolley desa al costat de cada text."""
    return MIRALL + "2" + text.encode("cp1252").hex().upper()


def _com_original(original, nou):
    """Mirall si el camp original era mirall; text pla si no."""
    return enc(nou) if original.startswith(MIRALL) else nou


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

def seccions(text):
    """{nom: [línies amb el seu salt]} en l'ordre de l'arxiu."""
    out, actual = {}, None
    for linia in text.splitlines(keepends=True):
        m = re.match(r"\[(3[A-Z\-]+)\]", linia)
        if m:
            actual = m.group(1)
            out[actual] = [linia]
        elif actual:
            out[actual].append(linia)
    return out


def _camps(linia):
    cos = linia.rstrip("\r\n")
    return cos.split(";"), linia[len(cos):]


def _junta(camps, salt):
    return ";".join(camps) + salt


def llegeix(cami):
    with open(cami, "rb") as f:
        return f.read().decode("latin-1")


def equips(sec):
    return [_camps(l)[0][1] for l in sec["3TEAMS"][1:3]]


def jugadors(sec, idx_equip):
    nom_sec = "3PLAYERS-H" if idx_equip == 0 else "3PLAYERS-V"
    out = []
    for l in sec[nom_sec][1:]:
        c, _ = _camps(l)
        if len(c) > 10 and c[1].strip():
            out.append((int(c[1]), c[9], c[10]))
    return out


# ---------------------------------------------------------------------------
# Equivalències
# ---------------------------------------------------------------------------

def equivalencies(arxius):
    noms_equips = [equips(sec) for _, sec in arxius]
    comuns = set(noms_equips[0]).intersection(*map(set, noms_equips[1:]))
    if len(comuns) != 1:
        sys.exit(f"cal exactament un equip comú a tots els arxius, n'hi ha {len(comuns)}")
    comu = comuns.pop()

    rivals = sorted({n for ns in noms_equips for n in ns if n != comu})
    if len(rivals) > 26:
        sys.exit("massa rivals per a les lletres A-Z")
    lletra = {r: chr(ord("A") + i) for i, r in enumerate(rivals)}
    eq = {comu: (EQUIP_DEMO, CODI_DEMO)}
    eq.update({r: (f"Rival {lletra[r]}", f"RV{lletra[r]}") for r in rivals})

    # Jugadors: per equip, ordenats pel primer dorsal amb què surten.
    vistos = {}
    for (_, sec), ns in zip(arxius, noms_equips):
        for i, equip in enumerate(ns):
            for dorsal, cognom, nom in jugadors(sec, i):
                clau = (equip, cognom, nom)
                vistos[clau] = min(vistos.get(clau, dorsal), dorsal)
    jug = {}
    for equip in [comu] + rivals:
        claus = sorted((k for k in vistos if k[0] == equip),
                       key=lambda k: (vistos[k], k[1], k[2]))
        for n, k in enumerate(claus):
            if equip == comu:
                if n >= len(OTAN):
                    sys.exit("massa jugadors a l'equip comú per a l'alfabet OTAN")
                jug[k] = (OTAN[n], f"P{n + 1:02d}")
            else:
                l = lletra[equip]
                jug[k] = (f"Opp {l}{n + 1:02d}", f"{l}{n + 1:02d}")
    return comu, eq, jug


# ---------------------------------------------------------------------------
# Reescriptura
# ---------------------------------------------------------------------------

def _data(dmy):
    d = datetime.datetime.strptime(dmy, "%d/%m/%Y").date()
    return (d + datetime.timedelta(days=DESPLACAMENT)).strftime("%d/%m/%Y")


def _temporada(t):
    return re.sub(r"\d{4}", lambda m: str(int(m.group()) - ANYS), t)


def anonimitza(sec, eq, jug, sensibles):
    """Reescriu les capçaleres de `sec` in situ i apunta a `sensibles` tot el
    que s'ha tret, per buscar-ho després als arxius nous."""
    noms = equips(sec)

    # [3DATAVOLLEYSCOUT]: les dates de creació i de l'últim canvi
    for i, l in enumerate(sec["3DATAVOLLEYSCOUT"]):
        m = re.match(r"((?:GENERATOR|LASTCHANGE)-DAY: )(\d\d/\d\d/\d{4})(.*)", l, re.S)
        if m:
            sensibles.add(m.group(2))
            sec["3DATAVOLLEYSCOUT"][i] = m.group(1) + _data(m.group(2)) + m.group(3)

    # [3MATCH]: data, temporada, lliga (+ mirall), data sèrie i llicència
    c, s = _camps(sec["3MATCH"][1])
    sensibles.update(v for v in (c[0], c[3]) if v)
    c[0], c[2] = _data(c[0]), _temporada(c[2])
    c[12] = _com_original(c[12], LLIGA) if len(c) > 12 and c[12] else c[12]
    c[3] = LLIGA
    sec["3MATCH"][1] = _junta(c, s)
    if len(sec["3MATCH"]) > 2:
        c, s = _camps(sec["3MATCH"][2])
        if len(c) > 2 and c[2].isdigit():
            c[2] = str(int(c[2]) + DESPLACAMENT)
        if len(c) > 9 and c[9]:
            sensibles.add(c[9])
            c[9] = ""
        sec["3MATCH"][2] = _junta(c, s)

    # [3TEAMS]: codi, nom, entrenadors i els seus miralls
    for i in (1, 2):
        c, s = _camps(sec["3TEAMS"][i])
        nom, codi = eq[c[1]]
        sensibles.update(v for v in (c[1], c[3], c[4]) if len(v) > 2)
        c[0], c[1], c[3], c[4] = codi, nom, "", ""
        for k, v in ((6, nom), (7, ""), (8, "")):
            if len(c) > k and c[k]:
                c[k] = _com_original(c[k], v)
        sec["3TEAMS"][i] = _junta(c, s)

    # [3MORE]: àrbitres, ciutat, pavelló i el camp numèric de la segona línia
    if len(sec.get("3MORE", [])) > 1:
        c, s = _camps(sec["3MORE"][1])
        sensibles.update(v for k, v in enumerate(c) if k in (0, 3, 4) and len(v) > 2)
        for k in (0, 3, 4):
            if len(c) > k:
                c[k] = ""
        for k in (6, 7, 8):
            if len(c) > k and c[k]:
                c[k] = _com_original(c[k], "")
        sec["3MORE"][1] = _junta(c, s)
    if len(sec.get("3MORE", [])) > 2:
        c, s = _camps(sec["3MORE"][2])
        if c[0]:
            sensibles.add(c[0])
            c[0] = ""
        sec["3MORE"][2] = _junta(c, s)

    # [3COMMENTS] i [3VIDEO]: fora qualsevol text lliure
    for nom_sec in ("3COMMENTS", "3VIDEO"):
        for i in range(1, len(sec.get(nom_sec, []))):
            cos = sec[nom_sec][i].rstrip("\r\n")
            if cos and cos != "no comments":
                sensibles.add(cos)
                sec[nom_sec][i] = sec[nom_sec][i][len(cos):]

    # [3PLAYERS-H] / [3PLAYERS-V]
    for idx, nom_sec in ((0, "3PLAYERS-H"), (1, "3PLAYERS-V")):
        for i in range(1, len(sec[nom_sec])):
            c, s = _camps(sec[nom_sec][i])
            if len(c) <= 10 or not c[1].strip():
                continue
            pseudonim, codi = jug[(noms[idx], c[9], c[10])]
            sensibles.update(v for v in (c[8], c[9], c[10], c[11]) if len(v) > 2)
            c[8], c[9], c[10], c[11] = codi, pseudonim, "", ""
            if len(c) > 17 and c[17]:
                c[17] = _com_original(c[17], pseudonim)
            if len(c) > 18:
                c[18] = ""
            sec[nom_sec][i] = _junta(c, s)


def nom_arxiu(rival, n):
    return f"{EQUIP_DEMO} vs {rival}{'' if n == 1 else f' {n}'}.dvw"


def main(origen, desti):
    camins = sorted(os.path.join(a, n) for a, _, ns in os.walk(origen)
                    for n in ns if n.lower().endswith(".dvw"))
    if not camins:
        sys.exit(f"no hi ha cap .dvw a {origen}")
    arxius = [(c, seccions(llegeix(c))) for c in camins]
    comu, eq, jug = equivalencies(arxius)

    # El nom nou porta el rival i, si s'hi ha jugat més d'un cop, l'ordinal
    # cronològic. Sense data al davant, a propòsit: l'ordre alfabètic no ha
    # de coincidir amb el de calendari (test_temporada ho comprova).
    def data_de(sec):
        return datetime.datetime.strptime(_camps(sec["3MATCH"][1])[0][0], "%d/%m/%Y")
    ordre = sorted(arxius, key=lambda a: data_de(a[1]))
    comptador, noms_nous = {}, {}
    for cami, sec in ordre:
        rival = eq[[n for n in equips(sec) if n != comu][0]][0]
        comptador[rival] = comptador.get(rival, 0) + 1
        noms_nous[cami] = nom_arxiu(rival, comptador[rival])

    sensibles = set()
    sortida = {}
    for cami, sec in arxius:
        anonimitza(sec, eq, jug, sensibles)
        sortida[noms_nous[cami]] = "".join("".join(ls) for ls in sec.values())

    # Comprovació final: cap valor original, ni en text ni com a mirall.
    agulles = set()
    for v in sensibles:
        agulles.add(v)
        agulles.add(v.encode("cp1252", "replace").hex().upper())
    trobats = [(nom, a) for nom, t in sortida.items() for a in agulles
               if len(a) > 2 and a in t]
    if trobats:
        sys.exit(f"queden {len(trobats)} valors originals als arxius nous: no s'escriu res")

    os.makedirs(desti, exist_ok=True)
    for nom, text in sortida.items():
        with open(os.path.join(desti, nom), "wb") as f:
            f.write(text.encode("latin-1"))

    for cami in camins:
        print(f"  {os.path.basename(cami)}  ->  {noms_nous[cami]}")
    print(f"\n{len(sortida)} arxius anonimitzats a {desti}")
    print(f"{len(sensibles)} valors retirats; cap no apareix als arxius nous")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
