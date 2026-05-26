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
    # Grundlegende Bereinigung
    s = raw_string.strip(' \t\n\r"\'()[]{}').lower()
    s = s.rstrip('.,:-*?!')
    s = re.sub(r"^https?://", "", s)
    s = s.split('/')[0]
    
    if s.startswith("www."):
        s = s[4:]
    
    # 1. FILTER: Direkte Datumsangaben blockieren (z.B. 07.05.2026)
    if re.match(r"^\d{1,2}\.\d{1,2}\.\d{2,4}$", s):
        return None

    # 2. FILTER: Reine IP-Adressen blockieren
    if re.match(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$", s):
        return None

    # 3. FILTER: Whitelist für unschuldige Domains
    whitelist = ["verbraucherzentrale.de", "fakeshop-finder.de", "google.com", "google.de"]
    if s in whitelist:
        return None

    # 4. FILTER: Valide Domain-Struktur prüfen
    if "." in s and " " not in s:
        # TLD extrahieren und checken (verhindert 'kreditkarte.mehr' oder 'index.html')
        tld = s.split('.')[-1]
        invalid_tlds = ["mehr", "html", "php", "htm", "pdf"]
        if tld in invalid_tlds:
            return None

        # IDN Punycode Konvertierung & strikter Regex für TLD-Länge (2-10 Zeichen)
        try:
            punycode = s.encode("idna").decode("ascii")
            if re.fullmatch(r"^(?:[a-z0-9-]+\.)+[a-z]{2,10}$", punycode):
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
        cleaned = clean_domain(a.get_text())
        if cleaned:
            found_domains.add(cleaned)

    # Strategie 2: Extrahieren aus Fließtext
    # WICHTIG: separator=' ' verhindert das Zusammenkleben von HTML-Tags!
    all_text = soup.get_text(separator=' ')
    
    # Etwas strikterer Such-Regex für potenzielle Domains im Text
    potential_domains = re.findall(r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,15}\b', all_text)
    
    for pot in potential_domains:
        cleaned = clean_domain(pot)
        if cleaned:
            found_domains.add(cleaned)

    log("[INFO]", f"Found {len(found_domains)} valid domains on current VZ page.")
    return found_domains

def main():
    log("[SYSTEM]", "VZ Fakeshop Pipeline execution triggered.")
    os.makedirs(DEBUG_DIR, exist_ok=True)

    historical_domains = load_existing_domains()
    current_vz_domains = fetch_vz_domains()
    
    new_domains = current_vz_domains - historical_domains
    
    if new_domains:
        log("[STATS]", f"Identified {len(new_domains)} BRAND NEW domains!")
        for nd in sorted(new_domains):
            log("[NEW]", f" -> {nd}")
    else:
        log("[STATS]", "No new domains found today. Archive is up-to-date.")

    all_valid_domains = sorted(historical_domains | current_vz_domains)

    if not all_valid_domains:
        log("[ERROR]", "Total domain count is 0. Aborting.")
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
        f.write("# Verbraucherzentrale Fakeshop Blocklist - Hosts Format\n")
        for d in all_valid_domains:
            f.write(f"0.0.0.0 {d}\n")

    # Plain Domains
    with open(DOMAINS_FILE, "w", encoding="utf-8") as f:
        for d in all_valid_domains:
            f.write(f"{d}\n")

    # Debug Log
    with open(BLACKLIST_TXT_PATH, "w", encoding="utf-8") as f:
        f.write(f"# {'='*78}\n")
        f.write(f"# VERBRAUCHERZENTRALE FAKESHOP BLACKLIST - DEBUG LOG\n")
        f.write(f"# {'='*78}\n#\n")
        for log_line in process_logs:
            f.write(f"# {log_line}\n")

    # Stats JSON
    stats = {
        "schemaVersion": 1,
        "label": "VZ Fakeshops",
        "message": f"{len(all_valid_domains)}",
        "color": "orange"
    }
    with open("stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)

    log("[SUCCESS]", "Pipeline compiled and saved successfully!")

if __name__ == "__main__":
    main()
