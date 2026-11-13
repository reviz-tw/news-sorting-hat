import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prompts import TEMPLATES, build_prompt_request, build_slot_request, render_template
from scripts.validate import SCHEMAS, ValidationError, check_schema, load_json, schema_validate


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.rag = load_json(ROOT / "examples/mixed-policy.input.json")
        self.selection = load_json(ROOT / "examples/mixed-policy.classification.json")

    def test_dotted_variables_and_json_are_inserted_once(self):
        source = '{{missing}} "quoted"\n原文'
        rendered = render_template("{{ slot.role }}\n{{sources}}", {
            "slot": {"role": "成果比較"}, "sources": [{"text": source}],
        })
        title, body = rendered.split("\n", 1)
        self.assertEqual(title, "成果比較")
        self.assertEqual(json.loads(body), [{"text": source}])
        self.assertEqual(render_template("{{question}}", {"question": "{{slot.role}}"}), "{{slot.role}}")

    def test_invalid_or_missing_variables_fail_before_invocation(self):
        for template in ("{{slot.missing}}", "{{slot.role.upper()}}", "{{slot[0]}}", "{{broken"):
            with self.subTest(template=template), self.assertRaises(ValueError):
                render_template(template, {"slot": {"role": "已知"}})

    def test_templates_do_not_delegate_file_reads_to_model(self):
        for stage, path in TEMPLATES.items():
            with self.subTest(stage=stage):
                text = path.read_text()
                self.assertNotRegex(text, r"\[[^\]]+\]\([^)]+\)")
                self.assertEqual(text.count("<!-- INPUT -->"), 1)
                self.assertIn("{{response_schema}}", text)
                self.assertIn("{{repair}}", text)

    def test_slot_request_contains_selected_definition_rag_and_expanded_schema(self):
        original = copy.deepcopy(self.rag)
        request = build_slot_request(self.rag, self.selection, "policy_evaluation.outcomes",
                                     rewritten_question="實際成果距離政策目標還有多少？")
        self.assertEqual(request["stage"], "slot")
        self.assertTrue(request["data"]["is_primary"])
        self.assertIn("實際成果距離政策目標還有多少？", request["prompt"])
        self.assertIn(request["data"]["slot"]["role"], request["prompt"])
        self.assertIn(request["data"]["article_type"]["narrative_logic"], request["prompt"])
        self.assertIn(json.dumps(original, ensure_ascii=False, separators=(",", ":")), request["prompt"])
        self.assertNotIn("{{", request["prompt"])
        self.assertNotIn('"$ref"', request["prompt"])
        self.assertNotIn("skills/", request["prompt"])
        self.assertNotIn("schemas/", request["prompt"])
        self.assertEqual(request["response_schema"]["properties"]["slot_type"],
                         {"const": "policy_evaluation.outcomes"})
        check_schema(request["response_schema"], SCHEMAS / "slot-draft.schema.json")
        self.assertEqual(self.rag, original)
        secondary = build_slot_request(self.rag, self.selection, "data_analysis.finding")
        self.assertFalse(secondary["data"]["is_primary"])
        with self.assertRaisesRegex(ValidationError, "not part"):
            build_slot_request(self.rag, self.selection, "event_context.sequence")

    def test_fallback_slot_and_draft_format(self):
        self.rag["sources"] = []
        request = build_slot_request(self.rag, dict(status="undetermined", primary=None, secondary=[]),
                                     "unclassified.answer")
        draft = dict(kind="slot_draft", slot_type="unclassified.answer", status="missing",
                     reason="沒有來源", section=None, evidence=[], limitations=[])
        schema_validate(draft, request["response_schema"], SCHEMAS / "slot-draft.schema.json")
        draft["slot_type"] = "unclassified.limits"
        with self.assertRaises(ValidationError):
            schema_validate(draft, request["response_schema"], SCHEMAS / "slot-draft.schema.json")

    def test_unresolved_schema_and_empty_question_are_rejected(self):
        data = {"rag_input": self.rag, "categories": []}
        with self.assertRaisesRegex(ValueError, "references"):
            build_prompt_request("classification", data, {"$ref": "classification.schema.json"})
        with self.assertRaisesRegex(ValueError, "rewritten_question"):
            build_prompt_request("classification", data, {}, rewritten_question=" ")


if __name__ == "__main__":
    unittest.main()
