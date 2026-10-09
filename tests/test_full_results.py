import csv
import io
import unittest
import tempfile
import threading
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from fastapi.testclient import TestClient

import api
import full_results as results


class CompleteResultsTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def test_real_parquet_scan_across_batches_preserves_all_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            df = pd.DataFrame([{"devicename": "laser ablation system", "role": "Manufacturer" if i % 2 == 0 else "Importer", "address": "Company", "str_licence_no": str(i)} for i in range(2100)])
            df.to_parquet(Path(directory) / "cdsco_approved_devices.parquet", row_group_size=700)
            with patch.object(api, "BASE_DIR", Path(directory)):
                answer = api.cdsco_search("manufacturer", "laser ablation system")
            self.assertEqual(answer["total"], 1050)
            token = answer["results_url"].rsplit("/", 1)[-1]
            content = self.client.get(f"/results/{token}/download").text.lstrip("\ufeff")
            rows = list(csv.DictReader(io.StringIO(content)))
            self.assertEqual(len(rows), 1050)
            self.assertEqual(rows[-1]["str_licence_no"], "2098")

    def test_slow_scan_returns_link_and_rejects_concurrent_scan(self):
        ready = threading.Event()
        done = threading.Event()
        def batches(filename):
            try:
                ready.wait(5)
                yield pd.DataFrame([{"medical_device_name": "laser"}])
            finally:
                done.set()
        with patch("api.load_database", side_effect=batches):
            try:
                answer = api.cdsco_search("risk", "laser")
                self.assertIsNone(answer["total"])
                self.assertIn("results_url", answer)
                self.assertIn("already running", api.cdsco_search("risk", "laser")["text"])
                request = api.ChatRequest(message="risk laser", user_id="pending-user", chat_id="pending-chat")
                api.remember_context(request, api.SearchPlan(action="search", tool="risk", device="laser"), answer)
                self.assertEqual(api.get_context(request)["results_url"], answer["results_url"])
            finally:
                ready.set()
                done.wait(5)
        # Wait until scan releases its admission slot before subsequent tests.
        self.assertTrue(api.CDSCO_SLOT.acquire(timeout=5))
        api.CDSCO_SLOT.release()

    def test_all_cdsco_rows_beyond_five_and_complete_csv(self):
        df = pd.DataFrame([{"medical_device_name": f"Laser {i}", "intended_use": "surgery", "risk_classification_under_mdr_2017": "C"} for i in range(120)])
        with patch("api.load_database", return_value=[df]):
            answer = api.cdsco_search("risk", "laser")
        token = answer["results_url"].rsplit("/", 1)[-1]
        first = self.client.get(f"/results/{token}/data").json()
        second = self.client.get(f"/results/{token}/data?offset=100").json()
        self.assertEqual(first["loaded"], 120)
        self.assertEqual(len(first["rows"]), 100)
        self.assertEqual(len(second["rows"]), 20)
        content = self.client.get(f"/results/{token}/download").text.lstrip("\ufeff")
        rows = list(csv.DictReader(io.StringIO(content)))
        self.assertEqual(len(rows), 120)
        self.assertEqual(rows[-1]["medical_device_name"], "Laser 119")
        self.assertEqual(self.client.get(f"/results/{token}").status_code, 200)

    @patch("full_results.requests.get")
    def test_fda_search_after_download_and_failure(self, get):
        token = results.save_results([{"k_number": "K1"}], 1)
        job = results.get_job(token)
        job["total"] = 3
        job["status"] = "loading"
        a = Mock()
        a.json.return_value = {"meta": {"results": {"total": 3}}, "results": [{"k_number": "K2"}]}
        a.links = {"next": {"url": "https://api.fda.gov/device/510k.json?search_after=second"}}
        b = Mock()
        b.json.return_value = {"meta": {"results": {"total": 3}}, "results": [{"k_number": "K3"}]}
        b.links = {}
        get.side_effect = [a, b]
        results.SLOTS.acquire()
        results.collect_fda(job, "https://api.fda.gov/device/510k.json?search_after=first")
        self.assertEqual(job["status"], "complete")
        self.assertIn("K3", self.client.get(f"/results/{token}/download").text)
        job["total"] = 4
        job["status"] = "loading"
        results.SLOTS.acquire()
        results.collect_fda(job, None)
        self.assertEqual(job["status"], "error")
        self.assertEqual(self.client.get(f"/results/{token}/download").status_code, 409)

    def test_private_tokens_expiry_and_csv_formula_protection(self):
        token = results.save_results([{"name": "=1+1", "nested": {"a": 1}}], 1)
        self.assertIn("'=1+1", self.client.get(f"/results/{token}/download").text)
        self.assertEqual(self.client.get("/results/unknown/data").status_code, 410)
        results.get_job(token)["created"] -= results.TTL + 1
        self.assertEqual(self.client.get(f"/results/{token}/data").status_code, 410)

    @patch("full_results.requests.get")
    def test_untrusted_pagination_url_is_rejected(self, get):
        token = results.save_results([], 0)
        job = results.get_job(token)
        job["total"] = 1
        results.SLOTS.acquire()
        results.collect_fda(job, "https://evil.example/device/510k.json")
        get.assert_not_called()
        self.assertEqual(job["status"], "error")


if __name__ == "__main__":
    unittest.main()
