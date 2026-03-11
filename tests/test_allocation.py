from allocation import AssetEstimate, MeanVarianceUtility, UtilityAllocator


def test_utility_allocator_weights_and_cash_buffer():
    allocator = UtilityAllocator(
        utility=MeanVarianceUtility(risk_aversion=1.0),
        min_score=0.0,
        max_weight=0.6,
        cash_buffer=0.1,
    )

    estimates = [
        AssetEstimate(symbol="AAPL", expected_return=0.04, volatility=0.10),
        AssetEstimate(symbol="MSFT", expected_return=0.03, volatility=0.10),
    ]
    weights = allocator.target_weights(estimates)

    assert set(weights.keys()) == {"AAPL", "MSFT"}
    assert weights["AAPL"] <= 0.54  # 0.6 cap scaled by 0.9 investable
    assert abs(sum(weights.values()) - 0.9) < 1e-9


def test_utility_allocator_target_quantities():
    allocator = UtilityAllocator(
        utility=MeanVarianceUtility(risk_aversion=1.0),
        min_score=0.0,
        max_weight=1.0,
        cash_buffer=0.0,
    )

    estimates = [AssetEstimate(symbol="AAPL", expected_return=0.02, volatility=0.01)]
    qtys = allocator.target_quantities(
        estimates=estimates,
        prices={"AAPL": 100.0},
        equity=1_050.0,
    )
    assert qtys == {"AAPL": 10}


def test_utility_allocator_respects_single_asset_max_weight_cap():
    allocator = UtilityAllocator(
        utility=MeanVarianceUtility(risk_aversion=1.0),
        max_weight=0.25,
        cash_buffer=0.0,
    )
    weights = allocator.target_weights(
        [AssetEstimate(symbol="AAPL", expected_return=0.02, volatility=0.01)]
    )
    assert weights == {"AAPL": 0.25}
