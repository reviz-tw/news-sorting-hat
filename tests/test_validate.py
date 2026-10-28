import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate import ValidationError, check_schema, load_json, validate

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.input = load_json(EXAMPLES / "air-quality.input.json")
        self.doc = load_json(EXAMPLES / "air-quality.presentation.json")

    def invalid(self, pattern=None):
        with self.assertRaisesRegex(ValidationError, pattern or "."):
            validate(self.doc, self.input)

    def test_all_examples(self):
        for name in ("event-brief", "air-quality", "incomplete-air-quality"):
            rag = load_json(EXAMPLES / (name + ".input.json"))
            analysis = load_json(EXAMPLES / (name + ".analysis.json"))
            presentation = load_json(EXAMPLES / (name + ".presentation.json"))
            with self.subTest(name=name):
                validate(rag)
                validate(analysis, rag)
                validate(presentation, rag, analysis)

    def test_unknown_component(self):
        self.doc["blocks"][1]["type"] = "arbitrary_html"
        self.invalid()

    def test_extra_property(self):
        self.doc["blocks"][0]["script"] = "alert(1)"
        self.invalid("unexpected fields")

    def test_wrong_version(self):
        self.doc["schema_version"] = "9.0.0"
        self.invalid("wrong constant")

    def test_missing_field(self):
        del self.doc["blocks"][1]["unit"]
        self.invalid("missing required")

    def test_duplicate_evidence_id(self):
        self.doc["analysis"]["evidence"][1]["id"] = "m2020"
        self.invalid("Duplicate evidence")

    def test_unknown_chunk(self):
        self.doc["analysis"]["evidence"][0]["refs"][0]["chunk_id"] = "missing"
        self.invalid("unknown source/chunk")

    def test_changed_source(self):
        self.doc["analysis"]["sources"][0]["chunks"][0]["text"] = "替換原文"
        self.invalid("changed input sources")

    def test_changed_question(self):
        self.doc["analysis"]["question"] = "另一個問題"
        self.invalid("changed input question")

    def test_stage_two_cannot_change_analysis(self):
        expected = copy.deepcopy(self.doc["analysis"])
        self.doc["analysis"]["title"] = "修改標題"
        with self.assertRaisesRegex(ValidationError, "changed first-stage"):
            validate(self.doc, self.input, expected)

    def test_primary_not_secondary(self):
        self.doc["analysis"]["classification"]["secondary"] = ["data_analysis"]
        self.invalid("Primary repeated")

    def test_undetermined_classification(self):
        cls = self.doc["analysis"]["classification"]
        cls["status"] = "undetermined"
        self.invalid("status and primary")
        cls["primary"] = None
        validate(self.doc, self.input)

    def test_unknown_section_evidence(self):
        self.doc["analysis"]["sections"][0]["evidence_ids"].append("missing")
        self.invalid("unknown evidence ID")

    def test_chart_cannot_invent_number(self):
        self.doc["blocks"][1]["points"][0]["value"] = 99
        self.invalid("chart value differs")

    def test_boolean_is_not_number(self):
        self.doc["blocks"][1]["points"][0]["value"] = True
        self.invalid("wrong type")

    def test_non_finite_number(self):
        self.doc["blocks"][1]["points"][0]["value"] = float("inf")
        self.invalid("wrong type")

    def test_mixed_metrics(self):
        self.doc["analysis"]["evidence"][1]["metric"] = "AQI"
        self.invalid("incomparable metric")

    def test_mixed_statistic(self):
        self.doc["analysis"]["evidence"][1]["statistic"] = "單日尖峰"
        self.invalid("incomparable statistic")

    def test_missing_year_cannot_be_connected(self):
        self.doc["blocks"][1]["points"].pop(2)
        self.invalid("missing periods")

    def test_sourced_null_is_valid_but_needs_note(self):
        self.doc["analysis"]["evidence"][2]["value"] = None
        self.doc["blocks"][1]["points"][2]["value"] = None
        self.doc["blocks"][1]["notes"] = ["來源明確標記此年缺值；斷線呈現。"]
        validate(self.doc, self.input)
        self.doc["blocks"][1]["notes"] = []
        self.invalid("missing data must be explained")

    def test_not_enough_real_points(self):
        for i in range(3):
            self.doc["analysis"]["evidence"][i]["value"] = None
            self.doc["blocks"][1]["points"][i]["value"] = None
        self.invalid("not enough non-null")

    def test_preserve_complete_text(self):
        self.doc["blocks"][0]["body"] = "只剩摘要"
        self.invalid("preserve section")

    def test_no_text_coverage(self):
        self.doc["blocks"].pop(0)
        self.invalid("Every section")

    def test_visual_decision_must_match(self):
        self.doc["blocks"][1]["decision"] = "text_sufficient"
        self.invalid("invalid decision")

    def test_invalid_calendar_date(self):
        self.doc["analysis"]["evidence"][0]["period"] = "2024-02-30"
        self.invalid("calendar date")

    def test_unsafe_source_url(self):
        self.doc["analysis"]["sources"][0]["url"] = "javascript:alert(1)"
        self.invalid("Unsafe")

    def test_invalid_input_kind(self):
        with self.assertRaisesRegex(ValidationError, "Unknown document"):
            validate({"kind": "unknown"})

    def test_no_evidence_answer(self):
        a = self.doc["analysis"]
        a["status"] = "insufficient"
        a["evidence"] = []
        a["sources"] = []
        a["classification"].update(status="undetermined", primary=None, evidence_ids=[])
        a["sections"][0]["evidence_ids"] = []
        a["limitations"] = [{"code": "missing_data", "text": "沒有檢索到來源。", "evidence_ids": []}]
        self.doc["blocks"] = self.doc["blocks"][:1]
        self.doc["blocks"][0].update(evidence_ids=[], decision="insufficient_data")
        validate(self.doc)

    def test_inference_cycle(self):
        a = self.doc["analysis"]
        a["evidence"].extend([
            {"id": "i1", "kind": "inference", "text": "推論一", "refs": a["evidence"][0]["refs"], "based_on": ["i2"]},
            {"id": "i2", "kind": "inference", "text": "推論二", "refs": a["evidence"][0]["refs"], "based_on": ["i1"]},
        ])
        self.invalid("dependency cycle")

    def test_table_cells_and_width(self):
        block = {k: copy.deepcopy(v) for k, v in self.doc["blocks"][1].items()
                 if k in ("id", "title", "section_ids", "evidence_ids", "decision", "decision_reason", "notes")}
        block.update(type="table", columns=["年", "數值"], rows=[[
            {"text": "2020", "evidence_ids": ["m2020"]}, {"text": "20", "evidence_ids": ["m2020"]}]])
        self.doc["blocks"][1] = block
        validate(self.doc, self.input)
        block["rows"][0][0]["evidence_ids"] = ["unknown"]
        self.invalid("cell evidence")
        block["rows"][0][0]["evidence_ids"] = ["m2020"]
        block["rows"][0].append(copy.deepcopy(block["rows"][0][0]))
        self.invalid("width mismatch")

    def test_bar_chart_common_period(self):
        chart = self.doc["blocks"][1]
        chart.update(type="bar_chart", zero_baseline=True)
        for i, (point, item) in enumerate(zip(chart["points"], self.doc["analysis"]["evidence"])):
            point["x"] = item["category"] = "類別" + str(i)
            item["period"] = "2024"
        validate(self.doc, self.input)
        self.doc["analysis"]["evidence"][0]["period"] = "2023"
        self.invalid("periods differ")

    def test_timeline(self):
        evidence = self.doc["analysis"]["evidence"]
        for item in evidence:
            item["kind"] = "event"
            item["date"] = item.pop("period")
            for key in ("metric", "unit", "region", "statistic", "category", "value"):
                del item[key]
        block = self.doc["blocks"][1]
        for key in ("metric", "unit", "region", "statistic", "points"):
            del block[key]
        block.update(type="timeline", events=[{"date": e["date"], "text": e["text"], "evidence_id": e["id"]} for e in evidence])
        validate(self.doc, self.input)
        block["events"].reverse()
        self.invalid("not chronological")

    def test_quote_must_be_verbatim(self):
        a = self.doc["analysis"]
        quote = {"id": "q", "kind": "claim", "speaker": "合成資料", "verbatim": True,
                 "text": "非實測新聞數據", "refs": [{"source_id": "s1", "chunk_id": "c1"}]}
        a["evidence"].append(quote)
        a["sections"][0]["evidence_ids"].append("q")
        # Fixtures are loaded independently, so update the text block citation too.
        self.doc["blocks"][0]["evidence_ids"].append("q")
        base = self.doc["blocks"][0]
        block = {k: copy.deepcopy(v) for k, v in base.items() if k not in ("body",)}
        block.update(id="quote", type="quote", evidence_ids=["q"], evidence_id="q")
        self.doc["blocks"] = [base, block]
        validate(self.doc, self.input)
        quote["text"] = "來源沒有說過這句話"
        self.invalid("verbatim quote missing")

    def test_unsupported_schema_keyword_fails_closed(self):
        with self.assertRaisesRegex(ValidationError, "Unsupported"):
            check_schema({"properties": {"unused": {"maximum": 2}}})

    def test_duplicate_json_keys_and_nan_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            for raw in ('{"kind":"analysis","kind":"presentation"}', '{"x":NaN}'):
                path.write_text(raw)
                with self.subTest(raw=raw), self.assertRaises(ValidationError):
                    load_json(path)


if __name__ == "__main__":
    unittest.main()
