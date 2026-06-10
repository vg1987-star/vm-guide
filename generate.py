import os
import requests
import anthropic
from datetime import datetime, timedelta
from pathlib import Path

# --- Config ---
API_FOOTBALL_KEY = os.environ["API_FOOTBALL_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TOURNAMENT_ID = 1  # FIFA World Cup – verifiera rätt ID när turneringen startar
SEASON = 2026
OUTPUT_DIR = Path("docs")

HEADERS = {
    "x-rapidapi-key": API_FOOTBALL_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}
BASE_URL = "https://v3.football.api-sports.io"
ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── DATAHÄMTNING ────────────────────────────────────────────────────────────

def get_todays_matches():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    params = {
        "league": TOURNAMENT_ID,
        "season": SEASON,
        "from": today,
        "to": tomorrow,
        "timezone": "Europe/Stockholm"
    }
    r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json().get("response", [])


def get_team_form(team_id):
    params = {"team": team_id, "last": 5, "timezone": "Europe/Stockholm"}
    r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS, params=params)
    r.raise_for_status()
    fixtures = r.json().get("response", [])
    form = []
    for f in fixtures:
        home = f["teams"]["home"]
        away = f["teams"]["away"]
        gh = f["goals"]["home"]
        ga = f["goals"]["away"]
        if home["id"] == team_id:
            result = "V" if home["winner"] else ("O" if away["winner"] else "X")
            form.append({"result": result, "score": f"{gh}-{ga}", "opponent": away["name"]})
        else:
            result = "V" if away["winner"] else ("O" if home["winner"] else "X")
            form.append({"result": result, "score": f"{gh}-{ga}", "opponent": home["name"]})
    return form


def get_odds(fixture_id):
    params = {"fixture": fixture_id, "bet": 1}  # bet 1 = Match Winner (1X2)
    r = requests.get(f"{BASE_URL}/odds", headers=HEADERS, params=params)
    r.raise_for_status()
    data = r.json().get("response", [])
    if not data:
        return None
    try:
        bets = data[0]["bookmakers"][0]["bets"][0]["values"]
        odds = {b["value"]: float(b["odd"]) for b in bets}
        return {
            "home": odds.get("Home"),
            "draw": odds.get("Draw"),
            "away": odds.get("Away"),
            "bookmaker": data[0]["bookmakers"][0]["name"]
        }
    except (IndexError, KeyError):
        return None


# ── REDAKTIONELLT INNEHÅLL VIA CLAUDE ───────────────────────────────────────

def build_context(home, away, home_form, away_form, odds):
    def form_str(form):
        if not form:
            return "Ingen data tillgänglig"
        return ", ".join([f"{f['result']} mot {f['opponent']} ({f['score']})" for f in form])

    odds_str = ""
    if odds:
        odds_str = f"\nODDS ({odds['bookmaker']}): {home['name']} {odds['home']} | Oavgjort {odds['draw']} | {away['name']} {odds['away']}"

    return f"""Match: {home['name']} vs {away['name']}
Turnering: FIFA VM 2026

{home['name'].upper()} – senaste 5 matcher:
{form_str(home_form)}

{away['name'].upper()} – senaste 5 matcher:
{form_str(away_form)}
{odds_str}"""


def claude_call(system_prompt, context, max_tokens=400):
    msg = ai.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": context}]
    )
    return msg.content[0].text.strip()


def get_intro(context):
    return claude_call("""Du är chefredaktör på Expressen Sport med 20 år i branschen.
Skriv en matchintro på svenska (3–5 meningar). Expressen-stil: korthuggat, engagerat,
känslosam inledningsrad som drar in läsaren. Ren löptext, inga rubriker eller punkter.""",
        context, max_tokens=300)


def get_taktik(context):
    return claude_call("""Du är taktikanalytiker på Expressen Sport.
Skriv en taktisk analys på svenska (max 150 ord). Täck:
– Förväntad spelstil och uppställning för varje lag
– En nyckelduell att hålla koll på
Skriv som löptext i korta stycken. Inga punktlistor.""",
        context, max_tokens=400)


def get_snackisar(context):
    return claude_call("""Du är snackisredaktör på Expressen Sport.
Skriv exakt 3 snackisar inför matchen på svenska.
Format – varje snackis på detta sätt:
RUBRIK I VERSALER
Två meningar i tabloidstil. Underhållande och lite provokativt men faktabaserat.

Separera snackisarna med en blank rad. Inget annat.""",
        context, max_tokens=500)


def get_odds_text(context, odds):
    if not odds:
        return None
    return claude_call("""Du är oddsanalytiker på Expressen Sport.
Analysera oddsen kort på svenska (max 70 ord).
Avsluta alltid med raden: VÅRT TIPS: [ditt tips]
Inga moraliseringar om spelande.""",
        context, max_tokens=200)


# ── HTML-GENERERING ─────────────────────────────────────────────────────────

def format_snackisar_html(text):
    html = ""
    for block in text.strip().split("\n\n"):
        lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
        if len(lines) >= 2:
            html += f'<div class="snackis"><div class="snackis-title">{lines[0]}</div><p>{" ".join(lines[1:])}</p></div>'
    return html


def render_match_page(match, home_form, away_form, odds, intro, taktik, snackisar, odds_text):
    fixture = match["fixture"]
    home = match["teams"]["home"]
    away = match["teams"]["away"]
    venue = fixture.get("venue", {})

    kickoff_dt = datetime.fromisoformat(fixture["date"].replace("Z", "+00:00"))
    kickoff_swe = kickoff_dt + timedelta(hours=2)
    kickoff_str = kickoff_swe.strftime("%d %b %Y · %H:%M")

    def form_badges(form):
        colors = {"V": "#16a34a", "X": "#d97706", "O": "#dc2626"}
        return "".join(
            f'<span class="badge" style="background:{colors.get(f["result"], "#888")}" title="{f["opponent"]} {f["score"]}">{f["result"]}</span>'
            for f in form
        )

    odds_section = ""
    if odds:
        tip_html = f'<p class="odds-tip">{odds_text}</p>' if odds_text else ""
        odds_section = f"""
  <div class="section-header">
    <div class="section-label">Odds &amp; Speltips</div>
    <div class="byline">Oddsanalytiker</div>
  </div>
  <div class="odds-row">
    <div class="odds-cell"><div class="odds-label">{home['name']}</div><div class="odds-value">{odds['home']}</div></div>
    <div class="odds-cell"><div class="odds-label">Oavgjort</div><div class="odds-value">{odds['draw']}</div></div>
    <div class="odds-cell"><div class="odds-label">{away['name']}</div><div class="odds-value">{odds['away']}</div></div>
  </div>
  {tip_html}
  <p class="odds-source">Källa: {odds['bookmaker']}</p>"""

    taktik_html = "".join(
        f"<p>{p.strip()}</p>" for p in taktik.split("\n") if p.strip()
    )

    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{home['name']} vs {away['name']} – VM 2026</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --ink: #0f0f0f;
      --paper: #f7f4ef;
      --rule: #d4cfc7;
      --accent: #e30613;
      --muted: #6b6560;
    }}
    body {{
      background: var(--paper);
      color: var(--ink);
      font-family: 'Inter', sans-serif;
      font-size: 15px;
      line-height: 1.65;
      padding: 0 16px 56px;
      max-width: 680px;
      margin: 0 auto;
    }}

    /* MASTHEAD */
    .masthead {{
      border-top: 5px solid var(--accent);
      border-bottom: 3px solid var(--ink);
      padding: 20px 0 14px;
      margin-bottom: 28px;
      text-align: center;
    }}
    .kicker {{
      font-size: 10px;
      font-weight: 600;
      letter-spacing: .16em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 8px;
    }}
    .masthead h1 {{
      font-family: 'Playfair Display', serif;
      font-size: clamp(28px, 8vw, 46px);
      font-weight: 900;
      line-height: 1.05;
      letter-spacing: -.02em;
    }}
    .meta {{
      margin-top: 10px;
      font-size: 12px;
      color: var(--muted);
      letter-spacing: .06em;
      text-transform: uppercase;
    }}
    .meta span {{ margin: 0 8px; }}

    /* TEAMS */
    .teams {{
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      gap: 8px;
      margin: 0 0 28px;
      padding: 20px 0;
      border-bottom: 1px solid var(--rule);
    }}
    .team {{ text-align: center; }}
    .team img {{ width: 52px; height: 52px; object-fit: contain; margin-bottom: 8px; display: block; margin-left: auto; margin-right: auto; }}
    .team-name {{ font-family: 'Playfair Display', serif; font-size: 17px; font-weight: 700; line-height: 1.2; }}
    .vs {{ font-size: 13px; font-weight: 600; letter-spacing: .1em; color: var(--muted); text-transform: uppercase; }}

    /* SECTION */
    .section-header {{ margin: 28px 0 10px; }}
    .section-label {{
      font-size: 10px;
      font-weight: 600;
      letter-spacing: .16em;
      text-transform: uppercase;
      color: var(--accent);
      border-top: 2px solid var(--accent);
      padding-top: 7px;
      margin-bottom: 3px;
    }}
    .byline {{
      font-size: 11px;
      font-weight: 600;
      letter-spacing: .1em;
      text-transform: uppercase;
      color: var(--muted);
    }}

    /* EDITORIAL */
    .editorial p {{ font-size: 16px; line-height: 1.7; margin-bottom: 8px; }}

    /* FORM */
    .form-row {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 0;
      border-bottom: 1px solid var(--rule);
    }}
    .form-row:first-of-type {{ border-top: 1px solid var(--rule); }}
    .form-team {{ min-width: 120px; font-weight: 600; font-size: 13px; }}
    .badges {{ display: flex; gap: 5px; flex-wrap: wrap; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 27px;
      height: 27px;
      border-radius: 4px;
      color: #fff;
      font-size: 11px;
      font-weight: 700;
      cursor: default;
    }}

    /* TAKTIK */
    .taktik p {{ margin-bottom: 10px; }}

    /* SNACKISAR */
    .snackis {{
      padding: 14px 0;
      border-bottom: 1px solid var(--rule);
    }}
    .snackis:last-child {{ border-bottom: none; }}
    .snackis-title {{
      font-family: 'Playfair Display', serif;
      font-size: 18px;
      font-weight: 700;
      line-height: 1.2;
      margin-bottom: 5px;
    }}
    .snackis p {{ font-size: 14px; color: #222; line-height: 1.6; }}

    /* ODDS */
    .odds-row {{
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 1px;
      background: var(--rule);
      border: 1px solid var(--rule);
      border-radius: 6px;
      overflow: hidden;
      margin-bottom: 12px;
    }}
    .odds-cell {{ background: var(--paper); padding: 14px 10px; text-align: center; }}
    .odds-label {{ font-size: 10px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); margin-bottom: 5px; }}
    .odds-value {{ font-family: 'Playfair Display', serif; font-size: 28px; font-weight: 900; }}
    .odds-tip {{ font-size: 14px; line-height: 1.6; margin-bottom: 8px; }}
    .odds-source {{ font-size: 11px; color: var(--muted); }}

    /* MATCHFAKTA */
    .info-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1px;
      background: var(--rule);
      border: 1px solid var(--rule);
      border-radius: 6px;
      overflow: hidden;
    }}
    .info-cell {{ background: var(--paper); padding: 12px 14px; }}
    .info-label {{ font-size: 10px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); margin-bottom: 3px; }}
    .info-value {{ font-size: 15px; font-weight: 600; }}

    /* FOOTER */
    footer {{
      margin-top: 48px;
      border-top: 1px solid var(--rule);
      padding-top: 12px;
      font-size: 11px;
      color: var(--muted);
      text-align: center;
      line-height: 1.8;
    }}
    .back-link {{
      display: inline-block;
      margin-bottom: 16px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: .08em;
      text-transform: uppercase;
      color: var(--accent);
      text-decoration: none;
    }}
  </style>
</head>
<body>

  <a class="back-link" href="index.html">← Alla matcher</a>

  <div class="masthead">
    <div class="kicker">VM 2026 · Matchguide</div>
    <h1>{home['name']}<br>mot {away['name']}</h1>
    <div class="meta">
      <span>⏱ {kickoff_str}</span>
      <span>📍 {venue.get('city', '–')}</span>
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

  <div class="section-header">
    <div class="section-label">Matchintro</div>
    <div class="byline">Chefredaktör</div>
  </div>
  <div class="editorial"><p>{intro}</p></div>

  <div class="section-header">
    <div class="section-label">Senaste form</div>
  </div>
  <div class="form-row">
    <div class="form-team">{home['name']}</div>
    <div class="badges">{form_badges(home_form)}</div>
  </div>
  <div class="form-row">
    <div class="form-team">{away['name']}</div>
    <div class="badges">{form_badges(away_form)}</div>
  </div>

  <div class="section-header">
    <div class="section-label">Taktisk analys</div>
    <div class="byline">Taktikanalytiker</div>
  </div>
  <div class="taktik">{taktik_html}</div>

  <div class="section-header">
    <div class="section-label">Snackisar</div>
    <div class="byline">Snackisredaktör</div>
  </div>
  {format_snackisar_html(snackisar)}

  {odds_section}

  <div class="section-header">
    <div class="section-label">Matchfakta</div>
  </div>
  <div class="info-grid">
    <div class="info-cell"><div class="info-label">Turnering</div><div class="info-value">FIFA VM 2026</div></div>
    <div class="info-cell"><div class="info-label">Avspark</div><div class="info-value">{kickoff_str}</div></div>
    <div class="info-cell"><div class="info-label">Arena</div><div class="info-value">{venue.get('name', '–')}</div></div>
    <div class="info-cell"><div class="info-label">Stad</div><div class="info-value">{venue.get('city', '–')}</div></div>
  </div>

  <footer>
    Genererad {datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC · VM-guide 2026<br>
    Spelinnehåll är AI-genererat. Spel kan vara beroendeframkallande – spela ansvarsfullt.
  </footer>

</body>
</html>"""


def render_index(matches_meta):
    today_str = datetime.utcnow().strftime("%d %B %Y")
    cards = ""
    for m in matches_meta:
        cards += f"""
  <a class="card" href="{m['filename']}">
    <div class="card-time">{m['time']}</div>
    <div class="card-teams">{m['home']} <span>vs</span> {m['away']}</div>
    <div class="card-venue">{m['venue']}</div>
  </a>"""

    content = cards if matches_meta else '<div class="empty">Inga matcher de kommande 24 timmarna.</div>'

    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VM 2026 – Matchguide</title>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{ --ink: #0f0f0f; --paper: #f7f4ef; --rule: #d4cfc7; --accent: #e30613; --muted: #6b6560; }}
    body {{ background: var(--paper); color: var(--ink); font-family: 'Inter', sans-serif; padding: 16px; max-width: 680px; margin: 0 auto; }}
    .masthead {{ border-top: 5px solid var(--accent); border-bottom: 3px solid var(--ink); padding: 20px 0 14px; margin-bottom: 24px; text-align: center; }}
    .masthead h1 {{ font-family: 'Playfair Display', serif; font-size: 42px; font-weight: 900; letter-spacing: -.02em; }}
    .masthead .sub {{ font-size: 13px; color: var(--muted); margin-top: 4px; letter-spacing: .08em; text-transform: uppercase; }}
    .date {{ font-size: 12px; color: var(--muted); margin-top: 8px; text-transform: uppercase; letter-spacing: .1em; }}
    .card {{ display: block; text-decoration: none; color: inherit; border: 1px solid var(--rule); border-radius: 8px; padding: 16px 18px; margin-bottom: 10px; transition: border-color .15s; }}
    .card:hover {{ border-color: var(--accent); }}
    .card-time {{ font-size: 10px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--accent); margin-bottom: 5px; }}
    .card-teams {{ font-family: 'Playfair Display', serif; font-size: 21px; font-weight: 700; line-height: 1.2; }}
    .card-teams span {{ color: var(--muted); font-family: 'Inter', sans-serif; font-size: 14px; font-weight: 400; margin: 0 6px; }}
    .card-venue {{ font-size: 12px; color: var(--muted); margin-top: 5px; }}
    .empty {{ text-align: center; color: var(--muted); padding: 48px 0; font-style: italic; }}
    footer {{ margin-top: 32px; border-top: 1px solid var(--rule); padding-top: 12px; font-size: 11px; color: var(--muted); text-align: center; }}
  </style>
</head>
<body>
  <div class="masthead">
    <h1>VM 2026</h1>
    <div class="sub">Matchguide</div>
    <div class="date">{today_str}</div>
  </div>
  {content}
  <footer>Uppdaterad {datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC</footer>
</body>
</html>"""


# ── MAIN ────────────────────────────────────────────────────────────────────

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

        print(f"  → {home['name']} vs {away['name']}")

        home_form = get_team_form(home["id"])
        away_form = get_team_form(away["id"])
        odds = get_odds(fixture_id)
        context = build_context(home, away, home_form, away_form, odds)

        print("    Genererar redaktionellt innehåll...")
        intro = get_intro(context)
        taktik = get_taktik(context)
        snackisar = get_snackisar(context)
        odds_text = get_odds_text(context, odds)

        html = render_match_page(match, home_form, away_form, odds, intro, taktik, snackisar, odds_text)
        filename = f"match_{fixture_id}.html"
        (OUTPUT_DIR / filename).write_text(html, encoding="utf-8")
        print(f"    ✓ {filename}")

        kickoff_dt = datetime.fromisoformat(match["fixture"]["date"].replace("Z", "+00:00"))
        kickoff_swe = kickoff_dt + timedelta(hours=2)

        matches_meta.append({
            "filename": filename,
            "home": home["name"],
            "away": away["name"],
            "time": kickoff_swe.strftime("%H:%M"),
            "venue": venue.get("name", "–")
        })

    (OUTPUT_DIR / "index.html").write_text(render_index(matches_meta), encoding="utf-8")
    print(f"\nKlart! {len(matches_meta)} matchsidor + index genererade.")


if __name__ == "__main__":
    main()
