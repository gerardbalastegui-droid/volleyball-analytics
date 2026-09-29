# -*- coding: utf-8 -*-
"""Revisor .dvw — linter + editor segur d'scouts de DataVolley.

Eina LOCAL i autònoma (companya de app_dvw.py, però sense dependre'n):
llegeix un .dvw, descodifica el scout a una taula llegible, marca els errors
probables (linter) i permet corregir els edits SEGURS (dorsal i avaluació no
terminal) reescrivint el fitxer de forma quirúrgica. Mai toca l'original:
sempre desa una còpia nova.

Execució:  python -m streamlit run revisor_dvw.py

El fitxer es llegeix i s'escriu en latin-1 (cp1252-safe, round-trip byte a byte
per a tot el que no editem: els .dvw porten accents en la codificació antiga i
noms hex que no s'han de tocar).
"""

import hashlib
import os

import pandas as pd
import streamlit as st

# ===========================================================================
# CONSTANTS DE FORMAT .dvw
# ===========================================================================
ENC = "latin-1"                 # round-trip byte a byte
SCOUT_HEADER = "[3SCOUT]"

# Índexs de camp dins una línia d'scout (separada per ';')
F_CODE, F_TIME, F_SET = 0, 7, 8
F_SETTER_H, F_SETTER_V = 9, 10   # setter_position (rotació) local / visitant
F_LINEUP_H = 14                  # local: camps 14..19 = posicions 1..6
F_LINEUP_V = 20                  # visitant: camps 20..25 = posicions 1..6

# Gest = lletra després del dorsal. Noms bilingües.
SKILL_LETTER = {
    "S": "saque", "R": "recepción", "A": "atacar",
    "B": "bloqueo", "D": "defensa", "E": "colocación", "F": "freeball",
}
NOM_GEST = {
    "saque": {"ca": "Saque", "de": "Aufschlag"},
    "recepción": {"ca": "Recepció", "de": "Annahme"},
    "atacar": {"ca": "Atac", "de": "Angriff"},
    "bloqueo": {"ca": "Bloqueig", "de": "Block"},
    "defensa": {"ca": "Defensa", "de": "Abwehr"},
    "colocación": {"ca": "Col·locació", "de": "Zuspiel"},
    "freeball": {"ca": "Free-ball", "de": "Freeball"},
}
MARQUES = ["#", "+", "!", "-", "/", "="]

# Marques TERMINALS per gest: tanquen el rally (canvien marcador i rotació).
# Editar-les = edit estructural → fora de l'abast segur del v1.
TERMINAL = {
    "S": {"#", "="},          # ace / error
    "R": {"="},               # error de recepció (punt per qui saca)
    "A": {"#", "=", "/"},     # kill / error / bloquejat
    "B": {"#", "=", "/"},     # bloqueig-punt / error / pilota fora del bloc
    "D": {"="},               # error de defensa
    "E": {"="},               # error de col·locació
    "F": {"="},
}
# Marca terminal que dóna el punt a QUI la fa (la resta el dóna al rival).
MARCA_PUNT = "#"

# Gests que pot fer el líbero (no ataca, no bloqueja, no saca).
LIBERO_SKILLS = {"R", "D", "E", "F"}

# Segona lletra del codi (tipus) per gest. Els valors surten dels meus scouts:
# AH 3090, ST 1899, RT 1732, BH 916, DH 285, FH 267.
TIPUS_DEFECTE = {"A": "H", "S": "T", "R": "T", "B": "H",
                 "D": "H", "F": "H", "E": "H"}

# ===========================================================================
# IDIOMES
# ===========================================================================
IDIOMA_DEF = "ca"

TXT = {
    "titol": {"ca": "Revisor .dvw", "de": ".dvw-Prüfer"},
    "subtitol": {"ca": "Puja un .dvw per revisar-lo i corregir errors del scout.",
                 "de": "Lade eine .dvw hoch, um Scoutfehler zu prüfen und zu korrigieren."},
    "uploader": {"ca": "Arxiu DataVolley (.dvw)", "de": "DataVolley-Datei (.dvw)"},
    "sense_arxiu": {"ca": "Cap arxiu carregat.", "de": "Keine Datei geladen."},
    "error_llegir": {"ca": "No s'ha pogut llegir l'arxiu: {}",
                     "de": "Datei konnte nicht gelesen werden: {}"},
    "idioma": {"ca": "Idioma", "de": "Sprache"},
    "partit": {"ca": "Partit", "de": "Spiel"},
    "sec_revisio": {"ca": "Revisió automàtica", "de": "Automatische Prüfung"},
    "sec_editor": {"ca": "Editor del scout", "de": "Scout-Editor"},
    "cap_error": {"ca": "Cap error detectat.", "de": "Keine Fehler erkannt."},
    "n_avisos": {"ca": "{} avís/os detectat/s.", "de": "{} Hinweis(e) erkannt."},
    "col_linia": {"ca": "Línia", "de": "Zeile"},
    "col_gravetat": {"ca": "Tipus", "de": "Art"},
    "col_motiu": {"ca": "Motiu", "de": "Grund"},
    "col_set": {"ca": "Set", "de": "Satz"},
    "col_marcador": {"ca": "Marcador", "de": "Spielstand"},
    "col_equip": {"ca": "Equip", "de": "Team"},
    "col_dorsal": {"ca": "Dorsal", "de": "Nr."},
    "col_jugador": {"ca": "Jugador", "de": "Spieler"},
    "col_gest": {"ca": "Gest", "de": "Aktion"},
    "col_aval": {"ca": "Aval.", "de": "Bew."},
    "col_zona": {"ca": "Zona", "de": "Zone"},
    "col_correccio": {"ca": "Correcció", "de": "Korrektur"},
    "col_anar": {"ca": "Anar", "de": "Gehe"},
    "ajuda_salt": {
        "ca": "Marca la casella → d'una fila per portar-la al panell d'edició de "
              "sota. Els avisos de la revisió també hi salten si els cliques.",
        "de": "Häkchen → bringt die Zeile ins Bearbeitungspanel unten. Auch "
              "Klicken auf einen Hinweis springt dorthin."},
    # Inserir / esborrar
    "sec_estructura": {"ca": "Inserir, editar o esborrar accions",
                       "de": "Aktionen einfügen, bearbeiten oder löschen"},
    "ajuda_estructura": {
        "ca": "Per al que et vas deixar en directe i per a qualsevol línia que "
              "vulguis retocar, tingui error o no. Aquí pots canviar-ho tot "
              "(equip, dorsal, gest i marca), també les marques que decideixen el "
              "punt, que a la taula estan bloquejades. El context es copia de la "
              "línia veïna, el marcador no es toca mai i si la marca decideix el "
              "punt es comprova que quadri amb qui va guanyar el rally.",
        "de": "Für ausgelassene Aktionen und für jede Zeile, die du ändern willst "
              "— mit oder ohne Fehler. Hier ist alles änderbar (Team, Nr., Aktion, "
              "Bewertung), auch punktentscheidende Bewertungen. Der Spielstand "
              "wird nie verändert."},
    "ins_linia": {"ca": "Línia de referència", "de": "Bezugszeile"},
    "ins_rally": {"ca": "Rally on caurà", "de": "Betroffener Ballwechsel"},
    "ins_accio": {"ca": "Què vols fer", "de": "Aktion"},
    "ins_abans": {"ca": "Inserir abans", "de": "Davor einfügen"},
    "ins_despres": {"ca": "Inserir després", "de": "Danach einfügen"},
    "ins_edita": {"ca": "Editar aquesta línia", "de": "Zeile bearbeiten"},
    "ins_esborra": {"ca": "Esborrar la línia", "de": "Zeile löschen"},
    "ins_desa_edicio": {"ca": "Desar el canvi", "de": "Änderung speichern"},
    "ins_nomes_accions": {
        "ca": "Només es poden editar o esborrar línies d'acció. Aquesta és de "
              "marcador, rotació o canvi, i toca-la trencaria el partit.",
        "de": "Nur Aktionszeilen können bearbeitet/gelöscht werden."},
    "ins_actual": {"ca": "Ara: {}", "de": "Aktuell: {}"},
    "ins_sense_canvi": {"ca": "No has canviat res.", "de": "Nichts geändert."},
    "op_edit": {"ca": "Editar línia {}: {} → {}", "de": "Zeile {}: {} → {}"},
    "ins_equip": {"ca": "Equip", "de": "Team"},
    "ins_dorsal": {"ca": "Dorsal", "de": "Nr."},
    "ins_gest": {"ca": "Gest", "de": "Aktion"},
    "ins_marca": {"ca": "Marca", "de": "Bewertung"},
    "ins_afegir": {"ca": "Afegir operació", "de": "Vorgang hinzufügen"},
    "ins_pendents": {"ca": "Operacions pendents ({})", "de": "Offene Vorgänge ({})"},
    "ins_treure": {"ca": "Treure", "de": "Entfernen"},
    "ins_cap": {"ca": "Cap operació pendent.", "de": "Keine offenen Vorgänge."},
    "ins_dorsal_fora": {"ca": "El dorsal {} no és a pista aquí ({}).",
                        "de": "Nr. {} ist hier nicht auf dem Feld ({})."},
    "ins_incoherent": {
        "ca": "{} donaria el punt a l'equip que va PERDRE el rally. Revisa la marca.",
        "de": "{} würde den Punkt dem Verliererteam geben. Bewertung prüfen."},
    "ins_no_scout": {"ca": "Aquesta línia no és del scout: tria'n una d'acció.",
                     "de": "Diese Zeile gehört nicht zum Scout."},
    "ins_feta": {"ca": "Operació afegida. Es veurà a la taula i al fitxer desat.",
                 "de": "Vorgang hinzugefügt."},
    "ins_esborrar_terminal": {
        "ca": "Compte: esborres una acció que decideix el punt; deixarà de comptar "
              "per al jugador (el marcador no canvia).",
        "de": "Achtung: punktentscheidende Aktion wird gelöscht."},
    "op_ins": {"ca": "Inserir {} {} línia {}", "de": "{} {} Zeile {} einfügen"},
    "op_del": {"ca": "Esborrar línia {} ({})", "de": "Zeile {} löschen ({})"},
    "nova_marca": {"ca": "nova", "de": "neu"},
    "sug_auto": {"ca": "auto", "de": "auto"},
    "ajuda_autocorrect": {
        "ca": "L'autocorrector proposa el dorsal probable a la columna Correcció: "
              "«auto: N» vol dir que un candidat destaca i ja s'ha pre-omplert (només "
              "cal confirmar en desar); «→ a · b · c» és el top-3 si hi ha dubte, i "
              "pots escriure'n un altre a Dorsal.",
        "de": "Der Autokorrektor schlägt die Nummer in der Spalte Korrektur vor: "
              "«auto: N» ist vorausgefüllt (nur bestätigen); «→ a · b · c» ist die "
              "Top-3 bei Zweifel — du kannst in Nr. eine andere eintragen."},
    "ajuda_editor": {
        "ca": "Pots editar **Dorsal** i **Avaluació**. Les avaluacions terminals "
              "(les que decideixen el punt) estan bloquejades: canvien el marcador "
              "i s'han de corregir a DataVolley.",
        "de": "Editierbar: **Nr.** und **Bewertung**. Terminale Bewertungen "
              "(punktentscheidend) sind gesperrt: sie ändern den Spielstand und "
              "müssen in DataVolley korrigiert werden."},
    "filtre_equip": {"ca": "Equip", "de": "Team"},
    "filtre_tots": {"ca": "Tots", "de": "Alle"},
    "filtre_nomes_avisos": {"ca": "Només línies amb avís",
                            "de": "Nur Zeilen mit Hinweis"},
    "desar": {"ca": "Desar còpia corregida", "de": "Korrigierte Kopie speichern"},
    "sense_canvis": {"ca": "No hi ha canvis per desar.", "de": "Keine Änderungen."},
    "desat_ok": {"ca": "Desat: {} ({} canvi/s).", "de": "Gespeichert: {} ({} Änderung(en))."},
    "baixar": {"ca": "Descarregar", "de": "Herunterladen"},
    "canvi_bloquejat": {
        "ca": "Línia {}: '{}' decideix el punt ({}). A la taula no es pot canviar; "
              "fes-ho al panell d'inserir/editar, que comprova qui va guanyar el rally.",
        "de": "Zeile {}: '{}' ist punktentscheidend ({}). Nicht in der Tabelle "
              "änderbar; nutze das Einfügen/Bearbeiten-Panel."},
    "dorsal_fora": {
        "ca": "Línia {}: el dorsal {} no és a pista en aquesta acció.",
        "de": "Zeile {}: Nr. {} ist bei dieser Aktion nicht auf dem Feld."},
    # motius del linter
    "lint_dorsal_plantilla": {"ca": "Dorsal {} no és a la plantilla de {}.",
                              "de": "Nr. {} nicht im Kader von {}."},
    "lint_dorsal_pista": {"ca": "Dorsal {} no és a pista ({} en zona).",
                          "de": "Nr. {} nicht auf dem Feld ({} in Rotation)."},
    "lint_doble_saque": {"ca": "Dos saques seguits de {} sense punt entremig.",
                         "de": "Zwei Aufschläge von {} ohne Punkt dazwischen."},
    "lint_rece_propi": {"ca": "Recepció de l'equip que saca ({}).",
                        "de": "Annahme des aufschlagenden Teams ({})."},
    "lint_zona_nd": {"ca": "Atac de davanter sense zona deduïble (revisa rotació/dorsal).",
                     "de": "Angriff vorne ohne ableitbare Zone (Rotation/Nr. prüfen)."},
    "lint_marcador_salt": {"ca": "El marcador salta de {} a {} (hauria de pujar d'un punt).",
                           "de": "Spielstand springt von {} auf {} (sollte um einen Punkt steigen)."},
    "grav_error": {"ca": "Error", "de": "Fehler"},
    "grav_avis": {"ca": "Avís", "de": "Hinweis"},
}


def get_lang():
    # Eina personal: sempre català (sense selector).
    return IDIOMA_DEF


def t(key):
    e = TXT.get(key)
    if e is None:
        return key
    return e.get(get_lang(), e.get(IDIOMA_DEF, key))


def nom_gest(intern):
    e = NOM_GEST.get(intern)
    return e.get(get_lang(), intern) if e else intern


# ===========================================================================
# PARSEIG
# ===========================================================================
def _detecta_nl(text):
    return "\r\n" if "\r\n" in text else "\n"


def parse_dvw(text):
    """Descompon el .dvw en seccions + scout. No perd res: guarda les línies
    crues per poder reconstruir el fitxer byte a byte.

    Retorna un dict amb:
      lines    : llista de línies (sense el salt de línia)
      nl       : el salt de línia original
      teams    : {'*': (codi, nom), 'a': (codi, nom)}
      roster   : {'*': {dorsal: nom}, 'a': {...}}
      scout    : llista de dicts, un per línia d'scout (només informatiu;
                 l'edició es fa sobre `lines` per índex)
    """
    nl = _detecta_nl(text)
    lines = text.split(nl)

    teams = {}
    roster = {"*": {}, "a": {}}
    liberos = {"*": set(), "a": set()}   # dorsals amb flag 'L' (no surten a la formació)
    scout = []

    sec = None
    for i, raw in enumerate(lines):
        if raw.startswith("[3") and raw.endswith("]"):
            sec = raw
            continue
        if not raw:
            continue
        if sec == "[3TEAMS]":
            f = raw.split(";")
            # 1a línia = local ('*'), 2a = visitant ('a')
            key = "*" if "*" not in teams else "a"
            teams[key] = (f[0], f[1] if len(f) > 1 else f[0])
        elif sec in ("[3PLAYERS-H]", "[3PLAYERS-V]"):
            f = raw.split(";")
            key = "*" if sec == "[3PLAYERS-H]" else "a"
            # camp 1 = dorsal; camps 9,10 = cognom, nom
            if len(f) > 10 and f[1]:
                # camp 9 = cognom, camp 10 = nom de pila. Els volem com "Nom
                # Cognom", i si en falta un, només el que hi hagi.
                cognom, nom_pila = f[9].strip(), f[10].strip()
                nom = " ".join(x for x in (nom_pila, cognom) if x) or f[8]
                roster[key][f[1]] = nom
                if len(f) > 12 and f[12] == "L":   # 'L' = líbero, 'C' = capità
                    liberos[key].add(f[1])
        elif sec == SCOUT_HEADER:
            scout.append(parse_scout_line(i, raw))

    return {"lines": lines, "nl": nl, "teams": teams,
            "roster": roster, "liberos": liberos, "scout": scout}


def parse_scout_line(idx, raw):
    """Descodifica una línia d'scout. Camps buits → None als llocs clau."""
    f = raw.split(";")
    code = f[0]
    d = {"idx": idx, "code": code, "fields": f,
         "team": None, "player": None, "skill": None, "type": None,
         "eval": None, "kind": "other",
         "set": f[F_SET] if len(f) > F_SET else None}

    if not code:
        return d
    d["team"] = code[0] if code[0] in ("*", "a") else None
    rest = code[1:]
    if rest[:1].isdigit() and len(rest) >= 4:
        # acció de jugador: dorsal(2) gest(1) tipus(1) aval(1) [extres]
        d["kind"] = "skill"
        d["player"] = rest[0:2]
        d["skill"] = rest[2]
        d["type"] = rest[3]
        d["eval"] = rest[4] if len(rest) > 4 else None
    elif rest[:1] == "p":
        d["kind"] = "point"          # marcador (score a rest[1:])
    elif rest[:1] == "z":
        d["kind"] = "rot"            # rotació
    elif rest[:1] == "P":
        d["kind"] = "setter"
    elif rest[:1] == "c":
        d["kind"] = "sub"            # canvi
    elif rest[:1] == "T":
        d["kind"] = "timeout"
    elif rest[:1] == "*":
        d["kind"] = "setend"
    return d


def on_court(fields, team):
    """Els 6 dorsals a pista de l'equip en aquesta línia (o None si no hi són)."""
    base = F_LINEUP_H if team == "*" else F_LINEUP_V
    if len(fields) < base + 6:
        return None
    vals = [fields[base + k].strip() for k in range(6)]
    return vals if any(vals) else None


def setter_pos(fields, team):
    idx = F_SETTER_H if team == "*" else F_SETTER_V
    if len(fields) > idx and fields[idx].strip():
        return fields[idx].strip()
    return None


# ---- Deducció de zona d'atac (portada de app_dvw._zona_fila) ----------------
def zona_atac(fields, team, dorsal):
    """Zona d'un atac assumint 5-1. None si no es pot deduir.

    Aquí és la regla per rol i prou: l'app hi afegeix l'excepció de R1 en
    recepció (l'opposite ataca per 4), que necessita saber la fase de la
    jugada i aquí es treballa línia a línia. Per al que serveix la zona en
    aquest arxiu -- avisar d'un atac de davanter sense zona deduïble i puntuar
    candidats a l'autocorrector -- només compta si en surt una o no, i això no
    canvia.
    """
    llista = on_court(fields, team)
    sp = setter_pos(fields, team)
    if llista is None or sp is None or dorsal is None:
        return None
    try:
        posicio = llista.index(dorsal) + 1
    except ValueError:
        return None
    rol = (posicio - int(sp)) % 6
    davanter = posicio in (2, 3, 4)
    if rol in (2, 5):
        return "Z3" if davanter else None
    if rol in (1, 4):
        return "Z4" if davanter else "Z6"
    if rol == 3:
        return "Z2" if davanter else "Z1"
    if rol == 0:
        return "Z2" if davanter else None
    return None


# ===========================================================================
# AUTOCORRECTOR (suggeriments de dorsal)
# ===========================================================================
# Idea: quan un dorsal és erroni, el correcte quasi sempre és un dels 6 a pista
# (la mateixa línia ja els porta). El puntuem combinant:
#   - proximitat de dedada (Damerau-Levenshtein amb el que vaig teclejar),
#   - encaix de posició segons el gest (verificat: saque = posició 1 al 100%;
#     bloqueig = davanter al 97%; atac = pot atacar en aquesta rotació),
#   - freqüència: qui fa aquest gest en aquesta rotació al llarg del set.
# Si un candidat destaca clarament → es pre-omple (confiança). Si no → top-3.

def _nd(x):
    """Dorsal normalitzat (sense zeros al davant) per comparar."""
    return (x.lstrip("0") or "0") if x and x.isdigit() else x


def _dlev(a, b):
    """Distància de Damerau-Levenshtein (inclou transposició: 19↔91)."""
    a, b = str(a), str(b)
    m, n = len(a), len(b)
    d = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        d[i][0] = i
    for j in range(n + 1):
        d[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[m][n]


def build_freq(parsed):
    """freq[(team, set, setter_pos, skill)][dorsal] = accions correctes comptades.
    Serveix per saber qui fa cada gest en cada rotació/set (desempat)."""
    from collections import defaultdict
    freq = defaultdict(lambda: defaultdict(int))
    libs = {k: {_nd(x) for x in v} for k, v in parsed["liberos"].items()}
    for d in parsed["scout"]:
        if d["kind"] != "skill":
            continue
        team = d["team"]
        llista = on_court(d["fields"], team)
        sp = setter_pos(d["fields"], team)
        if llista is None or sp is None:
            continue
        dor = _nd(d["player"])
        onc = [_nd(x) for x in llista]
        if dor not in onc and dor not in libs.get(team, set()):
            continue                       # acció amb dorsal erroni: no la comptem
        freq[(team, d["set"], sp, d["skill"])][dor] += 1
    return freq


def _pos_prior(skill, cand, onc, es_libero, fields, team):
    """Versemblança que aquest candidat faci aquest gest per la seva posició."""
    if skill == "S":                       # el sacador és a la posició 1 (100%)
        return 1.0 if cand == onc[0] else 0.0
    if skill == "B":                       # el blocador és davanter (2,3,4) (97%)
        return 1.0 if cand in (onc[1], onc[2], onc[3]) else 0.2
    if skill == "A":                       # pot atacar en aquesta rotació?
        return 1.0 if zona_atac(fields, team, cand) is not None else 0.1
    if es_libero or cand in (onc[0], onc[4], onc[5]):   # R/D/E/F: zaguer o líbero
        return 0.7
    return 0.4


def suggereix_dorsal(parsed, d, freq):
    """Retorna (candidats_ordenats, confiança).
    candidats_ordenats = [(dorsal, score, pos_prior, dedada, freq), ...]."""
    f = d["fields"]
    team = d["team"]
    escrit = _nd(d["player"])
    llista = on_court(f, team)
    sp = setter_pos(f, team)
    if llista is None:
        return [], False
    onc = [_nd(x) for x in llista]
    libs = {_nd(x) for x in parsed["liberos"].get(team, set())}
    cands = onc + (list(libs) if d["skill"] in LIBERO_SKILLS else [])
    cands = list(dict.fromkeys(cands))     # únics, mantenint ordre

    fr = freq.get((team, d["set"], sp, d["skill"]), {})
    fmax = max(fr.values()) if fr else 0

    scored = []
    for c in cands:
        es_lib = c in libs
        pp = _pos_prior(d["skill"], c, onc, es_lib, f, team)
        dl = _dlev(escrit, c)
        ts = {0: 1.0, 1: 1.0, 2: 0.35}.get(dl, 0.0)     # >d2 no és dedada
        fs = (fr.get(c, 0) / fmax) if fmax else 0.0
        score = round(0.4 * ts + 0.4 * pp + 0.2 * fs, 3)
        scored.append((c, score, pp, dl, fr.get(c, 0)))
    scored.sort(key=lambda x: (-x[1], x[3], -x[4]))     # score, dedada, freq

    confident = False
    if scored:
        if d["skill"] == "S" and scored[0][2] == 1.0:   # saque: determinista
            confident = True
        elif len(scored) == 1:
            confident = True
        elif (scored[0][1] - scored[1][1] >= 0.25 and scored[0][3] <= 1
              and scored[0][2] >= 0.7):
            confident = True
    return scored, confident


# ===========================================================================
# ESCRIPTURA (lossless)
# ===========================================================================
def rebuild(parsed):
    """Reconstrueix el text del fitxer a partir de `lines`. Ha de ser idèntic
    a l'original si no s'ha tocat res."""
    return parsed["nl"].join(parsed["lines"])


def set_code_eval(code, nova):
    """Reemplaça l'avaluació (posició fixa) del token d'acció."""
    # code = team(1) dorsal(2) gest(1) tipus(1) aval(1) [extres]
    return code[:5] + nova + code[6:]


def set_code_player(code, nou_dorsal):
    """Reemplaça el dorsal (2 dígits, zero-padded)."""
    return code[0] + f"{int(nou_dorsal):02d}" + code[3:]


# ===========================================================================
# OPERACIONS ESTRUCTURALS (inserir / esborrar accions)
# ===========================================================================
# Verificat sobre 2304 rallies: els camps de context (set, rotacions, formació)
# són IDÈNTICS a totes les línies d'un mateix rally i cap en canvia. Per això
# inserir una acció és copiar el context del veí: no hi ha cap cascada.
# El marcador (línies `p`) i les genèriques `$$&` no es toquen mai.

def guanyador_rally(parsed, idx):
    """Equip que guanya el rally on cau la línia idx ('*'/'a'), llegit del
    marcador següent. Verificat: el prefix encerta 2255/2255 vegades."""
    for d in parsed["scout"]:
        if d["idx"] > idx and d["kind"] == "point":
            return d["team"]
    return None


def construeix_codi(team, dorsal, skill, aval, tipus=None):
    """Token d'acció nou: equip + dorsal(2) + gest + tipus + avaluació."""
    return f"{team}{int(dorsal):02d}{skill}{tipus or TIPUS_DEFECTE.get(skill, 'H')}{aval}"


def construeix_linia(ref_linia, codi):
    """Línia nova: el codi + el context de la línia de referència. Els camps
    1-6 (combinació/objectiu) es deixen buits, com moltes línies reals."""
    f = ref_linia.split(";")
    f[0] = codi
    for k in range(1, min(7, len(f))):
        f[k] = ""
    return ";".join(f)


def tipus_recepcio(parsed, idx):
    """La recepció copia el tipus del saque del rally (ST→RT, SQ→RQ)."""
    saque = None
    for d in parsed["scout"]:
        if d["idx"] > idx:
            break
        if d["kind"] == "point":
            saque = None
        elif d["kind"] == "skill" and d["skill"] == "S":
            saque = d["type"]
    return saque


def valida_accio(parsed, ref_idx, team, dorsal, skill, aval):
    """(ok, motiu) per a una acció nova o editada. Dorsal a pista i, si la marca
    és terminal, coherent amb qui guanya el rally: no es pot donar un punt a
    l'equip que l'ha perdut."""
    fields = parsed["lines"][ref_idx].split(";")
    llista = on_court(fields, team)
    libs = {_nd(x) for x in parsed["liberos"].get(team, set())}
    if llista is not None:
        valids = {_nd(x) for x in llista}
        if skill in LIBERO_SKILLS:
            valids |= libs
        if str(int(dorsal)) not in valids:
            return False, t("ins_dorsal_fora").format(int(dorsal), ", ".join(llista))
    if aval in TERMINAL.get(skill, set()):
        win = guanyador_rally(parsed, ref_idx)
        if win and (team == win) != (aval == MARCA_PUNT):
            return False, t("ins_incoherent").format(f"{skill}{aval}")
    return True, ""


def aplica_operacions(text, operacions):
    """Aplica inserts/esborrats i retorna (parsed, ids), on ids[i] és
    l'identificador ESTABLE de la línia i (int original o 'nN' si és nova).
    Cal perquè inserir renumera: les correccions es guarden per id, no per línia."""
    p = parse_dvw(text)
    ids = list(range(len(p["lines"])))
    for op in operacions:
        if op["ref"] not in ids:
            continue                      # la referència ja no hi és: ignora
        pos = ids.index(op["ref"])
        if op["tipus"] == "esborra":
            del p["lines"][pos]
            del ids[pos]
        elif op["tipus"] == "edita":
            camps = p["lines"][pos].split(";")
            camps[0] = op["codi"]           # només el token; el context intacte
            p["lines"][pos] = ";".join(camps)
        else:
            k = pos + (1 if op["on"] == "despres" else 0)
            p["lines"].insert(k, op["linia"])
            ids.insert(k, op["id"])
    # Re-parsegem: parse_dvw només parteix per salts de línia, així que les
    # posicions segueixen alineades amb ids.
    return parse_dvw(p["nl"].join(p["lines"])), ids


# ===========================================================================
# LINTER
# ===========================================================================
def _marcador_codi(code):
    """(local, visitant) d'un codi de marcador `*p01:02`. None si no es llegeix."""
    sc = code[2:].replace(" ", "")
    if ":" not in sc:
        return None
    a, b = sc.split(":", 1)
    try:
        return int(a), int(b)
    except ValueError:
        return None


def lint(parsed):
    """Retorna llista d'avisos: dicts {idx, linia(1-based), grav, motiu}."""
    avisos = []
    roster = parsed["roster"]
    liberos = parsed.get("liberos", {"*": set(), "a": set()})
    teams = parsed["teams"]

    def nom_equip(team):
        return teams.get(team, (team, team))[1]

    ultim_saque = {"*": None, "a": None}   # per detectar doble saque
    marcador_ant = None                    # últim marcador llegit d'aquest set
    set_ant = None

    for d in parsed["scout"]:
        if d["kind"] != "skill":
            if d["kind"] == "point":
                ultim_saque = {"*": None, "a": None}

                # 6) el marcador ha de pujar d'un punt, i d'un de sol.
                # Quan em vaig equivocar donant un punt i ho vaig desfer, el
                # marcador retrocedeix i queden files fantasma al darrere.
                # No embruta les estadístiques (aquestes files no tenen dorsal
                # ni gest), però sí que compta un rally de més.
                if d["set"] != set_ant:        # cada set torna a començar a 0
                    set_ant, marcador_ant = d["set"], None
                sc = _marcador_codi(d["code"])
                if sc is not None:
                    if (marcador_ant is not None
                            and (sc[0] - marcador_ant[0],
                                 sc[1] - marcador_ant[1]) not in ((1, 0), (0, 1))):
                        avisos.append({
                            "idx": d["idx"], "linia": d["idx"] + 1,
                            "grav": "avis", "codi": "marcador_salt",
                            "motiu": t("lint_marcador_salt").format(
                                f"{marcador_ant[0]}:{marcador_ant[1]}",
                                f"{sc[0]}:{sc[1]}")})
                    marcador_ant = sc
            continue
        team, dorsal, skill = d["team"], d["player"], d["skill"]
        linia = d["idx"] + 1
        f = d["fields"]

        # dorsal normalitzat (sense zero al davant) per comparar amb plantilla
        dnorm = str(int(dorsal)) if dorsal and dorsal.isdigit() else dorsal

        # 1) dorsal a la plantilla
        if team in roster and dnorm not in roster[team]:
            avisos.append({"idx": d["idx"], "linia": linia, "grav": "error",
                           "codi": "dorsal_plantilla",
                           "motiu": t("lint_dorsal_plantilla").format(
                               dnorm, nom_equip(team))})
        elif dnorm not in liberos.get(team, set()):
            # 2) dorsal a pista (només si és a la plantilla i NO és líbero:
            #    el líbero entra a rebre/defensar i no surt als camps de formació)
            llista = on_court(f, team)
            if llista is not None and dnorm not in [
                    (str(int(x)) if x.isdigit() else x) for x in llista]:
                avisos.append({"idx": d["idx"], "linia": linia, "grav": "error",
                               "codi": "dorsal_pista",
                               "motiu": t("lint_dorsal_pista").format(
                                   dnorm, ", ".join(llista))})

        # 3) doble saque del mateix equip sense punt entremig
        if skill == "S":
            if ultim_saque[team] is not None:
                avisos.append({"idx": d["idx"], "linia": linia, "grav": "avis",
                               "codi": "doble_saque",
                               "motiu": t("lint_doble_saque").format(nom_equip(team))})
            ultim_saque[team] = d["idx"]

        # 4) recepció de l'equip que saca
        if skill == "R":
            altre = "a" if team == "*" else "*"
            if ultim_saque[team] is not None and ultim_saque[altre] is None:
                avisos.append({"idx": d["idx"], "linia": linia, "grav": "avis",
                               "codi": "rece_propi",
                               "motiu": t("lint_rece_propi").format(nom_equip(team))})

        # 5) atac de davanter sense zona deduïble
        if skill == "A":
            llista = on_court(f, team)
            sp = setter_pos(f, team)
            if llista is not None and sp is not None:
                dstr = dorsal.lstrip("0") or "0"
                match = next((x for x in llista
                              if (x.lstrip("0") or "0") == dstr), None)
                if match is not None:
                    posicio = llista.index(match) + 1
                    if posicio in (2, 3, 4) and zona_atac(f, team, match) is None:
                        avisos.append({"idx": d["idx"], "linia": linia,
                                       "grav": "avis", "codi": "zona_nd",
                                       "motiu": t("lint_zona_nd")})

    return avisos


# ===========================================================================
# UI
# ===========================================================================
def marcadors_per_linia(parsed):
    """Marcador (HH:VV) vigent a cada línia d'scout, llegit dels marcadors `p`."""
    res = {}
    actual = "0:0"
    for d in parsed["scout"]:
        if d["kind"] == "point":
            sc = d["code"][2:]        # p01:02 → 01:02
            if ":" in sc:
                actual = sc.replace(" ", "")
        res[d["idx"]] = actual
    return res


def main():
    st.set_page_config(page_title="Revisor .dvw", layout="wide")
    st.markdown("""
    <style>
      .block-container { padding-top: 4.2rem; max-width: 1500px; }
      h1 { font-size: 1.6rem !important; font-weight: 600 !important; }
      .sec { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.09em;
             text-transform: uppercase; color: #8a94a6;
             border-bottom: 1px solid #dfe3e8; padding-bottom: 0.35rem;
             margin: 1.6rem 0 0.9rem 0; }
    </style>
    """, unsafe_allow_html=True)

    st.title(t("titol"))
    st.caption(t("subtitol"))

    pujat = st.file_uploader(t("uploader"), type=["dvw"])
    if pujat is None:
        st.info(t("sense_arxiu"))
        return

    try:
        raw_bytes = pujat.getvalue()
        text = raw_bytes.decode(ENC)
    except Exception as e:
        st.error(t("error_llegir").format(e))
        return

    # ---- Estat propi, per IDENTIFICADOR estable de línia --------------------
    # No ens refiem del delta intern del data_editor: quan les dades d'entrada
    # canvien (i canvien, perquè hi refresquem el nom), Streamlit el descarta i
    # el dorsal editat tornava al valor per defecte. Aquí ho fixem nosaltres.
    # I ha de ser per id, no per número de línia, perquè inserir renumera.
    fitxer_id = hashlib.md5(raw_bytes).hexdigest()
    if st.session_state.get("fitxer_id") != fitxer_id:      # fitxer nou: reinicia
        st.session_state.update(fitxer_id=fitxer_id, correccions={},
                                ordre_idx=[], delta_sig=None, operacions=[])
    correccions = st.session_state.setdefault("correccions", {})
    operacions = st.session_state.setdefault("operacions", [])

    try:
        parsed, ids = aplica_operacions(text, operacions)
    except Exception as e:
        st.error(t("error_llegir").format(e))
        return
    idx_de_id = {v: i for i, v in enumerate(ids)}

    # El delta ve per POSICIÓ de la taula pintada l'última vegada: el traduïm a
    # línia amb l'ordre que vam desar. Només si és nou, perquè si no, en canviar
    # de filtre el reaplicaríem sobre la fila equivocada.
    pend = st.session_state.get("editor")
    delta = pend.get("edited_rows", {}) if isinstance(pend, dict) else {}
    sig = repr(sorted((int(k), sorted(v.items())) for k, v in delta.items()))
    salta_a = None
    if delta and sig != st.session_state.get("delta_sig"):
        ordre = st.session_state.get("ordre_idx", [])
        for pos, canvis in delta.items():
            if int(pos) >= len(ordre):
                continue
            nou_d = canvis.get(t("col_dorsal"))
            nova_a = canvis.get(t("col_aval"))
            if nou_d not in (None, "") or nova_a:   # no creïs entrades buides
                c = correccions.setdefault(ordre[int(pos)], {})
                if nou_d not in (None, ""):
                    c["dorsal"] = int(nou_d)
                if nova_a:
                    c["aval"] = nova_a
            if canvis.get(t("col_anar")):          # casella → marcada
                salta_a = ordre[int(pos)]
    st.session_state["delta_sig"] = sig

    if salta_a is not None and salta_a in idx_de_id:
        # Portem la línia al panell. Els canvis reals ja s'han fusionat a
        # `correccions` just aquí sobre, així que buidar l'estat del widget
        # (per treure el tic) no perd res.
        # SENSE st.rerun(): el panell es pinta més avall en aquesta mateixa
        # passada i ja agafa el valor nou. Si reiniciàvem aquí, la passada
        # s'avortava abans de pintar els filtres i Streamlit els esborrava
        # l'estat: la casella "només avisos" es veia marcada però es llegia
        # com a falsa i la llista tornava sencera.
        st.session_state["ins_linia_val"] = idx_de_id[salta_a] + 1
        st.session_state.pop("editor", None)
        st.session_state["delta_sig"] = None

    teams = parsed["teams"]
    nom_local = teams.get("*", ("", ""))[1]
    nom_visit = teams.get("a", ("", ""))[1]
    st.markdown(f"**{t('partit')}:** {nom_local} — {nom_visit}  ·  `{pujat.name}`")

    avisos = lint(parsed)
    marcadors = marcadors_per_linia(parsed)

    # Autocorrector: suggeriment de dorsal per a cada error de dorsal.
    freq = build_freq(parsed)
    by_idx = {d["idx"]: d for d in parsed["scout"]}
    suggeriments = {}
    for a in avisos:
        if a.get("codi") in ("dorsal_plantilla", "dorsal_pista"):
            scored, conf = suggereix_dorsal(parsed, by_idx[a["idx"]], freq)
            if scored:
                suggeriments[a["idx"]] = {
                    "top": [c for c, *_ in scored[:3]],
                    "confident": conf, "best": scored[0][0]}

    # ---- Secció revisió automàtica ----
    st.markdown(f'<div class="sec">{t("sec_revisio")}</div>', unsafe_allow_html=True)
    if not avisos:
        st.success(t("cap_error"))
    else:
        st.write(t("n_avisos").format(len(avisos)))
        grav_txt = {"error": t("grav_error"), "avis": t("grav_avis")}
        df_av = pd.DataFrame([{
            t("col_linia"): a["linia"],
            t("col_gravetat"): grav_txt[a["grav"]],
            t("col_motiu"): a["motiu"],
        } for a in avisos])
        sel = st.dataframe(df_av, hide_index=True, width="stretch",
                           on_select="rerun", selection_mode="single-row",
                           key="taula_avisos")
        tria = list(getattr(getattr(sel, "selection", None), "rows", []) or [])
        # Només saltem quan la selecció CANVIA: si no, el panell tornaria sempre
        # a aquesta línia i no podries moure'l a mà.
        if tria and st.session_state.get("ultim_avis_triat") != tria[0]:
            # Sense st.rerun() (mateix motiu que al salt des de la taula: avortar
            # la passada aquí esborrava l'estat dels filtres de sota).
            st.session_state["ultim_avis_triat"] = tria[0]
            st.session_state["ins_linia_val"] = int(
                df_av.iloc[tria[0]][t("col_linia")])

    # ---- Secció editor ----
    st.markdown(f'<div class="sec">{t("sec_editor")}</div>', unsafe_allow_html=True)
    st.caption(t("ajuda_editor"))
    st.caption(t("ajuda_autocorrect"))
    st.caption(t("ajuda_salt"))

    idx_avis = {a["idx"] for a in avisos}
    roster = parsed["roster"]
    files = []
    for d in parsed["scout"]:
        if d["kind"] != "skill":
            continue
        team = d["team"]
        dorsal = d["player"]
        dnorm = str(int(dorsal)) if dorsal and dorsal.isdigit() else dorsal
        nom = roster.get(team, {}).get(dnorm, "?")
        # OJO: la formació guarda els dorsals sense zeros ("9"), no com el token
        # ("09"); cal passar-hi el normalitzat o no s'hi troba mai.
        zona = zona_atac(d["fields"], team, dnorm) if d["skill"] == "A" else ""

        # Autocorrector: text de correcció + pre-omplert si hi ha confiança.
        sug = suggeriments.get(d["idx"])
        correccio, prefill, prefill_nom = "", None, ""
        if sug:
            if sug["confident"]:
                correccio = f"{t('sug_auto')}: {sug['best']}"
                prefill = int(sug["best"])
                prefill_nom = roster.get(team, {}).get(sug["best"], "?")
            else:
                correccio = "→ " + " · ".join(sug["top"])
        es_nova = not isinstance(ids[d["idx"]], int)      # línia inserida per mi
        avis_marca = "+" if es_nova else ("●" if d["idx"] in idx_avis else "")
        if es_nova and not correccio:
            correccio = t("nova_marca")

        files.append({
            "_idx": d["idx"],
            "_id": ids[d["idx"]],
            t("col_anar"): False,
            t("col_linia"): d["idx"] + 1,
            t("col_set"): d["set"],
            t("col_marcador"): marcadors.get(d["idx"], ""),
            t("col_equip"): nom_local if team == "*" else nom_visit,
            t("col_dorsal"): int(dorsal) if dorsal and dorsal.isdigit() else 0,
            t("col_jugador"): nom,
            t("col_correccio"): correccio,
            t("col_gest"): nom_gest(SKILL_LETTER.get(d["skill"], d["skill"])),
            t("col_aval"): d["eval"] or "",
            t("col_zona"): zona or "",
            "_avis": avis_marca,
            "_prefill": prefill,
            "_prefill_nom": prefill_nom,
        })

    base_df = pd.DataFrame(files)

    # Vista amb els candidats confiats ja pre-omplerts (base_df manté l'original,
    # perquè el desat compari amb el que hi ha realment al fitxer).
    view = base_df.copy()
    for i in view.index:
        if pd.notna(view.at[i, "_prefill"]):
            view.at[i, t("col_dorsal")] = int(view.at[i, "_prefill"])
            view.at[i, t("col_jugador")] = view.at[i, "_prefill_nom"]

    c1, c2 = st.columns([1, 1])
    with c1:
        equip_sel = st.selectbox(t("filtre_equip"),
                                 [t("filtre_tots"), nom_local, nom_visit])
    with c2:
        nomes_avisos = st.checkbox(t("filtre_nomes_avisos"), value=False)

    if equip_sel != t("filtre_tots"):
        view = view[view[t("col_equip")] == equip_sel]
    if nomes_avisos:
        view = view[view["_avis"] != ""]

    # Apliquem les correccions pròpies (dorsal/avaluació) i recalculem el que
    # se'n deriva (Jugador, Zona). Com que van a `view`, sobreviuen encara que
    # Streamlit descarti el seu delta intern.
    for i in view.index:
        c = correccions.get(view.at[i, "_id"])
        if not c:
            continue
        d = by_idx[view.at[i, "_idx"]]
        if "aval" in c:
            view.at[i, t("col_aval")] = c["aval"]
        if "dorsal" in c:
            dn = str(c["dorsal"])
            view.at[i, t("col_dorsal")] = c["dorsal"]
            view.at[i, t("col_jugador")] = roster.get(d["team"], {}).get(dn, "?")
            if d["skill"] == "A":
                view.at[i, t("col_zona")] = zona_atac(d["fields"], d["team"], dn) or ""

    # L'ordre realment pintat: el delta del widget ve per posició, i el
    # necessitarem per traduir-lo a id estable a la propera passada.
    st.session_state["ordre_idx"] = list(view["_id"])

    col_cfg = {
        "_idx": None, "_id": None, "_prefill": None, "_prefill_nom": None,
        t("col_linia"): st.column_config.NumberColumn(disabled=True),
        t("col_set"): st.column_config.TextColumn(disabled=True),
        t("col_marcador"): st.column_config.TextColumn(disabled=True),
        t("col_equip"): st.column_config.TextColumn(disabled=True),
        t("col_dorsal"): st.column_config.NumberColumn(min_value=0, max_value=99),
        t("col_jugador"): st.column_config.TextColumn(disabled=True),
        t("col_correccio"): st.column_config.TextColumn(disabled=True),
        t("col_gest"): st.column_config.TextColumn(disabled=True),
        t("col_aval"): st.column_config.SelectboxColumn(options=MARQUES),
        t("col_zona"): st.column_config.TextColumn(disabled=True),
        "_avis": st.column_config.TextColumn("!", disabled=True, width="small"),
        t("col_anar"): st.column_config.CheckboxColumn("→", width="small"),
    }

    edited = st.data_editor(
        view, column_config=col_cfg, hide_index=True,
        width="stretch", key="editor",
        column_order=["_avis", t("col_anar"), t("col_linia"), t("col_set"),
                      t("col_marcador"), t("col_equip"), t("col_dorsal"),
                      t("col_jugador"), t("col_correccio"), t("col_gest"),
                      t("col_aval"), t("col_zona")],
    )

    # ---- Secció inserir / esborrar ----
    st.markdown(f'<div class="sec">{t("sec_estructura")}</div>', unsafe_allow_html=True)
    st.caption(t("ajuda_estructura"))

    panell_operacions(parsed, ids, nom_local, nom_visit, operacions)
    llista_operacions(operacions)

    # ---- Desar ----
    if st.button(t("desar"), type="primary"):
        canvis, ignorats = aplica_canvis(parsed, base_df, edited)
        canvis += len(operacions)
        for msg in ignorats:
            st.warning(msg)
        if not canvis:
            st.info(t("sense_canvis"))
        else:
            nou_text = rebuild(parsed)
            nom_out = os.path.splitext(pujat.name)[0] + "_rev.dvw"
            st.success(t("desat_ok").format(nom_out, canvis))
            st.download_button(
                t("baixar"), data=nou_text.encode(ENC),
                file_name=nom_out, mime="text/plain")


GESTOS_INSERIBLES = ["A", "S", "R", "B", "D", "F"]   # la col·locació quasi no la marco


def previsualitza_rally(parsed, ref_idx):
    """El rally sencer on cau la línia, amb una fletxa a la de referència."""
    ini, fi = 0, len(parsed["lines"])
    for d in parsed["scout"]:
        if d["kind"] != "point":
            continue
        if d["idx"] < ref_idx:
            ini = d["idx"] + 1
        else:
            fi = d["idx"]
            break
    out = [f"{'>>' if d['idx'] == ref_idx else '  '} L{d['idx']+1}: {d['code']}"
           for d in parsed["scout"] if ini <= d["idx"] <= fi]
    return "\n".join(out) or "(sense accions)"


def panell_operacions(parsed, ids, nom_local, nom_visit, operacions):
    """Inserir/esborrar accions. Les operacions viuen a session_state i es
    reapliquen a cada passada, així que la taula ja mostra el resultat."""
    scout_idx = {d["idx"]: d for d in parsed["scout"]}
    n_lin = len(parsed["lines"])
    if st.session_state.get("ins_linia_val", 1) > n_lin:
        st.session_state["ins_linia_val"] = 1
    st.session_state.setdefault("ins_linia_val", 1)

    linia = st.number_input(t("ins_linia"), min_value=1, max_value=n_lin,
                            step=1, key="ins_linia_val")
    ref_idx = int(linia) - 1
    if ref_idx not in scout_idx:
        st.info(t("ins_no_scout"))
        return

    st.text(previsualitza_rally(parsed, ref_idx))

    accio = st.radio(t("ins_accio"),
                     [t("ins_despres"), t("ins_abans"), t("ins_edita")],
                     horizontal=True)
    d = scout_idx[ref_idx]
    editant = accio == t("ins_edita")

    # Editar i esborrar només tenen sentit sobre accions: tocar una línia de
    # marcador, rotació o canvi trencaria el partit.
    if editant and d["kind"] != "skill":
        st.info(t("ins_nomes_accions"))
        return

    opcions = {nom_gest(SKILL_LETTER[g]): g for g in GESTOS_INSERIBLES}
    inv = {v: k for k, v in opcions.items()}
    if editant:      # pre-omplim amb el que hi ha ara
        st.caption(t("ins_actual").format(d["code"]))
        eq_def = 0 if d["team"] == "*" else 1
        dor_def = int(d["player"]) if d["player"] and d["player"].isdigit() else 1
        gest_def = list(opcions).index(inv[d["skill"]]) if d["skill"] in inv else 0
        marca_def = MARQUES.index(d["eval"]) if d["eval"] in MARQUES else 0
    else:
        eq_def, dor_def, gest_def, marca_def = 0, 1, 0, 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        equip = st.selectbox(t("ins_equip"), [nom_local, nom_visit], index=eq_def)
    with c2:
        dorsal = st.number_input(t("ins_dorsal"), min_value=1, max_value=99,
                                 step=1, value=dor_def)
    with c3:
        gest = st.selectbox(t("ins_gest"), list(opcions.keys()), index=gest_def)
    with c4:
        marca = st.selectbox(t("ins_marca"), MARQUES, index=marca_def)

    team = "*" if equip == nom_local else "a"
    skill = opcions[gest]
    # el tipus segueix el gest; la recepció copia el del saque del rally (RT/RQ)
    tip = tipus_recepcio(parsed, ref_idx) if skill == "R" else None
    if editant and skill == d["skill"]:
        tip = d["type"]                       # mateix gest: conserva el tipus
    codi = construeix_codi(team, int(dorsal), skill, marca, tip)

    if editant:
        b1, b2 = st.columns([1, 1])
        desa = b1.button(t("ins_desa_edicio"), type="primary")
        if d["eval"] in TERMINAL.get(d["skill"], set()):
            st.warning(t("ins_esborrar_terminal"))
        esborra = b2.button(t("ins_esborra"))
        if esborra:
            operacions.append({"tipus": "esborra", "ref": ids[ref_idx],
                               "desc": t("op_del").format(linia, d["code"])})
            st.session_state.get("correccions", {}).pop(ids[ref_idx], None)
            st.rerun()
        if desa:
            if codi == d["code"]:
                st.info(t("ins_sense_canvi"))
                return
            ok, motiu = valida_accio(parsed, ref_idx, team, int(dorsal), skill, marca)
            if not ok:
                st.error(motiu)
                return
            # una sola edició per línia: la nova substitueix l'anterior
            operacions[:] = [o for o in operacions
                             if not (o["tipus"] == "edita" and o["ref"] == ids[ref_idx])]
            operacions.append({"tipus": "edita", "ref": ids[ref_idx], "codi": codi,
                               "desc": t("op_edit").format(linia, d["code"], codi)})
            # el panell mana sobre el que hagis tocat a la taula per aquesta línia
            st.session_state.get("correccions", {}).pop(ids[ref_idx], None)
            st.rerun()
        return

    if st.button(t("ins_afegir")):
        ok, motiu = valida_accio(parsed, ref_idx, team, int(dorsal), skill, marca)
        if not ok:
            st.error(motiu)
        else:
            n = st.session_state.get("comptador_nous", 0)
            st.session_state["comptador_nous"] = n + 1
            operacions.append({
                "tipus": "insereix", "ref": ids[ref_idx],
                "on": "despres" if accio == t("ins_despres") else "abans",
                "linia": construeix_linia(parsed["lines"][ref_idx], codi),
                "id": f"n{n}",
                "desc": t("op_ins").format(codi, accio.lower(), linia)})
            st.success(t("ins_feta"))
            st.rerun()


def llista_operacions(operacions):
    """Operacions pendents, amb botó per treure-les."""
    if not operacions:
        st.caption(t("ins_cap"))
        return
    st.write(t("ins_pendents").format(len(operacions)))
    for k, op in enumerate(list(operacions)):
        c1, c2 = st.columns([8, 1])
        c1.text(op["desc"])
        if c2.button(t("ins_treure"), key=f"treu_{k}"):
            operacions.pop(k)
            st.rerun()


def aplica_canvis(parsed, base_df, edited):
    """Compara l'editat amb l'original, valida i aplica sobre parsed['lines'].
    Retorna (n_canvis_aplicats, [missatges d'ignorats])."""
    scout_by_idx = {d["idx"]: d for d in parsed["scout"]}
    orig_by_idx = {r["_idx"]: r for _, r in base_df.iterrows()}
    canvis = 0
    ignorats = []

    for _, row in edited.iterrows():
        idx = row["_idx"]
        orig = orig_by_idx.get(idx)
        d = scout_by_idx.get(idx)
        if orig is None or d is None:
            continue
        linia = idx + 1
        code = parsed["lines"][idx].split(";")[0]

        # --- avaluació ---
        nova_av = row[t("col_aval")]
        if nova_av != orig[t("col_aval")] and nova_av in MARQUES:
            skill = d["skill"]
            if nova_av in TERMINAL.get(skill, set()) or \
                    d["eval"] in TERMINAL.get(skill, set()):
                ignorats.append(t("canvi_bloquejat").format(
                    linia, nova_av, nom_gest(SKILL_LETTER.get(skill, skill))))
            else:
                code = set_code_eval(code, nova_av)
                d["eval"] = nova_av
                _reemplaça_code(parsed, idx, code)
                canvis += 1

        # --- dorsal ---
        nou_d = int(row[t("col_dorsal")]) if row[t("col_dorsal")] else 0
        if nou_d != orig[t("col_dorsal")] and nou_d > 0:
            llista = on_court(d["fields"], d["team"])
            libs = parsed.get("liberos", {}).get(d["team"], set())
            # vàlids = els 6 a pista + els líberos (que no surten a la formació)
            norm_court = [(x.lstrip("0") or "0") for x in llista] if llista else []
            valids = set(norm_court) | {(x.lstrip("0") or "0") for x in libs}
            if llista is not None and str(nou_d) not in valids:
                ignorats.append(t("dorsal_fora").format(linia, nou_d))
            else:
                code = set_code_player(code, nou_d)
                d["player"] = f"{nou_d:02d}"
                _reemplaça_code(parsed, idx, code)
                canvis += 1

    return canvis, ignorats


def _reemplaça_code(parsed, idx, nou_code):
    """Reescriu només el camp 0 de la línia, deixant la resta intacta."""
    parts = parsed["lines"][idx].split(";")
    parts[0] = nou_code
    parsed["lines"][idx] = ";".join(parts)
    parsed["scout"] = [parse_scout_line(x["idx"], parsed["lines"][x["idx"]])
                       if x["idx"] == idx else x for x in parsed["scout"]]


if __name__ == "__main__":
    main()
