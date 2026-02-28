#!/usr/bin/env python3
"""
Burraco Scraper - versione pulita
Legge credenziali da credentials.txt, fa login su burracoepinelle.com
e scarica tutta la cronologia partite, salvando partite.json
"""

import requests
import json
import re
import os
from datetime import datetime, timezone
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Configurazione ──────────────────────────────────────────────────────────
BASE_URL    = "https://www.burracoepinelle.com/burrachi_pinelle/index.php"
LOGIN_URL   = BASE_URL + "?page=login"
HISTORY_URL = BASE_URL + "?page=match_history_user&user=237071&p={page}"
CREDS_FILE  = "credentials.txt"
OUTPUT      = "partite.json"

PLAYER1 = "ginola700"    # utente loggato (user=237071)
PLAYER2 = "zappaclaud"   # avversario da cercare

DATE_RE  = re.compile(r'(\d{4}-\d{2}-\d{2})')
SCORE_RE = re.compile(r'^(\d+)\s*\(')

# ── Credenziali ─────────────────────────────────────────────────────────────
def read_credentials():
    if not os.path.exists(CREDS_FILE):
        raise FileNotFoundError(f"File '{CREDS_FILE}' non trovato.")
    creds = {}
    with open(CREDS_FILE) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                creds[k.strip().lower()] = v.strip()
    if "username" not in creds or "password" not in creds:
        raise ValueError("credentials.txt deve contenere 'username=...' e 'password=...'")
    return creds["username"], creds["password"]

# ── Login ───────────────────────────────────────────────────────────────────
def login(session, username, password):
    print(f"[login] Tentativo login...")
    session.get(LOGIN_URL)  # ottieni cookie iniziali

    resp = session.post(LOGIN_URL, data={
        "action":  "login",
        "poll":    "-1",
        "vip":     "-1",
        "gift_id": "-1",
        "nick":    username,
        "pwd":     password,
    }, allow_redirects=True)
    resp.raise_for_status()

    if "logout" in resp.text.lower() or username.lower() in resp.text.lower():
        print("[login] ✓ Login riuscito")
        return True

    print("[login] ✗ Login fallito")
    return False

# ── Parsing ─────────────────────────────────────────────────────────────────
def parse_page(html, all_opponents):
    soup = BeautifulSoup(html, "html.parser")
    matches = []

    table = soup.find("table", class_="gridtable")
    if not table:
        return matches

    current_date = "sconosciuta"

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        # intestazione
        if cells[0].name == "th":
            continue

        texts = [c.get_text(strip=True) for c in cells]

        # riga data (2 celle): "ITALIANO2026-02-27 14:43:58" | "Hai ottenuto..."
        if len(cells) == 2:
            m = DATE_RE.search(texts[0])
            if m:
                try:
                    current_date = datetime.strptime(m.group(1), "%Y-%m-%d").strftime("%d/%m/%Y")
                except ValueError:
                    pass
            continue

        # riga partita (9 celle)
        if len(cells) < 5:
            continue
        if not SCORE_RE.match(texts[3]) or not SCORE_RE.match(texts[4]):
            continue

        squad_ns = texts[1]
        squad_eo = texts[2]

        # Raccogli tutti i nick per debug
        all_opponents.add(squad_ns)
        all_opponents.add(squad_eo)

        score_ns = int(SCORE_RE.match(texts[3]).group(1))
        score_eo = int(SCORE_RE.match(texts[4]).group(1))

        # Filtra: tieni solo partite in cui compare zappaclaud
        p2_in_ns = PLAYER2.lower() in squad_ns.lower()
        p2_in_eo = PLAYER2.lower() in squad_eo.lower()
        if not p2_in_ns and not p2_in_eo:
            continue

        if p2_in_eo:
            ginola_score = score_ns
            zappa_score  = score_eo
        else:
            ginola_score = score_eo
            zappa_score  = score_ns

        winner = PLAYER1 if ginola_score > zappa_score else PLAYER2
        matches.append({
            "data":         current_date,
            "ginola_score": ginola_score,
            "zappa_score":  zappa_score,
            "winner":       winner,
        })

    return matches

# ── Paginazione ──────────────────────────────────────────────────────────────
def count_pages(html):
    soup = BeautifulSoup(html, "html.parser")
    pages = set()
    for a in soup.select("a[href*='p=']"):
        m = re.search(r'p=(\d+)', a.get("href", ""))
        if m:
            pages.add(int(m.group(1)))
    return max(pages) + 1 if pages else 1

# ── Fetch tutte le pagine ────────────────────────────────────────────────────
def fetch_all_pages(session):
    all_raw = []
    all_opponents = set()
    page = 0
    total_pages = None

    while True:
        url = HISTORY_URL.format(page=page)
        print(f"[scraper] Pagina {page}...")

        r = session.get(url)
        r.raise_for_status()
        html = r.text

        if page == 0:
            total_pages = count_pages(html)
            print(f"[scraper] Pagine totali: {total_pages}")

        matches = parse_page(html, all_opponents)
        all_raw.extend(matches)
        print(f"[scraper] Pagina {page}: {len(matches)} partite vs {PLAYER2}")

        if total_pages and page + 1 >= total_pages:
            print("[scraper] Ultima pagina raggiunta.")
            break

        page += 1
        if page > 500:
            break

    print(f"\n[debug] Tutti i giocatori trovati:")
    for opp in sorted(all_opponents):
        print(f"  '{opp}'")

    return all_raw

# ── Aggregazione ─────────────────────────────────────────────────────────────
def aggregate(raw_matches):
    by_day = {}
    for m in raw_matches:
        data = m.get("data", "sconosciuta")
        if data not in by_day:
            by_day[data] = {"data": data, "ginola_vittorie": 0, "zappa_vittorie": 0, "partite": []}
        if m.get("winner") == PLAYER1:
            by_day[data]["ginola_vittorie"] += 1
        else:
            by_day[data]["zappa_vittorie"] += 1
        by_day[data]["partite"].append({
            "ginola_score": m["ginola_score"],
            "zappa_score":  m["zappa_score"],
            "winner":       m["winner"],
        })

    def parse_date(d):
        try:
            return datetime.strptime(d, "%d/%m/%Y")
        except Exception:
            return datetime.min

    per_giorno = sorted(by_day.values(), key=lambda x: parse_date(x["data"]), reverse=True)
    for g in per_giorno:
        g["n_partite"] = len(g["partite"])

    tot_g = sum(g["ginola_vittorie"] for g in per_giorno)
    tot_z = sum(g["zappa_vittorie"]  for g in per_giorno)
    tot   = tot_g + tot_z

    return {
        "aggiornato": datetime.now(timezone.utc).isoformat(),
        "giocatori":  [PLAYER1, PLAYER2],
        "totali": {
            "ginola_vittorie": tot_g,
            "zappa_vittorie":  tot_z,
            "totale_partite":  tot,
            "giorni_giocati":  len(per_giorno),
            "ginola_pct":      round(tot_g / tot * 100, 1) if tot else 0,
            "zappa_pct":       round(tot_z / tot * 100, 1) if tot else 0,
        },
        "per_giorno": per_giorno,
    }

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  Burraco Scraper")
    print("=" * 55)

    username, password = read_credentials()

    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
        "Accept-Language": "it-IT,it;q=0.9",
    })

    login(session, username, password)
    raw_matches = fetch_all_pages(session)

    print(f"\n[aggregazione] Partite vs {PLAYER2}: {len(raw_matches)}")
    data = aggregate(raw_matches)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[✓] Salvato '{OUTPUT}'")
    print(f"    Partite totali : {data['totali']['totale_partite']}")
    print(f"    {PLAYER1:12s}: {data['totali']['ginola_vittorie']} vittorie")
    print(f"    {PLAYER2:12s}: {data['totali']['zappa_vittorie']} vittorie")
    print(f"    Giorni giocati : {data['totali']['giorni_giocati']}")

if __name__ == "__main__":
    main()
