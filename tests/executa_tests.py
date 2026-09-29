# -*- coding: utf-8 -*-
"""Passa totes les proves (revisor i mètriques de l'app d'informes) i en fa un resum.

    python tests/executa_tests.py        (o doble clic a "Passar Tests.bat")

Cada prova és un script independent que imprimeix línies "[OK ]" o "[FAIL]".
No cal cap llibreria de tests: només python, i els .dvw de Partits/.
"""
import os
import subprocess
import sys

ACI = os.path.dirname(os.path.abspath(__file__))

PROVES = [
    ("test_roundtrip.py", "Round-trip lossless dels 14 partits + linter"),
    ("test_escriptura.py", "Escriptura del token i guardes de la taula"),
    ("test_autocorrect.py", "Autocorrector de dorsal (saque determinista)"),
    ("test_reedicio.py", "Reeditar un dorsal diverses vegades"),
    ("test_derivades.py", "Zona i nom es recalculen en canviar el dorsal"),
    ("test_estructura.py", "Motor d'inserir/editar/esborrar accions"),
    ("test_panell.py", "Panell: inserir des de la interfície"),
    ("test_edicio_panell.py", "Panell: editar línies sense error"),
    ("test_salts.py", "Salts al panell des de la taula i la revisió"),
    ("test_filtre.py", "El filtre sobreviu als salts"),
    ("test_marcador.py", "Linter: salts i retrocessos del marcador"),
    ("test_metriques.py", "Mètriques d'app_dvw: marcador, fórmules i zones"),
    ("test_temporada.py", "Data del partit, ordre cronològic i tendència"),
    ("test_idiomes.py", "Textos de l'app en anglès, català i alemany"),
]


def main():
    entorn = dict(os.environ, PYTHONIOENCODING="utf-8")
    tot_ok = tot_ko = 0
    fallides = []

    for fitxer, descripcio in PROVES:
        r = subprocess.run([sys.executable, os.path.join(ACI, fitxer)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=entorn)
        sortida = (r.stdout or "") + (r.stderr or "")
        linies = sortida.splitlines()
        ok = sum(1 for l in linies if l.startswith("[OK "))
        ko = sum(1 for l in linies if "[FAIL]" in l)
        # el round-trip no fa servir [OK ]: mira la seva línia de resum
        if fitxer == "test_roundtrip.py":
            ok += sum(1 for l in linies if "ROUND-TRIP LOSSLESS TOTAL: OK" in l)
            ko += sum(1 for l in linies if "HI HA FALLADES" in l)
        petat = r.returncode != 0
        tot_ok += ok
        tot_ko += ko

        estat = "OK  " if (ko == 0 and not petat) else "FALLA"
        print(f"[{estat}] {descripcio:52s} {ok:3d} ok, {ko} fall")
        if ko or petat:
            fallides.append((fitxer, sortida))

    print("-" * 78)
    print(f"TOTAL: {tot_ok} comprovacions correctes, {tot_ko} fallides")

    for fitxer, sortida in fallides:
        print(f"\n===== detall de {fitxer} =====")
        for l in sortida.splitlines():
            if "[FAIL]" in l or "Error" in l or "Traceback" in l:
                print("   ", l[:160])

    return 1 if (tot_ko or fallides) else 0


if __name__ == "__main__":
    sys.exit(main())
