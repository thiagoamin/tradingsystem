import math

from allocation import ExponentialUtility, LogUtility, MeanVarianceUtility


def test_mean_variance_utility_formula():
    u = MeanVarianceUtility(risk_aversion=2.0)
    score = u.evaluate(expected_return=0.03, volatility=0.10)
    assert abs(score - 0.02) < 1e-12


def test_log_utility_handles_extreme_negative_return():
    u = LogUtility(risk_aversion=1.0)
    assert u.evaluate(expected_return=-1.1, volatility=0.2) == -float("inf")


def test_exponential_utility_risk_neutral_case():
    u = ExponentialUtility(risk_aversion=0.0)
    assert math.isclose(u.evaluate(expected_return=0.015, volatility=0.5), 0.015)
