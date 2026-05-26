# 🛡️ Verbraucherzentrale Fakeshop Blocklist for Pi-hole

![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/nice42q/verbraucherzentrale-fakeshops/update_blocklist.yml)
![GitHub Last Commit](https://img.shields.io/github/last-commit/nice42q/verbraucherzentrale-fakeshops?label=Last%20update&color=blue)
![Blocklist entries](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/nice42q/verbraucherzentrale-fakeshops/main/stats.json)

A fully automated parser that checks the official [German Consumer Advice Center Warning Feed (Verbraucherzentrale Fakeshop-Finder)](https://warnung.fakeshop-finder.de/) daily and compiles the discoveries into structured DNS-sinkhole formats.

Since the source website periodically removes older alerts, this pipeline operates **incrementally**. It archives every single domain it encounters over time, creating a growing, historical database of malicious e-commerce nodes.

| File | Format | Typical use |
|------|--------|-------------|
| **[`blocklist.txt`](https://raw.githubusercontent.com/nice42q/verbraucherzentrale-fakeshops/main/blocklist.txt)** | **AdBlock (`\|\|domain^`)** | **Pi‑hole, uBlock Origin, Adblock Plus, Brave** |
| [`blocklist-hosts.txt`](https://raw.githubusercontent.com/nice42q/verbraucherzentrale-fakeshops/main/blocklist-hosts.txt) | Hosts (`0.0.0.0 domain`) | Pi‑hole, AdGuard Home, `/etc/hosts`, Diversion |
| [`blocklist-domains.txt`](https://raw.githubusercontent.com/nice42q/verbraucherzentrale-fakeshops/main/blocklist-domains.txt) | Plain domains | AdGuard Home, custom scripts |

## 🚀 How to use in Pi-hole

1. Go to your Pi-hole admin dashboard.
2. Navigate to **Adlists** (*Group Management → Adlists*).
3. Paste **one** of the following URLs into the **Address** field:
   - AdBlock format (recommended):  
     `https://raw.githubusercontent.com/nice42q/verbraucherzentrale-fakeshops/main/blocklist.txt`
   - Hosts format:  
     `https://raw.githubusercontent.com/nice42q/verbraucherzentrale-fakeshops/main/blocklist-hosts.txt`
4. Click **Add blocklist**.
5. **Update** your gravity list (*Tools → Update Gravity* → **Update** or run `pihole -g`).

## 🏠 Compatible with AdGuard Home

Both the AdBlock list and the plain domain list work with **AdGuard Home**.

1. Go to your AdGuard Home dashboard → **Filters** → **DNS blocklists**.
2. Click **Add blocklist** → **Add a custom list**.
3. Enter a name (e.g., "Verbraucherzentrale Fakeshops") and one of these URLs:
   - `https://raw.githubusercontent.com/nice42q/verbraucherzentrale-fakeshops/main/blocklist.txt` (AdBlock)
   - `https://raw.githubusercontent.com/nice42q/verbraucherzentrale-fakeshops/main/blocklist-domains.txt` (plain domains)
4. Click **Save**.

## 🔄 Automation & Safety

The workflow runs daily **(04:00 UTC)**.  
`cron: '0 4 * * *'`

* **Incremental Archiving:** The script automatically imports its own local history (`blocklist-domains.txt`) at launch, appends newly uncovered threats from the live web crawler, and ensures historical data is never lost when the source drops it.
* **DNS-Native Normalization:** All parsed lines are normalized to lowercase. Extraneous protocols (`http://`, `https://`), path fragments (`/index.html`), and `www.` subdomains are stripped to match clean DNS root targets.
* **IDN Punycode Translation:** Internationalized domain names containing non-ASCII symbols (e.g., German umlauts like `ä`, `ö`, `ü`) are safely compiled into their structural `xn--` Punycode format to prevent syntax dropping during sinkhole compilation.
* **Syntax Validation:** Pure IP addresses, structural gaps, and parsing remnants are automatically filtered out and logged under `debug/blacklist.txt` to keep the production files light and compliant.

## 📜 License

The code in this repository is open-source. However, the original domain data comes from [fakeshop-finder.de](https://warnung.fakeshop-finder.de/). Please respect their terms of use.

## 🙏 Acknowledgements

* **fakeshop-finder.de** for maintaining the crucial fake shop blacklist.
* The **Pi‑hole community** for the great blocking ecosystem.

**Happy scam‑free browsing!** 🛡️
