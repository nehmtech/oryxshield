"""
OryxShield - Spatial Analysis Functions
================================================

Three production-ready spatial statistics functions.

Functions:
    calculate_morans_i    – Moran's I spatial autocorrelation
    hotspot_analysis      – Getis-Ord Gi* hotspot/coldspot detection
    spatial_clustering    – DBSCAN or K-means spatial clustering
"""

import numpy as np
from scipy.spatial import distance_matrix
from scipy import stats
from sklearn.cluster import DBSCAN, KMeans
import logging

logger = logging.getLogger(__name__)


def calculate_morans_i(values, coordinates, weights='inverse_distance'):
    """
    Calculate Moran's I statistic for spatial autocorrelation.

    Interpretation:
        I > 0  – positive autocorrelation (similar values cluster)
        I ≈ 0  – random spatial pattern
        I < 0  – negative autocorrelation (dispersion)

    Args:
        values (array-like):      Numeric values at each location.
        coordinates (array-like): (N, 2) array of (lat, lon) pairs.
        weights (str):            'inverse_distance' or 'binary'.

    Returns:
        dict: {morans_i, expected_i, variance, z_score, p_value, is_significant}
    """
    try:
        values = np.array(values, dtype=float)
        n      = len(values)
        mean   = np.mean(values)

        dist = distance_matrix(coordinates, coordinates)

        if weights == 'inverse_distance':
            W = np.where(dist > 0, 1.0 / dist, 0.0)
        else:
            threshold = np.percentile(dist[dist > 0], 10)
            W = ((dist > 0) & (dist <= threshold)).astype(float)
        np.fill_diagonal(W, 0.0)

        # Row-normalise
        row_sums = W.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        W = W / row_sums

        dev       = values - mean
        numerator = float(np.dot(dev, np.dot(W, dev)))
        denom     = float(np.dot(dev, dev))

        S0  = float(W.sum())
        I   = (n / S0) * (numerator / denom) if denom != 0 else 0.0
        E_I = -1.0 / (n - 1)
        var = 1.0 / ((n - 1) * S0 ** 2) if S0 != 0 else 0.0

        z_score = (I - E_I) / np.sqrt(var) if var > 0 else 0.0
        p_value = float(2 * (1 - stats.norm.cdf(abs(z_score))))

        logger.info("Moran's I: %.4f  p-value: %.6f", I, p_value)

        return {
            'morans_i':      float(I),
            'expected_i':    float(E_I),
            'variance':      float(var),
            'z_score':       float(z_score),
            'p_value':       p_value,
            'is_significant': p_value < 0.05,
        }

    except Exception as exc:
        logger.error("Moran's I error: %s", exc, exc_info=True)
        raise


def hotspot_analysis(values, coordinates, threshold=1.96):
    """
    Getis-Ord Gi* hotspot / coldspot analysis.

    Args:
        values (array-like):      Case counts or rates at each location.
        coordinates (array-like): (N, 2) array of (lat, lon) pairs.
        threshold (float):        Z-score significance threshold (default 1.96 = 95 %).

    Returns:
        dict: {hotspots, coldspots, z_scores, threshold}
              Each hotspot/coldspot: {index, coordinates, value, z_score, p_value}
    """
    try:
        values      = np.array(values, dtype=float)
        coordinates = np.array(coordinates, dtype=float)
        n           = len(values)
        mean        = np.mean(values)
        std         = np.std(values)

        dist = distance_matrix(coordinates, coordinates)
        W    = np.where(dist > 0, 1.0 / dist, 0.0)
        np.fill_diagonal(W, 0.0)

        z_scores = []
        for i in range(n):
            W_i       = W[i].copy()
            W_i[i]    = 1.0              # include focal point
            sum_wi    = W_i.sum()
            sum_wi_xi = float(np.dot(W_i, values))

            numerator = sum_wi_xi - mean * sum_wi
            denom_sq  = (n * float(np.sum(W_i ** 2)) - sum_wi ** 2) / (n - 1)
            denom     = std * np.sqrt(denom_sq) if denom_sq > 0 else 0.0

            z_scores.append(numerator / denom if denom > 0 else 0.0)

        z_scores = np.array(z_scores)
        hotspots, coldspots = [], []

        for i, z in enumerate(z_scores):
            if abs(z) < threshold:
                continue
            entry = {
                'index':       i,
                'coordinates': coordinates[i].tolist(),
                'value':       float(values[i]),
                'z_score':     float(z),
                'p_value':     float(2 * (1 - stats.norm.cdf(abs(z)))),
            }
            (hotspots if z > 0 else coldspots).append(entry)

        logger.info("Hotspot analysis: %d hotspots, %d coldspots",
                    len(hotspots), len(coldspots))

        return {
            'hotspots':  hotspots,
            'coldspots': coldspots,
            'z_scores':  z_scores.tolist(),
            'threshold': threshold,
        }

    except Exception as exc:
        logger.error("Hotspot analysis error: %s", exc, exc_info=True)
        raise


def spatial_clustering(coordinates, values=None, method='dbscan', **kwargs):
    """
    DBSCAN or K-means spatial clustering.

    Args:
        coordinates (array-like): (N, 2) array of (lat, lon) pairs.
        values (array-like|None): Optional per-point values for cluster statistics.
        method (str):             'dbscan' or 'kmeans'.
        **kwargs:
            dbscan  – eps (default 0.1), min_samples (default 5)
            kmeans  – n_clusters (default 5)

    Returns:
        dict: {method, labels, clusters, n_clusters, noise_count}
              Each cluster: {cluster_id, size, center, members,
                             mean_value?, total_value?}
    """
    try:
        coords = np.array(coordinates, dtype=float)

        if method == 'dbscan':
            eps         = kwargs.get('eps', 0.1)
            min_samples = kwargs.get('min_samples', 5)
            labels      = DBSCAN(eps=eps, min_samples=min_samples).fit(coords).labels_

        elif method == 'kmeans':
            n_clusters = kwargs.get('n_clusters', 5)
            labels     = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto') \
                            .fit(coords).labels_

        else:
            raise ValueError(f"Unknown clustering method: {method}")

        unique_labels = sorted(set(labels) - {-1})
        clusters = []

        for label in unique_labels:
            mask   = labels == label
            c_coords = coords[mask]
            entry  = {
                'cluster_id': int(label),
                'size':       int(mask.sum()),
                'center':     c_coords.mean(axis=0).tolist(),
                'members':    np.where(mask)[0].tolist(),
            }
            if values is not None:
                c_vals = np.array(values)[mask]
                entry['mean_value']  = float(c_vals.mean())
                entry['total_value'] = float(c_vals.sum())
            clusters.append(entry)

        noise_count = int((labels == -1).sum()) if method == 'dbscan' else 0

        logger.info("Clustering (%s): %d clusters, %d noise points",
                    method, len(unique_labels), noise_count)

        return {
            'method':      method,
            'labels':      labels.tolist(),
            'clusters':    clusters,
            'n_clusters':  len(unique_labels),
            'noise_count': noise_count,
        }

    except Exception as exc:
        logger.error("Clustering error: %s", exc, exc_info=True)
        raise