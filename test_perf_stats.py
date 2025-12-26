import unittest
import time
import threading
import os
import tempfile
from perf_stats import PerfStats, PerfTimer

class TestPerfStats(unittest.TestCase):
    def setUp(self):
        self.stats = PerfStats.get_instance()
        self.stats.init()

    def test_singleton(self):
        s1 = PerfStats.get_instance()
        s2 = PerfStats()
        self.assertIs(s1, s2)

    def test_record_value_manual(self):
        # 模拟数据：1, 2, 3, 10
        # Count=4, Min=1, Max=10
        # Avg Raw = (1+2+3+10)/4 = 4.0
        # Avg Filtered = (2+3)/2 = 2.5
        values = [0.001, 0.002, 0.003, 0.010]
        for v in values:
            self.stats.record_value("TestCat", "ManualTag", v)
        
        res = self.stats.get_stats("TestCat")["ManualTag"]
        self.assertEqual(res["count"], 4)
        self.assertAlmostEqual(res["min"], 0.001)
        self.assertAlmostEqual(res["max"], 0.010)
        self.assertAlmostEqual(res["avg_raw"], 0.004)
        self.assertAlmostEqual(res["avg_filtered"], 0.0025)

    def test_timer_context(self):
        with PerfTimer("TestCat", "TimerTag"):
            time.sleep(0.01)
        
        res = self.stats.get_stats("TestCat")["TimerTag"]
        self.assertEqual(res["count"], 1)
        self.assertTrue(res["min"] >= 0.01)

    def test_small_sample_size(self):
        # Count=2，无法去掉最大最小，应直接返回平均
        values = [0.01, 0.02]
        for v in values:
            self.stats.record_value("TestCat", "SmallTag", v)
            
        res = self.stats.get_stats("TestCat")["SmallTag"]
        self.assertEqual(res["count"], 2)
        self.assertAlmostEqual(res["avg_filtered"], 0.015)

    def test_multithread_safety(self):
        def worker():
            for _ in range(100):
                with PerfTimer("ThreadCat", "ThreadTag"):
                    time.sleep(0.0001)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        res = self.stats.get_stats("ThreadCat")["ThreadTag"]
        self.assertEqual(res["count"], 500)

    def test_save_stats(self):
        self.stats.record_value("FileCat", "FileTag", 0.123)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp_path = tmp.name
        
        try:
            self.stats.save_stats(tmp_path)
            
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            print(f"File content:\n{content}")
            
            self.assertIn("Category", content)
            self.assertIn("FileCat", content)
            self.assertIn("FileTag", content)
            self.assertIn("123.000", content) # 0.123s = 123ms
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == "__main__":
    unittest.main()
