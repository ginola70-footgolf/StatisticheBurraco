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

    # Prima carica la pagina di login per eventuali token/cookie
    r = session.get(LOGIN_URL)
    r.raise_for_status()

    # Analizza il form per trovare i campi nascosti
    soup = BeautifulSoup(r.text, "html.parser")
    form_data = {"username": username, "password": password}

    form = soup.find("form")
    if form:
        for inp in form.find_all("input", type=["hidden", "text", "password"]):
            name = inp.get("name")
            val  = inp.get("value", "")
            if name and name not in ("username", "password"):
                form_data[name] = val
        # Cattura anche il nome del campo submit se presente
        for inp in form.find_all("input", type="submit"):
            if inp.get("name"):
                form_data[inp["name"]] = inp.get("value", "login")

    # Determina l'action del form
    action = form.get("action") if form else None
    post_url = (
        requests.compat.urljoin(LOGIN_URL, action)
        if action and not action.startswith("http")
        else (action or LOGIN_URL)
    )

    resp = session.post(post_url, data=form_data, allow_redirects=True)
    resp.raise_for_status()

    # Verifica login riuscito cercando segni di autenticazione
    if "logout" in resp.text.lower() or username.lower() in resp.text.lower():
        print("[login] ✓ Login riuscito")
        return True

    # Prova alternativa: alcuni siti usano nomi diversi
    for attempt_data in [
        {"user": username, "pass": password},
        {"login": username, "pwd": password},
        {"nick": username, "password": password},
    ]:
        resp2 = session.post(post_url, data=attempt_data, allow_redirects=True)
        if "logout" in resp2.text.lower() or username.lower() in resp2.text.lower():
            print("[login] ✓ Login riuscito (tentativo alternativo)")
            return True

    print("[login] ⚠ Login potrebbe non essere riuscito, continuo comunque...")
    return False

# ── Parsing pagina ──────────────────────────────────────────────────────────
def parse_page(html):
    """Estrae le partite dall'HTML di una pagina di cronologia."""
    soup = BeautifulSoup(html, "html.parser")
    matches = []

    # Cerca tabelle o righe con i dati delle partite
    # Adatta i selettori in base alla struttura reale della pagina
    rows = soup.select("table tr") or soup.select(".match") or soup.select(".game")

    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 4:
            continue

        texts = [c.get_text(strip=True) for c in cells]

        # Salta intestazioni
        if any(h in texts[0].lower() for h in ["data", "date", "giorno"]):
            continue

        # Prova a estrarre: data, giocatori, punteggi
        match = extract_match(texts, row)
        if match:
            matches.append(match)

    return matches

def extract_match(texts, row):
    """Estrae un singolo match dai testi di una riga."""
    # Cerca pattern di punteggio (numeri)
    scores = [t for t in texts if re.match(r'^\d+$', t)]

    # Cerca una data
    date_pattern = re.compile(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}')
    date_str = None
    for t in texts:
        m = date_pattern.search(t)
        if m:
            date_str = m.group()
            break

    # Cerca i nomi dei giocatori
    p1_found = any(PLAYER1.lower() in t.lower() for t in texts)
    p2_found = any(PLAYER2.lower() in t.lower() for t in texts)

    if not date_str and not scores:
        return None

    # Costruisci oggetto match con i dati disponibili
    match = {"raw": texts}

    if date_str:
        # Normalizza data in GG/MM/AAAA
        try:
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
                        "%d/%m/%y",  "%d-%m-%y",  "%d.%m.%y"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    match["data"] = dt.strftime("%d/%m/%Y")
                    break
                except ValueError:
                    continue
        except Exception:
            match["data"] = date_str

    if len(scores) >= 2:
        # Assumiamo che il primo punteggio sia di P1 e il secondo di P2
        # (potrebbe richiedere aggiustamenti in base alla struttura reale)
        try:
            s1 = int(scores[0])
            s2 = int(scores[1])
            match["ginola_score"] = s1
            match["zappa_score"]  = s2
            match["winner"] = PLAYER1 if s1 > s2 else PLAYER2
        except Exception:
            pass

    return match

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

        # Prima pagina: conta il totale se possibile
        if page == 0:
            total = count_pages(html)
            if total:
                print(f"[scraper] Trovate {total} pagine totali")

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

    session = requests.Session()
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
