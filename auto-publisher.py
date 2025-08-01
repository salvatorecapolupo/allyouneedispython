import os
import hashlib
import time
import requests
import certifi
import feedparser
from tinydb import TinyDB, Query
from datetime import datetime
from typing import Optional
from datetime import datetime, timezone

# Percorso DB relativo alla posizione dello script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'log_gia_pubblicati.json')

# Configurazione blog e telegram
BLOGS = {
    "https://nomesito.com": { # testato con siti wordpress, funzionamentonon garantito su altri CMS
        "token": "il_tuo_token", # il bot associato alla chiave deve essere amministratore del canale
        "chatid": "@nome_del_canale"
    }
}

def sha1_hash(text: str) -> str:
    """Genera hash SHA1 da stringa"""
    return hashlib.sha1(text.encode('utf-8')).hexdigest()

def estrai_data(entry) -> float:
    """Estrai timestamp da entry feed, usato per ordinare"""
    if 'published_parsed' in entry and entry.published_parsed:
        return time.mktime(entry.published_parsed)
    if 'updated_parsed' in entry and entry.updated_parsed:
        return time.mktime(entry.updated_parsed)
    return 0  # se non disponibile, consideralo vecchio

def gia_pubblicato(db: TinyDB, hash_: str) -> bool:
    """Controlla se hash esiste nel DB"""
    Tupla = Query()
    return db.contains(Tupla.hash == hash_)

def salva_pubblicazione(db: TinyDB, entry, hash_: str):
    """Salva notizia pubblicata nel DB"""
    db.insert({
        "title": entry.title,
        "link": entry.link,
        "when": datetime.now(timezone.utc).isoformat(),  # <-- cambio qui
        "hash": hash_
    })

def pubblica_telegram(token: str, chat_id: str, testo: str) -> bool:
    """Invia messaggio Telegram, ritorna True se ok"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": testo,
        "parse_mode": "HTML"
    }
    try: 
        response = requests.post(url, data=payload, timeout=10)
        return response.status_code == 200
    except requests.RequestException as e:
        print(f"[ERRORE] Invio Telegram fallito: {e}")
        return False

def main():
    db = TinyDB(DB_FILE)

    for blog_url, creds in BLOGS.items():
        feed_url = blog_url.rstrip('/') + '/feed'
        try:
            response = requests.get(feed_url, verify=certifi.where(), timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"[ERRORE] Fallito download feed: {e}")
            continue

        feed = feedparser.parse(response.content)

        if feed.bozo:
            print(f"[ERRORE] Parsing feed fallito: {feed.bozo_exception}")
            continue

        entries = sorted(feed.entries, key=estrai_data)

        notizia_da_pubblicare: Optional[dict] = None
        for entry in entries:
            hash_ = sha1_hash(entry.link)
            if not gia_pubblicato(db, hash_):
                notizia_da_pubblicare = {
                    "entry": entry,
                    "hash": hash_
                }
                break

        if notizia_da_pubblicare is None:
            print("Nessuna nuova notizia da pubblicare.")
            return

        entry = notizia_da_pubblicare["entry"]
        hash_ = notizia_da_pubblicare["hash"]

        testo = f"{entry.title}\n{entry.link}"
        testo = testo.replace('&', 'and')

        print(f"Pubblicazione notizia: {entry.title}")

        if pubblica_telegram(creds["token"], creds["chatid"], testo):
            salva_pubblicazione(db, entry, hash_)
            print("Notizia pubblicata con successo.")
        else:
            print("Errore nella pubblicazione su Telegram.")

if __name__ == "__main__":
    main()
