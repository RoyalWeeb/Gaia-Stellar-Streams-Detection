import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import adjusted_rand_score
from umap import UMAP
import hdbscan
from .preprocessing import FEATURES


def embed_umap(x, config, seed):
    return UMAP(n_neighbors=config.n_neighbors, n_components=config.n_components,
                     min_dist=config.min_dist, metric="euclidean", random_state=seed,
                     n_jobs=1, low_memory=True).fit_transform(x)


def fit_density(x, config):
    return hdbscan.HDBSCAN(min_cluster_size=config.min_cluster_size,
                           min_samples=config.min_samples, metric="euclidean",
                           cluster_selection_method=config.cluster_selection_method,
                           core_dist_n_jobs=1).fit(x)


def cluster_embedding(x, config, seed):
    embedding = embed_umap(x, config, seed)
    model = fit_density(embedding, config)
    return embedding, model


def scale_features(df, config):
    raw = df[FEATURES].to_numpy(float)
    if not np.isfinite(raw).all():
        raise ValueError("Nonfinite phase-space features")
    scaler = RobustScaler(quantile_range=(25, 75))
    weights = np.array([config.position_weight] * 3 + [config.velocity_weight] * 3)
    return scaler.fit_transform(raw) * weights, scaler, weights


def best_jaccard(reference, other):
    result = {}
    for label in sorted(set(reference) - {-1}):
        a = reference == label
        overlaps = []
        for alt in set(other[a]) - {-1}:
            b = other == alt
            overlaps.append(float(np.count_nonzero(a & b) / np.count_nonzero(a | b)))
        result[int(label)] = max(overlaps, default=0.0)
    return result


def fit_clusters(df, config, progress=None):
    if len(df) <= max(config.n_neighbors, config.min_cluster_size, config.min_samples, config.n_components + 1):
        raise ValueError("Too few selected stars for configured neighbors/cluster size/minimum samples/components")
    def report(message):
        if progress:
            progress(message)
    report("Scaling six physical features")
    x, scaler, weights = scale_features(df, config)
    report(f"Fitting UMAP with seed {config.seed}")
    embedding = embed_umap(x, config, config.seed)
    report("Finding density candidates with HDBSCAN")
    model = fit_density(embedding, config)
    labels = model.labels_
    stability = []
    for offset in range(1, config.stability_runs + 1):
        report(f"Checking UMAP seed {config.seed + offset} ({offset}/{config.stability_runs})")
        _, alternative = cluster_embedding(x, config, config.seed + offset)
        overlap = best_jaccard(labels, alternative.labels_)
        for label, score in overlap.items():
            stability.append({"cluster_id": label, "seed": config.seed + offset,
                              "best_membership_jaccard": score})
    report("Checking memberships in the original six dimensions")
    direct = fit_density(x, config)
    agreement = best_jaccard(labels, direct.labels_)
    assigned = df.copy()
    assigned["cluster_id"] = labels
    assigned["membership_strength"] = model.probabilities_
    assigned["outlier_score"] = model.outlier_scores_
    assigned["direct_6d_cluster_id"] = direct.labels_
    for i in range(embedding.shape[1]):
        assigned[f"umap_{i+1}"] = embedding[:, i]
    catalog = candidate_diagnostics(assigned, model.cluster_persistence_, stability, agreement)
    diagnostics = {
        "n_clusters": len(catalog), "noise_rows": int(np.sum(labels == -1)),
        "noise_fraction": float(np.mean(labels == -1)),
        "direct_6d_clusters": len(set(direct.labels_) - {-1}),
        "original_6d_supported_candidates": int(catalog.original_6d_supported.sum()),
        "original_6d_support_note": "Descriptive flag: best membership Jaccard >= 0.5 against direct 6D clustering; not a confirmation threshold.",
        "ari_embedded_vs_direct_6d_including_noise": float(adjusted_rand_score(labels, direct.labels_)),
        "scaler_center": scaler.center_.tolist(), "scaler_iqr": scaler.scale_.tolist(),
        "feature_weights": weights.tolist(), "features": FEATURES,
        "stability_note": "Best cluster membership Jaccard across additional UMAP seeds; not uncertainty propagation.",
        "membership_note": "HDBSCAN strengths are relative density membership scores, not calibrated physical probabilities."
    }
    return assigned, catalog, pd.DataFrame(stability, columns=["cluster_id", "seed", "best_membership_jaccard"]), diagnostics


def candidate_diagnostics(assigned, persistence, stability=(), agreement=None):
    """Physical summaries always use all assigned members, never a display sample."""
    labels = assigned.cluster_id.to_numpy()
    rows = []
    for label in sorted(set(labels) - {-1}):
        members = assigned.loc[labels == label]
        eig = np.linalg.eigvalsh(np.cov(members[["x_kpc", "y_kpc", "z_kpc"]].to_numpy().T))
        seed_scores = [r["best_membership_jaccard"] for r in stability if r["cluster_id"] == label]
        row = {"cluster_id": int(label), "n_members": len(members),
               "mean_membership_strength": float(members.membership_strength.mean()),
               "cluster_persistence": float(persistence[label]),
               "seed_jaccard_mean": float(np.mean(seed_scores)) if seed_scores else np.nan,
               "direct_6d_best_jaccard": agreement[int(label)] if agreement is not None else np.nan,
               "original_6d_supported": agreement[int(label)] >= 0.5 if agreement is not None else False,
               "position_elongation": float(np.sqrt(max(eig[-1], 0) / max(eig[0], 1e-12))),
               "velocity_dispersion_3d_kms": float(np.sqrt(members[FEATURES[3:]].var(ddof=1).sum())),
               "status": "unvalidated_density_candidate"}
        row.update({f"median_{key}": float(members[key].median()) for key in FEATURES})
        rows.append(row)
    columns = ["cluster_id", "n_members", "mean_membership_strength", "cluster_persistence",
               "seed_jaccard_mean", "direct_6d_best_jaccard", "original_6d_supported", "position_elongation",
               "velocity_dispersion_3d_kms", "status"] + [f"median_{key}" for key in FEATURES]
    return pd.DataFrame(rows, columns=columns)
