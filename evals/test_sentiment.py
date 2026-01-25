"""Evaluation tests for sentiment analysis."""
import json
import os
import pytest
from pathlib import Path

# Skip if no API key (for CI environments)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
skip_no_api_key = pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set"
)


class TestSentimentAnalysis:
    """Tests for sentiment analysis accuracy."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        from src.agent.analysis import analyze_sentiment
        self.analyze_sentiment = analyze_sentiment

    @skip_no_api_key
    def test_negative_sentiment_angry(self):
        """Test detection of angry negative sentiment."""
        messages = [{"role": "customer", "content": "This is terrible! I've been waiting for weeks!"}]
        result = self.analyze_sentiment(messages)

        assert result["label"] == "negative", f"Expected negative, got {result['label']}"
        assert result["score"] < 0, f"Expected negative score, got {result['score']}"

    @skip_no_api_key
    def test_negative_sentiment_caps(self):
        """Test detection of negative sentiment with caps."""
        messages = [{"role": "customer", "content": "I WANT A REFUND NOW!!!"}]
        result = self.analyze_sentiment(messages)

        assert result["label"] == "negative", f"Expected negative, got {result['label']}"
        assert result["score"] < -0.3, f"Expected strongly negative score, got {result['score']}"

    @skip_no_api_key
    def test_positive_sentiment_grateful(self):
        """Test detection of positive grateful sentiment."""
        messages = [{"role": "customer", "content": "Thank you so much! You've been incredibly helpful!"}]
        result = self.analyze_sentiment(messages)

        assert result["label"] == "positive", f"Expected positive, got {result['label']}"
        assert result["score"] > 0, f"Expected positive score, got {result['score']}"

    @skip_no_api_key
    def test_positive_sentiment_satisfied(self):
        """Test detection of satisfied positive sentiment."""
        messages = [{"role": "customer", "content": "Great service, I'm very satisfied with the resolution."}]
        result = self.analyze_sentiment(messages)

        assert result["label"] == "positive", f"Expected positive, got {result['label']}"
        assert result["score"] > 0.3, f"Expected strongly positive score, got {result['score']}"

    @skip_no_api_key
    def test_neutral_sentiment_inquiry(self):
        """Test detection of neutral inquiry."""
        messages = [{"role": "customer", "content": "Can you check the status of my order?"}]
        result = self.analyze_sentiment(messages)

        assert result["label"] == "neutral", f"Expected neutral, got {result['label']}"
        assert -0.4 <= result["score"] <= 0.4, f"Expected neutral score, got {result['score']}"

    @skip_no_api_key
    def test_neutral_sentiment_info_request(self):
        """Test detection of neutral information request."""
        messages = [{"role": "customer", "content": "I'd like to know about your return policy."}]
        result = self.analyze_sentiment(messages)

        assert result["label"] == "neutral", f"Expected neutral, got {result['label']}"
        assert -0.4 <= result["score"] <= 0.4, f"Expected neutral score, got {result['score']}"

    @skip_no_api_key
    def test_multi_turn_sentiment_positive_resolution(self):
        """Test sentiment detection in multi-turn conversation with positive resolution."""
        messages = [
            {"role": "customer", "content": "This is frustrating."},
            {"role": "ai", "content": "I understand. Let me help."},
            {"role": "customer", "content": "Thank you, that's much better now!"},
        ]
        result = self.analyze_sentiment(messages)

        # Should detect the most recent positive sentiment
        assert result["label"] == "positive", f"Expected positive (recent message), got {result['label']}"

    @skip_no_api_key
    def test_multi_turn_sentiment_degraded(self):
        """Test sentiment detection when sentiment degrades during conversation."""
        messages = [
            {"role": "customer", "content": "Hi, I need help with my order."},
            {"role": "ai", "content": "Sure, what's the issue?"},
            {"role": "customer", "content": "It's been 3 weeks and nothing! This is unacceptable!"},
        ]
        result = self.analyze_sentiment(messages)

        # Should detect the degraded negative sentiment
        assert result["label"] == "negative", f"Expected negative (degraded), got {result['label']}"

    def test_empty_messages(self):
        """Test handling of empty messages."""
        result = self.analyze_sentiment([])

        assert result["label"] == "neutral"
        assert result["score"] == 0.0
        assert result["confidence"] == 0.5

    def test_no_customer_messages(self):
        """Test handling when no customer messages present."""
        messages = [{"role": "ai", "content": "How can I help you?"}]
        result = self.analyze_sentiment(messages)

        assert result["label"] == "neutral"
        assert result["score"] == 0.0

    @skip_no_api_key
    def test_confidence_score(self):
        """Test that confidence score is within valid range."""
        messages = [{"role": "customer", "content": "I'm very happy with this!"}]
        result = self.analyze_sentiment(messages)

        assert 0.0 <= result["confidence"] <= 1.0, f"Confidence out of range: {result['confidence']}"


class TestSentimentDataset:
    """Run evals against the full sentiment dataset."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Load test dataset."""
        dataset_path = Path(__file__).parent / "datasets" / "sentiment_cases.json"
        with open(dataset_path) as f:
            self.dataset = json.load(f)
        from src.agent.analysis import analyze_sentiment
        self.analyze_sentiment = analyze_sentiment

    @skip_no_api_key
    @pytest.mark.parametrize("case_id", [
        "neg_001", "neg_002", "neg_003", "neg_004", "neg_005",
    ])
    def test_negative_cases(self, case_id):
        """Test negative sentiment cases from dataset."""
        case = next(c for c in self.dataset["cases"] if c["id"] == case_id)
        result = self.analyze_sentiment(case["messages"])

        assert result["label"] == case["expected_label"], \
            f"Case {case_id}: Expected {case['expected_label']}, got {result['label']}"

        min_score, max_score = case["expected_score_range"]
        assert min_score <= result["score"] <= max_score, \
            f"Case {case_id}: Score {result['score']} not in range [{min_score}, {max_score}]"

    @skip_no_api_key
    @pytest.mark.parametrize("case_id", [
        "pos_001", "pos_002", "pos_003", "pos_004", "pos_005",
    ])
    def test_positive_cases(self, case_id):
        """Test positive sentiment cases from dataset."""
        case = next(c for c in self.dataset["cases"] if c["id"] == case_id)
        result = self.analyze_sentiment(case["messages"])

        assert result["label"] == case["expected_label"], \
            f"Case {case_id}: Expected {case['expected_label']}, got {result['label']}"

        min_score, max_score = case["expected_score_range"]
        assert min_score <= result["score"] <= max_score, \
            f"Case {case_id}: Score {result['score']} not in range [{min_score}, {max_score}]"

    @skip_no_api_key
    @pytest.mark.parametrize("case_id", [
        "neu_001", "neu_002", "neu_003", "neu_004", "neu_005",
    ])
    def test_neutral_cases(self, case_id):
        """Test neutral sentiment cases from dataset."""
        case = next(c for c in self.dataset["cases"] if c["id"] == case_id)
        result = self.analyze_sentiment(case["messages"])

        assert result["label"] == case["expected_label"], \
            f"Case {case_id}: Expected {case['expected_label']}, got {result['label']}"

    @skip_no_api_key
    @pytest.mark.parametrize("case_id", [
        "multi_001", "multi_002",
    ])
    def test_multi_turn_cases(self, case_id):
        """Test multi-turn conversation cases from dataset."""
        case = next(c for c in self.dataset["cases"] if c["id"] == case_id)
        result = self.analyze_sentiment(case["messages"])

        assert result["label"] == case["expected_label"], \
            f"Case {case_id}: Expected {case['expected_label']}, got {result['label']}"

    @skip_no_api_key
    def test_overall_accuracy(self):
        """Test overall accuracy across the entire dataset."""
        correct = 0
        total = 0
        failures = []

        for case in self.dataset["cases"]:
            if "edge_case" in case.get("tags", []):
                continue  # Skip edge cases for accuracy calculation

            result = self.analyze_sentiment(case["messages"])
            total += 1

            if result["label"] == case["expected_label"]:
                correct += 1
            else:
                failures.append({
                    "id": case["id"],
                    "expected": case["expected_label"],
                    "got": result["label"],
                    "score": result["score"],
                })

        accuracy = correct / total if total > 0 else 0
        print(f"\nSentiment Accuracy: {accuracy:.1%} ({correct}/{total})")

        if failures:
            print(f"Failures: {json.dumps(failures, indent=2)}")

        # Expect at least 80% accuracy
        assert accuracy >= 0.8, f"Accuracy {accuracy:.1%} below threshold of 80%"
