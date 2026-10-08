import os
import unittest
from unittest.mock import patch, Mock

import pandas as pd
from fastapi.testclient import TestClient

import api


class BotTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"CLIQ_API_KEY": "test-secret", "STREAMLIT_APP_URL": ""})
        self.environment.start()
        self.client = TestClient(api.app)
        self.headers = {"X-API-Key": "test-secret"}

    def tearDown(self):
        self.environment.stop()

    def send(self, message):
        return self.client.post("/chat", json={"message": message}, headers=self.headers)

    def test_authentication_and_help(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.post("/chat", json={"message": "help"}).status_code, 401)
        self.assertEqual(self.client.post("/chat", json={"message": "help"}, headers={"X-API-Key": "wrong"}).status_code, 401)
        with patch.dict(os.environ, {"CLIQ_API_KEY": ""}):
            self.assertEqual(self.send("help").status_code, 503)
        self.assertIn("Commands:", self.send("help").json()["text"])
        self.assertIn("Commands:", self.send("fda ").json()["text"])
        self.assertEqual(self.send("x" * 501).status_code, 422)

    @patch("api.requests.get")
    def test_fda_bounded_search_and_applicant(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {"meta": {"results": {"total": 101}}, "results": [{"k_number": "K123456", "device_name": "Catheter", "applicant": "Abbott", "decision_date": "20260101"}]}
        get.return_value = response
        result = self.send("fda catheter | Abbott").json()
        self.assertEqual(result["total"], 101)
        self.assertIn("K123456", result["text"])
        self.assertEqual(get.call_args.kwargs["params"]["limit"], 5)
        self.assertEqual(get.call_args.kwargs["params"]["search"], 'device_name:"catheter" AND applicant:"Abbott"')

    @patch("api.requests.get")
    def test_fda_no_matches_and_errors(self, get):
        response = Mock(status_code=404)
        response.json.return_value = {"error": {"code": "NOT_FOUND"}}
        get.return_value = response
        self.assertEqual(self.send("fda xyz").json()["total"], 0)
        get.side_effect = api.requests.Timeout()
        self.assertIn("temporarily unavailable", self.send("fda xyz").json()["text"])

    @patch("api.load_database")
    def test_cdsco_role_and_all_word_filters(self, load):
        load.return_value = pd.DataFrame([
            {"devicename": "Balloon catheter", "role": "Manufacturer", "address": "Company A", "str_licence_no": "L1"},
            {"devicename": "Balloon catheter", "role": "Importer", "address": "Company B", "str_licence_no": "L2"},
            {"devicename": "Other catheter", "role": "Manufacturer", "address": "Company C"}
        ])
        result = self.send("manufacturer balloon catheter").json()
        self.assertEqual(result["total"], 1)
        self.assertIn("Company A", result["text"])
        self.assertNotIn("Company B", result["text"])
        self.assertNotIn("Company C", result["text"])
        self.assertIn("Company B", self.send("importer balloon").json()["text"])

    @patch("api.load_database")
    def test_risk_and_missing_schema(self, load):
        load.return_value = pd.DataFrame([{"medical_device_name": "Diode laser", "risk_classification_under_mdr_2017": "C", "intended_use": "Surgery"}])
        self.assertIn("Risk class: C", self.send("risk diode laser").json()["text"])
        self.assertEqual(self.send("risk unknown").json()["total"], 0)
        load.return_value = pd.DataFrame({"unexpected": ["value"]})
        self.assertEqual(self.send("risk laser").status_code, 503)


if __name__ == "__main__":
    unittest.main()
