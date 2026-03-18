"""
Fetches car-related articles from Wikipedia and indexes them into Solr.
Wikipedia is free, public, and provides rich text content — good enough
for all search engine features (ranking, clustering, query expansion).

Usage:
    python3 crawl_and_index.py

What it does:
    1. Searches Wikipedia for articles matching each seed topic.
    2. Downloads the full text of each article.
    3. POSTs them to the local Solr 'nutch' core in batches.

Note on precomputed features:
    The clustering and HITS files were built from the original crawl URLs,
    so cluster reranking and HITS sorting will have limited effect on newly
    indexed documents. Search and query expansion will work fully.
"""
import hashlib
import sys
import time
from datetime import datetime, timezone

import requests
import pysolr

SOLR_URL = "http://localhost:8983/solr/nutch/"
WIKI_API = "https://en.wikipedia.org/w/api.php"

# Wikipedia requires a descriptive User-Agent (blocks the default requests one)
HEADERS = {"User-Agent": "CarSearchEngineProject/1.0 (educational IR project)"}
BATCH_SIZE = 20          # documents per Solr commit
DELAY_SECS = 0.5         # pause between Wikipedia API calls (be polite)

# Topics to search on Wikipedia — covers the car domain this project targets
SEED_TOPICS = [
    "BMW automobile",
    "Mercedes-Benz",
    "Audi car",
    "Volkswagen",
    "Toyota car",
    "Honda automobile",
    "Ford Motor Company",
    "electric vehicle",
    "hybrid car",
    "car engine",
    "automotive industry",
    "sports car",
    "sedan car",
    "SUV automobile",
    "pickup truck",
    "car dealership",
    "car insurance",
    "car maintenance",
    "auto parts",
    "Formula One",
    "NASCAR racing",
    "autonomous vehicle",
    "car manufacturing",
    "luxury car",
    "used car",
]

ARTICLES_PER_TOPIC = 8   # how many Wikipedia articles to fetch per topic


def search_wikipedia(topic, limit):
    """Return a list of Wikipedia page IDs matching the topic."""
    params = {
        "action":   "query",
        "list":     "search",
        "srsearch": topic,
        "srlimit":  limit,
        "format":   "json",
    }
    resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    results = resp.json().get("query", {}).get("search", [])
    return [r["pageid"] for r in results]


def fetch_article(page_id):
    """Return (url, title, plain_text) for a Wikipedia page ID."""
    params = {
        "action":      "query",
        "prop":        "extracts|info",
        "pageids":     page_id,
        "explaintext": True,     # plain text, no HTML
        "inprop":      "url",
        "format":      "json",
    }
    resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    pages = resp.json()["query"]["pages"]
    page  = pages[str(page_id)]

    title   = page.get("title", "")
    content = page.get("extract", "")
    url     = page.get("fullurl", f"https://en.wikipedia.org/?curid={page_id}")
    return url, title, content


def make_solr_doc(url, title, content):
    """Build a Solr document dict matching the nutch schema."""
    return {
        "id":      url,
        "url":     url,
        "title":   title,
        "content": content,
        "digest":  hashlib.md5(content.encode()).hexdigest(),
        "boost":   1.0,
        "tstamp":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main():
    # Verify Solr is reachable
    try:
        requests.get("http://localhost:8983/solr/admin/info/system", timeout=5)
    except requests.ConnectionError:
        sys.exit("Solr is not running. Start it with:  brew services start solr")

    solr = pysolr.Solr(SOLR_URL, always_commit=False, timeout=30)

    seen_ids  = set()
    batch     = []
    total     = 0

    print(f"Fetching up to {len(SEED_TOPICS) * ARTICLES_PER_TOPIC} articles …\n")

    for topic in SEED_TOPICS:
        print(f"  [{topic}]")
        try:
            page_ids = search_wikipedia(topic, ARTICLES_PER_TOPIC)
        except Exception as e:
            print(f"    Search failed: {e}")
            continue

        for page_id in page_ids:
            if page_id in seen_ids:
                continue
            seen_ids.add(page_id)

            try:
                url, title, content = fetch_article(page_id)
            except Exception as e:
                print(f"    Page {page_id} fetch failed: {e}")
                continue

            if not content.strip():
                continue

            batch.append(make_solr_doc(url, title, content))
            total += 1
            print(f"    + {title[:70]}")

            if len(batch) >= BATCH_SIZE:
                solr.add(batch)
                solr.commit()
                batch.clear()
                print(f"    — committed {total} documents so far")

            time.sleep(DELAY_SECS)

    # Commit any remaining documents
    if batch:
        solr.add(batch)
        solr.commit()

    print(f"\nDone. {total} documents indexed into Solr core 'nutch'.")
    print("You can now start the app:  python3 app.py")


if __name__ == "__main__":
    main()
