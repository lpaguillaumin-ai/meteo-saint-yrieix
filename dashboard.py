"""Génère output/index.html : tableau de bord météo St-Yrieix.

Onglets :
  Mois en cours  — KPIs + détail jour-par-jour + climogramme 12 mois
  Bilan hydrique — P cumulée, ETP cumulée et bilan P-ETP vs référence 1995-2024
  Heatmap T° max — calendrier 12 mois glissants
  Records        — valeurs extrêmes depuis 1994
  Phénologie     — sommes de degrés-jours et seuils agroclimatiques

Formules et sources
───────────────────
ETP Hargreaves-Samani (1985)
  ETP = 0,0023 × (Tmoy + 17,8) × √(TX − TN) × Ra
  Ra : rayonnement extra-terrestre FAO-56 (Allen et al., 1998),
       latitude 45,513667 °N, constante solaire 0,0820 MJ·m⁻²·min⁻¹.
  Réf. : Hargreaves & Samani, Applied Engineering in Agriculture, 1(2), 1985.

Degrés-jours de croissance (DJC / GDD)
  DJC(base) = Σ max(0, (TN + TX) / 2 − Tbase) depuis le 1ᵉʳ janvier
  Base 0 °C  : développement végétatif général (herbe)
  Base 6 °C  : céréales (blé, orge)
  Base 10 °C : maïs
  Réf. : McMaster & Wilhelm, Agric. Forest Meteorol. 87(4), 1997.

Seuils phénologiques
  200 DJC base 0 °C  : démarrage pousse de l'herbe — INRAE / ARVALIS
  1 000 DJC base 6 °C : épiaison blé tendre — ARVALIS, Guide Grandes Cultures 2022
  1 700 DJC base 10 °C : floraison maïs grain — ARVALIS / INRAE

Normales de référence : fenêtre 1995-2024, station 87187003, méthode OMM.

Inspiré de docs/maquette.png."""

from __future__ import annotations

import csv
import json
import math
import sys
from datetime import date, datetime, timedelta
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RACINE = Path(__file__).parent
QUOTIDIEN = RACINE / "data" / "quotidien.csv"
HISTORIQUE = RACINE / "data" / "historique.csv"
NORMALES = RACINE / "data" / "normales.csv"
SORTIE = RACINE / "output" / "index.html"

LATITUDE_DEG = 45.513667  # St-Yrieix-la-Perche
ANNEE_REF_DEBUT, ANNEE_REF_FIN = 1995, 2024

MOIS_FR = ["", "janv.", "févr.", "mars", "avr.", "mai", "juin",
           "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MOIS_FR_LONG = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


# ── Lecture des données ───────────────────────────────────────────────────────

def parser_float(s: str) -> float | None:
    if s is None or s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def charger_csv(chemin: Path) -> list[dict]:
    lignes = []
    with chemin.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            d = datetime.strptime(row["date"], "%Y-%m-%d").date()
            lignes.append({
                "date": d,
                "RR":   parser_float(row.get("RR", "")),
                "TN":   parser_float(row.get("TN", "")),
                "TX":   parser_float(row.get("TX", "")),
                "FXI":  parser_float(row.get("FXI", "")),
                "DXI":  parser_float(row.get("DXI", "")),
                "UN":   parser_float(row.get("UN", "")),
                "UX":   parser_float(row.get("UX", "")),
                "INST": parser_float(row.get("INST", "")),
            })
    return lignes


def charger_normales() -> dict[int, dict[str, float | None]]:
    out = {}
    with NORMALES.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            mois = int(row["mois"])
            out[mois] = {k: parser_float(v) for k, v in row.items() if k != "mois"}
    return out


# ── ETP Hargreaves ────────────────────────────────────────────────────────────

def rayonnement_extraterrestre(jour_annee: int) -> float:
    """Ra en mm/jour-équivalent pour la latitude du site (FAO-56)."""
    phi = math.radians(LATITUDE_DEG)
    dr = 1 + 0.033 * math.cos(2 * math.pi * jour_annee / 365)
    delta = 0.409 * math.sin(2 * math.pi * jour_annee / 365 - 1.39)
    cos_ws = max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta)))
    ws = math.acos(cos_ws)
    gsc = 0.0820  # MJ/m²/min
    ra_mj = (24 * 60 / math.pi) * gsc * dr * (
        ws * math.sin(phi) * math.sin(delta)
        + math.cos(phi) * math.cos(delta) * math.sin(ws)
    )
    return ra_mj / 2.45  # conversion en mm/jour


def etp_hargreaves(tn: float, tx: float, jour_annee: int) -> float:
    """ETP journalière (mm) — formule de Hargreaves-Samani."""
    if tx <= tn:
        return 0.0
    tmoy = (tn + tx) / 2
    ra = rayonnement_extraterrestre(jour_annee)
    return max(0.0, 0.0023 * (tmoy + 17.8) * math.sqrt(tx - tn) * ra)


# ── Métriques ─────────────────────────────────────────────────────────────────

def direction_rose(deg: float | None) -> str:
    if deg is None:
        return "—"
    rose = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]
    return rose[int((deg % 360) / 22.5 + 0.5) % 16]


def construire_kpis(jours_mois: list[dict], normales_mois: dict[str, float | None]) -> list[dict]:
    rr_total = sum(j["RR"] for j in jours_mois if j["RR"] is not None)
    rr_norm = normales_mois.get("RR")

    tnxs = [(j["TN"] + j["TX"]) / 2 for j in jours_mois
            if j["TN"] is not None and j["TX"] is not None]
    t_moy = sum(tnxs) / len(tnxs) if tnxs else None
    t_norm = ((normales_mois["TN"] + normales_mois["TX"]) / 2
              if normales_mois.get("TN") is not None and normales_mois.get("TX") is not None
              else None)

    rafales = [(j["FXI"], j["DXI"], j["date"]) for j in jours_mois if j["FXI"] is not None]
    if rafales:
        fxi_max, dxi_max, date_max = max(rafales, key=lambda x: x[0])
        vent_kmh = fxi_max * 3.6
    else:
        vent_kmh = dxi_max = date_max = None

    inst_min = sum(j["INST"] for j in jours_mois if j["INST"] is not None)
    inst_h = inst_min / 60 if inst_min else 0
    inst_norm_h = (normales_mois["INST"] / 60) if normales_mois.get("INST") else None

    def pct(v, n):
        if v is None or n is None or n == 0:
            return None
        return (v - n) / n * 100

    def fmt_pct(p):
        if p is None:
            return ""
        signe = "+" if p >= 0 else ""
        return f"{signe}{p:.0f}%"

    p_rr = pct(rr_total, rr_norm)
    p_inst = pct(inst_h, inst_norm_h)
    delta_t = (t_moy - t_norm) if (t_moy is not None and t_norm is not None) else None

    return [
        {
            "titre": "Cumul pluie",
            "valeur": f"{rr_total:.1f} mm",
            "comparaison": f"{fmt_pct(p_rr)} / normale ≈ {rr_norm:.0f} mm" if rr_norm else "",
            "tendance": "up" if p_rr and p_rr > 5 else ("down" if p_rr and p_rr < -5 else "flat"),
        },
        {
            "titre": "T° moyenne",
            "valeur": f"{t_moy:.1f} °C" if t_moy is not None else "—",
            "comparaison": (
                f"{'+' if delta_t >= 0 else ''}{delta_t:.1f} °C / normale ≈ {t_norm:.1f} °C"
                if delta_t is not None else ""
            ),
            "tendance": "up" if delta_t and delta_t > 0.5 else ("down" if delta_t and delta_t < -0.5 else "flat"),
        },
        {
            "titre": "Vent max",
            "valeur": f"{vent_kmh:.1f} km/h" if vent_kmh else "—",
            "comparaison": f"{date_max.strftime('%d/%m')} · {direction_rose(dxi_max)}" if date_max else "",
            "tendance": "flat",
        },
        {
            "titre": "Insolation",
            "valeur": f"{inst_h:.0f} h" if inst_h else "—",
            "comparaison": f"normale ≈ {inst_norm_h:.0f} h" if inst_norm_h else "",
            "tendance": "up" if p_inst and p_inst > 5 else ("down" if p_inst and p_inst < -5 else "flat"),
        },
    ]


def cumul_mensuel(jours: list[dict], mois: int, annee: int, champ: str) -> float | None:
    valeurs = [j[champ] for j in jours
               if j["date"].year == annee and j["date"].month == mois and j[champ] is not None]
    return sum(valeurs) if valeurs else None


def moyenne_mensuelle(jours: list[dict], mois: int, annee: int, champ: str) -> float | None:
    valeurs = [j[champ] for j in jours
               if j["date"].year == annee and j["date"].month == mois and j[champ] is not None]
    return sum(valeurs) / len(valeurs) if valeurs else None


def construire_climogramme(jours: list[dict], normales: dict, annee: int) -> dict:
    rr_reel, rr_norm, t_reel, t_norm = [], [], [], []
    for m in range(1, 13):
        rr_reel.append(round(cumul_mensuel(jours, m, annee, "RR") or 0, 1))
        rr_norm.append(normales[m]["RR"])
        tn = moyenne_mensuelle(jours, m, annee, "TN")
        tx = moyenne_mensuelle(jours, m, annee, "TX")
        t_reel.append(round((tn + tx) / 2, 1) if tn is not None and tx is not None else None)
        t_norm.append(round((normales[m]["TN"] + normales[m]["TX"]) / 2, 1))
    return {
        "labels": [MOIS_FR[m] for m in range(1, 13)],
        "rr_reel": rr_reel, "rr_norm": rr_norm,
        "t_reel": t_reel,   "t_norm": t_norm,
    }


def construire_detail_mois(jours_mois: list[dict]) -> dict:
    return {
        "labels": [j["date"].strftime("%d") for j in jours_mois],
        "rr": [j["RR"] if j["RR"] is not None else 0 for j in jours_mois],
        "tx": [j["TX"] for j in jours_mois],
        "tn": [j["TN"] for j in jours_mois],
    }


# ── Bilan hydrique P-ETP ──────────────────────────────────────────────────────

def serie_p_etp_annuelle(jours_annee: list[dict]) -> list[float | None]:
    """Cumul P-ETP jour après jour pour les jours de l'année donnée
    (longueur = nombre de jours présents, dans l'ordre chronologique)."""
    cumul = 0.0
    serie = []
    for j in sorted(jours_annee, key=lambda x: x["date"]):
        if j["TN"] is None or j["TX"] is None:
            serie.append(None)
            continue
        p = j["RR"] if j["RR"] is not None else 0.0
        etp = etp_hargreaves(j["TN"], j["TX"], j["date"].timetuple().tm_yday)
        cumul += p - etp
        serie.append(round(cumul, 1))
    return serie


def construire_bilan_hydrique(quotidien: list[dict], historique: list[dict], annee_courante: int) -> dict:
    jours_courants = sorted(
        [j for j in quotidien if j["date"].year == annee_courante],
        key=lambda x: x["date"],
    )
    labels = [j["date"].strftime("%d/%m") for j in jours_courants]

    # Cumuls journaliers de l'année en cours (P, ETP, P-ETP)
    rr_cumul, etp_cumul, p_etp_courant = [], [], []
    c_rr = c_etp = 0.0
    for j in jours_courants:
        c_rr += j["RR"] if j["RR"] is not None else 0.0
        if j["TN"] is not None and j["TX"] is not None:
            c_etp += etp_hargreaves(j["TN"], j["TX"], j["date"].timetuple().tm_yday)
        rr_cumul.append(round(c_rr, 1))
        etp_cumul.append(round(c_etp, 1))
        p_etp_courant.append(round(c_rr - c_etp, 1))

    # Référence 1995-2024 : moyenne du bilan P-ETP par jour-de-l'année
    par_doy: dict[int, list[float]] = {}
    for an in range(ANNEE_REF_DEBUT, ANNEE_REF_FIN + 1):
        jours_an = [j for j in historique if j["date"].year == an]
        if not jours_an:
            continue
        c = 0.0
        for j in sorted(jours_an, key=lambda x: x["date"]):
            if j["TN"] is None or j["TX"] is None:
                continue
            p = j["RR"] if j["RR"] is not None else 0.0
            c += p - etp_hargreaves(j["TN"], j["TX"], j["date"].timetuple().tm_yday)
            par_doy.setdefault(j["date"].timetuple().tm_yday, []).append(c)

    p_etp_reference = []
    for j in jours_courants:
        valeurs = par_doy.get(j["date"].timetuple().tm_yday, [])
        p_etp_reference.append(round(sum(valeurs) / len(valeurs), 1) if valeurs else None)

    bilan_actuel = next((v for v in reversed(p_etp_courant) if v is not None), 0.0)

    return {
        "labels": labels,
        "rr_cumul": rr_cumul,
        "etp_cumul": etp_cumul,
        "p_etp_courant": p_etp_courant,
        "p_etp_reference": p_etp_reference,
        "bilan_actuel": bilan_actuel,
        "annee": annee_courante,
    }


# ── Heatmap T° max — 12 mois glissants ────────────────────────────────────────

def construire_heatmap(jours: list[dict], date_fin: date) -> dict:
    """Grille semaines × jours pour les 365 derniers jours."""
    date_debut = date_fin - timedelta(days=364)
    par_date = {j["date"]: j["TX"] for j in jours if j["TX"] is not None}

    # Cellules : lundi (0) → dimanche (6) sur l'axe vertical.
    # Aligner sur le lundi qui précède (ou égale) date_debut.
    debut_grille = date_debut - timedelta(days=date_debut.weekday())
    fin_grille = date_fin + timedelta(days=(6 - date_fin.weekday()))
    nb_jours = (fin_grille - debut_grille).days + 1

    cellules = []
    valeurs_visibles = []
    for i in range(nb_jours):
        d = debut_grille + timedelta(days=i)
        tx = par_date.get(d) if date_debut <= d <= date_fin else None
        cellules.append({
            "date": d.isoformat(),
            "tx": tx,
            "dans_periode": date_debut <= d <= date_fin,
            "semaine": i // 7,
            "jour_semaine": d.weekday(),
        })
        if tx is not None:
            valeurs_visibles.append(tx)

    nb_semaines = (nb_jours + 6) // 7

    # Étiquettes de mois : on place le label sur la première colonne de chaque mois
    etiquettes_mois = []
    mois_vu = None
    for s in range(nb_semaines):
        d = debut_grille + timedelta(days=s * 7)
        if d.month != mois_vu and date_debut <= d + timedelta(days=6):
            etiquettes_mois.append({"semaine": s, "label": MOIS_FR[d.month]})
            mois_vu = d.month

    return {
        "cellules": cellules,
        "nb_semaines": nb_semaines,
        "etiquettes_mois": etiquettes_mois,
        "min": min(valeurs_visibles) if valeurs_visibles else 0,
        "max": max(valeurs_visibles) if valeurs_visibles else 0,
        "periode": f"{date_debut.strftime('%d/%m/%Y')} → {date_fin.strftime('%d/%m/%Y')}",
    }


def couleur_heatmap(tx: float | None, t_min: float, t_max: float) -> str:
    """Échelle bleu froid → orange chaud."""
    if tx is None:
        return "#2a313b"
    span = t_max - t_min if t_max > t_min else 1
    t = max(0.0, min(1.0, (tx - t_min) / span))
    # Palette par paliers (5 niveaux).
    paliers = [
        (0.0,  "#1f4068"),   # froid
        (0.25, "#3a73a8"),
        (0.5,  "#9aa3ad"),
        (0.75, "#e8995c"),
        (1.0,  "#c0392b"),   # chaud
    ]
    for (s1, c1), (s2, c2) in zip(paliers[:-1], paliers[1:]):
        if t <= s2:
            return c2 if t > (s1 + s2) / 2 else c1
    return paliers[-1][1]


def rendre_heatmap_html(heatmap: dict) -> str:
    """Construit la grille HTML (CSS Grid)."""
    t_min, t_max = heatmap["min"], heatmap["max"]
    cells_par_semaine: dict[int, list[dict]] = {}
    for c in heatmap["cellules"]:
        cells_par_semaine.setdefault(c["semaine"], []).append(c)

    colonnes_html = []
    for s in range(heatmap["nb_semaines"]):
        col = cells_par_semaine.get(s, [])
        col.sort(key=lambda c: c["jour_semaine"])
        cellules_html = []
        for c in col:
            if not c["dans_periode"]:
                cellules_html.append('<div class="hm-cell hm-vide"></div>')
                continue
            couleur = couleur_heatmap(c["tx"], t_min, t_max)
            tx_txt = f"{c['tx']:.1f} °C" if c["tx"] is not None else "n/d"
            d_obj = datetime.fromisoformat(c["date"]).date()
            tip = f"{d_obj.strftime('%d/%m/%Y')} : {tx_txt}"
            cellules_html.append(
                f'<div class="hm-cell" style="background:{couleur}" title="{tip}"></div>'
            )
        colonnes_html.append(f'<div class="hm-col">{"".join(cellules_html)}</div>')

    etiquettes = []
    for e in heatmap["etiquettes_mois"]:
        etiquettes.append(
            f'<div class="hm-mois" style="grid-column:{e["semaine"]+1}">{e["label"]}</div>'
        )

    return f"""
    <div class="heatmap-wrapper">
      <div class="heatmap-scroll">
        <div class="hm-mois-row" style="grid-template-columns:repeat({heatmap['nb_semaines']},14px)">
          {''.join(etiquettes)}
        </div>
        <div class="hm-grid">
          <div class="hm-jours">
            <span></span><span>mar</span><span></span><span>jeu</span><span></span><span>sam</span><span></span>
          </div>
          <div class="hm-cols">{''.join(colonnes_html)}</div>
        </div>
        <div class="hm-legende">
          <span>{t_min:.0f} °C</span>
          <span class="hm-grad"></span>
          <span>{t_max:.0f} °C</span>
        </div>
      </div>
    </div>"""


# ── Gel et stress thermique ───────────────────────────────────────────────────
#
# ITH (Indice Température-Humidité) bovin
#   ITH = (1,8 × TX + 32) − (0,55 − 0,0055 × HRmoy) × (1,8 × TX − 26)
#   TX en °C, HRmoy = (UN + UX) / 2 en % (0-100)
#   Source : INRAE, recommandations stress thermique bovin (formule NRC adaptée)
#
# Seuils INRAE :
#   < 68   : Confort
#   68-72  : Alerte
#   72-78  : Stress modéré
#   78-84  : Stress sévère
#   ≥ 84   : Danger

ITH_CLASSES = [
    (68,  "Confort",       "#2a6496"),
    (72,  "Alerte",        "#d4ac0d"),
    (78,  "Stress modéré", "#e8995c"),
    (84,  "Stress sévère", "#c0392b"),
    (999, "Danger",        "#7b241c"),
]
GEL_PALETTE = {
    -1: "#2a313b",  # données manquantes
     0: "#1e2830",  # hors gel
     1: "#8ec8e8",  # gel léger   (−2 à 0 °C)
     2: "#2980b9",  # gel modéré  (−5 à −2 °C)
     3: "#1a3f6f",  # gel sévère  (< −5 °C)
}


def calculer_ith(tx: float, hr_moy: float) -> float:
    """ITH journalier bovin (formule INRAE / NRC). TX en °C, HRmoy en %."""
    return (1.8 * tx + 32) - (0.55 - 0.0055 * hr_moy) * (1.8 * tx - 26)


def _classe_ith(v: float) -> int:
    for i, (seuil, *_) in enumerate(ITH_CLASSES):
        if v < seuil:
            return i
    return len(ITH_CLASSES) - 1


def _cat_gel(tn: float | None) -> int:
    if tn is None: return -1
    if tn >= 0:    return 0
    if tn >= -2:   return 1
    if tn >= -5:   return 2
    return 3


def construire_gel_et_chaleur(quotidien: list[dict], historique: list[dict], annee: int) -> dict:
    tout = sorted(historique + quotidien, key=lambda j: j["date"])
    jours_an = [j for j in tout if j["date"].year == annee]
    par_date_tn = {j["date"]: j["TN"] for j in tout}
    derniere_dispo = max((j["date"] for j in jours_an), default=date(annee, 1, 1))

    # ── Calendrier des gelées (grille semaines × jours) ──────────────────────
    debut = date(annee, 1, 1)
    fin   = date(annee, 12, 31)
    debut_grille = debut - timedelta(days=debut.weekday())
    fin_grille   = fin   + timedelta(days=(6 - fin.weekday()))
    nb_jours_gr  = (fin_grille - debut_grille).days + 1

    cellules_gel = []
    for i in range(nb_jours_gr):
        d = debut_grille + timedelta(days=i)
        dans_an = debut <= d <= fin
        tn = par_date_tn.get(d) if (dans_an and d <= derniere_dispo) else None
        cellules_gel.append({
            "date": d.isoformat(),
            "tn":   tn,
            "cat":  _cat_gel(tn) if dans_an else -2,
            "sem":  i // 7,
            "jour": d.weekday(),
            "dans_an": dans_an,
        })
    nb_sem = (nb_jours_gr + 6) // 7
    etiq_mois = []
    vu = None
    for s in range(nb_sem):
        d = debut_grille + timedelta(days=s * 7)
        if d.month != vu and debut <= d + timedelta(days=6):
            etiq_mois.append({"s": s, "lab": MOIS_FR[d.month]})
            vu = d.month

    # ── Récapitulatif par année ───────────────────────────────────────────────
    annees_recap = []
    for an in range(ANNEE_REF_DEBUT, annee + 1):
        jj = [j for j in tout if j["date"].year == an and j["TN"] is not None]
        if not jj:
            continue
        nb_gel = sum(1 for j in jj if j["TN"] <= 0)
        gels_pr = sorted(j["date"] for j in jj if j["TN"] <= 0 and j["date"].month <= 6)
        gels_au = sorted(j["date"] for j in jj if j["TN"] <= 0 and j["date"].month >= 7)
        d_pr = gels_pr[-1].strftime("%d/%m") if gels_pr else "—"
        d_au = gels_au[0].strftime("%d/%m")  if gels_au else "—"
        ssf = (gels_au[0] - gels_pr[-1]).days - 1 if (gels_pr and gels_au) else None
        annees_recap.append({"an": an, "nb": nb_gel, "pr": d_pr, "au": d_au, "ssf": ssf})
    annees_recap.sort(key=lambda r: r["an"], reverse=True)

    # ── ITH mensuel (année en cours) ─────────────────────────────────────────
    ith_par_mois: dict[int, list[int]] = {}
    for m in range(1, 13):
        counts = [0] * len(ITH_CLASSES)
        for j in jours_an:
            if j["date"].month == m and j["TX"] is not None and j["UN"] is not None and j["UX"] is not None:
                ith = calculer_ith(j["TX"], (j["UN"] + j["UX"]) / 2)
                counts[_classe_ith(ith)] += 1
        ith_par_mois[m] = counts

    # ── Référence ITH 1995-2024 — une seule passe sur historique ─────────────
    ith_hist: dict[tuple, list[float]] = {}
    for j in historique:
        if j["TX"] is not None and j["UN"] is not None and j["UX"] is not None:
            ith_hist.setdefault((j["date"].year, j["date"].month), []).append(
                calculer_ith(j["TX"], (j["UN"] + j["UX"]) / 2)
            )
    ith_ref_par_mois: dict[int, list[float]] = {}
    for m in range(1, 13):
        acc = [[] for _ in ITH_CLASSES]
        for an_h in range(ANNEE_REF_DEBUT, ANNEE_REF_FIN + 1):
            vals = ith_hist.get((an_h, m), [])
            if not vals:
                continue
            c = [0] * len(ITH_CLASSES)
            for v in vals:
                c[_classe_ith(v)] += 1
            for i in range(len(ITH_CLASSES)):
                acc[i].append(c[i])
        ith_ref_par_mois[m] = [
            round(sum(a) / len(a), 1) if a else 0.0 for a in acc
        ]

    # ── Texte d'alerte ───────────────────────────────────────────────────────
    mois_courant = max((j["date"].month for j in jours_an), default=1)
    mois_check   = mois_courant
    if sum(1 for j in jours_an if j["date"].month == mois_courant) < 15 and mois_courant > 1:
        mois_check = mois_courant - 1
    nb_sev = sum(ith_par_mois.get(mois_check, [0]*5)[3:])
    alerte_txt = None
    if nb_sev > 5:
        alerte_txt = (
            f"⚠️ {nb_sev} jours de stress sévère ou danger (ITH ≥ 78) "
            f"en {MOIS_FR_LONG[mois_check]} {annee}. "
            f"Surveiller l'abreuvement et la ventilation des bâtiments."
        )

    return {
        "annee": annee,
        "cellules_gel": cellules_gel,
        "nb_sem": nb_sem,
        "etiq_mois": etiq_mois,
        "annees_recap": annees_recap,
        "ith_par_mois": {str(m): ith_par_mois[m] for m in range(1, 13)},
        "ith_ref_par_mois": {str(m): ith_ref_par_mois[m] for m in range(1, 13)},
        "alerte_txt": alerte_txt,
        "labels_mois": [MOIS_FR[m] for m in range(1, 13)],
    }


def rendre_gel_chaleur_html(gc: dict) -> str:
    annee = gc["annee"]

    # ── Calendrier des gelées ─────────────────────────────────────────────────
    cols: dict[int, list] = {}
    for c in gc["cellules_gel"]:
        cols.setdefault(c["sem"], []).append(c)

    col_html = []
    for s in range(gc["nb_sem"]):
        cel = sorted(cols.get(s, []), key=lambda c: c["jour"])
        parts = []
        for c in cel:
            if not c["dans_an"]:
                parts.append('<div class="hm-cell hm-vide"></div>')
                continue
            col = GEL_PALETTE.get(c["cat"], GEL_PALETTE[-1])
            d = datetime.fromisoformat(c["date"]).date()
            tn_s = f"{c['tn']:.1f} °C" if c["tn"] is not None else "n/d"
            cats = ["", " — Gel léger", " — Gel modéré", " — Gel sévère"]
            tip = f"{d.strftime('%d/%m/%Y')} Tn = {tn_s}{cats[c['cat']] if c['cat'] > 0 else ''}"
            parts.append(f'<div class="hm-cell" style="background:{col}" title="{tip}"></div>')
        col_html.append(f'<div class="hm-col">{"".join(parts)}</div>')

    etiq_html = "".join(
        f'<div class="hm-mois" style="grid-column:{e["s"]+1}">{e["lab"]}</div>'
        for e in gc["etiq_mois"]
    )
    nb_sem = gc["nb_sem"]

    cal_section = f"""<div class="heatmap-wrapper">
  <div class="heatmap-scroll">
    <div class="hm-mois-row" style="grid-template-columns:repeat({nb_sem},14px)">{etiq_html}</div>
    <div class="hm-grid">
      <div class="hm-jours">
        <span></span><span>mar</span><span></span><span>jeu</span><span></span><span>sam</span><span></span>
      </div>
      <div class="hm-cols">{"".join(col_html)}</div>
    </div>
    <div class="gel-legende">
      <span class="gel-sw" style="background:#1e2830"></span>Hors gel
      <span class="gel-sw" style="background:#8ec8e8"></span>Gel léger (−2 à 0 °C)
      <span class="gel-sw" style="background:#2980b9"></span>Gel modéré (−5 à −2 °C)
      <span class="gel-sw" style="background:#1a3f6f"></span>Gel sévère (&lt; −5 °C)
    </div>
  </div>
</div>"""

    # ── Tableau récapitulatif ─────────────────────────────────────────────────
    rows = []
    for r in gc["annees_recap"]:
        bold = ' style="font-weight:700"' if r["an"] == annee else ""
        ssf = f'{r["ssf"]} j' if r["ssf"] is not None else "—"
        rows.append(
            f'<tr><td{bold}>{r["an"]}</td>'
            f'<td class="rn">{r["nb"]}</td>'
            f'<td class="rn">{r["pr"]}</td>'
            f'<td class="rn">{r["au"]}</td>'
            f'<td class="rn">{ssf}</td></tr>'
        )
    recap_section = (
        f'<h2 style="margin-top:24px">Récapitulatif par année (1995–{annee})</h2>'
        f'<div class="rec-wrap"><table class="rec-table">'
        f'<thead><tr>'
        f'<th>Année</th><th>Jours de gel (TN ≤ 0 °C)</th>'
        f'<th>Dernière gelée de printemps</th>'
        f'<th>Première gelée d\'automne</th>'
        f'<th>Saison sans gel</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        f'</table></div>'
    )

    return cal_section + recap_section


# ── Phénologie — degrés-jours de croissance ───────────────────────────────────

BASES_GDD = [0, 6, 10]
SEUILS_PHENO = [
    {"base": 0,  "valeur": 200,  "libelle": "Démarrage pousse de l'herbe",
     "detail": "200 DJC base 0 °C — INRAE / ARVALIS"},
    {"base": 6,  "valeur": 1000, "libelle": "Épiaison blé tendre",
     "detail": "1 000 DJC base 6 °C — ARVALIS 2022"},
    {"base": 10, "valeur": 1700, "libelle": "Floraison maïs grain",
     "detail": "1 700 DJC base 10 °C — ARVALIS / INRAE"},
]


def _gdd_annee(jours: list[dict], base: float) -> list[float]:
    cumul, serie = 0.0, []
    for j in sorted(jours, key=lambda x: x["date"]):
        if j["TN"] is not None and j["TX"] is not None:
            cumul += max(0.0, (j["TN"] + j["TX"]) / 2 - base)
        serie.append(round(cumul, 1))
    return serie


def construire_phenologie(quotidien: list[dict], historique: list[dict], annee: int) -> dict:
    jours_an = sorted([j for j in quotidien if j["date"].year == annee], key=lambda j: j["date"])
    labels = [j["date"].strftime("%d/%m") for j in jours_an]

    # GDD cumulés année en cours
    gdd = {b: _gdd_annee(jours_an, b) for b in BASES_GDD}

    # Référence P50 par DOY sur 1995-2024
    gdd_doy: dict[int, dict[int, list[float]]] = {b: {} for b in BASES_GDD}
    for an_h in range(ANNEE_REF_DEBUT, ANNEE_REF_FIN + 1):
        jh = sorted([j for j in historique if j["date"].year == an_h], key=lambda j: j["date"])
        if not jh:
            continue
        c = {b: 0.0 for b in BASES_GDD}
        for j in jh:
            if j["TN"] is not None and j["TX"] is not None:
                for b in BASES_GDD:
                    c[b] += max(0.0, (j["TN"] + j["TX"]) / 2 - b)
            doy = j["date"].timetuple().tm_yday
            for b in BASES_GDD:
                gdd_doy[b].setdefault(doy, []).append(c[b])

    gdd_ref: dict[int, list[float | None]] = {}
    for b in BASES_GDD:
        serie = []
        for j in jours_an:
            vals = sorted(gdd_doy[b].get(j["date"].timetuple().tm_yday, []))
            serie.append(round(vals[len(vals) // 2], 1) if vals else None)
        gdd_ref[b] = serie

    # Seuils : date de franchissement et médiane historique
    seuils = []
    for s in SEUILS_PHENO:
        b, seuil = s["base"], s["valeur"]
        # Date de franchissement cette année
        date_an = None
        for i, val in enumerate(gdd[b]):
            if val >= seuil:
                date_an = jours_an[i]["date"].strftime("%d/%m")
                break
        gdd_actuel = gdd[b][-1] if gdd[b] else 0.0

        # Médiane historique (DOY → date)
        doys_hist = []
        for an_h in range(ANNEE_REF_DEBUT, ANNEE_REF_FIN + 1):
            jh = sorted([j for j in historique if j["date"].year == an_h], key=lambda j: j["date"])
            c_h = 0.0
            for j in jh:
                if j["TN"] is not None and j["TX"] is not None:
                    c_h += max(0.0, (j["TN"] + j["TX"]) / 2 - b)
                    if c_h >= seuil:
                        doys_hist.append(j["date"].timetuple().tm_yday)
                        break
        ref_med = "—"
        if doys_hist:
            doys_hist.sort()
            p50_doy = doys_hist[len(doys_hist) // 2]
            try:
                ref_d = date(annee, 1, 1) + timedelta(days=p50_doy - 1)
                ref_med = ref_d.strftime("%d/%m")
            except ValueError:
                ref_med = "—"

        seuils.append({
            **s,
            "date_an": date_an,
            "gdd_actuel": round(gdd_actuel, 0),
            "pct": min(100, int(gdd_actuel / seuil * 100)),
            "ref_med": ref_med,
        })

    return {
        "labels": labels,
        "gdd":     {str(b): gdd[b]     for b in BASES_GDD},
        "gdd_ref": {str(b): gdd_ref[b] for b in BASES_GDD},
        "seuils": seuils,
        "annee": annee,
    }


# ── Records historiques ───────────────────────────────────────────────────────

def _fdr(d) -> str:
    """Formate une date pour l'affichage dans les records."""
    return d.strftime("%d/%m/%Y") if d is not None else "—"


def construire_records(quotidien: list[dict], historique: list[dict]) -> dict:
    tout = sorted(historique + quotidien, key=lambda j: j["date"])
    annee = max(j["date"].year for j in quotidien)
    jours_an = [j for j in tout if j["date"].year == annee]

    def rec_max(jours, var):
        v = [(j[var], j["date"]) for j in jours if j[var] is not None]
        return max(v, key=lambda x: x[0]) if v else (None, None)

    def rec_min(jours, var):
        v = [(j[var], j["date"]) for j in jours if j[var] is not None]
        return min(v, key=lambda x: x[0]) if v else (None, None)

    # Records absolus
    tx_rv, tx_rd = rec_max(tout, "TX");   tx_av, tx_ad = rec_max(jours_an, "TX")
    tn_rv, tn_rd = rec_min(tout, "TN");   tn_av, tn_ad = rec_min(jours_an, "TN")
    rr_rv, rr_rd = rec_max(tout, "RR");   rr_av, rr_ad = rec_max(jours_an, "RR")
    fx_rv, fx_rd = rec_max(tout, "FXI");  fx_av, fx_ad = rec_max(jours_an, "FXI")
    it_rv, it_rd = rec_max(tout, "INST"); it_av, it_ad = rec_max(jours_an, "INST")

    # Pluies mensuelles
    mois_rr: dict = defaultdict(float)
    mois_n:  dict = defaultdict(int)
    for j in tout:
        if j["RR"] is not None:
            k = (j["date"].year, j["date"].month)
            mois_rr[k] += j["RR"]
            mois_n[k]  += 1
    complets = {k: mois_rr[k] for k, n in mois_n.items() if n >= 25}

    def lab_mois(k): return f"{MOIS_FR_LONG[k[1]]} {k[0]}" if k else "—"

    k_rrmax = max(complets, key=complets.get) if complets else None
    k_rrmin = min(complets, key=complets.get) if complets else None
    rrm_max_v = complets[k_rrmax] if k_rrmax else None
    rrm_min_v = complets[k_rrmin] if k_rrmin else None

    comp_an = {k: complets[k] for k in complets if k[0] == annee}
    k_rran_max = max(comp_an, key=comp_an.get) if comp_an else None
    k_rran_min = min(comp_an, key=comp_an.get) if comp_an else None

    # Séries consécutives
    def serie(jours, var, test):
        ml, cur, dd, dm_d, dm_f = 0, 0, None, None, None
        for j in jours:
            if j[var] is not None and test(j[var]):
                if cur == 0: dd = j["date"]
                cur += 1
                if cur > ml: ml, dm_d, dm_f = cur, dd, j["date"]
            elif j[var] is not None:
                cur = 0
        return ml, dm_d, dm_f

    sec_l, sec_d, sec_f = serie(tout,     "RR", lambda v: v < 0.2)
    sec_al, sec_ad, sec_af = serie(jours_an, "RR", lambda v: v < 0.2)
    gel_l, gel_d, gel_f = serie(tout,     "TN", lambda v: v <= 0.0)
    gel_al, gel_ad, gel_af = serie(jours_an, "TN", lambda v: v <= 0.0)

    # Mois chaud / froid (Tmoy)
    mois_tm: dict = defaultdict(list)
    for j in tout:
        if j["TN"] is not None and j["TX"] is not None:
            mois_tm[(j["date"].year, j["date"].month)].append((j["TN"] + j["TX"]) / 2)
    tm = {k: sum(v) / len(v) for k, v in mois_tm.items() if len(v) >= 25}
    k_tmc = max(tm, key=tm.get) if tm else None
    k_tmf = min(tm, key=tm.get) if tm else None
    tm_an = {k: tm[k] for k in tm if k[0] == annee}
    k_tmc_an = max(tm_an, key=tm_an.get) if tm_an else None
    k_tmf_an = min(tm_an, key=tm_an.get) if tm_an else None

    # Helpers
    def bm(r, a): return r is not None and a is not None and a >= r
    def bi(r, a): return r is not None and a is not None and a <= r

    lignes = [
        # ── Températures ────────────────────────────────────────────────────
        {"cat": "🌡️", "variable": "T° maximale absolue (TX)",
         "rv": f"{tx_rv:.1f} °C", "rl": _fdr(tx_rd),
         "av": f"{tx_av:.1f} °C" if tx_av else "—", "al": _fdr(tx_ad),
         "battu": bm(tx_rv, tx_av)},
        {"cat": "🌡️", "variable": "T° minimale absolue (TN)",
         "rv": f"{tn_rv:.1f} °C", "rl": _fdr(tn_rd),
         "av": f"{tn_av:.1f} °C" if tn_av else "—", "al": _fdr(tn_ad),
         "battu": bi(tn_rv, tn_av)},
        {"cat": "🌡️", "variable": "Mois le plus chaud (Tm moy.)",
         "rv": f"{tm[k_tmc]:.1f} °C" if k_tmc else "—", "rl": lab_mois(k_tmc),
         "av": f"{tm_an[k_tmc_an]:.1f} °C" if k_tmc_an else "—", "al": lab_mois(k_tmc_an),
         "battu": bm(tm.get(k_tmc), tm_an.get(k_tmc_an))},
        {"cat": "🌡️", "variable": "Mois le plus froid (Tm moy.)",
         "rv": f"{tm[k_tmf]:.1f} °C" if k_tmf else "—", "rl": lab_mois(k_tmf),
         "av": f"{tm_an[k_tmf_an]:.1f} °C" if k_tmf_an else "—", "al": lab_mois(k_tmf_an),
         "battu": bi(tm.get(k_tmf), tm_an.get(k_tmf_an))},
        # ── Pluie ────────────────────────────────────────────────────────────
        {"cat": "🌧️", "variable": "Pluie max en 24 h (RR)",
         "rv": f"{rr_rv:.1f} mm", "rl": _fdr(rr_rd),
         "av": f"{rr_av:.1f} mm" if rr_av else "—", "al": _fdr(rr_ad),
         "battu": bm(rr_rv, rr_av)},
        {"cat": "🌧️", "variable": "Pluie mensuelle maximale",
         "rv": f"{rrm_max_v:.0f} mm" if rrm_max_v else "—", "rl": lab_mois(k_rrmax),
         "av": f"{comp_an[k_rran_max]:.0f} mm" if k_rran_max else "—", "al": lab_mois(k_rran_max),
         "battu": bm(rrm_max_v, comp_an.get(k_rran_max))},
        {"cat": "🌧️", "variable": "Pluie mensuelle minimale",
         "rv": f"{rrm_min_v:.0f} mm" if rrm_min_v else "—", "rl": lab_mois(k_rrmin),
         "av": f"{comp_an[k_rran_min]:.0f} mm" if k_rran_min else "—", "al": lab_mois(k_rran_min),
         "battu": bi(rrm_min_v, comp_an.get(k_rran_min))},
        {"cat": "🌧️", "variable": "Série la plus longue sans pluie (< 0,2 mm)",
         "rv": f"{sec_l} j", "rl": f"{_fdr(sec_d)} → {_fdr(sec_f)}",
         "av": f"{sec_al} j" if sec_al else "—",
         "al": f"{_fdr(sec_ad)} → {_fdr(sec_af)}" if sec_al else "—",
         "battu": sec_al >= sec_l if sec_al and sec_l else False},
        # ── Vent ─────────────────────────────────────────────────────────────
        {"cat": "💨", "variable": "Vent maximal (rafale FXI)",
         "rv": f"{fx_rv * 3.6:.0f} km/h" if fx_rv else "—", "rl": _fdr(fx_rd),
         "av": f"{fx_av * 3.6:.0f} km/h" if fx_av else "—", "al": _fdr(fx_ad),
         "battu": bm(fx_rv, fx_av)},
        # ── Gel ──────────────────────────────────────────────────────────────
        {"cat": "❄️", "variable": "Série de gels consécutifs (TN ≤ 0 °C)",
         "rv": f"{gel_l} j", "rl": f"{_fdr(gel_d)} → {_fdr(gel_f)}",
         "av": f"{gel_al} j" if gel_al else "—",
         "al": f"{_fdr(gel_ad)} → {_fdr(gel_af)}" if gel_al else "—",
         "battu": gel_al >= gel_l if gel_al and gel_l else False},
        # ── Insolation ───────────────────────────────────────────────────────
        {"cat": "☀️", "variable": "Ensoleillement max (journée) ⚠️",
         "rv": f"{it_rv / 60:.1f} h" if it_rv else "—", "rl": _fdr(it_rd),
         "av": f"{it_av / 60:.1f} h" if it_av else "—", "al": _fdr(it_ad),
         "battu": bm(it_rv, it_av)},
    ]

    tuiles = [
        {"icone": "🌡️", "couleur": "#e74c3c", "titre": "Chaleur record",
         "rv": f"{tx_rv:.1f} °C" if tx_rv else "—", "rl": _fdr(tx_rd),
         "at": f"{tx_av:.1f} °C le {_fdr(tx_ad)}" if tx_av else "—",
         "battu": bm(tx_rv, tx_av)},
        {"icone": "❄️", "couleur": "#5dade2", "titre": "Froid record",
         "rv": f"{tn_rv:.1f} °C" if tn_rv else "—", "rl": _fdr(tn_rd),
         "at": f"{tn_av:.1f} °C le {_fdr(tn_ad)}" if tn_av else "—",
         "battu": bi(tn_rv, tn_av)},
        {"icone": "🌧️", "couleur": "#4ea1ff", "titre": "Pluie record (24 h)",
         "rv": f"{rr_rv:.1f} mm" if rr_rv else "—", "rl": _fdr(rr_rd),
         "at": f"{rr_av:.1f} mm le {_fdr(rr_ad)}" if rr_av else "—",
         "battu": bm(rr_rv, rr_av)},
        {"icone": "💨", "couleur": "#f39c12", "titre": "Vent record",
         "rv": f"{fx_rv * 3.6:.0f} km/h" if fx_rv else "—", "rl": _fdr(fx_rd),
         "at": f"{fx_av * 3.6:.0f} km/h le {_fdr(fx_ad)}" if fx_av else "—",
         "battu": bm(fx_rv, fx_av)},
    ]

    return {
        "annee": annee,
        "periode": f"{tout[0]['date'].strftime('%d/%m/%Y')} → {tout[-1]['date'].strftime('%d/%m/%Y')}",
        "tuiles": tuiles,
        "lignes": lignes,
    }


def rendre_records_html(records: dict) -> str:
    annee = records["annee"]

    tuiles_html = []
    for t in records["tuiles"]:
        badge = ' <span class="rec-badge">★ RECORD</span>' if t["battu"] else ""
        tuiles_html.append(
            f'<div class="rec-tuile" style="border-top-color:{t["couleur"]}">'
            f'<div class="rec-ico">{t["icone"]}</div>'
            f'<div class="rec-titre">{t["titre"]}{badge}</div>'
            f'<div class="rec-val-big" style="color:{t["couleur"]}">{t["rv"]}</div>'
            f'<div class="rec-date">{t["rl"]}</div>'
            f'<div class="rec-an">{annee} : {t["at"]}</div>'
            f'</div>'
        )

    lignes_html = []
    for lig in records["lignes"]:
        cls = ' class="rec-battu"' if lig["battu"] else ""
        star = ' <span class="rec-badge">★</span>' if lig["battu"] else ""
        lignes_html.append(
            f'<tr{cls}>'
            f'<td>{lig["cat"]} {lig["variable"]}</td>'
            f'<td class="rn">{lig["rv"]}</td>'
            f'<td class="rd">{lig["rl"]}</td>'
            f'<td class="rn">{lig["av"]}{star}</td>'
            f'<td class="rd">{lig["al"]}</td>'
            f'</tr>'
        )

    return (
        f'<div class="rec-tuiles">{"".join(tuiles_html)}</div>'
        f'<div class="rec-wrap">'
        f'<table class="rec-table">'
        f'<thead><tr>'
        f'<th>Variable</th><th>Record historique</th><th>Date / Période</th>'
        f'<th>{annee}</th><th>Date / Période</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(lignes_html)}</tbody>'
        f'</table></div>'
        f'<p class="rec-note">'
        f'⚠️ Ensoleillement (☀️) : 30 % de valeurs manquantes avant 2000 —'
        f' le record affiché est indicatif. Vent : valeur en m/s convertie en km/h. '
        f'Données : station 87187003, {records["periode"]}.'
        f'</p>'
    )


# ── Rendu principal ───────────────────────────────────────────────────────────

def main() -> int:
    if not QUOTIDIEN.exists() or not NORMALES.exists() or not HISTORIQUE.exists():
        print("Manquant : data/quotidien.csv, data/historique.csv ou data/normales.csv.", file=sys.stderr)
        return 1

    print("Lecture des données…")
    quotidien = charger_csv(QUOTIDIEN)
    historique = charger_csv(HISTORIQUE)
    normales = charger_normales()
    if not quotidien:
        print("Aucune donnée quotidienne.", file=sys.stderr)
        return 1

    derniere_date = max(j["date"] for j in quotidien)
    mois, annee = derniere_date.month, derniere_date.year
    print(f"  dernière mesure : {derniere_date.isoformat()}")

    jours_mois = sorted(
        [j for j in quotidien if j["date"].year == annee and j["date"].month == mois],
        key=lambda j: j["date"],
    )

    ctx = {
        "mois_titre": f"{MOIS_FR_LONG[mois]} {annee}",
        "annee": annee,
        "station": "Saint-Yrieix-la-Perche · Station 87187003 · alt. 404 m",
        "nb_jours": len(jours_mois),
        "edition": date.today().strftime("%d/%m/%Y"),
        "kpis": construire_kpis(jours_mois, normales[mois]),
        "climogramme": construire_climogramme(quotidien, normales, annee),
        "detail_mois": construire_detail_mois(jours_mois),
        "bilan": construire_bilan_hydrique(quotidien, historique, annee),
        "gc":    construire_gel_et_chaleur(quotidien, historique, annee),
        "pheno": construire_phenologie(quotidien, historique, annee),
        "heatmap": construire_heatmap(quotidien + historique, derniere_date),
        "records": construire_records(quotidien, historique),
    }
    alerte_gc = ctx["gc"]["alerte_txt"]
    print(f"  bilan hydrique  : bilan actuel {ctx['bilan']['bilan_actuel']:+.0f} mm")
    print(f"  gel et chaleur  : {'⚠ ALERTE ITH' if alerte_gc else 'RAS'}")
    print(f"  phénologie      : {len(jours_an := [j for j in quotidien if j['date'].year == annee])} jours")
    print(f"  heatmap         : {ctx['heatmap']['periode']}")

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(rendre_html(ctx), encoding="utf-8")
    print(f"Écrit {SORTIE.relative_to(RACINE)} ({SORTIE.stat().st_size // 1024} Ko).")
    return 0


def rendre_html(ctx: dict) -> str:
    cartes = "\n".join(f"""
        <div class="kpi">
          <div class="kpi-titre">{k['titre']}</div>
          <div class="kpi-valeur">{k['valeur']}</div>
          <div class="kpi-cmp tendance-{k['tendance']}">{k['comparaison']}</div>
        </div>""" for k in ctx["kpis"])

    heatmap_html = rendre_heatmap_html(ctx["heatmap"])
    records_html = rendre_records_html(ctx["records"])
    gc_html      = rendre_gel_chaleur_html(ctx["gc"])

    # Gel et chaleur — données JS pour le graphique ITH
    _ith  = ctx["gc"]["ith_par_mois"]
    _ref  = ctx["gc"]["ith_ref_par_mois"]
    gc_alerte_html = (
        f'<div class="ith-alerte">{ctx["gc"]["alerte_txt"]}</div>'
        if ctx["gc"]["alerte_txt"] else ""
    )
    gc_js = {
        "labels":  ctx["gc"]["labels_mois"],
        "confort": [_ith[str(m)][0] for m in range(1, 13)],
        "alerte":  [_ith[str(m)][1] for m in range(1, 13)],
        "mod":     [_ith[str(m)][2] for m in range(1, 13)],
        "sev":     [_ith[str(m)][3] for m in range(1, 13)],
        "danger":  [_ith[str(m)][4] for m in range(1, 13)],
        "ref_stress": [round(sum(_ref[str(m)][1:]), 1) for m in range(1, 13)],
    }

    # Bilan hydrique — indicateur KPI
    bv = ctx["bilan"]["bilan_actuel"]
    bilan_col  = "#56b85e" if bv >= 0 else "#e8995c"
    bilan_signe = "+" if bv >= 0 else ""
    bilan_mot  = "Excédent" if bv >= 0 else "Déficit"

    # Phénologie — tableau des seuils
    _seuil_rows = []
    for s in ctx["pheno"]["seuils"]:
        bar_col = "#56b85e" if s["date_an"] else "#f39c12"
        avance = ""
        if s["date_an"] and s["ref_med"] and s["ref_med"] != "—":
            # Comparer en jour-de-l'année
            try:
                d_an  = datetime.strptime(f"{s['date_an']}/{ctx['annee']}", "%d/%m/%Y").date()
                d_ref = datetime.strptime(f"{s['ref_med']}/{ctx['annee']}", "%d/%m/%Y").date()
                delta = (d_an - d_ref).days
                if delta != 0:
                    avance = f" <span style='color:{'#56b85e' if delta < 0 else '#e8995c'};font-size:11px'>" \
                             f"({'−' if delta < 0 else '+'}{abs(delta)} j)</span>"
            except ValueError:
                pass
        _seuil_rows.append(
            f'<tr>'
            f'<td>{s["libelle"]}<br>'
            f'<small style="color:var(--texte-doux)">{s["detail"]}</small></td>'
            f'<td class="rn">{s["gdd_actuel"]:.0f} °Cj'
            f'<div class="pheno-bar"><div style="width:{s["pct"]}%;background:{bar_col}"></div></div></td>'
            f'<td class="rn">{"✓ " + s["date_an"] if s["date_an"] else "en cours"}{avance}</td>'
            f'<td class="rn">{s["ref_med"]}</td>'
            f'</tr>'
        )
    pheno_seuils_html = "".join(_seuil_rows)

    data_json = json.dumps({
        "climogramme": ctx["climogramme"],
        "detail_mois": ctx["detail_mois"],
        "bilan": ctx["bilan"],
        "pheno": ctx["pheno"],
        "gc": gc_js,
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Météo St-Yrieix · {ctx['mois_titre']}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #1a1f26; --bg-carte: #232a33; --bg-section: #1f252d;
    --texte: #e6e9ec; --texte-doux: #aab3bc;
    --accent-pluie: #4ea1ff; --accent-tx: #e74c3c; --accent-tn: #5dade2;
    --bord: #2c333d; --hausse: #f39c12; --baisse: #56b85e;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--texte);
    max-width: 980px; margin-inline: auto;
  }}
  header {{ display: flex; justify-content: space-between; align-items: flex-end;
            gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }}
  h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
  h1 small {{ color: var(--texte-doux); font-weight: 400; font-size: 14px;
              display: block; margin-top: 4px; }}
  .edition {{ color: var(--texte-doux); font-size: 13px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }}
  .kpi {{ background: var(--bg-carte); border: 1px solid var(--bord);
          border-radius: 6px; padding: 14px 16px; min-width: 0; }}
  .kpi-titre {{ color: var(--texte-doux); font-size: 13px; }}
  .kpi-valeur {{ font-size: 24px; font-weight: 600; margin: 4px 0;
                 word-break: break-word; }}
  .kpi-cmp {{ font-size: 12px; color: var(--texte-doux); }}
  .tendance-up::before  {{ content: "↗ "; color: var(--hausse); }}
  .tendance-down::before {{ content: "↘ "; color: var(--baisse); }}
  /* Onglets */
  .tabs {{ display: flex; gap: 4px; margin-bottom: 0;
           overflow-x: auto; -webkit-overflow-scrolling: touch;
           scrollbar-width: none; }}
  .tabs::-webkit-scrollbar {{ display: none; }}
  .tab-btn {{ background: var(--bg-carte); color: var(--texte-doux);
              border: 1px solid var(--bord); border-bottom: none;
              padding: 8px 14px; border-radius: 6px 6px 0 0;
              cursor: pointer; font-size: 13px; font-family: inherit;
              white-space: nowrap; flex-shrink: 0; }}
  .tab-btn.actif {{ background: var(--bg-section); color: var(--texte); }}
  .panneau {{ background: var(--bg-section); border: 1px solid var(--bord);
              border-radius: 0 6px 6px 6px; padding: 16px; }}
  .panneau:not(.actif) {{ display: none; }}
  .panneau h2 {{ margin: 0 0 12px; font-size: 14px; font-weight: 600;
                 color: var(--texte-doux); text-transform: uppercase; letter-spacing: 0.5px; }}
  .panneau h2:not(:first-child) {{ margin-top: 24px; }}
  .legende {{ display: flex; gap: 16px; font-size: 13px; margin-bottom: 8px;
              color: var(--texte-doux); flex-wrap: wrap; }}
  .legende span::before {{ content: "■"; margin-right: 4px; }}
  .leg-pluie::before {{ color: var(--accent-pluie); }}
  .leg-tx::before    {{ color: var(--accent-tx); }}
  .leg-tn::before    {{ color: var(--accent-tn); }}
  .leg-norm::before  {{ color: #778291; }}
  .leg-bilan::before {{ color: #56b85e; }}
  canvas {{ max-height: 360px; }}
  /* Heatmap */
  .heatmap-wrapper {{ overflow: hidden; }}
  .heatmap-scroll {{ overflow-x: auto; padding-bottom: 6px; }}
  .hm-mois-row {{ display: grid; margin-left: 32px; font-size: 11px;
                  color: var(--texte-doux); margin-bottom: 4px; }}
  .hm-grid {{ display: flex; gap: 4px; }}
  .hm-jours {{ display: grid; grid-template-rows: repeat(7, 14px); gap: 2px;
               font-size: 10px; color: var(--texte-doux); padding-right: 4px; }}
  .hm-jours span {{ line-height: 14px; }}
  .hm-cols {{ display: flex; gap: 2px; }}
  .hm-col {{ display: grid; grid-template-rows: repeat(7, 14px); gap: 2px; }}
  .hm-cell {{ width: 14px; height: 14px; border-radius: 2px; }}
  .hm-cell.hm-vide {{ background: transparent; }}
  .hm-mois {{ grid-row: 1; }}
  .hm-legende {{ display: flex; align-items: center; gap: 6px;
                 margin-top: 10px; font-size: 11px; color: var(--texte-doux); }}
  .hm-grad {{ flex: 0 0 120px; height: 8px; border-radius: 2px;
              background: linear-gradient(to right, #1f4068, #3a73a8, #9aa3ad, #e8995c, #c0392b); }}

  /* ── Gel & chaleur ── */
  .gel-legende {{ display: flex; gap: 14px; flex-wrap: wrap; margin-top: 10px;
                 font-size: 12px; color: var(--texte-doux); align-items: center; }}
  .gel-sw {{ display: inline-block; width: 12px; height: 12px; border-radius: 2px;
             margin-right: 4px; vertical-align: middle; flex-shrink: 0; }}
  .ith-alerte {{ background: rgba(192,57,43,0.15); border: 1px solid rgba(192,57,43,0.5);
                 border-radius: 6px; padding: 10px 14px; margin-bottom: 14px;
                 font-size: 13px; color: #e74c3c; line-height: 1.5; }}
  .leg-ith-ok::before  {{ color: #2a6496; }}
  .leg-ith-al::before  {{ color: #d4ac0d; }}
  .leg-ith-mo::before  {{ color: #e8995c; }}
  .leg-ith-sv::before  {{ color: #c0392b; }}
  .leg-ith-dg::before  {{ color: #7b241c; }}
  /* ── Bilan hydrique KPI ── */
  .bilan-kpi {{ display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
               background: var(--bg-carte); border: 1px solid var(--bord);
               border-radius: 6px; padding: 12px 16px; margin-bottom: 14px; }}
  .bilan-kpi-val {{ font-size: 28px; font-weight: 700; }}
  .bilan-kpi-label {{ font-size: 13px; color: var(--texte-doux); }}
  .bilan-kpi-desc {{ font-size: 12px; color: var(--texte-doux); }}
  .leg-rr::before   {{ color: rgba(78,161,255,0.7); }}
  .leg-etp::before  {{ color: #e8995c; }}
  .leg-exc::before  {{ color: #56b85e; }}
  .leg-def::before  {{ color: #e8995c; }}
  /* ── Phénologie ── */
  .pheno-table-wrap {{ overflow-x: auto; margin-top: 16px; }}
  .pheno-table {{ width: 100%; border-collapse: collapse; font-size: 13px; min-width: 480px; }}
  .pheno-table thead th {{ text-align: left; padding: 8px 10px; background: var(--bg-carte);
                            color: var(--texte-doux); font-weight: 600; font-size: 11px;
                            text-transform: uppercase; letter-spacing: 0.5px; }}
  .pheno-table tbody td {{ padding: 8px 10px; border-top: 1px solid var(--bord);
                            vertical-align: middle; }}
  .pheno-table tbody tr:hover {{ background: rgba(255,255,255,0.03); }}
  .pheno-bar {{ height: 4px; background: var(--bord); border-radius: 2px;
               margin-top: 4px; width: 80px; display: inline-block; }}
  .pheno-bar div {{ height: 4px; border-radius: 2px; }}
  .leg-b0::before  {{ color: #56b85e; }}
  .leg-b6::before  {{ color: #f39c12; }}
  .leg-b10::before {{ color: #e74c3c; }}
  /* ── Records ── */
  .rec-tuiles {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
  .rec-tuile {{ background: var(--bg-carte); border: 1px solid var(--bord);
                border-top: 3px solid; border-radius: 6px; padding: 14px; }}
  .rec-ico {{ font-size: 22px; margin-bottom: 6px; }}
  .rec-titre {{ font-size: 11px; color: var(--texte-doux); text-transform: uppercase;
                letter-spacing: 0.5px; margin-bottom: 4px; }}
  .rec-val-big {{ font-size: 26px; font-weight: 700; margin-bottom: 2px; line-height: 1.1; }}
  .rec-date {{ font-size: 12px; color: var(--texte-doux); margin-bottom: 8px; }}
  .rec-an {{ font-size: 12px; color: var(--texte-doux); border-top: 1px solid var(--bord);
             padding-top: 7px; }}
  .rec-badge {{ background: #f39c12; color: #1a1f26; font-size: 10px; font-weight: 700;
                padding: 2px 5px; border-radius: 3px; vertical-align: middle;
                white-space: nowrap; }}
  .rec-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 4px; }}
  .rec-table {{ width: 100%; border-collapse: collapse; font-size: 13px; min-width: 560px; }}
  .rec-table thead th {{ text-align: left; padding: 8px 10px; background: var(--bg-carte);
                          color: var(--texte-doux); font-weight: 600; font-size: 11px;
                          text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }}
  .rec-table tbody td {{ padding: 8px 10px; border-top: 1px solid var(--bord);
                          vertical-align: middle; }}
  .rec-table tbody tr:hover {{ background: rgba(255,255,255,0.03); }}
  .rn {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 500; white-space: nowrap; }}
  .rd {{ color: var(--texte-doux); font-size: 12px; white-space: nowrap; }}
  .rec-battu {{ background: rgba(243,156,18,0.08) !important; }}
  .rec-battu td:first-child {{ font-weight: 600; }}
  .rec-note {{ font-size: 12px; color: var(--texte-doux); margin-top: 12px;
               line-height: 1.5; border-top: 1px solid var(--bord); padding-top: 10px; }}
  /* ── Bouton export ── */
  .btn-export {{ background: transparent; color: var(--texte-doux);
                 border: 1px solid var(--bord); border-radius: 4px;
                 padding: 6px 12px; font-size: 12px; font-family: inherit;
                 cursor: pointer; transition: border-color .15s, color .15s; }}
  .btn-export:hover {{ border-color: var(--accent-pluie); color: var(--texte); }}
  /* ── Footer ── */
  footer {{ margin-top: 32px; padding: 14px 0;
            border-top: 1px solid var(--bord);
            font-size: 12px; color: var(--texte-doux); text-align: center; }}
  /* ── Mobile ── */
  @media (max-width: 720px) {{
    .kpis {{ grid-template-columns: repeat(2, 1fr); }}
    canvas {{ max-height: 280px; }}
    .rec-tuiles {{ grid-template-columns: repeat(2, 1fr); }}
  }}
  @media (max-width: 480px) {{
    .gel-legende {{ font-size: 11px; gap: 8px; }}
    .ith-alerte  {{ font-size: 12px; padding: 8px 12px; }}
    body {{ padding: 12px; }}
    h1 {{ font-size: 18px; }}
    h1 small {{ font-size: 12px; }}
    .edition {{ font-size: 11px; }}
    .kpis {{ gap: 8px; }}
    .kpi {{ padding: 10px 12px; }}
    .kpi-titre {{ font-size: 11px; }}
    .kpi-valeur {{ font-size: 18px; }}
    .kpi-cmp {{ font-size: 11px; }}
    .tab-btn {{ padding: 6px 10px; font-size: 12px; }}
    .panneau {{ padding: 12px; border-radius: 0 0 6px 6px; }}
    .panneau h2 {{ font-size: 12px; }}
    .legende {{ font-size: 11px; gap: 8px; }}
    canvas {{ max-height: 240px; }}
    .hm-cell {{ width: 11px; height: 11px; }}
    .hm-jours, .hm-col {{ grid-template-rows: repeat(7, 11px); }}
    .rec-tuiles {{ gap: 8px; }}
    .rec-tuile {{ padding: 10px; }}
    .rec-val-big {{ font-size: 20px; }}
    .rec-table {{ font-size: 12px; }}
  }}
</style>
</head>
<body>
<header>
  <h1>{ctx['mois_titre']} — Saint-Yrieix-la-Perche
    <small>{ctx['station']} · {ctx['nb_jours']} jours</small>
  </h1>
  <div class="edition">Édité le {ctx['edition']}</div>
</header>

<div class="kpis">{cartes}
</div>

<div class="tabs" role="tablist" aria-label="Onglets du tableau de bord">
  <button class="tab-btn actif" id="btn-mois"    role="tab" aria-selected="true"  aria-controls="mois"    data-cible="mois">Mois en cours</button>
  <button class="tab-btn"       id="btn-bilan"   role="tab" aria-selected="false" aria-controls="bilan"   data-cible="bilan">Bilan hydrique</button>
  <button class="tab-btn"       id="btn-pheno"   role="tab" aria-selected="false" aria-controls="pheno"   data-cible="pheno">Phénologie</button>
  <button class="tab-btn"       id="btn-gel"     role="tab" aria-selected="false" aria-controls="gel"     data-cible="gel">Gel et chaleur</button>
  <button class="tab-btn"       id="btn-heatmap" role="tab" aria-selected="false" aria-controls="heatmap" data-cible="heatmap">Heatmap T° max</button>
  <button class="tab-btn"       id="btn-records" role="tab" aria-selected="false" aria-controls="records" data-cible="records">Records</button>
</div>

<div id="mois" class="panneau actif" role="tabpanel" aria-labelledby="btn-mois" tabindex="0">
  <h2>Détail jour par jour — {ctx['mois_titre']}</h2>
  <div class="legende">
    <span class="leg-pluie">Précipitations (mm)</span>
    <span class="leg-tx">T° max (°C)</span>
    <span class="leg-tn">T° min (°C)</span>
  </div>
  <canvas id="detail" role="img" aria-label="Graphique : précipitations journalières, températures max et min — {ctx['mois_titre']}"></canvas>

  <h2>Climogramme {ctx['annee']} — pluie et température</h2>
  <div class="legende">
    <span class="leg-pluie">Pluie {ctx['annee']} (mm)</span>
    <span class="leg-norm">Normale 1995-2024 (mm)</span>
    <span class="leg-tx">T° moyenne (°C)</span>
  </div>
  <canvas id="climo" role="img" aria-label="Climogramme {ctx['annee']} : cumul mensuel pluie et température moyenne vs normales 1995-2024"></canvas>

  <div style="display:flex;justify-content:flex-end;margin-top:14px">
    <button class="btn-export" onclick="exporterCSV()">⬇ Exporter les données du mois en CSV</button>
  </div>
</div>

<div id="bilan" class="panneau" role="tabpanel" aria-labelledby="btn-bilan" tabindex="0">
  <h2>Bilan hydrique {ctx['annee']} — depuis le 1ᵉʳ janvier</h2>
  <div class="bilan-kpi">
    <span class="bilan-kpi-label">{bilan_mot} hydrique cumulé au {ctx['bilan']['labels'][-1] if ctx['bilan']['labels'] else '—'}</span>
    <span class="bilan-kpi-val" style="color:{bilan_col}">{bilan_signe}{bv:.0f} mm</span>
    <span class="bilan-kpi-desc">P − ETP depuis le 1ᵉʳ jan. · référence 1995-2024 : {ctx['bilan']['p_etp_reference'][-1]:.0f} mm</span>
  </div>
  <div class="legende">
    <span class="leg-rr">Pluie cumulée (mm)</span>
    <span class="leg-etp">ETP cumulée (mm)</span>
    <span class="leg-exc">Bilan P−ETP {ctx['annee']}</span>
    <span class="leg-norm">Bilan moyen 1995-2024</span>
  </div>
  <canvas id="bilan_chart" style="max-height:380px" role="img" aria-label="Bilan hydrique {ctx['annee']} : pluie cumulée, ETP cumulée et bilan P-ETP vs référence 1995-2024"></canvas>
  <p style="font-size:12px;color:var(--texte-doux);margin-top:8px">
    ETP Hargreaves-Samani (latitude {LATITUDE_DEG:.3f}°, Ra FAO-56).
    Zone verte = excédent hydrique · zone orange = déficit hydrique.
  </p>
</div>

<div id="pheno" class="panneau" role="tabpanel" aria-labelledby="btn-pheno" tabindex="0">
  <h2>Phénologie {ctx['annee']} — degrés-jours de croissance depuis le 1ᵉʳ janvier</h2>
  <div class="legende">
    <span class="leg-b0">Base 0 °C — herbe (trait plein · pointillés = méd. 1995-2024)</span>
    <span class="leg-b6">Base 6 °C — céréales</span>
    <span class="leg-b10">Base 10 °C — maïs</span>
  </div>
  <canvas id="pheno_chart" style="max-height:340px" role="img" aria-label="Phénologie {ctx['annee']} : degrés-jours cumulés base 0/6/10 °C et médianes historiques 1995-2024"></canvas>
  <div class="pheno-table-wrap">
    <table class="pheno-table">
      <thead><tr>
        <th>Seuil phénologique</th>
        <th>DJC actuel</th>
        <th>{ctx['annee']}</th>
        <th>Médiane 1995-2024</th>
      </tr></thead>
      <tbody>{pheno_seuils_html}</tbody>
    </table>
  </div>
  <p style="font-size:12px;color:var(--texte-doux);margin-top:10px">
    DJC = Σ max(0, (TN+TX)/2 − Tbase) depuis le 1ᵉʳ jan. ·
    Seuils : ARVALIS / INRAE · Médiane calculée sur 1995-2024 (station 87187003).
  </p>
</div>

<div id="gel" class="panneau" role="tabpanel" aria-labelledby="btn-gel" tabindex="0">
  <h2>Gelées {ctx['annee']} — calendrier annuel (Tn journalière)</h2>
  {gc_html}

  <h2 style="margin-top:28px">Stress thermique bovin (ITH) — {ctx['annee']}</h2>
  {gc_alerte_html}
  <div class="legende">
    <span class="leg-ith-ok">Confort (ITH &lt; 68)</span>
    <span class="leg-ith-al">Alerte (68-72)</span>
    <span class="leg-ith-mo">Stress modéré (72-78)</span>
    <span class="leg-ith-sv">Stress sévère (78-84)</span>
    <span class="leg-ith-dg">Danger (≥ 84)</span>
  </div>
  <canvas id="ith_chart" style="max-height:340px" role="img" aria-label="Stress thermique bovin ITH {ctx['annee']} : jours par classe de confort et stress, par mois"></canvas>
  <p style="font-size:12px;color:var(--texte-doux);margin-top:8px">
    ITH = (1,8·TX + 32) − (0,55 − 0,0055·HRmoy) × (1,8·TX − 26) ·
    HRmoy = (UN + UX) / 2 · Seuils et formule : INRAE,
    recommandations stress thermique bovin. Barres = jours par classe ITH en
    {ctx['annee']} · Ligne pointillée = total jours de stress moyen 1995-2024.
  </p>
</div>

<div id="heatmap" class="panneau" role="tabpanel" aria-labelledby="btn-heatmap" tabindex="0">
  <h2>T° max — 12 mois glissants ({ctx['heatmap']['periode']})</h2>
  {heatmap_html}
</div>

<div id="records" class="panneau" role="tabpanel" aria-labelledby="btn-records" tabindex="0">
  <h2>Records historiques — {ctx['records']['periode']}</h2>
  {records_html}
</div>

<footer>
  Données : Météo-France, station Saint-Yrieix-la-Perche (87187003) — Mise à jour : {ctx['edition']}
</footer>

<script>
const DATA = {data_json};
Chart.defaults.color = '#9aa3ad';
Chart.defaults.borderColor = '#2c333d';
Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';

new Chart(document.getElementById('detail'), {{
  type: 'bar',
  data: {{
    labels: DATA.detail_mois.labels,
    datasets: [
      {{ label: 'Pluie (mm)', data: DATA.detail_mois.rr, backgroundColor: '#4ea1ff', yAxisID: 'y', order: 2 }},
      {{ label: 'T° max', data: DATA.detail_mois.tx, type: 'line', borderColor: '#e74c3c',
         backgroundColor: '#e74c3c', tension: 0.25, yAxisID: 'y1', order: 1, spanGaps: true }},
      {{ label: 'T° min', data: DATA.detail_mois.tn, type: 'line', borderColor: '#5dade2',
         backgroundColor: '#5dade2', borderDash: [4,4], tension: 0.25, yAxisID: 'y1', order: 1, spanGaps: true }},
    ],
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y:  {{ position: 'left',  title: {{ display: true, text: 'mm' }} }},
      y1: {{ position: 'right', title: {{ display: true, text: '°C' }}, grid: {{ drawOnChartArea: false }} }},
    }},
  }}
}});

new Chart(document.getElementById('climo'), {{
  data: {{
    labels: DATA.climogramme.labels,
    datasets: [
      {{ type: 'bar',  label: 'Pluie observée', data: DATA.climogramme.rr_reel, backgroundColor: '#4ea1ff', yAxisID: 'y', order: 3 }},
      {{ type: 'bar',  label: 'Pluie normale',  data: DATA.climogramme.rr_norm, backgroundColor: '#3a4452', yAxisID: 'y', order: 4 }},
      {{ type: 'line', label: 'T° moyenne',     data: DATA.climogramme.t_reel, borderColor: '#e74c3c',
         backgroundColor: '#e74c3c', tension: 0.3, yAxisID: 'y1', order: 1, spanGaps: true }},
      {{ type: 'line', label: 'T° normale',     data: DATA.climogramme.t_norm, borderColor: '#9aa3ad',
         borderDash: [5,5], tension: 0.3, yAxisID: 'y1', order: 2, pointRadius: 0 }},
    ],
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y:  {{ position: 'left',  title: {{ display: true, text: 'mm cumulés' }} }},
      y1: {{ position: 'right', title: {{ display: true, text: '°C' }}, grid: {{ drawOnChartArea: false }} }},
    }},
  }}
}});

new Chart(document.getElementById('bilan_chart'), {{
  data: {{
    labels: DATA.bilan.labels,
    datasets: [
      {{ type: 'bar',  label: 'Pluie cumulée',
         data: DATA.bilan.rr_cumul,
         backgroundColor: 'rgba(78,161,255,0.35)', yAxisID: 'y', order: 4 }},
      {{ type: 'line', label: 'ETP cumulée',
         data: DATA.bilan.etp_cumul,
         borderColor: '#e8995c', borderWidth: 1.5, pointRadius: 0,
         tension: 0.2, yAxisID: 'y', order: 3, spanGaps: true }},
      {{ type: 'line', label: 'P − ETP ' + DATA.bilan.annee,
         data: DATA.bilan.p_etp_courant,
         borderColor: '#56b85e', borderWidth: 2.5,
         fill: {{ target: 'origin', above: 'rgba(86,184,94,0.28)', below: 'rgba(232,153,92,0.28)' }},
         tension: 0.2, pointRadius: 0, yAxisID: 'y1', order: 1, spanGaps: true }},
      {{ type: 'line', label: 'Bilan moyen 1995-2024',
         data: DATA.bilan.p_etp_reference,
         borderColor: '#9aa3ad', borderDash: [5,5], borderWidth: 1.5,
         fill: false, tension: 0.2, pointRadius: 0, yAxisID: 'y1', order: 2, spanGaps: true }},
    ],
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ maxTicksLimit: 12, autoSkip: true }} }},
      y:  {{ position: 'left',  title: {{ display: true, text: 'mm cumulés' }}, min: 0 }},
      y1: {{ position: 'right', title: {{ display: true, text: 'P−ETP (mm)' }},
             grid: {{ color: c => c.tick.value === 0 ? '#56b85e66' : '#2c333d' }} }},
    }},
  }}
}});

new Chart(document.getElementById('ith_chart'), {{
  data: {{
    labels: DATA.gc.labels,
    datasets: [
      // ── Barres empilées (jours par classe ITH) ──────────────────────────
      {{ type: 'bar', label: 'Confort',       data: DATA.gc.confort,
         backgroundColor: '#2a6496', stack: 'an' }},
      {{ type: 'bar', label: 'Alerte',        data: DATA.gc.alerte,
         backgroundColor: '#d4ac0d', stack: 'an' }},
      {{ type: 'bar', label: 'Stress modéré', data: DATA.gc.mod,
         backgroundColor: '#e8995c', stack: 'an' }},
      {{ type: 'bar', label: 'Stress sévère', data: DATA.gc.sev,
         backgroundColor: '#c0392b', stack: 'an' }},
      {{ type: 'bar', label: 'Danger',        data: DATA.gc.danger,
         backgroundColor: '#7b241c', stack: 'an' }},
      // ── Référence : total jours de stress (1995-2024) ───────────────────
      {{ type: 'line', label: 'Stress total moyen 1995-2024',
         data: DATA.gc.ref_stress,
         borderColor: '#9aa3ad', borderDash: [5,5], borderWidth: 1.5,
         pointRadius: 4, pointBackgroundColor: '#9aa3ad',
         fill: false, spanGaps: true }},
    ],
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{}},
      y: {{ stacked: true, title: {{ display: true, text: 'Nombre de jours' }}, min: 0 }},
    }},
  }}
}});

new Chart(document.getElementById('pheno_chart'), {{
  type: 'line',
  data: {{
    labels: DATA.pheno.labels,
    datasets: [
      // ── Courbes année en cours ──────────────────────────────────────────
      {{ label: 'Base 0 °C',  data: DATA.pheno.gdd['0'],
         borderColor: '#56b85e', borderWidth: 2.5, pointRadius: 0, tension: 0.2, spanGaps: true }},
      {{ label: 'Base 6 °C',  data: DATA.pheno.gdd['6'],
         borderColor: '#f39c12', borderWidth: 2.5, pointRadius: 0, tension: 0.2, spanGaps: true }},
      {{ label: 'Base 10 °C', data: DATA.pheno.gdd['10'],
         borderColor: '#e74c3c', borderWidth: 2.5, pointRadius: 0, tension: 0.2, spanGaps: true }},
      // ── Références historiques P50 ───────────────────────────────────────
      {{ label: 'Réf. base 0 °C',  data: DATA.pheno.gdd_ref['0'],
         borderColor: '#56b85e', borderDash: [4,4], borderWidth: 1.2, pointRadius: 0, tension: 0.2, spanGaps: true }},
      {{ label: 'Réf. base 6 °C',  data: DATA.pheno.gdd_ref['6'],
         borderColor: '#f39c12', borderDash: [4,4], borderWidth: 1.2, pointRadius: 0, tension: 0.2, spanGaps: true }},
      {{ label: 'Réf. base 10 °C', data: DATA.pheno.gdd_ref['10'],
         borderColor: '#e74c3c', borderDash: [4,4], borderWidth: 1.2, pointRadius: 0, tension: 0.2, spanGaps: true }},
      // ── Lignes de seuils ────────────────────────────────────────────────
      {{ label: '200 DJC (herbe)',  data: Array(DATA.pheno.labels.length).fill(200),
         borderColor: 'rgba(86,184,94,0.45)',  borderDash: [2,5], borderWidth: 1, pointRadius: 0 }},
      {{ label: '1000 DJC (blé)',   data: Array(DATA.pheno.labels.length).fill(1000),
         borderColor: 'rgba(243,156,18,0.45)', borderDash: [2,5], borderWidth: 1, pointRadius: 0 }},
      {{ label: '1700 DJC (maïs)',  data: Array(DATA.pheno.labels.length).fill(1700),
         borderColor: 'rgba(231,76,60,0.45)',  borderDash: [2,5], borderWidth: 1, pointRadius: 0 }},
    ],
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ maxTicksLimit: 12, autoSkip: true }} }},
      y: {{ title: {{ display: true, text: '°C·j cumulés' }}, min: 0 }},
    }},
  }}
}});

// Onglets
function _activerOnglet(btn) {{
  document.querySelectorAll('.tab-btn').forEach(b => {{
    b.classList.remove('actif');
    b.setAttribute('aria-selected', 'false');
  }});
  document.querySelectorAll('.panneau').forEach(p => p.classList.remove('actif'));
  btn.classList.add('actif');
  btn.setAttribute('aria-selected', 'true');
  document.getElementById(btn.dataset.cible).classList.add('actif');
}}
document.querySelectorAll('.tab-btn').forEach(btn => {{
  btn.addEventListener('click', () => _activerOnglet(btn));
  btn.addEventListener('keydown', e => {{
    if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); _activerOnglet(btn); }}
  }});
}});

function exporterCSV() {{
  const d = DATA.detail_mois;
  const lignes = ['Date,Précipitations (mm),T° max (°C),T° min (°C)'];
  d.labels.forEach((l, i) => {{
    const rr = d.rr[i] != null ? d.rr[i] : '';
    const tx = d.tx[i] != null ? d.tx[i] : '';
    const tn = d.tn[i] != null ? d.tn[i] : '';
    lignes.push(`${{l}},${{rr}},${{tx}},${{tn}}`);
  }});
  const blob = new Blob(['﻿' + lignes.join('\n')], {{type: 'text/csv;charset=utf-8;'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const mois = new Date().toISOString().slice(0, 7);
  a.download = `meteo-st-yrieix-${{mois}}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
