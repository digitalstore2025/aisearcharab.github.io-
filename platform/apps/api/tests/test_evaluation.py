from scripts.evaluate_search import evaluate


def test_golden_dataset_thresholds() -> None:
    metrics = evaluate()
    assert metrics["mrr"] >= 0.85
    assert metrics["mrr_at_10"] >= 0.85
    assert metrics["ndcg_at_10"] >= 0.85
    assert metrics["recall_at_5"] == 1.0
    assert metrics["hit_rate_at_10"] == 1.0
    assert metrics["zero_result_rate"] == 0.0
