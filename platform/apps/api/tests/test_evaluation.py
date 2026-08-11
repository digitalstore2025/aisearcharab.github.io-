from scripts.evaluate_search import evaluate


def test_golden_dataset_thresholds() -> None:
    metrics = evaluate()
    assert metrics["mrr"] >= 0.85
    assert metrics["recall_at_5"] == 1.0
