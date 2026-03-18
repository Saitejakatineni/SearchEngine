import flask
from flask_cors import CORS
import pysolr
import re
from flask import request, jsonify
import json
from query_expansion.association import association_main
from query_expansion.metric import metric_cluster_main

solr = pysolr.Solr('http://localhost:8983/solr/nutch/', always_commit=True, timeout=10)

app = flask.Flask(__name__)
CORS(app)
app.config["DEBUG"] = True

# ── Preload expensive data once at startup ────────────────────────────────────

def _load_cluster_map(path):
    """Read a URL→cluster CSV file and return it as a dict."""
    cluster_map = {}
    with open(path) as f:
        for line in f:
            url, _, cluster = line.partition(",")
            cluster_map[url] = cluster.strip() or "99"
    return cluster_map

CLUSTER_MAPS = {
    "flat_clustering":       _load_cluster_map("clustering/clustering_f.txt"),
    "hierarchical_clustering": _load_cluster_map("clustering/test_single_clustering_result_20k.txt"),
    "dummy_clustering":      _load_cluster_map("clustering/Complete_clustering.txt"),
}

with open("HITS/precomputed_scores/authority_score") as f:
    AUTHORITY_SCORES = json.load(f)

# ── Route ─────────────────────────────────────────────────────────────────────

@app.route('/api/v1/indexer', methods=['GET'])
def get_query():
    if 'query' not in request.args or 'type' not in request.args:
        return "Error: No query or type provided"

    query      = str(request.args['query'])
    query_type = str(request.args['type'])

    solr_results = get_results_from_solr(query, total_results=50)
    api_resp     = parse_solr_results(solr_results)
    display_query = query[8:]   # strip leading "content:"

    if query_type in ("page_rank", "hits"):
        result = sort_by_hits_authority(api_resp)
        return jsonify({"query": display_query, "results": result})

    if "clustering" in query_type:
        result = rerank_by_cluster(api_resp, query_type)
        return jsonify({"query": display_query, "results": result})

    if query_type in ("association_qe", "scalar_qe"):
        expanded_query    = association_main(query, solr_results)
        expanded_results  = get_results_from_solr(expanded_query, total_results=20)
        result            = parse_solr_results(expanded_results)
        return jsonify({"query": expanded_query[8:], "results": result})

    if query_type == "metric_qe":
        expanded_query    = metric_cluster_main(query, solr_results)
        expanded_results  = get_results_from_solr(expanded_query, total_results=20)
        result            = parse_solr_results(expanded_results)
        return jsonify({"query": expanded_query[8:], "results": result})

    return "Error: Unknown query type"

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_results_from_solr(query, total_results):
    escaped = query.replace(' ', '\\ ')
    return solr.search(escaped, search_handler="/select", **{
        "wt": "json",
        "rows": total_results,
    })


def parse_solr_results(solr_results):
    if solr_results.hits == 0:
        return jsonify("query out of scope")

    api_resp = []
    meta_info = ""
    for rank, result in enumerate(solr_results, start=1):
        content = result.get('content', '')
        # Solr text_general fields are returned as lists; join to a single string
        if isinstance(content, list):
            content = ' '.join(content)
        if content:
            meta_info = " ".join(re.findall("[a-zA-Z]+", content[:200].replace("\n", " ")))
        title = result.get('title', '')
        url   = result.get('url', '')
        if isinstance(title, list):
            title = title[0] if title else ''
        if isinstance(url, list):
            url = url[0] if url else ''
        api_resp.append({
            "title":     title,
            "url":       url,
            "meta_info": meta_info,
            "rank":      rank,
        })
    return api_resp


def sort_by_hits_authority(results):
    """Re-rank results by preloaded HITS authority score (descending)."""
    return sorted(results, key=lambda r: AUTHORITY_SCORES.get(r['url'], 0.0), reverse=True)


def rerank_by_cluster(results, cluster_type):
    """Group results so that documents in the same cluster appear consecutively."""
    cluster_map = CLUSTER_MAPS[cluster_type]

    # Group results by cluster, preserving first-seen order
    groups = {}
    for r in results:
        cluster = cluster_map.get(r["url"], "99")
        groups.setdefault(cluster, []).append(r)

    # Flatten groups and assign new ranks
    ranked = []
    for group in groups.values():
        ranked.extend(group)

    return [
        {"title": r["title"], "url": r["url"], "meta_info": r["meta_info"], "rank": str(i + 1)}
        for i, r in enumerate(ranked)
    ]


if __name__ == '__main__':
    app.run(port='5000')
