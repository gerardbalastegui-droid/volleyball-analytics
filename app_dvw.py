# -*- coding: utf-8 -*-
"""
app_dvw.py — Eina LOCAL per generar informes a partir d'arxius DataVolley (.dvw).

Ús (al teu PC):
    pip install streamlit pandas matplotlib openvolley-pydatavolley xhtml2pdf
    python -m streamlit run app_dvw.py

v9: estil minimalista i professional.
v10: exportació de l'informe (mètriques seleccionades) a PDF.
"""
import os
import io
import collections
import datetime
import hashlib
import tempfile
import pandas as pd
import streamlit as st
import datavolley as dv
from xhtml2pdf import pisa
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from matplotlib import font_manager

st.set_page_config(page_title="DataVolley Reports", layout="wide")


@st.cache_resource(show_spinner=False)
def _init_pdf_fonts():
    """Registra DejaVuSans (ve amb matplotlib) per al PDF. Cobreix ca/de.

    Les fonts internes de reportlab (Helvetica) trenquen els accents; una TTF
    Unicode és imprescindible per a català i alemany.
    """
    reg = font_manager.findfont("DejaVu Sans")
    bold = font_manager.findfont(
        font_manager.FontProperties(family="DejaVu Sans", weight="bold"))
    pdfmetrics.registerFont(TTFont("AppSans", reg))
    pdfmetrics.registerFont(TTFont("AppSans-Bold", bold))
    registerFontFamily("AppSans", normal="AppSans", bold="AppSans-Bold")
    return True


try:
    PDF_OK = _init_pdf_fonts()
except Exception:
    PDF_OK = False

# ===========================================================================
# ESTIL
# ===========================================================================
INK = "#111827"        # text principal
MUTED = "#6b7280"      # text secundari
LINE = "#dfe3e8"       # línies de taula
HDR_BG = "#243244"     # capçalera principal
SUB_BG = "#37485f"     # subcapçalera
SOFT = "#f4f6f8"       # fons suau (columnes de total)
PAPER = "#ffffff"      # fons de cel·la
ROW_ALT = "#fafbfc"    # zebra
TOTAL_BG = "#eceff3"   # fila de totals

C_VERD = "#dcefe1"
C_AMBRE = "#fbf0d3"
C_ROIG = "#f7dedd"

st.markdown("""
<style>
  /* Tipografia més compacta i sòbria */
  html, body, [class*="css"] { font-feature-settings: "tnum" 1; }
  .block-container { padding-top: 4.2rem; max-width: 1500px; }
  h1 { font-size: 1.6rem !important; font-weight: 600 !important; letter-spacing: -0.01em; }
  /* Etiqueta de secció */
  .sec {
      font-size: 0.72rem; font-weight: 600; letter-spacing: 0.09em;
      text-transform: uppercase; color: #8a94a6;
      border-bottom: 1px solid #dfe3e8; padding-bottom: 0.35rem;
      margin: 1.6rem 0 0.9rem 0;
  }
  /* Taules */
  table.dv { border-collapse: collapse; font-size: 12px; text-align: center; }
  table.dv th, table.dv td { border: 1px solid #dfe3e8; padding: 4px 8px; white-space: nowrap; }
  table.dv th { font-weight: 600; font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase; }
  /* Taula general: ha de cabre sencera, sense scroll */
  table.dv.full { width: 100%; font-size: 11px; }
  table.dv.full th, table.dv.full td { padding: 3px 2px; }
  table.dv.full td.name, table.dv.full th.name { padding-left: 8px; padding-right: 6px; }
</style>
""", unsafe_allow_html=True)


def seccio(text):
    st.markdown(f'<div class="sec">{text}</div>', unsafe_allow_html=True)


# ===========================================================================
# IDIOMES
# ===========================================================================
IDIOMES = {"en": "English", "ca": "Català", "de": "Deutsch"}
IDIOMA_DEF = "en"

TXT = {
    "titol": {"ca": "Informes DataVolley", "de": "DataVolley-Berichte"},
    "subtitol": {"ca": "Tria els partits a analitzar.",
                 "de": "Wähle die Spiele zur Analyse."},
    "puja_per_comencar": {"ca": "Cap arxiu carregat.",
                          "de": "Keine Datei geladen."},
    "n_partits": {"ca": "{} partits", "de": "{} Spiele"},
    "sense_equip_comu": {"ca": "Cap equip juga a tots els arxius carregats. "
                               "Puja partits d'un mateix equip.",
                         "de": "Kein Team spielt in allen geladenen Dateien. "
                               "Lade Spiele desselben Teams hoch."},
    "comp_rivals": {"ca": "Rivals ({})", "de": "Gegner ({})"},
    "error_llegir": {"ca": "No s'ha pogut llegir l'arxiu: {}",
                     "de": "Datei konnte nicht gelesen werden: {}"},
    "sense_equips": {"ca": "No s'han trobat equips a l'arxiu.",
                     "de": "Keine Teams in der Datei gefunden."},
    "avis_scout": {"ca": "{} acció/ns sense jugador assignat (possible error de dorsal: {}). No es compten per jugador.",
                   "de": "{} Aktion(en) ohne zugewiesenen Spieler (möglicher Trikotnummer-Fehler: {}). Werden nicht pro Spieler gezählt."},
    "quin_equip": {"ca": "Equip", "de": "Team"},
    "ambit_label": {"ca": "Àmbit", "de": "Bereich"},
    "ambit_partit": {"ca": "Partit", "de": "Spiel"},
    "ambit_global": {"ca": "Global", "de": "Gesamt"},
    "ambit_jugador": {"ca": "Jugador", "de": "Spieler"},
    "ambit_comparativa": {"ca": "Comparativa", "de": "Vergleich"},
    "selecciona_jugador": {"ca": "Jugador", "de": "Spieler"},
    "sense_jugadors": {"ca": "No hi ha jugadors per aquest equip.",
                       "de": "Keine Spieler für dieses Team."},
    "metriques_mostrar": {"ca": "Mètriques", "de": "Kennzahlen"},
    "accions_mostrar": {"ca": "Accions", "de": "Aktionen"},
    "sense_metriques": {"ca": "Marca almenys una mètrica.",
                        "de": "Wähle mindestens eine Kennzahl."},
    "sense_dades": {"ca": "Sense dades per aquesta selecció.",
                    "de": "Keine Daten für diese Auswahl."},
    "objectius_header": {"ca": "Objectius", "de": "Ziele"},
    "dups_descartats": {"ca": "{} arxiu/s duplicat/s descartat/s (contingut idèntic).",
                        "de": "{} doppelte Datei(en) verworfen (identischer Inhalt)."},
    "netejar_tot": {"ca": "Treure tots els arxius",
                    "de": "Alle Dateien entfernen"},
    "carregar_titol": {"ca": "Carregar Partits", "de": "Spiele laden"},
    "tria_temporada": {"ca": "Temporada", "de": "Saison"},
    "tria_club": {"ca": "Club", "de": "Verein"},
    "tria_equip": {"ca": "Equip", "de": "Team"},
    "tria_quins": {"ca": "Quins partits?", "de": "Welche Spiele?"},
    "mode_tots": {"ca": "Tots els partits", "de": "Alle Spiele"},
    "mode_alguns": {"ca": "Un o uns quants", "de": "Eines oder mehrere"},
    "tria_partits": {"ca": "Partits", "de": "Spiele"},
    "carrega_tots": {"ca": "Carregar els {} partits", "de": "Alle {} Spiele laden"},
    "carrega_triats": {"ca": "Carregar els partits triats ({})",
                       "de": "Ausgewählte Spiele laden ({})"},
    "sense_temporades": {"ca": "No hi ha cap carpeta de temporada a {}.",
                         "de": "Kein Saison-Ordner in {}."},
    "sense_clubs_carpeta": {"ca": "No hi ha cap carpeta de club a {}.",
                            "de": "Kein Vereins-Ordner in {}."},
    "sense_equips_carpeta": {"ca": "No hi ha cap carpeta d'equip a {}.",
                             "de": "Kein Team-Ordner in {}."},
    "carpeta_buida": {"ca": "No hi ha cap .dvw a {}.",
                      "de": "Keine .dvw-Datei in {}."},
    "obj_placeholder": {"ca": "obj %", "de": "Ziel %"},
    "idioma": {"ca": "Idioma", "de": "Sprache"},
    # Mètriques
    "metrica_sideout": {"ca": "Side-out i contraatac", "de": "Side-out und Konter"},
    "rallies_exclosos": {"ca": "{} rally/s descartat/s (no s'hi identifica el saque).",
                         "de": "{} Rally(s) verworfen (Aufschlag nicht identifizierbar)."},
    "col_fase": {"ca": "Fase", "de": "Phase"},
    "fase_sideout": {"ca": "Side-out", "de": "Side-out"},
    "fase_contra": {"ca": "Contraatac", "de": "Konter"},
    "metrica_rotacio": {"ca": "Rendiment per rotació", "de": "Leistung nach Rotation"},
    "metrica_zones": {"ca": "Distribució d'atac per zona",
                      "de": "Angriffsverteilung nach Zone"},
    "col_zona": {"ca": "Zona", "de": "Zone"},
    "col_atacs": {"ca": "Atacs", "de": "Angriffe"},
    "col_pct": {"ca": "% del total", "de": "% gesamt"},
    "zones_descartats": {"ca": "{} atac/s sense zona deduïble (descartats)",
                         "de": "{} Angriff(e) ohne ableitbare Zone (verworfen)"},
    "col_rotacio": {"ca": "Rotació", "de": "Rotation"},
    "millor_pitjor_rot": {"ca": "Millor: {} ({}%) · Pitjor: {} ({}%)",
                          "de": "Beste: {} ({}%) · Schlechteste: {} ({}%)"},
    "metrica_taula_general": {"ca": "Taula general", "de": "Gesamttabelle"},
    "metrica_comparativa": {"ca": "Comparativa d'equips", "de": "Teamvergleich"},
    "comp_valor": {"ca": "Valor", "de": "Wert"},
    "metrica_desglossament": {"ca": "Desglossament", "de": "Aufschlüsselung"},
    "desglossament_agrupacio": {"ca": "Agrupació", "de": "Gruppierung"},
    "desglossament_set": {"ca": "Per set", "de": "Nach Satz"},
    "desglossament_partit": {"ca": "Per partit", "de": "Nach Spiel"},
    "metrica_evolucio": {"ca": "Evolució de temporada", "de": "Saisonverlauf"},
    "col_accio": {"ca": "Acció", "de": "Aktion"},
    "col_tendencia": {"ca": "Tendència", "de": "Tendenz"},
    "evolucio_peu": {"ca": "Eficàcia per partit, en ordre de calendari. "
                           "Tendència: mitjana de la segona meitat de la "
                           "temporada menys la de la primera, en punts.",
                     "de": "Effektivität pro Spiel, in Kalenderreihenfolge. "
                           "Tendenz: Mittel der zweiten Saisonhälfte minus "
                           "das der ersten, in Punkten."},
    "evolucio_un_partit": {"ca": "L'evolució necessita almenys dos partits carregats.",
                           "de": "Der Saisonverlauf braucht mindestens zwei geladene Spiele."},
    "col_set": {"ca": "Set", "de": "Satz"},
    "col_resultat": {"ca": "Resultat", "de": "Ergebnis"},
    "grp_rece": {"ca": "Recepció", "de": "Annahme"},
    "grp_atac": {"ca": "Atac", "de": "Angriff"},
    "grp_saque": {"ca": "Saque", "de": "Aufschlag"},
    "grp_bloc": {"ca": "Bloqueig", "de": "Block"},
    "col_tot": {"ca": "Tot.", "de": "Ges."},
    "grp_total": {"ca": "Balanç", "de": "Bilanz"},
    "fila_total": {"ca": "Total", "de": "Total"},
    "fila_pos": {"ca": "Eficàcia", "de": "Effektivität"},
    "fila_ef": {"ca": "Eficiència", "de": "Effizienz"},
    "col_jugador": {"ca": "Jugador", "de": "Spieler"},
    "valor_punts": {"ca": "Punts", "de": "Punkte"},
    "valor_errors": {"ca": "Errors", "de": "Fehler"},
    # Informe PDF
    "informe_titol": {"ca": "Informe", "de": "Bericht"},
    "baixar_pdf": {"ca": "Descarregar PDF", "de": "PDF herunterladen"},
    "pdf_error": {"ca": "No s'ha pogut generar el PDF.",
                  "de": "PDF konnte nicht erstellt werden."},
    "pdf_indisponible": {"ca": "Exportació a PDF no disponible (falta la font).",
                         "de": "PDF-Export nicht verfügbar (Schrift fehlt)."},
    "pdf_generat": {"ca": "Generat el", "de": "Erstellt am"},
}

# Anglès, per a la demo pública. Va en un bloc a part per no reescriure les
# entrades de TXT; `t()` el troba igual. tests/test_idiomes.py falla si una
# clau de TXT es queda sense alguna de les tres llengües.
_EN = {
    "titol": "DataVolley Reports",
    "subtitol": "Choose the matches to analyse.",
    "puja_per_comencar": "No file loaded.",
    "n_partits": "{} matches",
    "sense_equip_comu": "No team plays in every loaded file. "
                        "Load matches of a single team.",
    "comp_rivals": "Opponents ({})",
    "error_llegir": "Could not read the file: {}",
    "sense_equips": "No teams found in the file.",
    "avis_scout": "{} action(s) without an assigned player (possible jersey "
                  "number error: {}). Not counted per player.",
    "quin_equip": "Team",
    "ambit_label": "Scope",
    "ambit_partit": "Match",
    "ambit_global": "Overall",
    "ambit_jugador": "Player",
    "ambit_comparativa": "Comparison",
    "selecciona_jugador": "Player",
    "sense_jugadors": "No players for this team.",
    "metriques_mostrar": "Metrics",
    "accions_mostrar": "Skills",
    "sense_metriques": "Select at least one metric.",
    "sense_dades": "No data for this selection.",
    "objectius_header": "Targets",
    "dups_descartats": "{} duplicate file(s) discarded (identical content).",
    "netejar_tot": "Remove all files",
    "carregar_titol": "Load matches",
    "tria_temporada": "Season",
    "tria_club": "Club",
    "tria_equip": "Team",
    "tria_quins": "Which matches?",
    "mode_tots": "All matches",
    "mode_alguns": "One or several",
    "tria_partits": "Matches",
    "carrega_tots": "Load all {} matches",
    "carrega_triats": "Load selected matches ({})",
    "sense_temporades": "No season folder in {}.",
    "sense_clubs_carpeta": "No club folder in {}.",
    "sense_equips_carpeta": "No team folder in {}.",
    "carpeta_buida": "No .dvw file in {}.",
    "obj_placeholder": "target %",
    "idioma": "Language",
    "metrica_sideout": "Side-out and break point",
    "rallies_exclosos": "{} rally(s) discarded (serve could not be identified).",
    "col_fase": "Phase",
    "fase_sideout": "Side-out",
    "fase_contra": "Break point",
    "metrica_rotacio": "Performance by rotation",
    "metrica_zones": "Attack distribution by zone",
    "col_zona": "Zone",
    "col_atacs": "Attacks",
    "col_pct": "% of total",
    "zones_descartats": "{} attack(s) with no deducible zone (discarded)",
    "col_rotacio": "Rotation",
    "millor_pitjor_rot": "Best: {} ({}%) · Worst: {} ({}%)",
    "metrica_taula_general": "Overview table",
    "metrica_comparativa": "Team comparison",
    "comp_valor": "Value",
    "metrica_desglossament": "Breakdown",
    "desglossament_agrupacio": "Group by",
    "desglossament_set": "By set",
    "desglossament_partit": "By match",
    "metrica_evolucio": "Season trend",
    "col_accio": "Skill",
    "col_tendencia": "Trend",
    "evolucio_peu": "Efficacy per match, in calendar order. Trend: average "
                    "of the second half of the season minus the first half, "
                    "in points.",
    "evolucio_un_partit": "The season trend needs at least two matches loaded.",
    "col_set": "Set",
    "col_resultat": "Result",
    "grp_rece": "Reception",
    "grp_atac": "Attack",
    "grp_saque": "Serve",
    "grp_bloc": "Block",
    "col_tot": "Tot.",
    "grp_total": "Balance",
    "fila_total": "Total",
    "fila_pos": "Efficacy",
    "fila_ef": "Efficiency",
    "col_jugador": "Player",
    "valor_punts": "Points",
    "valor_errors": "Errors",
    "informe_titol": "Report",
    "baixar_pdf": "Download PDF",
    "pdf_error": "Could not generate the PDF.",
    "pdf_indisponible": "PDF export not available (font missing).",
    "pdf_generat": "Generated on",
}
for _clau, _text in _EN.items():
    TXT[_clau]["en"] = _text

NOMS = {
    "en": {"atacar": "Attack", "recepción": "Reception", "saque": "Serve", "bloqueo": "Block"},
    "ca": {"atacar": "Atac", "recepción": "Recepció", "saque": "Saque", "bloqueo": "Bloqueig"},
    "de": {"atacar": "Angriff", "recepción": "Annahme", "saque": "Aufschlag", "bloqueo": "Block"},
}

COLS = {
    "total": {"en": "Total", "ca": "Total", "de": "Gesamt"},
    "punts": {"en": "Points", "ca": "Punts", "de": "Punkte"},
    "efic":  {"en": "Efficacy", "ca": "Eficàcia", "de": "Effektivität"},
    "efn":   {"en": "Efficiency", "ca": "Eficiència", "de": "Effizienz"},
}


def get_lang():
    return st.session_state.get("lang", IDIOMA_DEF)


def t(key):
    e = TXT.get(key)
    if e is None:
        return key
    return e.get(get_lang(), e.get(IDIOMA_DEF, key))


# ===========================================================================
# LÒGICA DE DADES
# ===========================================================================
SKILL_MAP = {
    "Attack": "atacar", "Serve": "saque", "Reception": "recepción",
    "Block": "bloqueo", "Dig": "defensa", "Set": "colocación",
}
MARQUES = ['#', '+', '!', '-', '/', '=']
ACCIONS = ['recepción', 'atacar', 'saque', 'bloqueo']
MARGE_AMBRE = 2.5
ZONES_ORDRE = ['Z4', 'Z3', 'Z2', 'Z6', 'Z1']
MIN_ACCIONS_SET = 20  # sets amb menys accions que això es descarten (fantasma)
# Carpeta on deso els .dvw, al costat de l'app. Es llegeix, mai s'hi escriu.
CARPETA_PARTITS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Partits")

# Comptant RALLIES, tot rally té guanyador, o sigui que
# Eficiència ≡ 2 × Eficàcia − 100: no aporta cap informació nova.
# Posa-ho a False per amagar la columna a "Side-out i contraatac".
MOSTRA_EFN_RALLIES = True


def _norm_set(x):
    try:
        return int(float(x))
    except (ValueError, TypeError):
        return None


@st.cache_data(show_spinner=False)
def carregar_dvw(file_bytes):
    with tempfile.NamedTemporaryFile(suffix=".dvw", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        res = dv.read_dv(tmp_path)
        df = pd.DataFrame(res)
    finally:
        os.unlink(tmp_path)
    return df


def carregar_partits(fitxers):
    """Concatena els .dvw carregats afegint match_id (cal per no barrejar
    partits al side-out ni a la deducció de zona)."""
    dfs = []
    for i, (nom, bytes_) in enumerate(fitxers):
        d = carregar_dvw(bytes_).copy()
        d['match_id'] = i
        d['match_nom'] = nom
        dfs.append(d)
    return pd.concat(dfs, ignore_index=True)


def equips_comuns(df):
    """Equips que juguen a TOTS els partits carregats (amb 1 fitxer, els dos).

    Ordenats amb el local del primer partit primer.
    """
    per_partit = [set(g['team'].dropna().unique())
                  for _, g in df.groupby('match_id')]
    if not per_partit:
        return []
    comuns = set.intersection(*per_partit)
    primer = df[df['match_id'] == df['match_id'].min()]
    _h = primer['home_team'].dropna().unique()
    ordre = []
    if len(_h) and _h[0] in comuns:
        ordre.append(_h[0])
    ordre += [e for e in primer['team'].dropna().unique()
              if e in comuns and e not in ordre]
    ordre += [e for e in comuns if e not in ordre]
    return ordre


def info_partits(df, fitxers):
    """Per cada partit: equips i marcador oficial (de la secció [3SET])."""
    out = []
    for i, (nom, bytes_) in enumerate(fitxers):
        g = df[df['match_id'] == i]
        hn = g['home_team'].dropna().unique()
        vn = g['visiting_team'].dropna().unique()
        sets = marcador_sets(bytes_)
        out.append({
            'home': hn[0] if len(hn) else "?",
            'visiting': vn[0] if len(vn) else "?",
            'data': data_partit(bytes_),
            'sets': sets,
            'gh': sum(1 for a, b in sets if a > b),
            'gv': sum(1 for a, b in sets if b > a),
        })
    return out


@st.cache_data(show_spinner=False)
def data_partit(file_bytes):
    """Data del partit, del primer camp de la secció [3MATCH] (dd/mm/aaaa).

    Hi és als 14 partits meus, sense excepció. L'hora (camp 2) només a 4,
    i la lliga (camp 4) porta errors de plantilla: no s'usen. Torna None si
    falta o no es pot llegir, i llavors el partit va al final de l'ordre
    cronològic conservant l'ordre de pujada.
    """
    raw = file_bytes.decode('latin-1', errors='ignore')
    i = raw.find('[3MATCH]')
    if i < 0:
        return None
    for line in raw[i:].splitlines()[1:]:
        if line.startswith('['):     # secció següent: no hi havia data
            break
        camp = line.split(';')[0].strip()
        if not camp:
            continue
        try:
            return datetime.datetime.strptime(camp, '%d/%m/%Y').date()
        except ValueError:
            return None
    return None


def escaneja_carpeta(carpeta):
    """Tots els .dvw de la carpeta (i subcarpetes), sense duplicats de
    contingut. Recursiu perquè funcioni tant si tinc els partits solts com si
    els separo per temporada o per equip en subcarpetes."""
    if not os.path.isdir(carpeta):
        return []
    vistos, out = set(), []
    for arrel, _dirs, noms in os.walk(carpeta):
        for nom in sorted(noms):
            if not nom.lower().endswith('.dvw'):
                continue
            cami = os.path.join(arrel, nom)
            try:
                with open(cami, 'rb') as f:
                    b = f.read()
            except OSError:
                continue
            h = hashlib.md5(b).hexdigest()
            if h in vistos:
                continue
            vistos.add(h)
            out.append((nom, b))
    return out


def subcarpetes(cami):
    """Noms de les subcarpetes directes, ordenats. Buit si el camí no hi és.

    `Partits/` està organitzada `<temporada>/<club>/<equip>/`, o sigui que
    temporada, club i equip es llegeixen de l'arbre de carpetes i no cal
    deduir-los de dins dels arxius: la carpeta ja diu de qui és cada partit."""
    if not os.path.isdir(cami):
        return []
    return sorted(n for n in os.listdir(cami)
                  if os.path.isdir(os.path.join(cami, n)))


def primer_amb_partits(base, noms):
    """Índex del primer nom que té algun .dvw a dins; 0 si cap en té.

    És el valor per defecte dels desplegables: la temporada nova s'estrena
    buida (i un equip pot no haver jugat encara), i obrir sempre a una carpeta
    sense partits obligaria a canviar el desplegable cada vegada."""
    for i, n in enumerate(noms):
        for _arrel, _dirs, fitxers in os.walk(os.path.join(base, n)):
            if any(f.lower().endswith('.dvw') for f in fitxers):
                return i
    return 0


def _data_curta(d, anys=False):
    """dd/mm (o dd/mm/aa) per etiquetes. '—' si el partit no porta data."""
    if not d:
        return "—"
    return f"{d:%d/%m/%y}" if anys else f"{d:%d/%m}"


def ordena_per_data(fitxers):
    """Ordena els arxius per data de partit. Els que no en tenen queden al
    final en l'ordre de pujada. És l'ÚNIC lloc on s'ordena: el `match_id`
    surt d'aquest ordre, o sigui que tot el que va per match_id (side-out,
    zones, desglossament) ja queda cronològic."""
    amb_data = [(data_partit(b), i, (nom, b))
                for i, (nom, b) in enumerate(fitxers)]
    amb_data.sort(key=lambda x: (x[0] is None, x[0] or datetime.date.min, x[1]))
    return [f for _, _, f in amb_data]


@st.cache_data(show_spinner=False)
def marcador_sets(file_bytes):
    """Marcadors oficials de cada set, de la secció [3SET] del .dvw."""
    raw = file_bytes.decode('latin-1', errors='ignore')
    i = raw.find('[3SET]')
    if i < 0:
        return []
    j = raw.find('[', i + 3)
    bloc = raw[i:j] if j > 0 else raw[i:]
    sets = []
    for line in bloc.splitlines()[1:]:
        parts = line.split(';')
        if len(parts) < 5:
            continue
        final = parts[4].strip()
        if not final or '-' not in final:
            continue
        try:
            a, b = final.split('-')
            sets.append((int(a.strip()), int(b.strip())))
        except ValueError:
            continue
    return sets


def _fases_atac(d):
    """Marca cada atac com a side-out o contraatac. `d` són files ja filtrades
    (un equip o diversos). El shift va per (partit, equip) per no encadenar
    accions de partits diferents."""
    d = d[d['skill'].isin(['Reception', 'Set', 'Attack'])].copy().sort_index()
    atk = d[d['skill'] == 'Attack']
    if atk.empty:
        return atk.assign(fase=None)
    d['prev'] = d.groupby(['match_id', 'team'])['skill'].shift(1)
    d['prev2'] = d.groupby(['match_id', 'team'])['skill'].shift(2)
    atk = d[d['skill'] == 'Attack'].copy()

    def _cls(r):
        if r['prev'] == 'Reception' or (r['prev'] == 'Set' and r['prev2'] == 'Reception'):
            return 'sideout'
        return 'contra'
    atk['fase'] = atk.apply(_cls, axis=1)
    return atk


def _taula_fases(atk):
    out = []
    for fase in ['sideout', 'contra']:
        sub = atk[atk['fase'] == fase]
        total = len(sub)
        if total == 0:
            continue
        pos = sub['evaluation_code'].isin(['#', '+']).sum()
        pun = (sub['evaluation_code'] == '#').sum()
        err = (sub['evaluation_code'] == '=').sum()
        out.append({
            'fase': fase, 'total': total,
            'efic': round(pos / total * 100, 1),
            'efn': round((pun - err) / total * 100, 1),
        })
    return pd.DataFrame(out)


def rallies_equip(df, equip):
    """Un rally per fila: (match_id, set_number, _set, fase, guanyat).

    Delimitació: cada fila `skill == 'Point'` tanca un rally i el seu `team`
    és qui el guanya. El sacador és el `team` de la fila 'Serve' del rally.

    ATENCIÓ amb els camps del parser (verificat amb els meus arxius):
      - `rally_number` és sempre 1: no delimita res.
      - `point_won_by` és constant a tot l'arxiu: inservible.
      - `serving_team` només coincideix amb el 'Serve' real un ~50%.
    Comptar els 'Point' sí que reprodueix el marcador oficial de [3SET].

    fase: 'contra' si saquem nosaltres (break-point), 'sideout' si rep el
    nostre equip. Retorna (rallies, exclosos): els rallies amb Point però
    sense Serve identificable es descarten (≈1,5% als meus arxius).
    """
    partits_equip = df.loc[df['team'] == equip, 'match_id'].unique()
    d = df[df['match_id'].isin(partits_equip)].copy()
    if d.empty:
        return pd.DataFrame(columns=['match_id', 'set_number', '_set', 'fase', 'guanyat']), 0

    # El Point tanca el rally: el següent comença a la fila de després.
    d['_fi'] = d['skill'] == 'Point'
    d['_rally'] = (d.groupby(['match_id', 'set_number'])['_fi']
                    .transform(lambda s: s.shift(1, fill_value=False).cumsum()))
    K = ['match_id', 'set_number', '_rally']
    sacador = d[d['skill'] == 'Serve'].groupby(K)['team'].first().rename('sacador')
    guanyador = d[d['skill'] == 'Point'].groupby(K)['team'].first().rename('guanyador')
    r = pd.concat([sacador, guanyador], axis=1)

    # Sense Point no és un rally complet (cua residual al final del set).
    complets = r[r['guanyador'].notna()]
    valids = complets[complets['sacador'].notna()].reset_index()
    exclosos = len(complets) - len(valids)

    valids['_set'] = valids['set_number'].map(_norm_set)
    valids['fase'] = ['contra' if s == equip else 'sideout' for s in valids['sacador']]
    valids['guanyat'] = valids['guanyador'] == equip
    return valids[['match_id', 'set_number', '_set', 'fase', 'guanyat']], exclosos


def _taula_rallies(r):
    """Compta RALLIES (no atacs): cada rally hi surt exactament un cop.

    Eficàcia = guanyats / totals. Eficiència = (guanyats − perduts) / totals;
    com que tot rally té guanyador, perduts = totals − guanyats i per tant
    Eficiència ≡ 2 × Eficàcia − 100 (redundant). Vegeu MOSTRA_EFN_RALLIES.
    """
    out = []
    for fase in ['sideout', 'contra']:
        sub = r[r['fase'] == fase]
        total = len(sub)
        guanyats = int(sub['guanyat'].sum())
        perduts = total - guanyats
        out.append({
            'fase': fase, 'total': total,
            'efic': round(guanyats / total * 100, 1) if total else 0.0,
            'efn': round((guanyats - perduts) / total * 100, 1) if total else 0.0,
        })
    return pd.DataFrame(out)


def sideout_contra(df, equip, jugador=None):
    """Side-out i contraatac. Retorna (taula, rallies_exclosos).

    Àmbit equip: compta RALLIES sencers (un rally = un cop, encara que hi
    hagi diversos atacs). Àmbit jugador: un rally és d'equip i no s'atribueix
    a un jugador, així que allà es continuen comptant els seus ATACS.
    """
    if jugador is not None:
        atk = _fases_atac(df[df['team'] == equip])
        return _taula_fases(atk[atk['player_name'] == jugador]), 0
    r, exclosos = rallies_equip(df, equip)
    return _taula_rallies(r), exclosos


def rendiment_rotacio(df, equip, jugador=None):
    """Eficàcia/eficiència d'atac per rotació (posició del col·locador)."""
    d = df[(df['team'] == equip) & (df['skill'] == 'Attack') & df['setter_position'].notna()].copy()
    if jugador is not None:
        d = d[d['player_name'] == jugador]
    d['rot'] = d['setter_position'].astype(str)

    out = []
    for rot in ['1', '2', '3', '4', '5', '6']:
        sub = d[d['rot'] == rot]
        total = len(sub)
        if total == 0:
            continue
        pos = sub['evaluation_code'].isin(['#', '+']).sum()
        pun = (sub['evaluation_code'] == '#').sum()
        err = (sub['evaluation_code'] == '=').sum()
        out.append({
            'rot': f"P{rot}", 'total': total, 'punts': int(pun),
            'efic': round(pos / total * 100, 1),
            'efn': round((pun - err) / total * 100, 1),
        })
    return pd.DataFrame(out)


# --- Zona d'atac deduïda (start_zone/end_zone són buits als scouts) -----------
def _norm_dorsal(x):
    """A la formació els dorsals són text i a player_number són float."""
    try:
        return str(int(float(x)))
    except (ValueError, TypeError):
        return None


def _zona_fila(row, prefix, fase=None):
    """Zona d'atac d'una acció, assumint 5-1. None si no es pot deduir.

    Posició a pista = creuar el dorsal amb {prefix}_p1..p6; rol =
    (posició - setter_position) % 6 → 0=col·locador, 1=receptor1, 2=central1,
    3=opposite, 4=receptor2, 5=central2. Davanter = posicions 2, 3, 4.

    El rol dóna la zona perquè dóna per fet el canvi de lloc després del
    saque. A R1 (col·locador a P1) aquest canvi no es pot fer en la pilota de
    SIDE-OUT: la davantera és opposite a P4, central a P3 i receptor a P2, i
    creuar mitja pista mentre es rep no dóna temps. O sigui que en aquest cas
    la zona és la posició tal qual (P4 → Z4, P2 → Z2), i per això l'opposite
    hi surt atacant per 4. Al contraatac ja han canviat: mana el rol.

    ATENCIÓ: la fase ve de `_fases_atac` (atac just després de la nostra
    recepció), no de la columna `attack_phase` de l'arxiu, que sembla que
    hauria de servir però no: als 14 partits diu "Transition" a 3.108 atacs
    de 3.160 i només marca 52 com a "Reception".
    """
    dorsal = _norm_dorsal(row['player_number'])
    if dorsal is None:
        return None
    posicio = None
    for p in range(1, 7):
        if _norm_dorsal(row[f'{prefix}_p{p}']) == dorsal:
            posicio = p
            break
    if posicio is None:
        return None
    sp = _norm_dorsal(row[f'{prefix}_setter_position'])
    if sp is None:
        return None
    rol = (posicio - int(sp)) % 6
    davanter = posicio in (2, 3, 4)
    if int(sp) == 1 and davanter and fase == 'sideout':
        return f"Z{posicio}"
    if rol in (2, 5):        # central: només ataca de davanter
        return 'Z3' if davanter else None
    if rol in (1, 4):        # receptor
        return 'Z4' if davanter else 'Z6'
    if rol == 3:             # opposite
        return 'Z2' if davanter else 'Z1'
    if rol == 0:             # col·locador: dump només de davanter
        return 'Z2' if davanter else None
    return None


def atacs_amb_zona(df, equip, jugador=None):
    """Atacs de l'equip amb la zona deduïda.

    El prefix (home/visiting) es mira fila a fila: amb diversos partits el
    mateix equip pot ser local en un i visitant en un altre.
    """
    d = df[(df['team'] == equip) & (df['skill'] == 'Attack')].copy()
    if jugador is not None:
        d = d[d['player_name'] == jugador]
    if d.empty or 'home_p1' not in df.columns:
        return d.assign(zona=None)
    # La fase es calcula amb TOT l'equip encara que després mirem un jugador:
    # filtrant primer es perdria la recepció que va just abans de l'atac.
    fases = _fases_atac(df[df['team'] == equip])['fase']
    zones = []
    for idx, r in d.iterrows():
        prefix = 'home' if r['team'] == r['home_team'] else 'visiting'
        zones.append(_zona_fila(r, prefix, fases.get(idx)))
    d['zona'] = zones
    return d


def distribucio_zona(df, equip, jugador=None):
    """Taula per zona (Z4, Z3, Z2, Z6, Z1) i nombre d'atacs descartats."""
    d = atacs_amb_zona(df, equip, jugador)
    amb = d[d['zona'].notna()]
    total = len(amb)
    out = []
    for z in ZONES_ORDRE:
        sub = amb[amb['zona'] == z]
        n = len(sub)
        if n == 0:
            continue
        pos = sub['evaluation_code'].isin(['#', '+']).sum()
        pun = (sub['evaluation_code'] == '#').sum()
        err = (sub['evaluation_code'] == '=').sum()
        out.append({
            'zona': z, 'atacs': n, 'pct': round(n / total * 100, 1),
            'efic': round(pos / n * 100, 1),
            'efn': round((pun - err) / n * 100, 1),
            'punts': int(pun),
        })
    return pd.DataFrame(out), len(d) - total


def color_valor(v):
    return C_VERD if v > 0 else (C_ROIG if v < 0 else C_AMBRE)


def color_semafor(efic, obj):
    if obj is None:
        return None
    if efic > obj + MARGE_AMBRE:
        return C_VERD
    elif efic >= obj - MARGE_AMBRE:
        return C_AMBRE
    return C_ROIG


def badge_avis(n, tooltip):
    """Icona d'advertència amb comptador vermell, estil notificació d'app."""
    return (
        f'<div style="text-align:right;" title="{tooltip}">'
        f'<span style="position:relative;display:inline-block;line-height:0;cursor:help;">'
        f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="{MUTED}" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
        f'<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
        f'<span style="position:absolute;top:-7px;right:-9px;background:#dc2626;color:#fff;'
        f'border-radius:999px;min-width:17px;height:17px;font-size:10px;line-height:17px;'
        f'text-align:center;padding:0 4px;font-weight:700;box-sizing:border-box;">{n}</span>'
        f'</span></div>'
    )


def taula_simple(headers, rows, cell_bg=None):
    """Renderitza una taula petita amb l'estil de l'app.

    cell_bg: dict {(fila, columna): color} per pintar cel·les concretes.
    """
    cell_bg = cell_bg or {}
    h = ['<table class="dv"><tr>']
    for i, c in enumerate(headers):
        align = "text-align:left;" if i == 0 else ""
        h.append(f'<th style="background:{HDR_BG};color:#fff;{align}">{c}</th>')
    h.append('</tr>')
    for n, r in enumerate(rows):
        bg = PAPER if n % 2 == 0 else ROW_ALT
        h.append('<tr>')
        for i, c in enumerate(r):
            align = "text-align:left;font-weight:600;" if i == 0 else ""
            _c = cell_bg.get((n, i))
            if _c:
                h.append(f'<td style="background:{_c};color:{INK};font-weight:700;{align}">{c}</td>')
            else:
                h.append(f'<td style="background:{bg};color:{INK};{align}">{c}</td>')
        h.append('</tr>')
    h.append('</table>')
    html = "".join(h)
    st.markdown(html, unsafe_allow_html=True)
    return html


# ===========================================================================
# EXPORTACIÓ A PDF
# ===========================================================================
PDF_CSS = """
@page { size: A4 landscape; margin: 1.0cm 1.2cm; }
body { font-family: AppSans; color: #111827; font-size: 9px; }
.pdf-title { font-size: 15px; font-weight: bold; margin: 0 0 2px 0; }
.pdf-meta { color: #6b7280; font-size: 9px; margin: 1px 0; }
.pdf-score { font-size: 13px; font-weight: bold; margin: 4px 0 0 0; }
.pdf-parcials { color: #6b7280; font-size: 9px; font-weight: normal; }
.pdf-rule { border-bottom: 1px solid #dfe3e8; margin: 7px 0 10px 0; }
.pdf-sec { font-size: 9px; font-weight: bold; color: #37485f;
           margin: 13px 0 5px 0; -pdf-keep-with-next: true; }
.pdf-cap { color: #6b7280; font-size: 8px; margin: 4px 0 0 0; }
table.dv { border-collapse: collapse; text-align: center; font-size: 9px; }
/* line-height baix: reportlab centra la línia de base, però amb interlineat
   gran el text queda enganxat a dalt; 0.9 el deixa centrat a la cel·la. */
table.dv th, table.dv td { border: 1px solid #dfe3e8; padding: 3px 6px; line-height: 0.9; }
table.dv th { font-weight: bold; }
table.dv.full { width: 100%; font-size: 7px; table-layout: fixed; }
table.dv.full th, table.dv.full td { padding: 2px 1px; }
table.dv.full th.name, table.dv.full td.name { width: 130px; text-align: left;
                                               padding-left: 4px; padding-right: 4px; }
/* Maquetació de seccions de costat (side-out + rotació) */
table.pdf-cols { width: 100%; border-collapse: collapse; }
table.pdf-cols td.pdf-col { vertical-align: top; border: none; padding: 12px 14px 0 0; }
"""


def capcalera_pdf(equip, jugador, partits, titol=None):
    """Bloc de context a dalt del PDF: qui, partit(s), marcador i data.

    Amb un partit mostra el marcador gran i els parcials; amb diversos, la
    llista de partits amb el seu resultat.
    """
    qui = titol if titol else (jugador if jugador else equip)
    parts = [f'<div class="pdf-title">{qui}</div>']
    if len(partits) == 1:
        p = partits[0]
        parts.append(f'<div class="pdf-meta">{p["home"]} · {p["visiting"]}</div>')
        if p['sets']:
            parc = "&nbsp;&nbsp;".join(f"{a}-{b}" for a, b in p['sets'])
            parts.append(f'<div class="pdf-score">{p["gh"]} – {p["gv"]} '
                         f'<span class="pdf-parcials">({parc})</span></div>')
    else:
        parts.append(f'<div class="pdf-meta">{t("n_partits").format(len(partits))}</div>')
        for p in partits:
            sc = f"{p['gh']} – {p['gv']}" if p['sets'] else "·"
            parts.append(f'<div class="pdf-meta">{p["home"]} &nbsp;{sc}&nbsp; '
                         f'{p["visiting"]}</div>')
    avui = datetime.date.today().strftime("%d/%m/%Y")
    parts.append(f'<div class="pdf-meta">{t("pdf_generat")} {avui}</div>')
    parts.append('<div class="pdf-rule"></div>')
    return "".join(parts)


def _bloc_pdf(bloc):
    """Un 'bloc' és una llista de (títol, html). Amb 1 element va a tota amplada;
    amb més, es col·loquen de costat amb una taula de maquetació."""
    if len(bloc) == 1:
        titol, html = bloc[0]
        return f'<div class="pdf-sec">{titol}</div>{html}'
    amp = round(100 / len(bloc), 4)
    cel = [f'<td class="pdf-col" style="width:{amp}%;">'
           f'<div class="pdf-sec">{titol}</div>{html}</td>'
           for titol, html in bloc]
    return f'<table class="pdf-cols"><tr>{"".join(cel)}</tr></table>'


def generar_pdf(capcalera, blocs):
    """Munta l'HTML complet i el converteix a bytes PDF. None si falla.

    `blocs` és una llista de blocs; cada bloc és una llista de (títol, html).
    """
    parts = ['<html><head><meta charset="utf-8"><style>', PDF_CSS,
             '</style></head><body>', capcalera]
    for bloc in blocs:
        parts.append(_bloc_pdf(bloc))
    parts.append('</body></html>')
    doc = "".join(parts)
    buf = io.BytesIO()
    res = pisa.CreatePDF(io.BytesIO(doc.encode("utf-8")), dest=buf, encoding="utf-8")
    if res.err:
        return None
    return buf.getvalue()


def _nom_fitxer(qui, n_partits=1, prefix=None):
    """Nom del PDF. Amb diversos partits ho diu, per no trepitjar arxius."""
    net = "".join(c if c.isalnum() or c in " -_" else "_" for c in str(qui)).strip()
    net = "_".join(net.split()) or "informe"
    if prefix is None:
        prefix = "Global" if n_partits > 1 else "Informe"
    if n_partits > 1:
        return f"{prefix}_{net}_{n_partits}_partits.pdf"
    return f"{prefix}_{net}.pdf"


# ===========================================================================
# MÈTRIQUES
# ===========================================================================
def metrica_sideout(df, equip, jugador, lang):
    taula, exclosos = sideout_contra(df, equip, jugador)
    if taula.empty:
        st.caption(t("sense_dades"))
        return None
    fase_noms = {"sideout": t("fase_sideout"), "contra": t("fase_contra")}
    headers = [t("col_fase"), COLS['total'][lang], COLS['efic'][lang]]
    if MOSTRA_EFN_RALLIES or jugador is not None:
        headers.append(COLS['efn'][lang])
    rows = []
    for _, r in taula.iterrows():
        fila = [fase_noms[r['fase']], int(r['total']), f"{r['efic']}%"]
        if MOSTRA_EFN_RALLIES or jugador is not None:
            fila.append(f"{r['efn']}%")
        rows.append(fila)
    html = taula_simple(headers, rows)
    if exclosos:
        cap = t("rallies_exclosos").format(exclosos)
        st.caption(cap)
        html += f'<div class="pdf-cap">{cap}</div>'
    return html


def metrica_rotacio(df, equip, jugador, lang):
    taula = rendiment_rotacio(df, equip, jugador)
    if taula.empty:
        st.caption(t("sense_dades"))
        return None
    headers = [t("col_rotacio"), COLS['total'][lang], COLS['punts'][lang],
               COLS['efic'][lang], COLS['efn'][lang]]
    rows = [[r['rot'], int(r['total']), int(r['punts']), f"{r['efic']}%", f"{r['efn']}%"]
            for _, r in taula.iterrows()]
    html = taula_simple(headers, rows)
    if len(taula) >= 2:
        millor = taula.loc[taula['efic'].idxmax()]
        pitjor = taula.loc[taula['efic'].idxmin()]
        cap = t("millor_pitjor_rot").format(
            millor['rot'], millor['efic'], pitjor['rot'], pitjor['efic'])
        st.caption(cap)
        html += f'<div class="pdf-cap">{cap}</div>'
    return html


def metrica_zones(df, equip, jugador, lang):
    """Atacs per zona: on carrega l'equip, o per on ataca un jugador.

    Amb jugador, la zona ja surt de la seva posició respecte del col·locador a
    cada rotació (vegeu `_zona_fila`), o sigui que l'opposite hi surt repartida
    entre Z2, Z4 (R1 en recepció) i Z1 de zaguera.
    """
    taula, descartats = distribucio_zona(df, equip, jugador)
    if taula.empty:
        st.caption(t("sense_dades"))
        return None
    headers = [t("col_zona"), t("col_atacs"), t("col_pct"),
               COLS['efic'][lang], COLS['efn'][lang], COLS['punts'][lang]]
    # Verd on més carrega i roig on menys, per veure d'un cop la distribució.
    cell_bg = {}
    if len(taula) >= 2:
        cell_bg[(int(taula['atacs'].argmax()), 1)] = C_VERD
        cell_bg[(int(taula['atacs'].argmin()), 1)] = C_ROIG
    rows = [[r['zona'], int(r['atacs']), f"{r['pct']}%", f"{r['efic']}%",
             f"{r['efn']}%", int(r['punts'])] for _, r in taula.iterrows()]
    html = taula_simple(headers, rows, cell_bg)
    if descartats:
        cap = t("zones_descartats").format(descartats)
        st.caption(cap)
        html += f'<div class="pdf-cap">{cap}</div>'
    return html


def metrica_taula_general(df, equip, lang, jugador=None):
    """Totes les marques per jugador + punts/errors/valor."""
    ACC = [
        ("rece", "Reception", ['#', '+', '!', '-', '/', '=']),
        ("atac", "Attack",    ['#', '+', '!', '-', '/', '=']),
        ("saque", "Serve",    ['#', '/', '+', '!', '-', '=']),
        ("bloc", "Block",     ['#', '+', '!', '-', '/', '=']),
    ]
    grp_label = {"rece": t("grp_rece"), "atac": t("grp_atac"),
                 "saque": t("grp_saque"), "bloc": t("grp_bloc")}
    SKILL_A_ACC = {"Reception": "recepción", "Attack": "atacar",
                   "Serve": "saque", "Block": "bloqueo"}

    d = df[(df['team'] == equip) & df['skill'].isin(['Reception', 'Attack', 'Serve', 'Block'])].copy()
    if d.empty:
        st.caption(t("sense_dades"))
        return None

    # --- Selector d'accions (només en àmbit jugador) ---
    _bal = True
    if jugador is not None:
        st.caption(t("accions_mostrar"))
        _acols = st.columns(len(ACC) + 1)
        _sel = []
        for _i, (_k, _sk, _m) in enumerate(ACC):
            with _acols[_i]:
                if st.checkbox(grp_label[_k], value=True, key=f"acc_vis_{_k}"):
                    _sel.append(_k)
        with _acols[len(ACC)]:
            _bal = st.checkbox(t("grp_total"), value=True, key="acc_vis_balanc")
        ACC = [a for a in ACC if a[0] in _sel]
        if not ACC and not _bal:
            st.caption(t("sense_metriques"))
            return None

    # Accions visibles (claus internes), en l'ordre estàndard
    _visibles = [SKILL_A_ACC[sk] for _k, sk, _m in ACC]
    _objectius_acc = [a for a in ACCIONS if a in _visibles]

    # --- Objectius ---
    if "obj_store" not in st.session_state:
        st.session_state["obj_store"] = {a: None for a in ACCIONS}
    st.caption(t("objectius_header"))
    _ocols = st.columns(len(_objectius_acc))
    for _i, _acc in enumerate(_objectius_acc):
        with _ocols[_i]:
            _v = st.number_input(
                NOMS[lang][_acc],
                min_value=0.0, max_value=100.0,
                value=st.session_state["obj_store"].get(_acc),
                step=1.0, placeholder=t("obj_placeholder"),
                key=f"obj_input_{_acc}",
            )
            st.session_state["obj_store"][_acc] = _v
    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    cnt = d.groupby(['player_name', 'skill', 'evaluation_code']).size()
    nums = d.groupby('player_name')['player_number'].first()
    players = sorted(nums.index, key=lambda p: (nums[p] if pd.notna(nums[p]) else 999))
    if jugador is not None:
        players = [p for p in players if p == jugador]
        if not players:
            st.caption(t("sense_dades"))
            return None

    def g(p, sk, ev):
        try:
            return int(cnt.loc[(p, sk, ev)])
        except KeyError:
            return 0

    def punts_errors(p):
        pts = g(p, 'Attack', '#') + g(p, 'Serve', '#') + g(p, 'Block', '#')
        err = g(p, 'Attack', '=') + g(p, 'Serve', '=') + g(p, 'Reception', '=') + g(p, 'Block', '/')
        return pts, err

    HDR = f"background:{HDR_BG};color:#fff;"
    SUB = f"background:{SUB_BG};color:#fff;"
    JUG = f"background:{SOFT};color:{INK};font-weight:600;text-align:left;"
    TOT = f"background:{SOFT};color:{INK};font-weight:600;"
    TOTROW = f"background:{TOTAL_BG};color:{INK};font-weight:600;"
    PEF = f"background:{SOFT};color:{MUTED};font-weight:600;"

    h = ['<table class="dv full">']

    # Capçalera 1
    h.append('<tr>')
    h.append(f'<th rowspan="2" class="name" style="{HDR}text-align:left;">{t("col_jugador")}</th>')
    for k, sk, marks in ACC:
        h.append(f'<th colspan="{len(marks) + 1}" style="{HDR}">{grp_label[k]}</th>')
    if _bal:
        h.append(f'<th colspan="3" style="{HDR}">{t("grp_total")}</th>')
    h.append('</tr>')

    # Capçalera 2
    h.append('<tr>')
    for k, sk, marks in ACC:
        for m in marks:
            h.append(f'<th style="{SUB}">{m}</th>')
        h.append(f'<th style="{SUB}">{t("col_tot")}</th>')
    if _bal:
        h.append(f'<th style="{SUB}">{t("valor_punts")}</th>')
        h.append(f'<th style="{SUB}">{t("valor_errors")}</th>')
        h.append(f'<th style="{SUB}">+/-</th>')
    h.append('</tr>')

    # Cos
    for n, p in enumerate(players):
        bg = PAPER if n % 2 == 0 else ROW_ALT
        h.append('<tr>')
        h.append(f'<td class="name" style="{JUG}">{p}</td>')
        for k, sk, marks in ACC:
            for m in marks:
                val = g(p, sk, m)
                txt = val if val else '<span style="color:#c9ced6">·</span>'
                h.append(f'<td style="background:{bg};color:{INK};">{txt}</td>')
            h.append(f'<td style="{TOT}">{sum(g(p, sk, m) for m in marks)}</td>')
        if _bal:
            _p, _e = punts_errors(p)
            v = _p - _e
            h.append(f'<td style="{TOT}">{_p}</td>')
            h.append(f'<td style="{TOT}">{_e}</td>')
            h.append(f'<td style="background:{color_valor(v)};color:{INK};font-weight:700;">{v:+d}</td>')
        h.append('</tr>')

    # Fila Total
    if len(players) > 1:
        h.append('<tr>')
        h.append(f'<td style="{TOTROW}text-align:left;">{t("fila_total")}</td>')
        for k, sk, marks in ACC:
            for m in marks:
                h.append(f'<td style="{TOTROW}">{sum(g(p, sk, m) for p in players)}</td>')
            h.append(f'<td style="{TOTROW}">{sum(g(p, sk, m) for p in players for m in marks)}</td>')
        if _bal:
            _tp = sum(punts_errors(p)[0] for p in players)
            _te = sum(punts_errors(p)[1] for p in players)
            h.append(f'<td style="{TOTROW}">{_tp}</td>')
            h.append(f'<td style="{TOTROW}">{_te}</td>')
            h.append(f'<td style="background:{color_valor(_tp - _te)};color:{INK};font-weight:700;">{_tp - _te:+d}</td>')
        h.append('</tr>')

    # Positivitat i Eficiència
    def team_stat(sk, kind):
        total = sum(g(p, sk, m) for p in players for m in MARQUES)
        if total == 0:
            return "-"
        if kind == "pos":
            val = (sum(g(p, sk, m) for p in players for m in ['#', '+']) / total) * 100
        else:
            val = ((sum(g(p, sk, '#') for p in players) - sum(g(p, sk, '=') for p in players)) / total) * 100
        return f"{round(val)}%"

    for kind, lab in [("pos", t("fila_pos")), ("ef", t("fila_ef"))]:
        h.append('<tr>')
        h.append(f'<td style="{PEF}text-align:left;">{lab}</td>')
        for k, sk, marks in ACC:
            _txt = team_stat(sk, kind)
            _style = PEF + f"color:{INK};"
            if kind == "pos" and _txt != "-":
                _bg = color_semafor(float(_txt.rstrip('%')), st.session_state["obj_store"].get(SKILL_A_ACC[sk]))
                if _bg:
                    _style = f"background:{_bg};color:{INK};font-weight:700;"
            h.append(f'<td colspan="{len(marks) + 1}" style="{_style}">{_txt}</td>')
        if _bal:
            h.append(f'<td colspan="3" style="{PEF}"></td>')
        h.append('</tr>')

    h.append('</table>')
    html = "".join(h)
    st.markdown(html, unsafe_allow_html=True)
    return html


def _stats_df(d):
    """Eficàcia/eficiència per acció + punts/errors/valor. `d` són files ja
    filtrades (un equip, o diversos si s'agreguen els rivals)."""
    d = d[d['skill'].isin(['Reception', 'Attack', 'Serve', 'Block'])]
    cnt = d.groupby(['skill', 'evaluation_code']).size()

    def g(sk, ev):
        try:
            return int(cnt.loc[(sk, ev)])
        except KeyError:
            return 0

    out = {}
    for acc, sk in [('recepción', 'Reception'), ('atacar', 'Attack'),
                    ('saque', 'Serve'), ('bloqueo', 'Block')]:
        total = sum(g(sk, m) for m in MARQUES)
        if total:
            out[acc] = {'efic': (g(sk, '#') + g(sk, '+')) / total * 100,
                        'efn': (g(sk, '#') - g(sk, '=')) / total * 100}
        else:
            out[acc] = {'efic': None, 'efn': None}
    punts = g('Attack', '#') + g('Serve', '#') + g('Block', '#')
    errors = g('Attack', '=') + g('Serve', '=') + g('Reception', '=') + g('Block', '/')
    out['punts'], out['errors'], out['valor'] = punts, errors, punts - errors
    return out


def _sideout_efic_df(d):
    """Eficàcia de side-out/contraatac comptant ATACS. Només per a l'àmbit
    jugador: un rally és d'equip i no s'atribueix a ningú en concret."""
    m = {r['fase']: r['efic'] for _, r in _taula_fases(_fases_atac(d)).iterrows()}
    return m.get('sideout'), m.get('contra')


def _sideout_efic_rallies(r):
    """Eficàcia de side-out/contraatac comptant RALLIES. `r` és un subconjunt
    ja filtrat de rallies_equip(). None si la fase no té cap rally, perquè la
    taula hi posi "—" en comptes d'un 0% que semblaria una dada real."""
    taula = _taula_rallies(r)
    m = {row['fase']: (row['efic'] if row['total'] else None)
         for _, row in taula.iterrows()}
    return m.get('sideout'), m.get('contra')


# (més_alt_és_millor, format) per columna: 4 eficàcies, 4 eficiències, side-out,
# contraatac, punts, errors, valor. Constant — no depèn de les dades.
_META_METRIQUES = ([(True, 'pct')] * 4 + [(True, 'pct')] * 4
                   + [(True, 'pct'), (True, 'pct'), (True, 'int'),
                      (False, 'int'), (True, 'signed')])


def _fila_metriques(d, rallies=None):
    """Valors d'una fila de la taula d'eficàcia/eficiència (14 columnes,
    alineades amb _META_METRIQUES). `d` són files ja filtrades.

    `rallies`: subconjunt de rallies_equip() per al side-out/contraatac
    d'equip. Si és None (àmbit jugador) es compten els atacs del jugador,
    perquè un rally no s'atribueix a ningú en concret.
    """
    s = _stats_df(d)
    so = _sideout_efic_df(d) if rallies is None else _sideout_efic_rallies(rallies)
    skills = ['recepción', 'atacar', 'saque', 'bloqueo']
    vals = [s[a]['efic'] for a in skills] + [s[a]['efn'] for a in skills]
    vals += [so[0], so[1], s['punts'], s['errors'], s['valor']]
    return vals


def _fmt_metrica(v, kind):
    if v is None:
        return "—"
    if kind == 'pct':
        return f"{round(v, 1)}%"
    if kind == 'signed':
        return f"{int(v):+d}"
    return f"{int(v)}"


def _taula_metriques_html(files, lang, col_header, resultats=None):
    """Taula horitzontal: una fila per element (equip, set o partit),
    columnes d'eficàcia/eficiència per acció + side-out/contraatac +
    punts/errors/valor. Ressalta en verd el millor de cada columna (només si
    hi ha més d'un valor diferent — cap ressalt si tothom empata).

    `files`: llista de (etiqueta, vals) amb vals alineats a _META_METRIQUES.
    `resultats`: opcional, llista paral·lela de (text, color) per a una
    columna de resultat (guanyat/perdut) just després de l'etiqueta. color
    és C_VERD/C_ROIG o None (neutre, p. ex. quan no es pot determinar).
    """
    if not files:
        return None
    skills = ['recepción', 'atacar', 'saque', 'bloqueo']
    sk_noms = [NOMS[lang][a] for a in skills]

    # Millor valor de cada columna (conjunt de files que l'assoleixen)
    millors = []
    for ci, (hb, _kind) in enumerate(_META_METRIQUES):
        presents = [vals[ci] for _, vals in files if vals[ci] is not None]
        if len(set(presents)) < 2:
            millors.append(set())
            continue
        best = max(presents) if hb else min(presents)
        millors.append({i for i, (_, vals) in enumerate(files) if vals[ci] == best})

    HDR = f"background:{HDR_BG};color:#fff;"
    SUB = f"background:{SUB_BG};color:#fff;"
    JUG = f"background:{SOFT};color:{INK};font-weight:600;text-align:left;"

    h = ['<table class="dv full">']
    h.append('<tr>')
    h.append(f'<th rowspan="2" class="name" style="{HDR}text-align:left;">{col_header}</th>')
    if resultats is not None:
        h.append(f'<th rowspan="2" style="{HDR}">{t("col_resultat")}</th>')
    h.append(f'<th colspan="4" style="{HDR}">{COLS["efic"][lang]}</th>')
    h.append(f'<th colspan="4" style="{HDR}">{COLS["efn"][lang]}</th>')
    for lab in [t("fase_sideout"), t("fase_contra"), t("valor_punts"),
                t("valor_errors"), t("comp_valor")]:
        h.append(f'<th rowspan="2" style="{HDR}">{lab}</th>')
    h.append('</tr>')
    h.append('<tr>')
    for _ in range(2):
        for nom in sk_noms:
            h.append(f'<th style="{SUB}">{nom}</th>')
    h.append('</tr>')
    for idx, (label, vals) in enumerate(files):
        bg = PAPER if idx % 2 == 0 else ROW_ALT
        h.append('<tr>')
        h.append(f'<td class="name" style="{JUG}">{label}</td>')
        if resultats is not None:
            _txt, _color = resultats[idx]
            _cell = (f"background:{_color};color:{INK};font-weight:700;" if _color
                     else f"background:{bg};color:{INK};")
            h.append(f'<td style="{_cell}">{_txt}</td>')
        for ci, v in enumerate(vals):
            _hb, kind = _META_METRIQUES[ci]
            if idx in millors[ci]:
                cell = f"background:{C_VERD};color:{INK};font-weight:700;"
            else:
                cell = f"background:{bg};color:{INK};"
            h.append(f'<td style="{cell}">{_fmt_metrica(v, kind)}</td>')
        h.append('</tr>')
    h.append('</table>')
    html = "".join(h)
    st.markdown(html, unsafe_allow_html=True)
    return html


def metrica_comparativa(df, equips, lang):
    """Taula cara a cara dels dos equips (o l'equip vs tots els rivals sumats
    si hi ha diversos partits carregats)."""
    if len(equips) >= 2:
        nomA, nomB = equips[0], equips[1]
        dA = df[df['team'] == nomA]
        dB = df[df['team'] == nomB]
        rA = rallies_equip(df, nomA)[0]
        rB = rallies_equip(df, nomB)[0]
    elif len(equips) == 1:
        nomA = equips[0]
        dA = df[df['team'] == nomA]
        dB = df[df['team'].notna() & (df['team'] != nomA)]
        rivals = dB['team'].dropna().unique()
        if len(rivals) == 0:
            st.caption(t("sense_dades"))
            return None
        nomB = t("comp_rivals").format(len(rivals))
        rA = rallies_equip(df, nomA)[0]
        # Els rivals sumats: els rallies de cadascun des del seu punt de vista
        # (el que per a nosaltres és side-out, per a ells és contraatac).
        _r = [rallies_equip(df, riv)[0] for riv in rivals]
        _r = [x for x in _r if len(x)]
        rB = pd.concat(_r, ignore_index=True) if _r else pd.DataFrame(columns=rA.columns)
    else:
        st.caption(t("sense_dades"))
        return None

    files = [(nomA, _fila_metriques(dA, rA)), (nomB, _fila_metriques(dB, rB))]
    return _taula_metriques_html(files, lang, t("quin_equip"))


def _resultat(punts_equip, punts_rival):
    """(text, color) per a la columna de resultat: verd si guanya, roig si perd."""
    color = C_VERD if punts_equip > punts_rival else (C_ROIG if punts_equip < punts_rival else None)
    return f"{punts_equip}-{punts_rival}", color


def desglossament_per_set(df, equip, jugador, lang, partits):
    """Una fila per set (agregant tots els partits carregats), descartant
    sets fantasma (menys de MIN_ACCIONS_SET accions — files residuals al
    final del .dvw que no corresponen a cap set jugat).

    Quins set_number són reals es decideix a nivell d'EQUIP, no de jugador:
    un jugador concret pot tenir poques accions en un set perfectament real
    (hi ha jugat poc), i no per això s'ha de descartar el set.

    Retorna (files, resultats). El resultat exacte del set (p. ex. 25-20)
    només es calcula quan hi ha un sol partit carregat: amb diversos, un
    mateix "Set 1" pot estar guanyat en un i perdut en un altre, i barrejar-
    los en una sola fila enganyaria — la columna hi surt igualment però amb
    "—" a totes les files.
    """
    d_equip = df[(df['team'] == equip) & df['skill'].isin(['Reception', 'Attack', 'Serve', 'Block'])]
    if d_equip.empty or 'set_number' not in d_equip.columns:
        return [], None
    d_equip = d_equip.assign(_set=d_equip['set_number'].map(_norm_set))
    comptes = d_equip.groupby('_set').size()
    sets_reals = sorted(s for s in comptes.index if s is not None and comptes[s] >= MIN_ACCIONS_SET)

    d = d_equip[d_equip['player_name'] == jugador] if jugador is not None else d_equip
    # Els rallies es filtren pel mateix set. En àmbit jugador no s'hi passen:
    # el side-out es compta llavors amb els atacs del jugador.
    rall = None if jugador is not None else rallies_equip(df, equip)[0]
    files = [(f"{t('col_set')} {int(s)}",
              _fila_metriques(d[d['_set'] == s],
                              None if rall is None else rall[rall['_set'] == s]))
             for s in sets_reals]

    marcador = partits[0]['sets'] if len(partits) == 1 else None
    es_home = len(partits) == 1 and partits[0]['home'] == equip
    resultats = []
    for s in sets_reals:
        idx = int(s) - 1
        if marcador is not None and 0 <= idx < len(marcador):
            a, b = marcador[idx]
            resultats.append(_resultat(a, b) if es_home else _resultat(b, a))
        else:
            resultats.append(("—", None))
    return files, resultats


def desglossament_per_partit(df, equip, jugador, partits, lang):
    """Una fila per partit carregat, amb el nom del rival com a etiqueta i
    el resultat (sets guanyats-perduts de l'equip, sempre calculable)."""
    d = df[(df['team'] == equip) & df['skill'].isin(['Reception', 'Attack', 'Serve', 'Block'])]
    if jugador is not None:
        d = d[d['player_name'] == jugador]
    if d.empty or 'match_id' not in d.columns:
        return [], None
    # Els rallies es filtren pel mateix partit. En àmbit jugador no s'hi
    # passen: el side-out es compta llavors amb els atacs del jugador.
    rall = None if jugador is not None else rallies_equip(df, equip)[0]
    files, resultats = [], []
    for i in sorted(d['match_id'].dropna().unique()):
        sub = d[d['match_id'] == i]
        if sub.empty:
            continue
        i = int(i)
        if i < len(partits):
            info = partits[i]
            es_home = info['home'] == equip
            label = info['visiting'] if es_home else info['home']
            if info['data']:
                label += f" · {_data_curta(info['data'])}"
            resultats.append(_resultat(info['gh'], info['gv']) if es_home
                             else _resultat(info['gv'], info['gh']))
        else:
            label = f"{t('ambit_partit')} {i + 1}"
            resultats.append(("—", None))
        files.append((label, _fila_metriques(
            sub, None if rall is None else rall[rall['match_id'] == i])))
    return files, resultats


# Índexs dins del vector de _fila_metriques (alineat amb _META_METRIQUES)
# de les eficàcies que segueix l'evolució de temporada.
_EVOL_FILES = [('recepción', 0), ('atacar', 1), ('saque', 2), ('bloqueo', 3),
               ('sideout', 8), ('contra', 9)]
MIN_PARTITS_TENDENCIA = 4  # amb menys, mitja temporada és 1-2 partits: soroll


def metrica_evolucio(df, equip, jugador, partits, lang):
    """Evolució al llarg de la temporada: una fila per acció i una columna per
    partit en ordre cronològic, amb l'eficàcia de cada un.

    És la transposada del desglossament per partit, i existeix precisament per
    això: allà cada partit es llegeix sol, i aquí una acció es llegeix
    d'esquerra a dreta al llarg de la temporada, que és la pregunta que no es
    podia respondre. Només eficàcia: posar-hi també eficiència duplicaria les
    columnes i és el desglossament el lloc per mirar un partit a fons.
    """
    d = df[(df['team'] == equip) & df['skill'].isin(['Reception', 'Attack', 'Serve', 'Block'])]
    if jugador is not None:
        d = d[d['player_name'] == jugador]
    if d.empty or 'match_id' not in d.columns:
        st.caption(t("sense_dades"))
        return None
    rall = None if jugador is not None else rallies_equip(df, equip)[0]

    ids = sorted(int(i) for i in d['match_id'].dropna().unique())
    caps, vals_per_partit = [], []
    for i in ids:
        sub = d[d['match_id'] == i]
        if sub.empty:
            continue
        info = partits[i] if i < len(partits) else None
        caps.append(_data_curta(info['data']) if info else f"{i + 1}")
        vals_per_partit.append(_fila_metriques(
            sub, None if rall is None else rall[rall['match_id'] == i]))

    if len(vals_per_partit) < 2:
        st.caption(t("evolucio_un_partit"))
        return None

    noms = dict(NOMS[lang])
    noms['sideout'], noms['contra'] = t("fase_sideout"), t("fase_contra")

    rows, cell_bg = [], {}
    for n, (clau, ci) in enumerate(_EVOL_FILES):
        serie = [v[ci] for v in vals_per_partit]
        fila = [noms[clau]] + [_fmt_metrica(v, 'pct') for v in serie]
        # Tendència: mitjana de la segona meitat de temporada menys la de la
        # primera. Contra el primer-vs-últim, un sol mal partit no la decideix.
        tend = _tendencia(serie)
        if tend is None:
            fila.append("—")
        else:
            fila.append(f"{tend:+.1f}")
            # Semàfor amb objectiu 0: verd per sobre de +2.5, roig per sota de
            # -2.5 i ambre entremig. Sense la franja ambre, un +0.2 es pintava
            # de verd i semblava una millora quan és la temporada plana.
            cell_bg[(n, len(fila) - 1)] = color_semafor(tend, 0)
        rows.append(fila)

    headers = [t("col_accio")] + caps + [t("col_tendencia")]
    html = taula_simple(headers, rows, cell_bg)
    st.caption(t("evolucio_peu"))
    return html


def _tendencia(serie):
    """Diferència en punts entre la mitjana de la segona meitat de la sèrie i
    la de la primera. None si no hi ha prou partits amb dada a les dues
    meitats (una acció pot faltar en partits solts: bloqueig d'un jugador)."""
    if len(serie) < MIN_PARTITS_TENDENCIA:
        return None
    tall = len(serie) // 2
    prim = [v for v in serie[:tall] if v is not None]
    seg = [v for v in serie[tall:] if v is not None]
    if not prim or not seg:
        return None
    return sum(seg) / len(seg) - sum(prim) / len(prim)


def metrica_desglossament(df, equip, jugador, partits, lang):
    """Com la comparativa, però una fila per set o per partit en comptes
    d'una fila per equip. 'Per partit' només amb diversos arxius carregats."""
    n_partits = df['match_id'].nunique() if 'match_id' in df.columns else 1
    if n_partits > 1:
        agrupacio = st.radio(
            t("desglossament_agrupacio"), options=["set", "partit"],
            format_func=lambda x: t("desglossament_set") if x == "set" else t("desglossament_partit"),
            horizontal=True, label_visibility="collapsed", key="desglossament_agrup",
        )
    else:
        agrupacio = "set"

    if agrupacio == "partit":
        files, resultats = desglossament_per_partit(df, equip, jugador, partits, lang)
        header = t("ambit_partit")
    else:
        files, resultats = desglossament_per_set(df, equip, jugador, lang, partits)
        header = t("col_set")

    if not files:
        st.caption(t("sense_dades"))
        return None
    return _taula_metriques_html(files, lang, header, resultats)


# ===========================================================================
# INTERFÍCIE
# ===========================================================================
col_tit, col_lang = st.columns([5, 1])
with col_tit:
    st.title(t("titol"))
with col_lang:
    st.selectbox(t("idioma"), options=list(IDIOMES.keys()),
                 format_func=lambda x: IDIOMES[x], key="lang",
                 label_visibility="collapsed")
lang = get_lang()

st.caption(t("subtitol"))

# --- Carregar Partits ---
# Els .dvw viuen a Partits/<temporada>/<club>/<equip>/, o sigui que temporada,
# club i equip es trien navegant l'arbre de carpetes: no cal endevinar de qui és
# cada partit llegint-lo, i mai es barregen dos equips meus (l'app exigeix un
# equip comú a tots els arxius i carregar dos clubs junts petaria).
# El club és un nivell propi perquè d'un mateix club en porto més d'un equip
# (el femení i el masculí): sense aquest nivell, triar el club carregaria els
# dos alhora i l'app avisaria de "cap equip comú".
def _carrega(fitxers_triats):
    """Deixa els arxius triats a punt i repinta. `escaneja_carpeta` ja ha tret
    els duplicats de contingut, per això no n'hi ha cap de descartat aquí."""
    st.session_state["dvw_files"] = ordena_per_data(fitxers_triats)
    st.session_state["dvw_dups"] = 0
    st.rerun()


st.markdown(f"**{t('carregar_titol')}**")
# La temporada actual és la que té el nom més alt ("23-24" > "22-23"): primera.
_temporades = subcarpetes(CARPETA_PARTITS)[::-1]
if not _temporades:
    st.caption(t("sense_temporades").format(CARPETA_PARTITS))
else:
    _c1, _c2, _c3 = st.columns(3)
    with _c1:
        _temp = st.selectbox(t("tria_temporada"), options=_temporades,
                             index=primer_amb_partits(CARPETA_PARTITS, _temporades),
                             key="tria_temporada")
    _dir_temp = os.path.join(CARPETA_PARTITS, _temp)
    _clubs_dir = subcarpetes(_dir_temp)
    if not _clubs_dir:
        st.caption(t("sense_clubs_carpeta").format(_dir_temp))
    else:
        with _c2:
            _club_dir = st.selectbox(t("tria_club"), options=_clubs_dir,
                                     index=primer_amb_partits(_dir_temp, _clubs_dir),
                                     key="tria_club")
        _dir_club = os.path.join(_dir_temp, _club_dir)
        _equips_dir = subcarpetes(_dir_club)
        if not _equips_dir:
            st.caption(t("sense_equips_carpeta").format(_dir_club))
        else:
            with _c3:
                _equip_dir = st.selectbox(t("tria_equip"), options=_equips_dir,
                                          index=primer_amb_partits(_dir_club, _equips_dir),
                                          key="tria_equip")
            _dir_equip = os.path.join(_dir_club, _equip_dir)
            _de_la_carpeta = ordena_per_data(escaneja_carpeta(_dir_equip))
            if not _de_la_carpeta:
                st.caption(t("carpeta_buida").format(_dir_equip))
            else:
                _mode = st.radio(t("tria_quins"), options=["tots", "alguns"],
                                 format_func=lambda m: t(f"mode_{m}"),
                                 horizontal=True, key="tria_mode")
                if _mode == "tots":
                    if st.button(t("carrega_tots").format(len(_de_la_carpeta))):
                        _carrega(_de_la_carpeta)
                else:
                    # Etiquetes amb la data al davant: els noms d'arxiu porten
                    # codis de DataVolley i no diuen de quan és el partit.
                    _etiq = {nom: f"{_data_curta(data_partit(b), anys=True)} — "
                                  f"{os.path.splitext(nom)[0]}"
                             for nom, b in _de_la_carpeta}
                    _tria = st.multiselect(t("tria_partits"),
                                           options=list(_etiq),
                                           format_func=lambda n: _etiq[n],
                                           key="tria_partits")
                    if st.button(t("carrega_triats").format(len(_tria)),
                                 disabled=not _tria):
                        _carrega([f for f in _de_la_carpeta if f[0] in set(_tria)])

if st.session_state.get("dvw_files"):
    if st.button(t("netejar_tot")):
        st.session_state["dvw_files"] = []
        st.session_state["dvw_dups"] = 0
        st.rerun()

if not st.session_state.get("dvw_files"):
    st.caption(t("puja_per_comencar"))
    st.stop()

if st.session_state.get("dvw_dups"):
    st.caption(t("dups_descartats").format(st.session_state["dvw_dups"]))

fitxers = st.session_state["dvw_files"]
try:
    df = carregar_partits(fitxers)
except Exception as e:
    st.error(t("error_llegir").format(e))
    st.stop()

if df['team'].dropna().empty:
    st.error(t("sense_equips"))
    st.stop()

# Amb 1 fitxer són els dos equips; amb més, només el que es repeteix a tots.
equips = equips_comuns(df)
if not equips:
    st.error(t("sense_equip_comu"))
    st.stop()
partits = info_partits(df, fitxers)

# --- Selecció ---
_sel_head, _sel_badge = st.columns([6, 1])
with _sel_head:
    seccio(t("quin_equip"))
badge_slot = _sel_badge.empty()
c1, c2 = st.columns([1, 1])
with c1:
    equip = st.radio(t("quin_equip"), options=equips, horizontal=True,
                     label_visibility="collapsed")
with c2:
    ambit = st.radio(
        t("ambit_label"), options=["partit", "jugador", "comparativa"],
        format_func=lambda x: {
            # amb diversos partits l'àmbit "partit" és en realitat el global
            "partit": t("ambit_global") if len(fitxers) > 1 else t("ambit_partit"),
            "jugador": t("ambit_jugador"),
            "comparativa": t("ambit_comparativa")}[x],
        horizontal=True, label_visibility="collapsed",
    )

# Chequeig de salut del scout -> badge de notificació
_orfes = df[(df['team'] == equip) & (df['skill'].isin(SKILL_MAP)) & (df['player_name'].isna())]
if len(_orfes):
    _dorsals = []
    for x in _orfes['player_number'].dropna().unique().tolist():
        try:
            _dorsals.append(int(float(x)))
        except (ValueError, TypeError):
            pass
    _dorsals_txt = ", ".join(f"#{d}" for d in sorted(set(_dorsals))) if _dorsals else "?"
    badge_slot.markdown(
        badge_avis(len(_orfes), t("avis_scout").format(len(_orfes), _dorsals_txt)),
        unsafe_allow_html=True,
    )

# --- Miniresum del/s partit/s ---
if ambit in ("partit", "comparativa"):
    if len(partits) == 1 and partits[0]['sets']:
        _p = partits[0]
        _parcials = "&nbsp;&nbsp;&nbsp;".join(f"{a}-{b}" for a, b in _p['sets'])
        st.markdown(
            f'<div style="border:1px solid {LINE};border-left:3px solid {HDR_BG};'
            f'border-radius:4px;padding:0.7rem 1.1rem;margin:1.2rem 0 0.4rem 0;'
            f'background:{PAPER};color:{INK};display:inline-block;">'
            f'<div style="font-size:0.72rem;letter-spacing:0.08em;text-transform:uppercase;'
            f'color:{MUTED};margin-bottom:0.25rem;">{_p["home"]} &nbsp;·&nbsp; {_p["visiting"]}</div>'
            f'<div style="font-size:1.5rem;font-weight:600;line-height:1.1;">'
            f'{_p["gh"]} – {_p["gv"]}</div>'
            f'<div style="font-size:0.9rem;color:{MUTED};margin-top:0.3rem;'
            f'font-variant-numeric:tabular-nums;">{_parcials}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    elif len(partits) > 1:
        _files = "".join(
            f'<div style="font-size:0.9rem;margin:0.15rem 0;'
            f'font-variant-numeric:tabular-nums;">'
            f'<span style="color:{MUTED};">{_data_curta(p["data"], anys=True)}'
            f'</span>&nbsp;&nbsp;'
            f'{p["home"]} <b>{p["gh"]} – {p["gv"]}</b> {p["visiting"]}</div>'
            for p in partits)
        st.markdown(
            f'<div style="border:1px solid {LINE};border-left:3px solid {HDR_BG};'
            f'border-radius:4px;padding:0.7rem 1.1rem;margin:1.2rem 0 0.4rem 0;'
            f'background:{PAPER};color:{INK};display:inline-block;">'
            f'<div style="font-size:0.72rem;letter-spacing:0.08em;text-transform:uppercase;'
            f'color:{MUTED};margin-bottom:0.35rem;">{t("n_partits").format(len(partits))}</div>'
            f'{_files}</div>',
            unsafe_allow_html=True,
        )
else:
    st.caption(" · ".join(f'{p["home"]} – {p["visiting"]}' for p in partits))

jugador = None
if ambit == "jugador":
    jugadors = sorted(
        df[(df['team'] == equip) & df['player_name'].notna()]['player_name'].unique().tolist()
    )
    if not jugadors:
        st.caption(t("sense_jugadors"))
        st.stop()
    jugador = st.selectbox(t("selecciona_jugador"), options=jugadors)

# --- Mètriques ---
pdf_blocs = []
if ambit == "comparativa":
    seccio(t("metrica_comparativa"))
    _html = metrica_comparativa(df, equips, lang)
    if _html:
        pdf_blocs.append([(t("metrica_comparativa"), _html)])
else:
    METRIQUES = {
        "taula_general": t("metrica_taula_general"),
        "sideout": t("metrica_sideout"),
        "rotacio": t("metrica_rotacio"),
        "zones": t("metrica_zones"),
        "desglossament": t("metrica_desglossament"),
    }
    # L'evolució només té sentit amb temporada carregada: amb un sol partit
    # no hi ha res a seguir, i la casella només faria nosa.
    if len(fitxers) > 1:
        METRIQUES["evolucio"] = t("metrica_evolucio")
    seccio(t("metriques_mostrar"))
    mcols = st.columns(max(len(METRIQUES), 1))
    seleccio = []
    for i, (clau, etiqueta) in enumerate(METRIQUES.items()):
        with mcols[i]:
            if st.checkbox(etiqueta, value=True, key=f"chk_{ambit}_{clau}"):
                seleccio.append(clau)

    if not seleccio:
        st.caption(t("sense_metriques"))
    else:
        # Taula general: sempre a tota amplada
        if "taula_general" in seleccio:
            seccio(METRIQUES["taula_general"])
            _html = metrica_taula_general(df, equip, lang, jugador)
            if _html:
                pdf_blocs.append([(METRIQUES["taula_general"], _html)])

        # Side-out i rotació: de costat (dues columnes)
        _small = [c for c in ("sideout", "rotacio") if c in seleccio]
        if _small:
            _cols = st.columns(len(_small))
            _bloc = []
            for _i, _clau in enumerate(_small):
                with _cols[_i]:
                    seccio(METRIQUES[_clau])
                    if _clau == "sideout":
                        _html = metrica_sideout(df, equip, jugador, lang)
                    else:
                        _html = metrica_rotacio(df, equip, jugador, lang)
                if _html:
                    _bloc.append((METRIQUES[_clau], _html))
            if _bloc:
                pdf_blocs.append(_bloc)

        # Zones: una sola taula, a tota amplada
        if "zones" in seleccio:
            seccio(METRIQUES["zones"])
            _html = metrica_zones(df, equip, jugador, lang)
            if _html:
                pdf_blocs.append([(METRIQUES["zones"], _html)])

        # Desglossament: com la comparativa, però per set o per partit
        if "desglossament" in seleccio:
            seccio(METRIQUES["desglossament"])
            _html = metrica_desglossament(df, equip, jugador, partits, lang)
            if _html:
                pdf_blocs.append([(METRIQUES["desglossament"], _html)])

        # Evolució: la transposada del desglossament, al llarg del calendari
        if "evolucio" in seleccio:
            seccio(METRIQUES["evolucio"])
            _html = metrica_evolucio(df, equip, jugador, partits, lang)
            if _html:
                pdf_blocs.append([(METRIQUES["evolucio"], _html)])

# --- Descàrrega de l'informe en PDF ---
if pdf_blocs:
    seccio(t("informe_titol"))
    if not PDF_OK:
        st.caption(t("pdf_indisponible"))
    else:
        if ambit == "comparativa":
            _cap = capcalera_pdf(equip, None, partits,
                                 titol=t("metrica_comparativa"))
            _fn = _nom_fitxer(equip, len(partits), prefix="Comparativa")
        else:
            _cap = capcalera_pdf(equip, jugador, partits)
            _fn = _nom_fitxer(jugador if jugador else equip, len(partits))
        _pdf = generar_pdf(_cap, pdf_blocs)
        if _pdf:
            st.download_button(
                t("baixar_pdf"), data=_pdf, file_name=_fn, mime="application/pdf",
            )
        else:
            st.caption(t("pdf_error"))
