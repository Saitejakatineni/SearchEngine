import re
from collections import Counter

import numpy as np
from nltk.corpus import stopwords
from nltk import PorterStemmer
from tqdm import tqdm

porter_stemmer = PorterStemmer()
stop_words = set(stopwords.words('english'))


def tokenize_text(text):
    """Return a list of lowercase, stop-word-free alphabetic tokens."""
    text = re.sub(r'[\n,-]', ' ', text)        # newlines, commas, dashes → space
    text = re.sub(r'[^A-Za-z\s]', '', text)    # strip everything non-alpha
    text = text.lower()
    return [t for t in text.split() if t and t not in stop_words]


def make_stem_map(vocab):
    """
    Args:
        vocab: iterable of token strings

    Returns:
        token_2_stem: {token: stem}
        stem_2_tokens: {stem: set(tokens)}
    """
    token_2_stem  = {}
    stem_2_tokens = {}
    for token in vocab:
        stem = porter_stemmer.stem(token)
        stem_2_tokens.setdefault(stem, set()).add(token)
        token_2_stem[token] = stem
    return token_2_stem, stem_2_tokens


def get_metric_clusters(doc_tokens, token_2_stem, stem_2_tokens, query):
    """
    Build a stem-level co-occurrence matrix weighted by inverse count-difference,
    then pick the top-2 co-occurring stems for each query token.

    The contribution of a (token_i, token_j) pair within a document is:
        1 / |count_i - count_j|   (only when stems differ and counts differ)

    Args:
        doc_tokens:    list of token lists, one per document
        token_2_stem:  {token: stem}
        stem_2_tokens: {stem: set(tokens)}
        query:         list of query tokens

    Returns:
        list of stem strings to use as query expansions
    """
    stems     = sorted(stem_2_tokens.keys())
    stem_2_idx = {s: i for i, s in enumerate(stems)}
    n_stems   = len(stems)

    stem_len = np.array([len(stem_2_tokens[s]) for s in stems])  # number of variant forms

    # Co-occurrence matrix: c[i, j] accumulates 1/|count_i - count_j| contributions
    c = np.zeros((n_stems, n_stems), dtype=np.float64)

    for tokens in doc_tokens:
        if not tokens:
            continue

        # Count occurrences of each unique token in this document
        token_counts = Counter(tokens)

        # Build parallel arrays: one entry per unique token
        stem_ids = []
        counts   = []
        for token, count in token_counts.items():
            if token not in token_2_stem:
                continue
            stem_ids.append(stem_2_idx[token_2_stem[token]])
            counts.append(float(count))

        if len(stem_ids) < 2:
            continue

        stem_ids = np.array(stem_ids)
        counts   = np.array(counts)
        n_tok    = len(stem_ids)

        # Pairwise |count_i - count_j| — shape (n_tok, n_tok)
        diff = np.abs(counts[:, None] - counts[None, :])

        # Contribution is 1/diff where counts differ AND stems differ
        same_stem = stem_ids[:, None] == stem_ids[None, :]
        valid     = (diff > 0) & ~same_stem
        contrib   = np.where(valid, 1.0 / np.where(diff > 0, diff, 1.0), 0.0)

        # Scatter contributions into the stem-level matrix.
        # rows[k] / cols[k] give the (stem_i, stem_j) index for contrib.ravel()[k].
        rows = np.repeat(stem_ids, n_tok)
        cols = np.tile(stem_ids, n_tok)
        np.add.at(c, (rows, cols), contrib.ravel())

    # For each query token, pick the top-2 co-occurring stems (normalized by stem variant count)
    query_expand_ids = []
    for token in query:
        if token not in token_2_stem:
            continue
        stem_id = stem_2_idx[token_2_stem[token]]

        scores   = c[stem_id, :] / (stem_len[stem_id] * stem_len)
        top2_ids = np.argsort(scores)[::-1][:2]
        query_expand_ids.extend(top2_ids.tolist())

    return [stems[i] for i in query_expand_ids]


def metric_cluster_main(query, solr_results):
    """
    Expand a query using metric-based term clustering.

    Args:
        query:        raw query string (may be prefixed with "content:")
        solr_results: iterable of Solr result dicts

    Returns:
        expanded query string prefixed with "content:"
    """
    if query.startswith('content:'):
        query = query[8:]

    query_tokens = tokenize_text(query)

    vocab      = set(query_tokens)
    doc_tokens = []
    for result in tqdm(solr_results, desc='Preprocessing results'):
        raw = result.get('content', '')
        if isinstance(raw, list):
            raw = ' '.join(raw)
        tokens = tokenize_text(raw) if raw else []
        doc_tokens.append(tokens)
        vocab.update(tokens)

    token_2_stem, stem_2_tokens = make_stem_map(sorted(vocab))

    expand_stems  = get_metric_clusters(doc_tokens, token_2_stem, stem_2_tokens, query_tokens)
    expand_tokens = set()
    for stem in expand_stems:
        expand_tokens.update(stem_2_tokens[stem])
    expand_tokens -= set(query_tokens)   # don't repeat original query terms

    all_tokens    = query_tokens + list(expand_tokens)
    expanded      = ' '.join(all_tokens)
    print('Expanded query:', expanded)
    return 'content:' + expanded
