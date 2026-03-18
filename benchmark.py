"""
Benchmark and profile the search engine components.
Does not require a running Solr instance — uses jhol.json as mock data.
"""
import json
import time
import cProfile
import pstats
import io
import re

# ── Load mock data ────────────────────────────────────────────────────────────

with open("jhol.json", encoding="utf-8") as f:
    raw = json.load(f)

MOCK_DOCS = raw["response"]["docs"][:50]   # simulate 50 Solr results

MOCK_API_RESP = []
for i, doc in enumerate(MOCK_DOCS, 1):
    content = doc.get("content", "")
    meta = " ".join(re.findall("[a-zA-Z]+", content[:200].replace("\n", " ")))
    MOCK_API_RESP.append({
        "title":     doc.get("title", ""),
        "url":       doc.get("url", ""),
        "meta_info": meta,
        "rank":      i,
    })

# ── Timing helper ─────────────────────────────────────────────────────────────

def timed(label, fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  {label:<50} {elapsed:8.2f} ms")
    return result

# ── Clustering ────────────────────────────────────────────────────────────────

def _load_cluster_map(path):
    cluster_map = {}
    with open(path) as f:
        for line in f:
            url, _, cluster = line.partition(",")
            cluster_map[url] = cluster.strip() or "99"
    return cluster_map

def _rerank_new(results, cluster_map):
    groups = {}
    for r in results:
        cluster = cluster_map.get(r["url"], "99")
        groups.setdefault(cluster, []).append(r)
    ranked = []
    for group in groups.values():
        ranked.extend(group)
    return [
        {"title": r["title"], "url": r["url"], "meta_info": r["meta_info"], "rank": str(i + 1)}
        for i, r in enumerate(ranked)
    ]

def bench_clustering():
    print("\n=== Clustering ===")

    files = {
        "flat_clustering":          "clustering/clustering_f.txt",
        "hierarchical_clustering":  "clustering/test_single_clustering_result_20k.txt",
        "dummy_clustering":         "clustering/Complete_clustering.txt",
    }

    # OLD: read file + build dict on every request
    print("\n  [BEFORE] File read + dict build on every request:")
    for name, path in files.items():
        def old_approach(path=path):
            with open(path) as f:
                lines = f.readlines()
            m = {}
            for line in lines:
                parts = line.split(",")
                m[parts[0]] = parts[1].strip() if parts[1].strip() else "99"
            return m
        timed(f"    {name}", old_approach)

    # NEW: preload once, then just lookup
    print("\n  [AFTER] Preloaded at startup — per-request cost:")
    preloaded = {name: _load_cluster_map(path) for name, path in files.items()}
    for name, cm in preloaded.items():
        timed(f"    {name} (rerank only)", _rerank_new, MOCK_API_RESP, cm)

# ── HITS ──────────────────────────────────────────────────────────────────────

def bench_hits():
    print("\n=== HITS scoring ===")

    def old_hits(inp):
        auth_file = open("HITS/precomputed_scores/authority_score", "r").read()
        auth_dict = json.loads(auth_file)
        return sorted(inp, key=lambda x: auth_dict.get(x["url"], 0.0), reverse=True)

    print("\n  [BEFORE] open + read + JSON parse on every request:")
    for i in range(3):
        timed(f"    call #{i+1}", old_hits, MOCK_API_RESP)

    # NEW: preloaded
    with open("HITS/precomputed_scores/authority_score") as f:
        authority_scores = json.load(f)

    def new_hits(inp):
        return sorted(inp, key=lambda r: authority_scores.get(r['url'], 0.0), reverse=True)

    print("\n  [AFTER] Preloaded at startup — per-request cost:")
    for i in range(3):
        timed(f"    call #{i+1}", new_hits, MOCK_API_RESP)

# ── Query expansion ───────────────────────────────────────────────────────────

def bench_association():
    print("\n=== Association query expansion ===")
    from query_expansion.association import association_main
    timed("  association_main  (50 docs)", association_main, "content:bmw car", MOCK_DOCS)

def bench_metric():
    print("\n=== Metric query expansion ===")
    from query_expansion.metric import metric_cluster_main
    timed("  metric_cluster_main  (50 docs)", metric_cluster_main, "content:bmw car", MOCK_DOCS)

# ── cProfile deep-dives ───────────────────────────────────────────────────────

def profile_function(label, fn, *args, **kwargs):
    print(f"\n{'='*60}\ncProfile: {label}\n{'='*60}")
    pr = cProfile.Profile()
    pr.enable()
    fn(*args, **kwargs)
    pr.disable()
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(12)
    print(s.getvalue())

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running benchmarks …")

    bench_clustering()
    bench_hits()
    bench_association()
    bench_metric()

    from query_expansion.association import association_main
    from query_expansion.metric     import metric_cluster_main

    profile_function("association_main",    association_main,    "content:bmw car", MOCK_DOCS)
    profile_function("metric_cluster_main", metric_cluster_main, "content:bmw car", MOCK_DOCS)
