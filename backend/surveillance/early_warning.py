"""
Early-warning statistics for outbreak detection.

Pure, dependency-light functions (numpy only) operating on a daily case-count
series, so they are fast, deterministic and easy to unit test.

Algorithms
----------
* EARS C1 / C2 / C3  - CDC Early Aberration Reporting System detectors.
* CUSUM              - cumulative-sum detector for sustained small shifts.
* Poisson exceedance - one-sided Poisson tail probability against a baseline.
* Rt estimate        - instantaneous reproduction number (Cori et al. 2013
                       renewal-equation estimator, gamma serial interval).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Iterable, Sequence

import numpy as np

MIN_SERIES_DAYS = 10


# ---------------------------------------------------------------------------
# Series helpers
# ---------------------------------------------------------------------------

def fill_daily_series(counts_by_date: dict, start: date, end: date) -> list[int]:
    """Return a dense daily list from ``start`` to ``end`` inclusive (missing days = 0)."""
    if end < start:
        raise ValueError("end must not be before start")
    days = (end - start).days + 1
    return [int(counts_by_date.get(start + timedelta(days=i), 0)) for i in range(days)]


def _clean(series: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(series), dtype=float)
    if arr.size and (np.isnan(arr).any() or (arr < 0).any()):
        raise ValueError("series must contain non-negative numbers only")
    return arr


# ---------------------------------------------------------------------------
# EARS detectors
# ---------------------------------------------------------------------------

def ears(series: Sequence[float], variant: str = "C2", baseline: int = 7,
         guard: int = 2, threshold: float = 3.0, min_std: float = 1.0) -> list[dict]:
    """
    Run an EARS detector over the whole series.

    C1: baseline = previous ``baseline`` days.
    C2: same, but separated from today by a ``guard`` gap.
    C3: C2 statistic summed over the current and previous two days.

    Returns one dict per evaluable day: ``{index, value, score, alarm}``.
    ``min_std`` floors the baseline deviation so flat zero baselines don't divide by zero.
    """
    variant = variant.upper()
    if variant not in {"C1", "C2", "C3"}:
        raise ValueError("variant must be C1, C2 or C3")
    arr = _clean(series)
    gap = 0 if variant == "C1" else guard
    first = baseline + gap
    out: list[dict] = []

    def c_stat(t: int) -> float:
        window = arr[t - gap - baseline: t - gap]
        sd = max(window.std(ddof=1), min_std)
        return (arr[t] - window.mean()) / sd

    for t in range(first, len(arr)):
        if variant == "C3":
            if t < first + 2:
                continue
            score = sum(max(0.0, c_stat(t - k) - 1.0) for k in range(3))
            thr = 2.0 if threshold == 3.0 else threshold
        else:
            score = c_stat(t)
            thr = threshold
        out.append({"index": t, "value": float(arr[t]), "score": round(float(score), 4),
                    "alarm": bool(score > thr)})
    return out


def cusum(series: Sequence[float], baseline: int = 14, k: float = 0.5,
          h: float = 4.0, min_std: float = 1.0) -> list[dict]:
    """
    One-sided upper CUSUM on standardised counts.

    The reference mean/sd are fixed from the first ``baseline`` days; S_t =
    max(0, S_{t-1} + z_t - k); alarm when S_t > h (then S resets).
    """
    arr = _clean(series)
    if len(arr) <= baseline:
        return []
    ref = arr[:baseline]
    mu, sd = ref.mean(), max(ref.std(ddof=1), min_std)
    s = 0.0
    out = []
    for t in range(baseline, len(arr)):
        z = (arr[t] - mu) / sd
        s = max(0.0, s + z - k)
        alarm = s > h
        out.append({"index": t, "value": float(arr[t]), "score": round(s, 4), "alarm": bool(alarm)})
        if alarm:
            s = 0.0
    return out


# ---------------------------------------------------------------------------
# Poisson exceedance
# ---------------------------------------------------------------------------

def poisson_sf(observed: int, expected: float) -> float:
    """P(X >= observed) for X ~ Poisson(expected), numerically stable."""
    if observed <= 0:
        return 1.0
    if expected <= 0:
        return 0.0
    term = math.exp(-expected)
    cdf = term
    for i in range(1, observed):
        term *= expected / i
        cdf += term
    return max(0.0, min(1.0, 1.0 - cdf))


def poisson_exceedance(series: Sequence[float], window: int = 7, baseline: int = 28,
                       alpha: float = 0.01) -> dict | None:
    """
    Compare cases in the most recent ``window`` days against the mean rate of the
    preceding ``baseline`` days. Returns None when there is too little history.
    """
    arr = _clean(series)
    if len(arr) < window + baseline:
        return None
    recent = int(arr[-window:].sum())
    base = arr[-(window + baseline):-window]
    expected = float(base.mean() * window)
    p = poisson_sf(recent, expected)
    return {"observed": recent, "expected": round(expected, 3), "p_value": p,
            "alarm": bool(p < alpha)}


# ---------------------------------------------------------------------------
# Reproduction number
# ---------------------------------------------------------------------------

def serial_interval_pmf(mean: float = 5.0, sd: float = 3.0, max_days: int = 30) -> np.ndarray:
    """Discretised gamma serial-interval distribution for s = 1..max_days."""
    if mean <= 0 or sd <= 0:
        raise ValueError("mean and sd must be positive")
    shape, scale = (mean / sd) ** 2, sd ** 2 / mean
    s = np.arange(1, max_days + 1, dtype=float)

    def cdf(x):
        # regularised lower incomplete gamma via series/continued fraction (no scipy needed)
        return _gamma_cdf(x, shape, scale)

    pmf = np.array([cdf(i) - cdf(i - 1) for i in s])
    total = pmf.sum()
    return pmf / total if total > 0 else pmf


def _gamma_cdf(x: float, shape: float, scale: float) -> float:
    if x <= 0:
        return 0.0
    a, z = shape, x / scale
    # series expansion of the regularised lower incomplete gamma function
    term = 1.0 / a
    total = term
    for n in range(1, 500):
        term *= z / (a + n)
        total += term
        if abs(term) < 1e-12 * abs(total):
            break
    return min(1.0, total * math.exp(-z + a * math.log(z) - math.lgamma(a)))


def estimate_rt(series: Sequence[float], window: int = 7, si_mean: float = 5.0,
                si_sd: float = 3.0, prior_shape: float = 1.0, prior_scale: float = 5.0) -> dict | None:
    """
    Cori-style instantaneous reproduction number over the last ``window`` days.

    Posterior is Gamma(shape + sum(I_t), 1/(1/scale + sum(Lambda_t))); returns the
    mean and a 95% credible interval, or None when there is not enough data.
    """
    arr = _clean(series)
    w = serial_interval_pmf(si_mean, si_sd, max_days=min(30, max(len(arr) - 1, 1)))
    if len(arr) < window + 2 or arr[-window:].sum() == 0:
        return None
    incidence, lam = 0.0, 0.0
    for t in range(len(arr) - window, len(arr)):
        incidence += arr[t]
        lam += sum(arr[t - s] * w[s - 1] for s in range(1, min(t, len(w)) + 1))
    if lam <= 0:
        return None
    shape = prior_shape + incidence
    rate = 1.0 / prior_scale + lam
    mean = shape / rate
    sd = math.sqrt(shape) / rate
    return {"rt": round(mean, 3), "lower": round(max(0.0, mean - 1.96 * sd), 3),
            "upper": round(mean + 1.96 * sd, 3), "window_days": window,
            "growing": bool(mean - 1.96 * sd > 1.0)}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

@dataclass
class EarlyWarningResult:
    status: str                       # NORMAL | WATCH | WARNING | ALERT | INSUFFICIENT_DATA
    n_days: int
    detectors: dict = field(default_factory=dict)
    rt: dict | None = None
    reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def analyze(series: Sequence[float]) -> EarlyWarningResult:
    """
    Run all detectors on the latest point of ``series`` and combine into a status.

    ALERT   : 3+ independent signals fire
    WARNING : 2 signals
    WATCH   : 1 signal
    NORMAL  : none
    """
    arr = _clean(series)
    n = len(arr)
    if n < MIN_SERIES_DAYS:
        return EarlyWarningResult("INSUFFICIENT_DATA", n, reasons=[f"need at least {MIN_SERIES_DAYS} days"])

    signals: list[str] = []
    detectors: dict = {}
    for name, fn in (("ears_c1", lambda: ears(arr, "C1")), ("ears_c2", lambda: ears(arr, "C2")),
                     ("ears_c3", lambda: ears(arr, "C3")), ("cusum", lambda: cusum(arr, baseline=min(14, n // 2)))):
        res = fn()
        latest = res[-1] if res else None
        detectors[name] = latest
        if latest and latest["alarm"]:
            signals.append(name)

    pe = poisson_exceedance(arr)
    detectors["poisson"] = pe
    if pe and pe["alarm"]:
        signals.append("poisson")

    rt = estimate_rt(arr)
    if rt and rt["growing"]:
        signals.append("rt_growing")

    status = {0: "NORMAL", 1: "WATCH", 2: "WARNING"}.get(len(signals), "ALERT")
    return EarlyWarningResult(status, n, detectors, rt, signals)
