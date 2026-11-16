"""Mathematical correctness of the statistics layer, checked against closed-form results and independent scipy/statsmodels calls."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats
from statsmodels.stats.multitest import multipletests

from backend.analytics import stats as S
from backend.analytics.sports import lower_is_better, parse_perf
from backend.analytics.store import _clean


def test_describe_matches_hand_computation():
    x = pd.Series([2, 4, 4, 4, 5, 5, 7, 9])
    d = S.describe(x)
    assert d["n"] == 8 and d["mean"] == 5 and d["median"] == 4.5 and d["mode"] == 4
    assert d["range"] == 7 and d["min"] == 2 and d["max"] == 9
    assert d["variance"] == pytest.approx(np.var(x, ddof=1)) and d["std"] == pytest.approx(np.std(x, ddof=1))
    assert d["q1"] == pytest.approx(4) and d["q3"] == pytest.approx(5.5) and d["iqr"] == pytest.approx(1.5)
    assert d["cv"] == pytest.approx(np.std(x, ddof=1) / 5)
    assert d["skewness"] == pytest.approx(stats.skew(x, bias=False))


def test_describe_ignores_missing_values():
    assert S.describe(pd.Series([1, 2, np.nan, 3]))["n"] == 3


def test_cohens_d_known_value():
    a = np.array([10.0, 12, 14]); b = np.array([8.0, 10, 12])
    assert S.cohens_d(a, b) == pytest.approx(1.0)        # mean diff 2, pooled sd 2


def test_bootstrap_ci_contains_true_difference():
    rng = np.random.default_rng(0)
    a, b = rng.normal(5, 1, 400), rng.normal(4, 1, 400)
    lo, hi = S.boot_ci(lambda x, y: x.mean() - y.mean(), a, b, n=500)
    assert lo < 1.0 < hi and hi - lo < 0.4


def test_holm_correction_matches_statsmodels_and_is_monotone():
    p = np.array([0.001, 0.01, 0.03, 0.2])
    adj = multipletests(p, method="holm")[1]
    assert (adj >= p).all() and adj[0] == pytest.approx(0.004)
    assert (np.diff(adj[np.argsort(p)]) >= 0).all()


def test_mann_whitney_rank_biserial_sign_and_range():
    a, b = np.arange(10, 20), np.arange(0, 10)           # a stochastically larger
    mw = stats.mannwhitneyu(a, b)
    assert 1 - 2 * mw.statistic / (len(a) * len(b)) == pytest.approx(-1.0)  # U=n1*n2 -> r=-1 under this convention


def test_p_value_formatting_helper_never_returns_zero_string():
    from backend.analytics.store import _clean as c
    assert c(float("nan")) is None and c(np.float64("inf")) is None and c(np.int64(3)) == 3


def test_parse_perf_handles_times_distances_and_flags():
    assert parse_perf("1:07.27") == (67.27, "s")
    assert parse_perf("2:12:11") == (2 * 3600 + 12 * 60 + 11, "s")
    assert parse_perf("9.58 WR") == (9.58, "number")
    assert parse_perf("10.2 (1)") == (10.2, "number")
    assert parse_perf("2,616") == (2616.0, "number")
    assert parse_perf("DNS") == (None, None) and parse_perf(None) == (None, None) and parse_perf(float("nan")) == (None, None)


def test_direction_of_improvement_rules():
    assert lower_is_better("Athletics", "100 metres, Men", "number")
    assert not lower_is_better("Athletics", "Long Jump, Men", "number")
    assert not lower_is_better("Athletics", "Decathlon, Men", "number")
    assert lower_is_better("Swimming", "100 metres Freestyle, Men", "number")
    assert lower_is_better("Speed Skating", "500 metres, Men", "s")


def test_json_cleaner_handles_numpy_and_frames():
    out = _clean({"a": np.array([1, np.nan]), "b": pd.DataFrame({"x": [1]}), "c": np.bool_(True), "d": (1, 2)})
    assert out == {"a": [1, None], "b": [{"x": 1}], "c": True, "d": [1, 2]}


def test_regression_recovers_known_slope():
    import statsmodels.formula.api as smf
    rng = np.random.default_rng(1)
    x = rng.normal(size=500); y = 2.5 * x + rng.normal(scale=0.5, size=500)
    m = smf.ols("y ~ x", pd.DataFrame({"x": x, "y": y})).fit()
    assert m.params["x"] == pytest.approx(2.5, abs=0.1) and m.pvalues["x"] < 1e-10


def test_negative_binomial_detects_overdispersion_that_poisson_misses():
    import statsmodels.api as sm
    rng = np.random.default_rng(2)
    mu = np.exp(1 + 0.5 * rng.normal(size=1500))
    y = rng.negative_binomial(2, 2 / (2 + mu))            # variance >> mean
    pois = sm.GLM(y, np.ones_like(y), family=sm.families.Poisson()).fit()
    assert pois.pearson_chi2 / pois.df_resid > 1.5


def test_change_point_logic_finds_a_step():
    y = np.r_[np.full(8, 1.0), np.full(8, 5.0)] + np.random.default_rng(3).normal(scale=0.1, size=16)
    best = min(((((y[:k] - y[:k].mean()) ** 2).sum() + ((y[k:] - y[k:].mean()) ** 2).sum(), k) for k in range(3, 14)))
    assert best[1] == 8
