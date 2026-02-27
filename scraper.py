#!/usr/bin/env python3
"""
Burraco Scraper
Legge credenziali da credentials.txt, fa login su burracoepinelle.com
e scarica tutta la cronologia partite, salvando partite.json
"""

import requests
import json
import re
import os
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# ── Configurazione ──────────────────────────────────────────────────────────
BASE_URL   = "https://www.burracoepinelle.com/burrachi_pinelle/index.php"
LOGIN_URL  = BASE_URL + "?page=login"
HISTORY_URL= BASE_URL + "?page=match_history_user&user=237071&p={page}"
CREDS_FILE = "credentials.txt"
OUTPUT     = "partite.json"

PLAYER1 = "ginola700"   # user 237071
PLAYER2 = "zappaclaud"

# ── Lettura credenziali ─────────────────────────────────────────────────────
def read_credentials():
    if not os.path.exists(CREDS_FILE):
        raise FileNotFoundError(
            f"File '{CREDS_FILE}' non trovato.\n"
            "Crea il file con:\n  username=tuousername\n  password=tuapassword"
        )
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
    print(f"[login] Tentativo login come '{username}'...")

    # Carica la pagina di login per ottenere i cookie
    r = session.get(LOGIN_URL)
    r.raise_for_status()

    # Il form corretto è quello con action='login' e campi nick/pwd
    post_url = "https://www.burracoepinelle.com/burrachi_pinelle/index.php?page=login"
    form_data = {
        "action":  "login",
        "poll":    "-1",
        "vip":     "-1",
        "gift_id": "-1",
        "nick":    username,
        "pwd":     password,
    }

    resp = session.post(post_url, data=form_data, allow_redirects=True)
    resp.raise_for_status()

    print(f"[login] Status: {resp.status_code}, URL finale: {resp.url}")

    if "logout" in resp.text.lower() or username.lower() in resp.text.lower():
        print("[login] ✓ Login riuscito")
        return True

    print("[login] ✗ Login fallito — verifica username e password nei segreti GitHub")
    return False

# ── Parsing pagina ──────────────────────────────────────────────────────────
# Struttura reale della tabella:
#   Riga intestazione : <th> Info | Squadra NordSud | Squadra EstOvest | Punteggio NS(VP) | Punteggio EO(VP) | ...
#   Riga data         : 1 cella  "ITALIANO2026-02-27 14:43:58"  (oppure "ENGLISH2026-...")
#   Riga partita      : 9 celle  "ITALIANO Crea Tavolo" | giocatore1 | giocatore2 | "2425(19)" | "940(0)" | ...

DATE_RE  = re.compile(r'(\d{4}-\d{2}-\d{2})')          # 2026-02-27
SCORE_RE = re.compile(r'^(\d+)\s*\(')                   # "2425(19)" → 2425

def parse_page(html):
    """Estrae le partite dall'HTML della pagina di cronologia."""
    soup = BeautifulSoup(html, "html.parser")
    matches = []

    table = soup.find("table", class_="gridtable")
    if not table:
        table = soup.find("table")
    if not table:
        return matches

    rows = table.find_all("tr")
    current_date = "sconosciuta"

    for row in rows:
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(strip=True) for c in cells]

        if not texts:
            continue

        # ── Riga intestazione: salta ──────────────────────────────────
        if cells[0].name == "th":
            continue

        # ── Riga data: 1 cella con "ITALIANO2026-02-27 14:43:58" ─────
        if len(cells) == 1:
            m = DATE_RE.search(texts[0])
            if m:
                try:
                    dt = datetime.strptime(m.group(1), "%Y-%m-%d")
                    current_date = dt.strftime("%d/%m/%Y")
                except ValueError:
                    pass
            continue

        # ── Riga partita: 9 celle ─────────────────────────────────────
        # [0] "ITALIANO Crea Tavolo"
        # [1] Squadra NordSud  (giocatore / coppia)
        # [2] Squadra EstOvest (giocatore / coppia)
        # [3] Punteggio NordSud  es. "2425(19)"
        # [4] Punteggio EstOvest es. "940(0)"
        # [5] Punti Giocatore
        # [6] Punti Club
        # [7] Punti Lega
        # [8] Terminata per
        if len(texts) < 5:
            continue

        # Salta righe pubblicitarie/sistema (non hanno punteggio valido)
        if not SCORE_RE.match(texts[3]) and not SCORE_RE.match(texts[4]):
            continue

        squad_ns = texts[1]   # NordSud
        squad_eo = texts[2]   # EstOvest

        score_ns_m = SCORE_RE.match(texts[3])
        score_eo_m = SCORE_RE.match(texts[4])

        if not score_ns_m or not score_eo_m:
            continue

        score_ns = int(score_ns_m.group(1))
        score_eo = int(score_eo_m.group(1))

        # Determina chi è P1 (ginola700) e chi è P2 (zappaclaud)
        # I nomi possono essere in squad_ns o squad_eo
        p1_in_ns = PLAYER1.lower() in squad_ns.lower()
        p1_in_eo = PLAYER1.lower() in squad_eo.lower()

        if p1_in_ns:
            ginola_score = score_ns
            zappa_score  = score_eo
        elif p1_in_eo:
            ginola_score = score_eo
            zappa_score  = score_ns
        else:
            # ginola non trovato in questa riga, prendi NS come ginola per default
            ginola_score = score_ns
            zappa_score  = score_eo

        winner = PLAYER1 if ginola_score > zappa_score else PLAYER2

        matches.append({
            "data":         current_date,
            "ginola_score": ginola_score,
            "zappa_score":  zappa_score,
            "winner":       winner,
            "squad_ns":     squad_ns,
            "squad_eo":     squad_eo,
        })

    return matches

def has_next_page(html):
    """Controlla se esiste una pagina successiva."""
    soup = BeautifulSoup(html, "html.parser")

    # Cerca link "avanti", "next", "»" ecc.
    next_patterns = ["next", "successiv", "avanti", "»", ">"]
    for a in soup.find_all("a"):
        text = a.get_text(strip=True).lower()
        href = a.get("href", "")
        if any(p in text for p in next_patterns) or ("p=" in href and "match_history" in href):
            # Controlla che non sia disabilitato
            if "disabled" not in a.get("class", []):
                if any(p in text for p in ["next", "successiv", "avanti", "»"]):
                    return True

    # Alternativa: guarda se ci sono riferimenti alla pagina successiva nell'URL
    page_links = soup.select("a[href*='p=']")
    return len(page_links) > 1

def count_pages(html):
    """Tenta di contare il numero totale di pagine."""
    soup = BeautifulSoup(html, "html.parser")
    page_links = soup.select("a[href*='p=']")
    pages = set()
    for a in page_links:
        href = a.get("href", "")
        m = re.search(r'p=(\d+)', href)
        if m:
            pages.add(int(m.group(1)))
    return max(pages) + 1 if pages else None

# ── Fetch di tutte le pagine ────────────────────────────────────────────────
def fetch_all_pages(session):
    all_raw = []  # lista di dict con raw texts
    page = 0

    while True:
        url = HISTORY_URL.format(page=page)
        print(f"[scraper] Pagina {page}: {url}")

        r = session.get(url)
        r.raise_for_status()
        html = r.text

        # Prima pagina: conta il totale
        if page == 0:
            total = count_pages(html)
            if total:
                print(f"[scraper] Trovate {total} pagine totali")
            # DEBUG temporaneo: mostra HTML pagina autenticata
            soup_dbg = BeautifulSoup(html, "html.parser")
            table_dbg = soup_dbg.find("table", class_="gridtable")
            if table_dbg:
                rows_dbg = table_dbg.find_all("tr")
                print(f"[debug] Tabella trovata, righe: {len(rows_dbg)}")
                for i, row in enumerate(rows_dbg[:5]):
                    cells = row.find_all(["td","th"])
                    print(f"[debug] Riga {i} ({len(cells)} celle): {[c.get_text(strip=True)[:40] for c in cells]}")
            else:
                print("[debug] Nessuna tabella class=gridtable — tabelle presenti:")
                for t in soup_dbg.find_all("table"):
                    print(f"  <table class='{t.get('class')}' id='{t.get('id')}'>")
                print(f"[debug] HTML grezzo (primi 1200 char):\n{html[:1200]}")

        matches = parse_page(html)
        if not matches:
            print(f"[scraper] Nessuna partita a pagina {page}, stop.")
            break

        all_raw.extend(matches)
        print(f"[scraper] → {len(matches)} righe estratte (totale: {len(all_raw)})")

        if not has_next_page(html):
            print("[scraper] Ultima pagina raggiunta.")
            break

        page += 1

        # Safety limit
        if page > 500:
            print("[scraper] Limite pagine raggiunto (500)")
            break

    return all_raw

# ── Aggregazione dati ────────────────────────────────────────────────────────
def aggregate(raw_matches):
    """Aggrega le partite per giorno e calcola i totali."""
    by_day = {}

    for m in raw_matches:
        data = m.get("data", "sconosciuta")
        if data not in by_day:
            by_day[data] = {"data": data, "ginola_vittorie": 0, "zappa_vittorie": 0, "partite": []}

        if "winner" in m:
            if m["winner"] == PLAYER1:
                by_day[data]["ginola_vittorie"] += 1
            else:
                by_day[data]["zappa_vittorie"] += 1

        if "ginola_score" in m and "zappa_score" in m:
            by_day[data]["partite"].append({
                "ginola_score": m["ginola_score"],
                "zappa_score":  m["zappa_score"],
                "winner":       m.get("winner", "")
            })

    # Ordina per data decrescente
    def parse_date(d):
        try:
            return datetime.strptime(d, "%d/%m/%Y")
        except Exception:
            return datetime.min

    per_giorno = sorted(by_day.values(), key=lambda x: parse_date(x["data"]), reverse=True)

    for g in per_giorno:
        g["n_partite"] = len(g["partite"]) or (g["ginola_vittorie"] + g["zappa_vittorie"])

    # Totali
    tot_g = sum(g["ginola_vittorie"] for g in per_giorno)
    tot_z = sum(g["zappa_vittorie"] for g in per_giorno)
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

    # Silenzia i warning SSL (il sito ha certificato non verificabile)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    session = requests.Session()
    session.verify = False  # disabilita verifica certificato SSL
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9",
    })

    login(session, username, password)

    raw_matches = fetch_all_pages(session)
    print(f"\n[aggregazione] Totale righe grezze: {len(raw_matches)}")

    data = aggregate(raw_matches)

    # Salva
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[✓] Salvato '{OUTPUT}'")
    print(f"    Partite totali : {data['totali']['totale_partite']}")
    print(f"    {PLAYER1:12s}: {data['totali']['ginola_vittorie']} vittorie")
    print(f"    {PLAYER2:12s}: {data['totali']['zappa_vittorie']} vittorie")
    print(f"    Giorni giocati : {data['totali']['giorni_giocati']}")

if __name__ == "__main__":
    main()
