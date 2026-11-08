"""Dataset coverage: cluster the questions by meaning and show which clusters have few items or no expert labels, so
labelling effort goes where the dataset is thin rather than where it is easy."""

from __future__ import annotations

from collections import Counter

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from qloop.world.tasks import Task


def clusters(tasks: list[Task], labelled_ids: set[str], k: int, seed: int) -> list[dict]:
    texts = [t.prompt for t in tasks]
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    x = vec.fit_transform(texts)
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(x)
    terms = vec.get_feature_names_out()
    out = []
    for c in range(k):
        members = [t for t, lab in zip(tasks, km.labels_) if lab == c]
        top = km.cluster_centers_[c].argsort()[::-1][:4]
        labelled = sum(t.id in labelled_ids for t in members)
        out.append({"cluster": c, "items": len(members), "labelled": labelled,
                    "terms": [str(terms[i]) for i in top],
                    "topics": dict(Counter(t.topic for t in members).most_common(3)),
                    "languages": dict(Counter(t.language for t in members)),
                    "thin": len(members) < 8 or labelled < 3})
    return sorted(out, key=lambda r: (not r["thin"], r["labelled"]))
