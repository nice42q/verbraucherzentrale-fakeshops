import requests
from bs4 import BeautifulSoup
import re
import os
import sys
import json
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fake_useragent import UserAgent, FakeUserAgentError
import random

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

def get_random_user_agent():
    try:
        ua = UserAgent(browsers=["chrome", "firefox", "edge"])
        return ua.random
    except FakeUserAgentError:
        # Fallback list – current, real User‑Agents (May 2026)
        fallback_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:145.0) Gecko/20100101 Firefox/145.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
        ]
        return random.choice(fallback_agents)

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
    
    session = requests.Session()
    
    # Basis‑Header (ohne User‑Agent – der wird pro Anfrage neu gesetzt)
    session.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })

    # Retry‑Strategie (max. 5 Versuche, exponentielle Backoffs)
    retry_strategy = Retry(
        total=5,
        backoff_factor=0.5,  # Wartezeiten: 0.5s, 1s, 2s, 4s, 8s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # User‑Agent pro Anfrage zufällig setzen
    session.headers.update({"User-Agent": get_random_user_agent()})

    try:
        response = session.get(URL, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        log("[ERROR]", f"Connection failed after retries: {e}")
        # Optional: HTML für Fehleranalyse speichern
        with open(os.path.join(DEBUG_DIR, "failed_page.html"), "w", encoding="utf-8") as f:
            f.write(response.text if 'response' in locals() else "No response")
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
    all_valid_domains = sorted(historical_domains | current_vz_domains)

    if not all_valid_domains:
        log("[ERROR]", "Total domain count is 0. Aborting to protect lists.")
        sys.exit(1)

    # PRÜFUNG: Gibt es echte Änderungen an der Domain-Liste?
    # Nur wenn neue Domains gefunden wurden ODER die Gesamtanzahl nicht übereinstimmt,
    # aktualisieren wir die Listen und den Timestamp.
    changes_detected = len(new_domains) > 0 or len(all_valid_domains) != len(historical_domains)

    if changes_detected:
        log("[STATS]", f"Identified {len(new_domains)} BRAND NEW domains! Updating files...")
        for nd in sorted(new_domains):
            log("[NEW]", f" -> {nd}")
            
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        # AdBlock Format (wird NUR bei Änderungen geschrieben)
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

        # Stats JSON
        stats = {
            "schemaVersion": 1,
            "label": "Blocklist entries",
            "message": f"{len(all_valid_domains)}",
            "color": "red"
        }
        with open("stats.json", "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=4)
            
    else:
        log("[STATS]", "No new domains found today. Archive is up-to-date. Skipping file updates.")

    with open(BLACKLIST_TXT_PATH, "w", encoding="utf-8") as f:
        f.write(f"# {'='*78}\n")
        f.write(f"# VERBRAUCHERZENTRALE FAKESHOP BLACKLIST - DEBUG LOG\n")
        f.write(f"# {'='*78}\n#\n")
        for log_line in process_logs:
            f.write(f"# {log_line}\n")

    log("[SUCCESS]", "Pipeline finished execution.")

if __name__ == "__main__":
    main()
