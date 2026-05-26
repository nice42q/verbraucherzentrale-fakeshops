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
    if not raw_string:
        return None
        
    s = raw_string.strip(' \t\n\r"\'()[]{}').lower()
    s = s.rstrip('.,:-*?!')
    
    s = re.sub(r"^https?://", "", s)
    s = s.split('/')[0]
    
    if s.startswith("www."):
        s = s[4:]

    if re.match(r"^\d{1,2}\.\d{1,2}\.\d{2,4}$", s):
        return None
    if re.match(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$", s):
        return None

    if "." in s and " " not in s:
        # Erlaubte Top-Level-Domains von Fake-Shops (erweiterbar)
        tld = s.split('.')[-1]
        valid_tlds = {"de", "com", "net", "org", "info", "store", "online", "shop", "at", "ch", "co", "cc", "top", "biz", "xyz", "eu"}
        
        if tld in valid_tlds:
            try:
                punycode = s.encode("idna").decode("ascii")
                if re.fullmatch(r"^(?:[a-z0-9-]+\.)+[a-z]{2,6}$", punycode):
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

    title_links = soup.select("div.title a")
    
    for a in title_links:
        cleaned = clean_domain(a.get_text())
        if cleaned:
            found_domains.add(cleaned)

    log("[INFO]", f"Found {len(found_domains)} clean and validated domains on VZ page.")
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
        log("[ERROR]", "Total domain count is 0. Aborting to protect lists.")
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
        "label": "Blocklist entries",
        "message": f"{len(all_valid_domains)}",
        "color": "red"
    }
    with open("stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)

    log("[SUCCESS]", "Pipeline compiled and saved successfully with ultra-clean data!")

if __name__ == "__main__":
    main()
