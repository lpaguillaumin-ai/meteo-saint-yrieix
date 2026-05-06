"""Télécharge les fichiers quotidiens historiques 1950-2024 (dépt 87),
filtre la station 87187003 et écrit data/historique.csv au même schéma
que data/quotidien.csv (consommable par normales.py)."""

from __future__ import annotations

import csv
import gzip
import sys
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STATION = "87187003"

SOURCES = {
    "rr_t_vent": "https://www.data.gouv.fr/api/1/datasets/r/29a456ec-2ce9-4ce1-ba23-4ec3e8b25324",
    "autres":    "https://www.data.gouv.fr/api/1/datasets/r/1a208da5-d58f-4dac-af86-c1a99aaebaa6",
}

COLONNES = ("RR", "TN", "TX", "FXI", "DXI", "UN", "UX", "INST")

RACINE = Path(__file__).parent
DOSSIER_RAW = RACINE / "data" / "raw"
SORTIE = RACINE / "data" / "historique.csv"


def telecharger(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"  -> {url}")
    with urllib.request.urlopen(url) as reponse:
        destination.write_bytes(reponse.read())
    print(f"     {destination.name} ({destination.stat().st_size // 1024} Ko)")


def lire_station(chemin: Path) -> dict[str, dict[str, str]]:
    """Lit le CSV gzippé et renvoie {AAAAMMJJ: ligne_dict} pour la station."""
    par_date: dict[str, dict[str, str]] = {}
    with gzip.open(chemin, "rt", encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            if ligne["NUM_POSTE"] != STATION:
                continue
            par_date[ligne["AAAAMMJJ"]] = ligne
    return par_date


def valeur_propre(brut: str | None) -> str:
    if brut is None:
        return ""
    v = brut.strip()
    return "" if v in ("", "NA", "nan") else v


def formater_date(aaaammjj: str) -> str:
    return f"{aaaammjj[:4]}-{aaaammjj[4:6]}-{aaaammjj[6:8]}"


def main() -> int:
    print("Téléchargement de l'historique 1950-2024…")
    fichiers: dict[str, Path] = {}
    for nom, url in SOURCES.items():
        cible = DOSSIER_RAW / f"Q_87_previous_{nom}.csv.gz"
        telecharger(url, cible)
        fichiers[nom] = cible

    print(f"\nFiltrage de la station {STATION}…")
    rrtv = lire_station(fichiers["rr_t_vent"])
    autres = lire_station(fichiers["autres"])
    print(f"  RR-T-Vent : {len(rrtv)} jours")
    print(f"  autres    : {len(autres)} jours")

    dates = sorted(set(rrtv) | set(autres))
    print(f"  fusion    : {len(dates)} jours ({formater_date(dates[0])} -> {formater_date(dates[-1])})")

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    print(f"\nÉcriture de {SORTIE.relative_to(RACINE)}…")
    with SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["date", *COLONNES])
        for d in dates:
            l_rrtv = rrtv.get(d, {})
            l_autres = autres.get(d, {})
            sortie = [formater_date(d)]
            for col in COLONNES:
                source = l_rrtv if col in l_rrtv else l_autres
                sortie.append(valeur_propre(source.get(col, "")))
            ecrivain.writerow(sortie)
    print(f"  {len(dates)} lignes écrites.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
