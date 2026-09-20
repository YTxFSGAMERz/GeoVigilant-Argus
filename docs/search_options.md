# 🔍 Search Options & Dark Web Intelligence
```
================================================================================
  [ OSINT RECONNAISSANCE & TOR NETWORK INTEGRATION ]
================================================================================
```

GeoVigilant Argus provides multi-layered OSINT search, deep web scraping, social media reconnaissance, and Tor dark web routing capabilities.

---

## 🌐 MULTI-ENGINE WEB OSINT SCANNER

The Advanced Web Scan tool executes distributed OSINT queries across clear-net and developer platforms.

### 🛠️ API Specification
* **Endpoint**: `POST /api/tools/web_scan`
* **Parameters**:
  * `query`: Search string, username, email, phone number, or target keyword.
  * `type`: `text`, `images`, or `all`.
  * `sources`: Filter by platforms (`twitter`, `reddit`, `github`, `telegram`, `pastebin`).
  * `aggressive`: `true` for deep content scraping of top search results.

### 📱 Supported Platforms & Sources
* **Social Networks**: Twitter/X, Reddit, Instagram, LinkedIn.
* **Encrypted Chat/Channels**: Telegram channels, Discord public servers.
* **Developer Repositories**: GitHub commits, issues, and code search; GitLab, StackOverflow.
* **Breach & Paste Sites**: Pastebin, text dumps, and public breach blotters.
* **Surface Aggregation**: Multi-engine fusion (Google, Bing, DuckDuckGo).

---

## 🔒 SYSTEM 07: DEEP OSINT & TOR ONION SEARCH

The RF Surveillance dashboard integrates **System 07: Deep OSINT** for dark web intelligence:

![Deep OSINT and Tor Onion Intercept](../screenshots/wifi_surveillance.png)

### 🛡️ Routing Mechanics & Onion Engines
1. **Local Tor Proxy**: When a local Tor socks proxy is running (port `9050` or `9150`), queries are routed directly through the onion circuit to query hidden services:
   * **Ahmia** (`juhanurmih5wu7bv...onion`)
   * **OnionLand**
   * **Torgle**
   * **Torch**
2. **Ahmia Clearnet Fallback**: When operating in cloud serverless environments (e.g., Vercel) without a local SOCKS5 proxy, queries automatically fall back to Ahmia's secure clearnet gateway.
3. **Dedicated OSINT Triggers**:
   * `.ONION`: Searches indexed hidden service content.
   * `LEAKS`: Scrapes credential dump mirrors and paste sites.
   * `CRIMES`: Queries law enforcement APIs, open sanctions lists, and INTERPOL Red Notices.
   * `PHOTO`: Reverse image lookups and visual entity recognition.

---

## 🐦 SOCIAL MEDIA NEURAL RECONNAISSANCE

### Twitter / X OSINT Dashboard (`/social/twitter`)
Conducts timeline investigations, handle tracking, keyword sentiment extraction, and network engagement analysis.

![Twitter OSINT Dashboard](../screenshots/osint_twitter_stream.png)

* **Target Filters**: Filter by username, geolocation boundary, date range, verified badge, and minimum likes.
* **AI Engine Synthesis**: Summarizes target discourse patterns using local Ollama or cloud LLaMA-3.1 models.

---

### Reddit OSINT & Community Intelligence (`/social/reddit`)
Tracks subreddit sentiment, user posting patterns, and emerging crisis chatter.

![Reddit OSINT Dashboard](../screenshots/osint_reddit_stream.png)

* **Subreddit Monitoring**: Scrapes hot, new, and top threads across geopolitical subreddits.
* **User Dossier Generator**: Correlates user comment timestamps, active subreddits, and keyword frequencies.

```
================================================================================
  [ END OF SEARCH DOCUMENTATION ] // [ GEOVIGILANT ARGUS EYE ]
================================================================================
```
