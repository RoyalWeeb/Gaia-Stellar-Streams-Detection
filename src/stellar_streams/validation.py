import pandas as pd
from sklearn.metrics import adjusted_rand_score
from .preprocessing import normalize_ids


def evaluate_toy_truth(assigned, truth_path):
    truth = pd.read_csv(truth_path, dtype={"source_id": "string"})
    if not {"source_id", "truth_label"}.issubset(truth):
        raise ValueError("Truth file requires source_id and truth_label")
    truth["source_id"] = normalize_ids(truth.source_id)
    if truth.source_id.duplicated().any():
        raise ValueError("Duplicate truth identifiers")
    joined = assigned[["source_id", "cluster_id"]].merge(truth, on="source_id", validate="one_to_one")
    if len(joined) != len(assigned):
        raise ValueError("Truth file does not cover the complete selected sample")
    clustered = joined.cluster_id >= 0
    trail = joined.truth_label >= 0
    rows = []
    for label in sorted(joined.loc[trail, "truth_label"].unique()):
        group = joined.loc[joined.truth_label == label]
        nonnoise = group.loc[group.cluster_id >= 0, "cluster_id"]
        best = int(nonnoise.value_counts().idxmax()) if len(nonnoise) else -1
        overlap = int((group.cluster_id == best).sum()) if best >= 0 else 0
        total_pred = int((joined.cluster_id == best).sum()) if best >= 0 else 0
        rows.append({"truth_label": int(label), "best_cluster_id": best,
                     "selected_truth_members": len(group), "overlap": overlap,
                     "best_cluster_recall": overlap / len(group),
                     "best_cluster_precision": overlap / total_pred if total_pred else 0})
    return {"data_kind": "synthetic_toy_only", "selected_rows": len(joined),
            "adjusted_rand_index_including_field": float(adjusted_rand_score(joined.truth_label, joined.cluster_id)),
            "trail_member_clustered_fraction": float(clustered[trail].mean()) if trail.any() else None,
            "field_false_assignment_fraction": float(clustered[~trail].mean()) if (~trail).any() else None,
            "trail_recovery": rows}
