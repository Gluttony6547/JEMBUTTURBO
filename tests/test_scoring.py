import unittest

from jempol_turbo.scoring import compute_metrics, ranking_key


class ScoringTests(unittest.TestCase):
    def test_metrics_for_complete_text(self):
        metrics = compute_metrics("hello world", "hello world", 12.0)
        self.assertTrue(metrics.finished)
        self.assertEqual(metrics.progress, 1.0)
        self.assertEqual(metrics.accuracy, 100.0)
        self.assertGreater(metrics.wpm, 0)
        self.assertGreaterEqual(metrics.score, 25)

    def test_metrics_for_typo(self):
        metrics = compute_metrics("abcde", "abxde", 10.0)
        self.assertFalse(metrics.finished)
        self.assertEqual(metrics.correct_chars, 4)
        self.assertEqual(metrics.accuracy, 80.0)

    def test_finished_player_ranks_first(self):
        finished = {"finished": True, "finish_time": 10.0, "wpm": 50, "accuracy": 90, "score": 70}
        unfinished = {"finished": False, "finish_time": None, "wpm": 80, "accuracy": 100, "score": 80}
        ranked = sorted([unfinished, finished], key=ranking_key, reverse=True)
        self.assertIs(ranked[0], finished)


if __name__ == "__main__":
    unittest.main()
