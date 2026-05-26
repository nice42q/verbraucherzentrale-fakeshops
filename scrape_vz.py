import requests
from bs4 import BeautifulSoup
import re
import os
import sys
import json
from datetime import datetime

URL = "https://warnung.fakeshop-finder.de/"
DEBUG_DIR = "debug"
BLACKLIST_TXT_PATH = os.path.join(DEBUG_DIR, "blacklist.txt")
DOMAINS_FILE = "blocklist-domains.txt"

process_logs = []

def log(level, message):
    formatted_msg = f"{level:<9} {message}"
    print(formatted_msg)
    process_logs.append(formatted_msg)

def clean_domain(raw_string):
    s = raw_string.strip(' \t\n\r"').lower()
    s = s.rstrip('.,:-*')
    s = re.sub(r"^https?://", "", s)
    s = s.split('/')[0]
    
    if s.startswith("www."):
        s = s[4:]
    
    # Whitelist für harmlose Domains, die im VZ-Text auftauchen könnten
    whitelist = ["verbraucherzentrale.de", "fakeshop-finder.de", "google.com", "google.de"]
    if s in whitelist:
        return None

    # Valide Struktur prüfen
    if "." in s and " " not in s:
        # IPv4 filtern
        if re.match(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$", s):
            return None
        # IDN Punycode Konvertierung
        try:
            punycode = s.encode("idna").decode("ascii")
            if re.fullmatch(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", punycode):
                return punycode
        except:
            return None
    return None

def load_existing_domains():
    existing = set()
    if os.path.exists(DOMAINS_FILE):
        with open(DOMAINS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                d = line.strip()
                if d:
                    existing.add(d)
        log("[INFO]", f"Loaded {len(existing)} historical domains from archive.")
    else:
        log("[INFO]", "No existing domain archive found. Starting fresh.")
    return existing

def fetch_vz_domains():
    log("[SYSTEM]", f"Fetching VZ warnings from {URL} ...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(URL, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        log("[ERROR]", f"Connection failed: {e}")
        sys.exit(1)

    soup = BeautifulSoup(response.text, 'html.parser')
    found_domains = set()

    # Strategie 1: Extrahieren aus Links (a-Tags)
    for a in soup.find_all('a', href=True):
        link_text = a.get_text()
        cleaned = clean_domain(link_text)
        if cleaned:
            found_domains.add(cleaned)

    # Strategie 2: Extrahieren aus Fließtext (Regex Suche)
    all_text = soup.get_text()
    potential_domains = re.findall(r'\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', all_text)
    
    for pot in potential_domains:
        cleaned = clean_domain(pot)
        if cleaned:
            found_domains.add(cleaned)

    log("[INFO]", f"Found {len(found_domains)} potential domains on current VZ page.")
    return found_domains

def main():
    log("[SYSTEM]", "VZ Fakeshop Pipeline execution triggered.")
    os.makedirs(DEBUG_DIR, exist_ok=True)

    # 1. Altes Archiv laden
    historical_domains = load_existing_domains()
    
    # 2. Aktuelle VZ Seite scrapen
    current_vz_domains = fetch_vz_domains()
    
    # 3. Differenz ermitteln (Welche sind WIRKLICH neu?)
    new_domains = current_vz_domains - historical_domains
    
    if new_domains:
        log("[STATS]", f"Identified {len(new_domains)} BRAND NEW domains!")
        for nd in sorted(new_domains):
            log("[NEW]", f" -> {nd}")
    else:
        log("[STATS]", "No new domains found today. Archive is up-to-date.")

    # 4. Zusammenführen und sortieren
    all_valid_domains = sorted(historical_domains | current_vz_domains)

    if not all_valid_domains:
        log("[ERROR]", "Total domain count is 0. Aborting to protect empty lists.")
        sys.exit(1)

    log("[SYSTEM]", "Writing all updated blocklist files...")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # AdBlock Format
    with open("blocklist.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("# Pi-hole DNS Blocklist: Verbraucherzentrale Fakeshops\n")
        f.write(f"# Source: {URL}\n")
        f.write("# Pi-hole Source: https://github.com/nice42q/verbraucherzentrale-fakeshops\n")
        f.write(f"# Last update: {now}\n")
        f.write("#\n")
        f.write(f"# Total archived domains:    {len(all_valid_domains)}\n")
        f.write(f"# New domains added today:   {len(new_domains)}\n")
        f.write(f"# {'-'*43}\n#\n")
        for d in all_valid_domains:
            f.write(f"||{d}^\n")

    # Hosts Format
    with open("blocklist-hosts.txt", "w", encoding="utf-8") as f:
        f.write("# Verbraucherzentrale Fakeshop Blocklist – Hosts Format\n")
        for d in all_valid_domains:
            f.write(f"0.0.0.0 {d}\n")

    # Plain Domains (Crucial for the next run's archive!)
    with open(DOMAINS_FILE, "w", encoding="utf-8") as f:
        for d in all_valid_domains:
            f.write(f"{d}\n")

    # Debug Log
    with open(BLACKLIST_TXT_PATH, "w", encoding="utf-8") as f:
        f.write(f"# {'='*78}\n")
        f.write(f"# VERBRAUCHERZENTRALE FAKESHOP BLACKLIST – DEBUG LOG\n")
        f.write(f"# {'='*78}\n#\n")
        for log_line in process_logs:
            f.write(f"# {log_line}\n")

    # Stats JSON for Badges
    stats = {
        "schemaVersion": 1,
        "label": "VZ Fakeshops",
        "message": f"{len(all_valid_domains)} Domains",
        "color": "orange"
    }
    with open("stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)

    log("[SUCCESS]", "Pipeline compiled and saved successfully!")

if __name__ == "__main__":
    main()
