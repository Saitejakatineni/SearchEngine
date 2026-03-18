import re

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


def build_association(doc_tokens, token_2_stem, stem_2_tokens, query):
    """
    Compute a stem-to-stem co-occurrence (association) matrix and return
    the top-3 associated stems for each query token.

    The association score between stems u and v is:
        s(u, v) = c(u,v) / (c(u,u) + c(v,v) + c(u,v))
    where c is the raw co-occurrence dot product.

    Args:
        doc_tokens:    list of token lists, one per document
        token_2_stem:  {token: stem}
        stem_2_tokens: {stem: set(tokens)}
        query:         list of query tokens

    Returns:
        list of stem strings to use as query expansions (top-3 per query token)
    """
    stems      = sorted(stem_2_tokens.keys())
    stem_2_idx = {s: i for i, s in enumerate(stems)}
    n_stems    = len(stems)
    n_docs     = len(doc_tokens)

    # Term-frequency matrix: f[doc, stem] = count of stem in that document
    f = np.zeros((n_docs, n_stems), dtype=np.int64)
    for doc_id, tokens in enumerate(doc_tokens):
        for token in tokens:
            if token in token_2_stem:
                f[doc_id, stem_2_idx[token_2_stem[token]]] += 1

    # Co-occurrence matrix via matrix multiplication: c[u,v] = sum_d f[d,u]*f[d,v]
    c      = f.T @ f
    c_diag = np.diag(c)   # c[u,u] for all u

    # Pick top-3 associated stems for each query token
    query_expand_ids = []
    for token in query:
        if token not in token_2_stem:
            continue
        stem_id = stem_2_idx[token_2_stem[token]]

        c_row   = c[stem_id, :]
        scores  = c_row / (c_row[stem_id] + c_diag + c_row)
        top3    = np.argsort(scores)[::-1][:3]
        query_expand_ids.extend(top3.tolist())

    return [stems[i] for i in query_expand_ids]


def association_main(query, solr_results):
    """
    Expand a query using association-based term co-occurrence.

    Args:
        query:        raw query string (may be prefixed with "content:")
        solr_results: iterable of Solr result dicts

    Returns:
        expanded query string prefixed with "content:"
    """
    if query.startswith('content:'):
        query = query[8:]
    print("Initial Query:", query)

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

    expand_stems  = build_association(doc_tokens, token_2_stem, stem_2_tokens, query_tokens)
    expand_tokens = set()
    for stem in expand_stems:
        expand_tokens.update(stem_2_tokens[stem])
    expand_tokens -= set(query_tokens)   # don't repeat original query terms

    all_tokens = query_tokens + list(expand_tokens)
    expanded   = ' '.join(all_tokens)
    print('Expanded query:', expanded)
    return 'content:' + expanded
