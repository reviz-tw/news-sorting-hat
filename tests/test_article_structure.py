import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate import ValidationError, load_json, validate


class ArticleStructureTests(unittest.TestCase):
    def setUp(self):
        self.analysis = load_json(ROOT / "examples/mixed-policy.analysis.json")

    def invalid(self, pattern):
        with self.assertRaisesRegex(ValidationError, pattern):
            validate(self.analysis, require_structure=True)

    def test_mixed_roles_and_full_pipeline(self):
        rag = load_json(ROOT / "examples/mixed-policy.input.json")
        validate(self.analysis, rag, require_structure=True)
        validate(load_json(ROOT / "examples/mixed-policy.presentation.json"), rag,
                 self.analysis, require_structure=True)

    def test_brief_does_not_expand_unneeded_roles(self):
        brief = load_json(ROOT / "examples/structured-event.analysis.json")
        validate(brief, require_structure=True)
        self.assertEqual(len(brief["sections"]), 1)

    def test_catalog_covers_all_categories(self):
        catalog = load_json(ROOT / "schemas/article-templates.json")
        categories = load_json(ROOT / "schemas/common.schema.json")["$defs"]["category"]["enum"]
        self.assertEqual({t["type"] for t in catalog["templates"]}, set(categories))
        self.assertEqual(len(catalog["templates"]), 12)
        for template in catalog["templates"]:
            self.assertEqual(len({s["id"] for s in template["slots"]}), len(template["slots"]))
            self.assertTrue(any(s["priority"] == "core" for s in template["slots"]))

    def test_legacy_optional_but_new_output_requires_structure(self):
        del self.analysis["article_structure"]
        validate(self.analysis)
        self.invalid("structure is required")

    def test_classification_and_structure_must_agree(self):
        self.analysis["classification"]["secondary"] = []
        self.invalid("disagree with classification")

    def test_role_cannot_be_omitted(self):
        self.analysis["article_structure"]["nodes"].pop()
        self.invalid("every selected template slot")

    def test_role_cannot_be_assigned_twice(self):
        nodes = self.analysis["article_structure"]["nodes"]
        nodes[1]["roles"].append(copy.deepcopy(nodes[0]["roles"][0]))
        self.invalid("assigned more than once")

    def test_role_must_exist(self):
        self.analysis["article_structure"]["nodes"][0]["roles"][0]["slot"] = "made_up"
        self.invalid("Unknown or unselected")

    def test_primary_core_cannot_be_skipped(self):
        node = self.analysis["article_structure"]["nodes"][1]
        node.update(status="not_applicable", section_ids=[], evidence_ids=[])
        self.invalid("Primary core role")

    def test_unknown_section_rejected(self):
        self.analysis["article_structure"]["nodes"][0]["section_ids"].append("missing")
        self.invalid("unknown section")

    def test_evidence_must_belong_to_mapped_section(self):
        self.analysis["article_structure"]["nodes"][1]["evidence_ids"] = ["result"]
        self.invalid("outside mapped sections")

    def test_missing_role_cannot_claim_evidence(self):
        self.analysis["article_structure"]["nodes"][1]["status"] = "missing"
        self.invalid("must not claim")

    def test_missing_core_is_explicitly_allowed(self):
        node = self.analysis["article_structure"]["nodes"][1]
        node.update(status="missing", evidence_ids=[], reason="材料不足，段落只交代目前未知。")
        validate(self.analysis, require_structure=True)

    def test_all_sections_need_role_mapping(self):
        self.analysis["sections"].append(dict(id="orphan", heading="額外段落", body="未映射內容", evidence_ids=["goal"]))
        self.invalid("map every answer section")

    def test_no_evidence_fallback(self):
        a = self.analysis
        a["status"] = "insufficient"
        a["classification"].update(status="undetermined", primary=None, secondary=[], evidence_ids=[])
        a["sources"] = []; a["evidence"] = []
        a["sections"] = [dict(id="s1", heading="資料不足", body="未取得新聞材料。", evidence_ids=[])]
        a["limitations"] = [dict(code="missing_data", text="缺新聞來源。", evidence_ids=[])]
        a["article_structure"] = dict(structure_version="1.0.0", templates=["unclassified"],
            composition_reason="無來源，僅說明限制。", nodes=[dict(id="n1", roles=[dict(type="unclassified", slot="answer"),dict(type="unclassified", slot="limits")], reader_question="目前能回答什麼、缺什麼？", status="missing", reason="未取得資料。", section_ids=["s1"], evidence_ids=[])])
        validate(a, require_structure=True)


if __name__ == "__main__":
    unittest.main()
