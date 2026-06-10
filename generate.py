import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

# --- Config ---
API_KEY = os.environ["API_FOOTBALL_KEY"]
TOURNAMENT_ID = 1  # FIFA World Cup 2026 – uppdatera om nödvändigt
SEASON = 2026
OUTPUT_DIR = Path("docs")

HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}
BASE_URL = "https://v3.football.api-sports.io"


def get_todays_matches():
    """Hämtar matcher för kommande 24 timmar."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    url = f"{BASE_URL}/fixtures"
    params = {
        "league": TOURNAMENT_ID,
        "season": SEASON,
        "from": today,
        "to": tomorrow,
        "timezone": "Europe/Stockholm"
    }

    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    data = response.json()
    return data.get("response", [])


def get_team_form(team_id):
    """Hämtar senaste 5 matcherna för ett lag."""
    url = f"{BASE_URL}/fixtures"
    params = {
        "team": team_id,
        "last": 5,
        "timezone": "Europe/Stockholm"
    }
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    data = response.json()
    fixtures = data.get("response", [])

    form = []
    for f in fixtures:
        home = f["teams"]["home"]
        away = f["teams"]["away"]
        goals_home = f["goals"]["home"]
        goals_away = f["goals"]["away"]
        if home["id"] == team_id:
            result = "V" if home["winner"] else ("O" if away["winner"] else "X")
            form.append({"result": result, "score": f"{goals_home}-{goals_away}", "opponent": away["name"]})
        else:
            result = "V" if away["winner"] else ("O" if home["winner"] else "X")
            form.append({"result": result, "score": f"{goals_home}-{goals_away}", "opponent": home["name"]})

    return form


def render_html(match, home_form, away_form):
    """Genererar HTML för en matchsida."""
    fixture = match["fixture"]
    home = match["teams"]["home"]
    away = match["teams"]["away"]
    venue = fixture.get("venue", {})

    kickoff_utc = fixture["date"]
    kickoff_dt = datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
    kickoff_stockholm = kickoff_dt + timedelta(hours=2)  # CEST
    kickoff_str = kickoff_stockholm.strftime("%d %b %Y, %H:%M")

    def form_badges(form):
        badges = ""
        colors = {"V": "#22c55e", "X": "#f59e0b", "O": "#ef4444"}
        for f in form:
            color = colors.get(f["result"], "#888")
            badges += f'<span class="badge" style="background:{color}" title="{f["opponent"]} {f["score"]}">{f["result"]}</span>'
        return badges

    home_badges = form_badges(home_form)
    away_badges = form_badges(away_form)

    html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{home['name']} vs {away['name']} – VM 2026</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --ink: #0f0f0f;
      --paper: #f7f4ef;
      --rule: #d4cfc7;
      --accent: #c0392b;
      --muted: #6b6560;
      --green: #22c55e;
      --amber: #f59e0b;
      --red: #ef4444;
    }}

    body {{
      background: var(--paper);
      color: var(--ink);
      font-family: 'Inter', sans-serif;
      font-size: 15px;
      line-height: 1.6;
      padding: 0 16px 48px;
      max-width: 680px;
      margin: 0 auto;
    }}

    /* ── MASTHEAD ── */
    .masthead {{
      border-bottom: 3px solid var(--ink);
      padding: 20px 0 12px;
      margin-bottom: 24px;
      text-align: center;
    }}
    .masthead .kicker {{
      font-size: 11px;
      letter-spacing: .12em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .masthead h1 {{
      font-family: 'Playfair Display', serif;
      font-size: clamp(26px, 7vw, 42px);
      font-weight: 900;
      line-height: 1.05;
      letter-spacing: -.02em;
    }}
    .masthead .meta {{
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
      letter-spacing: .06em;
      text-transform: uppercase;
    }}
    .masthead .meta span {{
      margin: 0 8px;
    }}

    /* ── SECTION LABEL ── */
    .section-label {{
      font-size: 10px;
      font-weight: 600;
      letter-spacing: .14em;
      text-transform: uppercase;
      color: var(--accent);
      border-top: 1.5px solid var(--accent);
      padding-top: 6px;
      margin: 28px 0 12px;
    }}

    /* ── TEAMS ROW ── */
    .teams {{
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      gap: 12px;
      margin: 24px 0;
    }}
    .team {{ text-align: center; }}
    .team img {{
      width: 56px;
      height: 56px;
      object-fit: contain;
      margin-bottom: 8px;
    }}
    .team-name {{
      font-family: 'Playfair Display', serif;
      font-size: 18px;
      font-weight: 700;
      line-height: 1.2;
    }}
    .vs {{
      font-family: 'Playfair Display', serif;
      font-size: 22px;
      font-weight: 900;
      color: var(--muted);
    }}

    /* ── FORM ── */
    .form-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 0;
      border-bottom: 1px solid var(--rule);
    }}
    .form-row:first-child {{ border-top: 1px solid var(--rule); }}
    .form-team {{
      width: 120px;
      font-weight: 600;
      font-size: 13px;
    }}
    .badges {{ display: flex; gap: 5px; flex-wrap: wrap; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 26px;
      height: 26px;
      border-radius: 4px;
      color: #fff;
      font-size: 11px;
      font-weight: 700;
      cursor: default;
    }}

    /* ── INFO GRID ── */
    .info-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1px;
      background: var(--rule);
      border: 1px solid var(--rule);
      border-radius: 6px;
      overflow: hidden;
    }}
    .info-cell {{
      background: var(--paper);
      padding: 12px 14px;
    }}
    .info-cell .label {{
      font-size: 10px;
      font-weight: 600;
      letter-spacing: .1em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 3px;
    }}
    .info-cell .value {{
      font-size: 15px;
      font-weight: 600;
    }}

    /* ── FOOTER ── */
    footer {{
      margin-top: 40px;
      border-top: 1px solid var(--rule);
      padding-top: 12px;
      font-size: 11px;
      color: var(--muted);
      text-align: center;
    }}
  </style>
</head>
<body>

  <div class="masthead">
    <div class="kicker">VM 2026 · Matchguide</div>
    <h1>{home['name']}<br>mot {away['name']}</h1>
    <div class="meta">
      <span>⏱ {kickoff_str}</span>
      <span>📍 {venue.get('name', '–')}, {venue.get('city', '–')}</span>
    </div>
  </div>

  <div class="teams">
    <div class="team">
      <img src="{home['logo']}" alt="{home['name']}">
      <div class="team-name">{home['name']}</div>
    </div>
    <div class="vs">vs</div>
    <div class="team">
      <img src="{away['logo']}" alt="{away['name']}">
      <div class="team-name">{away['name']}</div>
    </div>
  </div>

  <div class="section-label">Senaste form (5 matcher)</div>
  <div class="form-row">
    <div class="form-team">{home['name']}</div>
    <div class="badges">{home_badges}</div>
  </div>
  <div class="form-row">
    <div class="form-team">{away['name']}</div>
    <div class="badges">{away_badges}</div>
  </div>

  <div class="section-label">Matchfakta</div>
  <div class="info-grid">
    <div class="info-cell">
      <div class="label">Turnering</div>
      <div class="value">FIFA VM 2026</div>
    </div>
    <div class="info-cell">
      <div class="label">Avspark</div>
      <div class="value">{kickoff_str}</div>
    </div>
    <div class="info-cell">
      <div class="label">Arena</div>
      <div class="value">{venue.get('name', '–')}</div>
    </div>
    <div class="info-cell">
      <div class="label">Stad</div>
      <div class="value">{venue.get('city', '–')}</div>
    </div>
  </div>

  <footer>
    Genererad {datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC · VM-guide 2026
  </footer>

</body>
</html>"""
    return html


def build_index(matches_meta):
    """Genererar en indexsida med länkar till alla dagens matcher."""
    today_str = datetime.utcnow().strftime("%d %B %Y")
    cards = ""
    for m in matches_meta:
        cards += f"""
    <a class="card" href="{m['filename']}">
      <div class="card-time">{m['time']}</div>
      <div class="card-teams">{m['home']} <span>vs</span> {m['away']}</div>
      <div class="card-venue">{m['venue']}</div>
    </a>"""

    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VM 2026 – Dagens matcher</title>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{ --ink: #0f0f0f; --paper: #f7f4ef; --rule: #d4cfc7; --accent: #c0392b; --muted: #6b6560; }}
    body {{ background: var(--paper); color: var(--ink); font-family: 'Inter', sans-serif; padding: 16px; max-width: 680px; margin: 0 auto; }}
    .masthead {{ border-bottom: 3px solid var(--ink); padding: 20px 0 12px; margin-bottom: 24px; text-align: center; }}
    .masthead h1 {{ font-family: 'Playfair Display', serif; font-size: 36px; font-weight: 900; }}
    .masthead .date {{ font-size: 13px; color: var(--muted); margin-top: 6px; text-transform: uppercase; letter-spacing: .08em; }}
    .card {{ display: block; text-decoration: none; color: inherit; border: 1px solid var(--rule); border-radius: 8px; padding: 16px; margin-bottom: 12px; transition: border-color .2s; }}
    .card:hover {{ border-color: var(--accent); }}
    .card-time {{ font-size: 11px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); margin-bottom: 4px; }}
    .card-teams {{ font-family: 'Playfair Display', serif; font-size: 20px; font-weight: 700; }}
    .card-teams span {{ color: var(--muted); font-weight: 400; margin: 0 6px; }}
    .card-venue {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
    .empty {{ text-align: center; color: var(--muted); padding: 48px 0; font-style: italic; }}
    footer {{ margin-top: 32px; border-top: 1px solid var(--rule); padding-top: 12px; font-size: 11px; color: var(--muted); text-align: center; }}
  </style>
</head>
<body>
  <div class="masthead">
    <h1>VM 2026</h1>
    <div class="date">Matcher · {today_str}</div>
  </div>
  {"".join([cards]) if matches_meta else '<div class="empty">Inga matcher de kommande 24 timmarna.</div>'}
  <footer>Uppdaterad {datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC</footer>
</body>
</html>"""


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("Hämtar matcher...")
    matches = get_todays_matches()
    print(f"Hittade {len(matches)} matcher.")

    matches_meta = []

    for match in matches:
        fixture_id = match["fixture"]["id"]
        home = match["teams"]["home"]
        away = match["teams"]["away"]
        venue = match["fixture"].get("venue", {})

        print(f"  Behandlar: {home['name']} vs {away['name']}")

        home_form = get_team_form(home["id"])
        away_form = get_team_form(away["id"])

        html = render_html(match, home_form, away_form)
        filename = f"match_{fixture_id}.html"
        (OUTPUT_DIR / filename).write_text(html, encoding="utf-8")

        kickoff_utc = match["fixture"]["date"]
        kickoff_dt = datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
        kickoff_stockholm = kickoff_dt + timedelta(hours=2)

        matches_meta.append({
            "filename": filename,
            "home": home["name"],
            "away": away["name"],
            "time": kickoff_stockholm.strftime("%H:%M"),
            "venue": venue.get("name", "–")
        })

    index_html = build_index(matches_meta)
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print("Klart! Indexsida och matchsidor genererade.")


if __name__ == "__main__":
    main()
