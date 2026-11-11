import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate import SCHEMAS, ValidationError, load_json, schema_validate, validate
from workflow import COMMON_FIELDS, build, compile_block, component_files, load_component, resolve


def example(name):
    return load_json(ROOT / "examples" / (name + ".json"))


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.selection = example("mixed-policy.classification")
        self.rag = example("mixed-policy.input")
        self.analysis = example("mixed-policy.analysis")
        self.plan = example("mixed-policy.modules")

    def build(self):
        return build(self.selection, self.rag, self.analysis, self.plan)

    def test_classification_handoff(self):
        validate(self.selection)
        context = resolve(self.selection)
        self.assertEqual([p["type"] for p in context["profiles"]], ["policy_evaluation", "data_analysis"])
        for profile in context["profiles"]:
            for slot in profile["slots"]:
                for m in slot["presentation_modules"]:
                    self.assertIn(m["module_id"], context["modules"])
        self.assertEqual(self.build(), example("mixed-policy.presentation"))

    def test_resolve_preserves_slot_order_and_specific_conditions(self):
        context = resolve(dict(status="determined", primary="claim_verification", secondary=[]))
        slots = {s["id"]: s["presentation_modules"] for s in context["profiles"][0]["slots"]}
        self.assertEqual([m["module_id"] for m in slots["event_background"]], ["text", "timeline"])
        self.assertIn("不把待查說法內容畫成已確認事件", slots["event_background"][1]["use_when"])
        self.assertEqual(slots["evidence_check"][2]["use_when"], context["modules"]["timeline"]["use_when"])
        mixed = resolve(self.selection)
        self.assertTrue(mixed["profiles"][1]["presentation_hints"])

    def test_classification_only_rejects_content_unknown_ids_and_contradictions(self):
        for change in ({"summary": "正文"}, {"primary": "../secrets"}, {"status": "undetermined"},
                       {"primary": None}, {"secondary": ["policy_evaluation"]},
                       {"secondary": ["data_analysis", "data_analysis"]}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                resolve({**self.selection, **change})

    def test_fallback_and_tentative(self):
        context = resolve(dict(primary=None, secondary=[], status="undetermined"))
        self.assertEqual([p["type"] for p in context["profiles"]], ["unclassified"])
        self.assertEqual(list(context["modules"]), ["text"])
        tentative = dict(self.selection, status="tentative")
        self.assertEqual(resolve(tentative)["classification"], tentative)

    def test_requires_original_classification_and_sources(self):
        self.selection["status"] = "tentative"
        with self.assertRaisesRegex(ValidationError, "changed classification"):
            self.build()
        self.selection["status"] = "determined"
        self.rag["question"] = "其他問題"
        with self.assertRaisesRegex(ValidationError, "changed input question"):
            self.build()

    def test_rejects_invalid_plan_at_each_boundary(self):
        for change in ({"module_id": "photo"}, {"module_id": "unknown"},
                       {"data": {"body": "偽造"}}, {"section_ids": ["unknown"]}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                build(self.selection, self.rag, self.analysis,
                      {"modules": [{**self.plan["modules"][0], **change}]})
        chart = next(m for m in self.plan["modules"] if m["module_id"] == "bar_chart")
        chart["evidence_ids"] = ["goal"]
        with self.assertRaisesRegex(ValidationError, "not cited"):
            self.build()

    def test_component_file_examples_match_both_contracts(self):
        files = component_files()
        for name in files:
            with self.subTest(component=name):
                contract = load_component(name, files)
                if contract["availability"] == "planning_only":
                    for key in ("input_schema", "frontend_schema"):
                        with self.assertRaises(ValidationError):
                            schema_validate({}, contract[key], SCHEMAS / files[name])
                    continue
                pair = contract["example"]
                self.assertEqual(pair["input"]["module_id"], name)
                self.assertEqual(pair["output"]["type"], contract["block_type"])
                schema_validate(pair["input"], contract["input_schema"], SCHEMAS / files[name])
                schema_validate(pair["output"], contract["frontend_schema"], SCHEMAS / files[name])
                self.assertEqual({k: pair["input"][k] for k in COMMON_FIELDS},
                                 {k: pair["output"][k] for k in COMMON_FIELDS})

    def test_all_supported_module_inputs_compile_to_declared_blocks(self):
        files = component_files()
        contracts = {name: load_component(name, files) for name in files}
        covered = set()
        for fixture in ("visualization-gallery", "air-quality", "mixed-policy"):
            doc = example(fixture + ".presentation")
            sections = {s["id"]: s for s in doc["analysis"]["sections"]}
            evidence = {e["id"]: e for e in doc["analysis"]["evidence"]}
            for block in doc["blocks"]:
                name = block["type"]
                data = {k: v for k, v in block.items() if k not in (*COMMON_FIELDS, "type")}
                if name == "text":
                    data = {}
                elif name in ("bar_chart", "line_chart"):
                    data = {"measurement_ids": [p["evidence_id"] for p in block["points"]]}
                item = {"module_id": name, "data": data, **{k: block[k] for k in COMMON_FIELDS}}
                self.assertEqual(compile_block(item, contracts[name], sections, evidence), block)
                covered.add(name)

        # Exercise the three formats without checked-in presentation fixtures.
        section = self.analysis["sections"][0]
        events = [{"id": "opened", "kind": "event", "date": "2024", "text": "開放"},
                  {"id": "closed", "kind": "event", "date": "2025", "text": "結束"}]
        refs = self.analysis["evidence"][0]["refs"]
        quote_text = self.analysis["sources"][0]["chunks"][0]["text"]
        extra = [*events, {"id": "said", "kind": "claim", "verbatim": True,
                           "speaker": "示例", "text": quote_text}]
        section["evidence_ids"].extend(e["id"] for e in extra)
        self.plan["modules"][0]["evidence_ids"] = section["evidence_ids"]
        self.analysis["evidence"].extend({**e, "refs": refs} for e in extra)
        cell = {"text": "開放", "evidence_ids": ["opened"]}
        for name, data in (("quote", {"evidence_id": "said"}),
                           ("timeline", {"event_ids": ["opened", "closed"]}),
                           ("table", {"columns": ["事項", "紀錄"], "rows": [[cell, cell]]})):
            self.plan["modules"].append({**self.plan["modules"][0], "id": name, "module_id": name,
                                         "data": data, "decision": "text_sufficient" if name == "quote"
                                         else "visual_selected"})
            covered.add(name)
        self.assertEqual(self.build()["blocks"][-2]["events"][0],
                         {"date": "2024", "text": "開放", "evidence_id": "opened"})
        self.assertEqual(covered, {k for k, c in contracts.items() if c["availability"] == "supported"})


if __name__ == "__main__":
    unittest.main()
