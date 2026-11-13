import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate import ValidationError, load_json, validate


class VisualizationTests(unittest.TestCase):
    def setUp(self):
        self.doc = load_json(ROOT / "examples/visualization-gallery.presentation.json")
        self.rag = load_json(ROOT / "examples/visualization-gallery.input.json")

    def block(self, kind):
        return next(x for x in self.doc["blocks"] if x["type"] == kind)

    def evidence(self, eid):
        return next(x for x in self.doc["analysis"]["evidence"] if x["id"] == eid)

    def invalid(self, message):
        with self.assertRaisesRegex(ValidationError, message):
            validate(self.doc, self.rag)

    def test_gallery(self):
        validate(self.doc, self.rag, load_json(ROOT / "examples/visualization-gallery.analysis.json"))

    def test_exact_original_thirteen_forms_and_two_basic_blocks(self):
        catalog = load_json(ROOT / "schemas/components.json")
        expected = {"line_chart", "bar_chart", "stacked_chart", "scatter_plot", "bubble_chart",
                    "unit_chart", "map", "table", "timeline", "flowchart", "network_graph",
                    "word_cloud", "treemap"}
        self.assertEqual({x["id"] for x in catalog["visualizations"]}, expected)
        variants = load_json(ROOT / "schemas/presentation.schema.json")["properties"]["blocks"]["items"]["oneOf"]
        actual = [Path(x["$ref"].split("#")[0]).stem for x in variants]
        self.assertEqual(set(actual), expected | {"text", "quote"})
        self.assertEqual(len(actual), 15)
        template = (ROOT / "skills/news-presentation/SKILL.md").read_text()
        scenarios = 0
        for item in catalog["visualizations"]:
            path = ROOT / item["reference"]
            self.assertTrue(path.is_file(), str(path))
            # Model-facing templates carry selection rules inline, not file navigation.
            self.assertIn("| " + item["id"] + " |", template)
            self.assertNotIn("references/forms/", template)
            text = path.read_text()
            self.assertIn("什麼情況可以用", text)
            self.assertIn("資料不足時", text)
            scenarios += text.count("拿到什麼資料")
        self.assertEqual(scenarios, 65)

    def test_partitions_sum_to_total(self):
        self.evidence("a")["value"] = 61
        self.invalid("do not sum")

    def test_partition_cannot_include_itself(self):
        self.evidence("part")["member_ids"] = ["total", "a"]
        self.invalid("total repeated")

    def test_partition_exclusivity_is_required(self):
        self.evidence("part")["mutually_exclusive"] = False
        self.invalid("wrong constant")

    def test_scatter_requires_same_subject(self):
        self.block("scatter_plot")["points"][0]["y_evidence_id"] = "yb"
        self.invalid("unpaired scatter")

    def test_scatter_requires_same_period(self):
        self.evidence("ya")["period"] = "2023"
        self.invalid("incomparable period")

    def test_bubbles_reject_radius_encoding(self):
        self.block("bubble_chart")["scale"] = "radius"
        self.invalid("wrong constant")

    def test_bubbles_cannot_encode_negative_area(self):
        self.evidence("ya")["value"] = -1
        self.block("bubble_chart").update(measurement_ids=["ya", "yb"], evidence_ids=["ya", "yb"])
        self.invalid("negative area")

    def test_units_cannot_round_fractional_unit_value(self):
        self.block("unit_chart")["unit_value"] = 2.5
        self.invalid("positive integer")

    def test_units_keep_explicit_remainder(self):
        self.block("unit_chart")["unit_value"] = 7
        validate(self.doc, self.rag)

    def test_percentage_units_need_percent_partition(self):
        self.block("unit_chart")["representation"] = "percentage"
        self.invalid("100-percent partition")

    def test_map_location_and_value_must_match(self):
        self.block("map")["features"][0]["measurement_id"] = "vloc2"
        self.invalid("another location")

    def test_coordinates_cannot_be_invented_outside_range(self):
        self.evidence("loc1")["latitude"] = 100
        self.invalid("out of range")

    def test_choropleth_requires_matching_versioned_boundaries(self):
        self.block("map")["mode"] = "choropleth"
        self.invalid("needs boundary mapping")
        for i, eid in enumerate(("loc1", "loc2")):
            self.evidence(eid).update(region_code="area" + str(i), boundary_id="registered-boundary-2024")
        validate(self.doc, self.rag)
        self.evidence("loc2")["boundary_id"] = "another-boundary-2025"
        self.invalid("incomparable boundary")

    def test_flow_cannot_mix_case_and_regulation(self):
        self.evidence("p1")["rule_basis"] = "case"
        self.invalid("incomparable rule_basis")

    def test_flow_decision_requires_conditions_and_exits(self):
        self.evidence("check")["role"] = "decision"
        self.invalid("branches need sourced conditions")

    def test_flow_dangling_edge(self):
        self.block("flowchart")["node_ids"].remove("end")
        self.invalid("dangling graph")

    def test_flow_return_path_keeps_reachable_exit(self):
        a = self.doc["analysis"]
        loop = copy.deepcopy(self.evidence("p2"))
        loop.update(id="return", from_id="check", to_id="check", label="退回補件後重新受理", conditions=["示例文件不全"])
        a["evidence"].append(loop)
        a["sections"][0]["evidence_ids"].append("return")
        self.block("text")["evidence_ids"].append("return")
        self.block("flowchart")["edge_ids"].append("return")
        self.block("flowchart")["evidence_ids"].append("return")
        validate(self.doc, self.rag)

    def test_network_requires_real_endpoints(self):
        self.evidence("rel")["to_id"] = "unknown"
        self.invalid("expected entity evidence")

    def test_network_periods_must_agree(self):
        self.evidence("n1")["period"] = "2023"
        self.invalid("incomparable period")

    def test_network_cannot_duplicate_shared_weight(self):
        a = self.doc["analysis"]
        first = self.evidence("rel")
        first["weight_evidence_id"] = "a"
        duplicate = copy.deepcopy(first)
        duplicate.update(id="rel2", relationship="另一筆服務")
        a["evidence"].append(duplicate)
        a["sections"][0]["evidence_ids"].append("rel2")
        self.block("text")["evidence_ids"].append("rel2")
        block = self.block("network_graph")
        block["edge_ids"].append("rel2")
        block["evidence_ids"].extend(["a", "rel2"])
        self.invalid("shared total duplicated")

    def test_presence_cloud_never_implies_frequency(self):
        self.block("word_cloud")["mode"] = "presence"
        self.invalid("equal text size")
        for eid in ("t1", "t2"):
            self.evidence(eid).update(value=None, unit=None)
        validate(self.doc, self.rag)

    def test_weighted_cloud_needs_sample_size(self):
        self.evidence("t1")["sample_size"] = None
        self.evidence("t2")["sample_size"] = None
        self.invalid("needs sample size")

    def test_cloud_cannot_mix_corpora(self):
        self.evidence("t1")["corpus"] = "另一批文本"
        self.invalid("incomparable corpus")

    def test_treemap_children_must_match_partition(self):
        self.block("treemap")["nodes"][2]["parent_id"] = "childa"
        self.invalid("children disagree")

    def test_treemap_parent_cannot_be_unknown(self):
        self.block("treemap")["nodes"][1]["parent_id"] = "missing"
        self.invalid("unknown treemap parent")

    def test_claude_and_gemini_share_canonical_skills(self):
        for agent in (".claude", ".gemini"):
            entry = ROOT / agent / "skills"
            self.assertTrue(entry.is_symlink())
            self.assertEqual(entry.resolve(), ROOT / "skills")
            for name in ("news-analysis", "news-presentation"):
                skill = (entry / name / "SKILL.md").resolve()
                self.assertEqual(skill, ROOT / "skills" / name / "SKILL.md")
                self.assertTrue((skill.parent / "../../schemas/analysis.schema.json").is_file())


if __name__ == "__main__":
    unittest.main()
