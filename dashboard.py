"""Génère output/index.html : tableau de bord météo St-Yrieix
(climogramme 12 mois + détail jour-par-jour du mois en cours + indicateurs clés
comparés aux normales). Inspiré de docs/maquette.png."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RACINE = Path(__file__).parent
QUOTIDIEN = RACINE / "data" / "quotidien.csv"
NORMALES = RACINE / "data" / "normales.csv"
SORTIE = RACINE / "output" / "index.html"

MOIS_FR = ["", "janv.", "févr.", "mars", "avr.", "mai", "juin",
           "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MOIS_FR_LONG = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def parser_float(s: str) -> float | None:
    if s is None or s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def charger_quotidien() -> list[dict]:
    lignes = []
    with QUOTIDIEN.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            d = datetime.strptime(row["date"], "%Y-%m-%d").date()
            lignes.append({
                "date": d,
                "RR":   parser_float(row["RR"]),
                "TN":   parser_float(row["TN"]),
                "TX":   parser_float(row["TX"]),
                "FXI":  parser_float(row["FXI"]),
                "DXI":  parser_float(row["DXI"]),
                "UN":   parser_float(row["UN"]),
                "UX":   parser_float(row["UX"]),
                "INST": parser_float(row["INST"]),
            })
    return lignes


def charger_normales() -> dict[int, dict[str, float]]:
    out = {}
    with NORMALES.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            mois = int(row["mois"])
            out[mois] = {k: parser_float(v) for k, v in row.items() if k != "mois"}
    return out


def direction_rose(deg: float | None) -> str:
    if deg is None:
        return "—"
    secteurs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]
    return secteurs[int((deg % 360) / 22.5 + 0.5) % 16]


def cumul_mensuel_actuel(jours: list[dict], mois: int, annee: int, champ: str) -> float | None:
    """Somme des `champ` pour les jours du mois (ignore None)."""
    valeurs = [j[champ] for j in jours if j["date"].year == annee and j["date"].month == mois and j[champ] is not None]
    return sum(valeurs) if valeurs else None


def moyenne_mensuelle(jours: list[dict], mois: int, annee: int, champ: str) -> float | None:
    valeurs = [j[champ] for j in jours if j["date"].year == annee and j["date"].month == mois and j[champ] is not None]
    return sum(valeurs) / len(valeurs) if valeurs else None


def construire_kpis(jours_mois: list[dict], normales_mois: dict[str, float]) -> list[dict]:
    """4 indicateurs : pluie, T° moyenne, vent max, insolation."""
    # Pluie
    rr_total = sum(j["RR"] for j in jours_mois if j["RR"] is not None)
    rr_normale = normales_mois.get("RR")
    # T° moyenne (TN+TX)/2 jour par jour, puis moyenne
    tnxs = [(j["TN"] + j["TX"]) / 2 for j in jours_mois if j["TN"] is not None and j["TX"] is not None]
    t_moy = sum(tnxs) / len(tnxs) if tnxs else None
    t_normale = ((normales_mois.get("TN") or 0) + (normales_mois.get("TX") or 0)) / 2 if normales_mois.get("TN") is not None else None
    # Vent max (FXI en m/s -> km/h)
    rafales = [(j["FXI"], j["DXI"], j["date"]) for j in jours_mois if j["FXI"] is not None]
    if rafales:
        fxi_max, dxi_max, date_max = max(rafales, key=lambda x: x[0])
        vent_kmh = fxi_max * 3.6
    else:
        vent_kmh = dxi_max = date_max = None
    # Insolation (minutes -> heures)
    inst_total_min = sum(j["INST"] for j in jours_mois if j["INST"] is not None)
    inst_h = inst_total_min / 60 if inst_total_min else 0
    inst_normale_h = (normales_mois.get("INST") or 0) / 60 if normales_mois.get("INST") else None

    def pct(v, n):
        if v is None or n is None or n == 0:
            return None
        return round((v - n) / n * 100, 0)

    return [
        {
            "titre": "Cumul pluie",
            "valeur": f"{rr_total:.1f} mm" if rr_total else "0,0 mm",
            "comparaison": (
                f"{'+' if pct(rr_total, rr_normale) and pct(rr_total, rr_normale) >= 0 else ''}{pct(rr_total, rr_normale):.0f}% / normale ≈ {rr_normale:.0f} mm"
                if rr_normale else ""
            ),
            "tendance": "up" if pct(rr_total, rr_normale) and pct(rr_total, rr_normale) > 5 else ("down" if pct(rr_total, rr_normale) and pct(rr_total, rr_normale) < -5 else "flat"),
        },
        {
            "titre": "T° moyenne",
            "valeur": f"{t_moy:.1f} °C" if t_moy is not None else "—",
            "comparaison": (
                f"{'+' if (t_moy - t_normale) >= 0 else ''}{(t_moy - t_normale):.1f} °C / normale ≈ {t_normale:.1f} °C"
                if t_moy is not None and t_normale is not None else ""
            ),
            "tendance": "up" if t_moy and t_normale and (t_moy - t_normale) > 0.5 else ("down" if t_moy and t_normale and (t_moy - t_normale) < -0.5 else "flat"),
        },
        {
            "titre": "Vent max",
            "valeur": f"{vent_kmh:.1f} km/h" if vent_kmh else "—",
            "comparaison": (
                f"{date_max.strftime('%d/%m')} · {direction_rose(dxi_max)}"
                if date_max else ""
            ),
            "tendance": "flat",
        },
        {
            "titre": "Insolation",
            "valeur": f"{inst_h:.0f} h" if inst_h else "—",
            "comparaison": (
                f"normale ≈ {inst_normale_h:.0f} h" if inst_normale_h else ""
            ),
            "tendance": "up" if inst_h and inst_normale_h and inst_h > inst_normale_h * 1.05 else ("down" if inst_h and inst_normale_h and inst_h < inst_normale_h * 0.95 else "flat"),
        },
    ]


def construire_climogramme(jours: list[dict], normales: dict, annee: int) -> dict:
    """12 mois : cumul pluie réel vs normale, T° moy réelle vs normale."""
    rr_reel, rr_norm, t_reel, t_norm = [], [], [], []
    for m in range(1, 13):
        rr_reel.append(cumul_mensuel_actuel(jours, m, annee, "RR") or 0)
        rr_norm.append(normales[m]["RR"])
        tn = moyenne_mensuelle(jours, m, annee, "TN")
        tx = moyenne_mensuelle(jours, m, annee, "TX")
        t_reel.append(round((tn + tx) / 2, 1) if tn is not None and tx is not None else None)
        t_norm.append(round((normales[m]["TN"] + normales[m]["TX"]) / 2, 1))
    return {
        "labels": [MOIS_FR[m] for m in range(1, 13)],
        "rr_reel": rr_reel,
        "rr_norm": rr_norm,
        "t_reel": t_reel,
        "t_norm": t_norm,
    }


def construire_detail_mois(jours_mois: list[dict]) -> dict:
    return {
        "labels": [j["date"].strftime("%d") for j in jours_mois],
        "rr":    [j["RR"]  if j["RR"]  is not None else 0 for j in jours_mois],
        "tx":    [j["TX"]  if j["TX"]  is not None else None for j in jours_mois],
        "tn":    [j["TN"]  if j["TN"]  is not None else None for j in jours_mois],
    }


def main() -> int:
    if not QUOTIDIEN.exists() or not NORMALES.exists():
        print("Il faut d'abord lancer download.py et normales.py.", file=sys.stderr)
        return 1

    print("Lecture des données…")
    jours = charger_quotidien()
    normales = charger_normales()
    if not jours:
        print("Aucune donnée quotidienne.", file=sys.stderr)
        return 1

    derniere_date = max(j["date"] for j in jours)
    mois_courant = derniere_date.month
    annee_courante = derniere_date.year
    print(f"  dernière mesure : {derniere_date.isoformat()}")
    print(f"  mois courant    : {MOIS_FR_LONG[mois_courant]} {annee_courante}")

    jours_mois = sorted(
        [j for j in jours if j["date"].year == annee_courante and j["date"].month == mois_courant],
        key=lambda j: j["date"],
    )

    contexte = {
        "mois_titre": f"{MOIS_FR_LONG[mois_courant]} {annee_courante}",
        "station": "Saint-Yrieix-la-Perche · Station 87187003 · alt. 404 m",
        "nb_jours": len(jours_mois),
        "edition": date.today().strftime("%d/%m/%Y"),
        "kpis": construire_kpis(jours_mois, normales[mois_courant]),
        "climogramme": construire_climogramme(jours, normales, annee_courante),
        "detail_mois": construire_detail_mois(jours_mois),
    }

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(rendre_html(contexte), encoding="utf-8")
    print(f"Écrit {SORTIE.relative_to(RACINE)} ({SORTIE.stat().st_size // 1024} Ko).")
    return 0


def rendre_html(ctx: dict) -> str:
    cartes = "\n".join(f"""
        <div class="kpi">
          <div class="kpi-titre">{k['titre']}</div>
          <div class="kpi-valeur">{k['valeur']}</div>
          <div class="kpi-cmp tendance-{k['tendance']}">{k['comparaison']}</div>
        </div>""" for k in ctx["kpis"])

    data_json = json.dumps({
        "climogramme": ctx["climogramme"],
        "detail_mois": ctx["detail_mois"],
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
    --bg: #1a1f26;
    --bg-carte: #232a33;
    --bg-section: #1f252d;
    --texte: #e6e9ec;
    --texte-doux: #9aa3ad;
    --accent: #4ea1ff;
    --accent-pluie: #4ea1ff;
    --accent-tx: #e74c3c;
    --accent-tn: #5dade2;
    --bord: #2c333d;
    --hausse: #f39c12;
    --baisse: #56b85e;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--texte);
    max-width: 980px; margin-inline: auto;
  }}
  header {{ display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px; }}
  h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
  h1 small {{ color: var(--texte-doux); font-weight: 400; font-size: 14px; display: block; margin-top: 4px; }}
  .edition {{ color: var(--texte-doux); font-size: 13px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
  .kpi {{ background: var(--bg-carte); border: 1px solid var(--bord); border-radius: 6px; padding: 14px 16px; }}
  .kpi-titre {{ color: var(--texte-doux); font-size: 13px; }}
  .kpi-valeur {{ font-size: 24px; font-weight: 600; margin: 4px 0; }}
  .kpi-cmp {{ font-size: 12px; color: var(--texte-doux); }}
  .tendance-up::before {{ content: "↗ "; color: var(--hausse); }}
  .tendance-down::before {{ content: "↘ "; color: var(--baisse); }}
  .section {{ background: var(--bg-section); border: 1px solid var(--bord); border-radius: 6px; padding: 16px; margin-bottom: 16px; }}
  .section h2 {{ margin: 0 0 12px; font-size: 14px; font-weight: 600; color: var(--texte-doux); text-transform: uppercase; letter-spacing: 0.5px; }}
  .legende {{ display: flex; gap: 16px; font-size: 13px; margin-bottom: 8px; color: var(--texte-doux); }}
  .legende span::before {{ content: "■"; margin-right: 4px; }}
  .leg-pluie::before {{ color: var(--accent-pluie); }}
  .leg-tx::before {{ color: var(--accent-tx); }}
  .leg-tn::before {{ color: var(--accent-tn); }}
  .leg-norm::before {{ color: #555e6b; }}
  canvas {{ max-height: 360px; }}
  @media (max-width: 720px) {{
    .kpis {{ grid-template-columns: repeat(2, 1fr); }}
    header {{ flex-direction: column; align-items: flex-start; gap: 8px; }}
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

<div class="section">
  <h2>Détail jour par jour — {ctx['mois_titre']}</h2>
  <div class="legende">
    <span class="leg-pluie">Précipitations (mm)</span>
    <span class="leg-tx">T° max (°C)</span>
    <span class="leg-tn">T° min (°C)</span>
  </div>
  <canvas id="detail"></canvas>
</div>

<div class="section">
  <h2>Climogramme {ctx['mois_titre'].split()[-1]} — pluie et température</h2>
  <div class="legende">
    <span class="leg-pluie">Pluie {ctx['mois_titre'].split()[-1]} (mm)</span>
    <span class="leg-norm">Normale 1995-2024 (mm)</span>
    <span class="leg-tx">T° moyenne (°C)</span>
  </div>
  <canvas id="climo"></canvas>
</div>

<script>
const DATA = {data_json};
Chart.defaults.color = '#9aa3ad';
Chart.defaults.borderColor = '#2c333d';

new Chart(document.getElementById('detail'), {{
  type: 'bar',
  data: {{
    labels: DATA.detail_mois.labels,
    datasets: [
      {{ label: 'Pluie (mm)', data: DATA.detail_mois.rr, backgroundColor: '#4ea1ff', yAxisID: 'y', order: 2 }},
      {{ label: 'T° max (°C)', data: DATA.detail_mois.tx, type: 'line', borderColor: '#e74c3c', backgroundColor: '#e74c3c', tension: 0.25, yAxisID: 'y1', order: 1 }},
      {{ label: 'T° min (°C)', data: DATA.detail_mois.tn, type: 'line', borderColor: '#5dade2', backgroundColor: '#5dade2', borderDash: [4,4], tension: 0.25, yAxisID: 'y1', order: 1 }},
    ],
  }},
  options: {{
    responsive: true,
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
      {{ type: 'bar', label: 'Pluie observée', data: DATA.climogramme.rr_reel, backgroundColor: '#4ea1ff', yAxisID: 'y', order: 3 }},
      {{ type: 'bar', label: 'Pluie normale',  data: DATA.climogramme.rr_norm, backgroundColor: '#3a4452', yAxisID: 'y', order: 4 }},
      {{ type: 'line', label: 'T° moyenne',    data: DATA.climogramme.t_reel, borderColor: '#e74c3c', backgroundColor: '#e74c3c', tension: 0.3, yAxisID: 'y1', order: 1, spanGaps: true }},
      {{ type: 'line', label: 'T° normale',    data: DATA.climogramme.t_norm, borderColor: '#9aa3ad', borderDash: [5,5], tension: 0.3, yAxisID: 'y1', order: 2, pointRadius: 0 }},
    ],
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y:  {{ position: 'left',  title: {{ display: true, text: 'mm cumulés' }} }},
      y1: {{ position: 'right', title: {{ display: true, text: '°C' }}, grid: {{ drawOnChartArea: false }} }},
    }},
  }}
}});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
