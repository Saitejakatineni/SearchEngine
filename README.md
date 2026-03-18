# CarFind — Automotive Search Engine

An Information Retrieval course project built on top of Apache Solr. It demonstrates classic IR techniques — ranking, clustering, and query expansion — through a modern search interface that compares results alongside Google and Bing.

---

## Architecture

```
┌─────────────────────┐        HTTP (port 5000)       ┌──────────────────────┐
│   Frontend          │  ──────────────────────────►  │   Backend (Flask)    │
│   Web-App/          │                               │   app.py             │
│   (static HTML/JS)  │  ◄──────────────────────────  │                      │
└─────────────────────┘        JSON response           └──────────┬───────────┘
                                                                  │ Solr query
                                                       ┌──────────▼───────────┐
                                                       │   Apache Solr        │
                                                       │   localhost:8983     │
                                                       └──────────────────────┘
```

---

## Features

| Category | Options |
|----------|---------|
| **Relevance Ranking** | Page Rank, HITS (Hubs & Authorities) |
| **Clustering** | K-Means (flat), Agglomerative Single-Link, Agglomerative Complete-Link |
| **Query Expansion** | Association-based, Metric-based, Scalar/Cosine |
| **Comparison** | Results shown alongside live Google and Bing searches |

---

## Prerequisites

- Python 3.8+
- Java 8+ (required by Apache Solr)
- Apache Solr 10.x via Homebrew

---

## Complete Setup Guide

### Step 1 — Install Python dependencies

```bash
pip install flask flask-cors pysolr nltk numpy pandas scikit-learn scipy fastcluster matplotlib networkx tqdm requests beautifulsoup4
```

### Step 2 — Download NLTK data (one-time)

```bash
python3 -c "import nltk; nltk.download('stopwords')"
```

### Step 3 — Install and start Solr

```bash
brew install solr
brew services start solr
```

Wait ~15 seconds, then verify Solr is up at `http://localhost:8983`.

### Step 4 — Set up the Solr schema

Creates the `nutch` core and configures all required schema fields:

```bash
python3 setup_solr.py
```

Expected output:
```
1. Checking core 'nutch' …
   Core 'nutch' not found — creating …
   Core 'nutch' created.

2. Configuring schema fields …
  Field 'url' (string) added.
  Field 'title' (text_general) added.
  Field 'content' (text_general) added.
  ...

Done. Core 'nutch' is ready.
```

### Step 5 — Index data from Wikipedia

Fetches ~200 car-related Wikipedia articles (BMW, Mercedes, Audi, Toyota, EVs, Formula One, etc.) and indexes them into Solr. Takes ~2–3 minutes.

```bash
python3 crawl_and_index.py
```

Expected output:
```
Fetching up to 200 articles …

  [BMW automobile]
    + BMW
    + BMW 5 Series (F10)
    ...

Done. 190 documents indexed into Solr core 'nutch'.
```

> **Note:** Clustering rerank and HITS sort rely on precomputed scores from the original crawl URLs. They have limited effect on newly indexed Wikipedia documents. Search and query expansion work fully.

---

## Running the App

### Backend

```bash
python3 app.py
```

The API will be available at `http://127.0.0.1:5000`.

### Frontend

```bash
cd Web-App
python3 -m http.server 8080
```

Open `http://localhost:8080/my_index.html` in your browser.

> The backend must be running before you search.

---

## Stopping Everything

### Stop the Flask server
Press `Ctrl+C` in the terminal running `python3 app.py`.

### Stop Solr

```bash
brew services stop solr
```

### Solr quick reference

| Action | Command |
|--------|---------|
| Start | `brew services start solr` |
| Stop | `brew services stop solr` |
| Restart | `brew services restart solr` |
| Status | `brew services list \| grep solr` |

---

## API Reference

```
GET /api/v1/indexer?query=content:<your query>&type=<type>
```

| `type` value | Description |
|---|---|
| `page_rank` | Re-rank by HITS authority score |
| `hits` | Re-rank by HITS authority score |
| `flat_clustering` | K-Means cluster-aware reranking |
| `hierarchical_clustering` | Agglomerative single-link cluster reranking |
| `dummy_clustering` | Agglomerative complete-link cluster reranking |
| `association_qe` | Query expansion via term association |
| `metric_qe` | Query expansion via metric clustering |
| `scalar_qe` | Query expansion via scalar/cosine similarity |

Example:

```bash
curl "http://127.0.0.1:5000/api/v1/indexer?query=content:bmw&type=hits"
```

---

## Project Structure

```
SearchEngine/
├── app.py                          # Flask REST API (entry point)
├── setup_solr.py                   # One-time Solr core + schema setup
├── crawl_and_index.py              # Wikipedia crawler and Solr indexer
├── benchmark.py                    # Performance benchmarks
│
├── query_expansion/
│   ├── association.py              # Association-based query expansion
│   ├── metric.py                   # Metric-based query expansion
│   └── scalar.py                   # Scalar/cosine query expansion
│
├── HITS/
│   ├── hits_algorithm.py           # HITS algorithm (offline precomputation)
│   └── precomputed_scores/
│       ├── authority_score         # Precomputed authority scores (JSON)
│       └── hub_score               # Precomputed hub scores (JSON)
│
├── clustering/
│   ├── clustering.py               # Offline clustering script
│   ├── clustering_f.txt            # K-Means results (102k docs)
│   ├── test_single_clustering_result_20k.txt   # Single-link results
│   └── Complete_clustering.txt     # Complete-link results
│
└── Web-App/
    ├── my_index.html               # Search UI
    ├── my_script.js                # API calls and result rendering
    └── my_style.css                # Stylesheet
```

---

## Running the Benchmarks

Measures per-component latency without a running Solr instance (uses `jhol.json` as mock data):

```bash
python3 benchmark.py
```

---

## License

MIT
