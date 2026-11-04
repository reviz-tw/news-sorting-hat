import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate import ValidationError, load_json, validate


class PositionTests(unittest.TestCase):
    def setUp(self):
        self.a = load_json(ROOT / "examples/positions-over-time.analysis.json")

    def invalid(self, message):
        with self.assertRaisesRegex(ValidationError, message):
            validate(self.a, require_structure=True)

    def test_temporal_fixture(self):
        validate(self.a, load_json(ROOT / "examples/positions-over-time.input.json"), require_structure=True)

    def test_cross_stakeholder_comparison(self):
        self.a["evidence"][1]["position"].update(stakeholder_id="other", stakeholder_name="其他協會")
        self.invalid("mixes stakeholders")

    def test_cross_issue_comparison(self):
        self.a["evidence"][1]["position"].update(issue_id="other", issue="不同方案")
        self.invalid("mixes stakeholders or issues")

    def test_ambiguous_identity(self):
        self.a["evidence"][1]["position"]["stakeholder_name"] = "另一機構"
        self.invalid("label differs")

    def test_unknown_date_cannot_prove_change(self):
        self.a["evidence"][0]["position"]["statement_date"] = None
        self.invalid("known statement dates")
        self.a["evidence"][2]["assessment"] = "insufficient"
        validate(self.a, require_structure=True)

    def test_date_precision_cannot_invent_order(self):
        self.a["evidence"][0]["position"]["statement_date"] = "2024"
        self.invalid("non-overlapping date precision")

    def test_reverse_chronology(self):
        self.a["evidence"][2]["claim_ids"].reverse()
        self.invalid("chronological")

    def test_one_statement_cannot_make_comparison(self):
        self.a["evidence"][2]["claim_ids"].pop()
        self.invalid("too few items")

    def test_source_chain_retained(self):
        self.a["evidence"][2]["refs"].pop()
        self.invalid("retain claim sources")

    def test_evolution_role_must_be_accounted_for(self):
        self.a["article_structure"]["nodes"][0]["roles"].pop()
        self.invalid("every selected template slot")


if __name__ == "__main__":
    unittest.main()
