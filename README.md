# 🃏 Burraco Battle — ginola700 vs zappaclaud

Dashboard automatica delle partite di Burraco su GitHub Pages.
Lo scraper gira ogni ora su **GitHub Actions** (gratis) e aggiorna i dati senza che tu debba fare nulla.

---

## 📁 Struttura del repository

```
burraco-battle/
├── docs/
│   ├── index.html       ← pagina web (servita da GitHub Pages)
│   └── partite.json     ← dati generati automaticamente dallo scraper
├── .github/
│   └── workflows/
│       └── update.yml   ← GitHub Actions: gira ogni ora
├── scraper.py           ← script Python per lo scraping
└── README.md
```

---

## 🚀 Setup completo (una volta sola)

### Passo 1 — Crea il repository su GitHub

1. Vai su [github.com/new](https://github.com/new)
2. Nome repository: `burraco-battle` (o come preferisci)
3. Visibilità: **Public** ← obbligatorio per GitHub Pages gratuito
4. Clicca **Create repository**

---

### Passo 2 — Carica i file

Hai due opzioni:

#### Opzione A — da browser (più semplice)

1. Nella pagina del repository clicca **Add file → Upload files**
2. Trascina questi file:
   - `scraper.py` → nella root
   - `index.html` → nella cartella `docs/` (creala cliccando su "docs/")
3. Crea anche un file `docs/partite.json` con contenuto: `{}`
4. Clicca **Commit changes**

Poi crea la cartella `.github/workflows/`:
1. Clicca **Add file → Create new file**
2. Nel campo nome scrivi: `.github/workflows/update.yml`
3. Incolla il contenuto del file `update.yml`
4. Clicca **Commit changes**

#### Opzione B — da terminale (se hai Git installato)

```bash
git clone https://github.com/TUO-USERNAME/burraco-battle.git
cd burraco-battle

# Crea le cartelle
mkdir -p docs .github/workflows

# Copia i file (da dove li hai scaricati)
cp /percorso/index.html   docs/
cp /percorso/scraper.py   .
cp /percorso/update.yml   .github/workflows/
echo '{}' > docs/partite.json

git add .
git commit -m "Setup iniziale Burraco Battle"
git push
```

---

### Passo 3 — Aggiungi le credenziali come Secrets

Le password non devono mai stare nel codice. Le conserviamo nei **Secrets** di GitHub:

1. Nel tuo repository vai su **Settings → Secrets and variables → Actions**
2. Clicca **New repository secret** e aggiungi:

| Nome          | Valore     |
|---------------|-----------|
| `BURRACO_USER`| `ginola700`|
| `BURRACO_PASS`| `pippo`    |

> ⚠️ Se la password cambia in futuro, aggiornala solo qui.

---

### Passo 4 — Abilita GitHub Pages

1. Nel repository vai su **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: **main** (o master)
4. Folder: **/docs**
5. Clicca **Save**

Dopo 1-2 minuti il sito sarà disponibile su:
```
https://TUO-USERNAME.github.io/burraco-battle/
```

---

### Passo 5 — Lancia il primo scraping manuale

Non aspettare un'ora: avvia lo scraper subito!

1. Vai sulla tab **Actions** del repository
2. Clicca su **Aggiorna Partite Burraco** nella lista a sinistra
3. Clicca **Run workflow → Run workflow** (pulsante verde)
4. Aspetta ~30 secondi che finisca (bollino verde = OK)

Il sito ora mostra i dati reali. Da questo momento lo scraper si ripete **ogni ora** da solo.

---

## 🔄 Come funziona l'aggiornamento automatico

```
Ogni ora:
  GitHub Actions avvia il container Ubuntu gratuito
    → installa requests, beautifulsoup4
    → esegue scraper.py
    → lo script fa login su burracoepinelle.com
    → scarica tutte le pagine di match history
    → estrae le righe ITALIANO
    → salva docs/partite.json
    → git push (aggiorna il repository)
  GitHub Pages serve il nuovo JSON
  La pagina web lo legge e si aggiorna
```

Costo: **€0**. GitHub offre 2000 minuti/mese gratuiti; ogni run dura ~30 secondi.

---

## 🔧 Se lo scraper trova 0 partite

1. Vai su **Actions → ultimo run fallito → Artifacts**
2. Scarica `debug-html`
3. Apri `debug_p0.html` nel browser
4. Cerca le righe della tabella contenenti "ITALIANO"
5. Guarda come sono strutturate (nomi colonne, posizione date e punteggi)
6. Aggiorna la funzione `parse_row()` in `scraper.py` di conseguenza
7. Fai un nuovo push → il workflow si riesegue automaticamente

---

## 🌐 URL del sito

```
https://TUO-USERNAME.github.io/burraco-battle/
```

Sostituisci `TUO-USERNAME` con il tuo username GitHub.

---

*Dati da burracoepinelle.com · Aggiornamento automatico ogni ora via GitHub Actions*
