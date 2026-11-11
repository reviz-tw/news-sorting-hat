import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.pipeline import CommandModel, WorkflowError, run_workflow
from scripts.validate import load_json


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.rag = load_json(ROOT / "examples/mixed-policy.input.json")
        self.responses = {
            stage: load_json(ROOT / ("examples/mixed-policy." + suffix + ".json"))
            for stage, suffix in (("classification", "classification"), ("analysis", "analysis"),
                                  ("presentation", "modules"))
        }
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return copy.deepcopy(self.responses[request["stage"]])

    def test_pipeline_loads_selected_profiles_and_section_modules(self):
        output = run_workflow(self.rag, self.generate)
        self.assertEqual(output, load_json(ROOT / "examples/mixed-policy.presentation.json"))
        self.assertEqual([r["stage"] for r in self.requests], ["classification", "analysis", "presentation"])
        self.assertEqual([p["type"] for p in self.requests[1]["data"]["profiles"]],
                         ["policy_evaluation", "data_analysis"])
        # The model receives the complete editorial checklist, not just module choices.
        for request in self.requests[1:]:
            for profile in request["data"]["profiles"]:
                for slot in profile["slots"]:
                    original = load_json(ROOT / "schemas/slots" / (slot["type"] + ".json"))
                    self.assertEqual(slot["writing_guidance"], original["writing_guidance"])
        self.assertIn("writing_guidance.output_checks", self.requests[1]["instruction"])
        data = self.requests[2]["data"]
        self.assertIn("bar_chart", data["section_modules"]["s_result"])
        self.assertNotIn("photo", data["components"])
        for request in self.requests:
            self.assertNotIn('"$ref"', json.dumps(request["response_schema"]))

    def test_invalid_input_stops_before_model_call(self):
        self.rag["sources"][0]["url"] = "invalid"
        with self.assertRaises(WorkflowError) as error:
            run_workflow(self.rag, self.generate)
        self.assertEqual(error.exception.stage, "input")
        self.assertFalse(self.requests)

    def test_repair_only_repeats_failed_stage(self):
        def generate(request):
            answer = self.generate(request)
            if request["stage"] == "analysis" and request["attempt"] == 1:
                answer["classification"]["primary"] = "event_brief"
            return answer
        run_workflow(self.rag, generate)
        self.assertEqual([r["stage"] for r in self.requests],
                         ["classification", "analysis", "analysis", "presentation"])
        repair = self.requests[2]["repair"]
        self.assertIn("changed classification", repair["validation_error"])
        self.assertEqual(repair["previous_response"]["classification"]["primary"], "event_brief")

    def test_persistent_invalid_json_stops_after_bounded_repairs(self):
        def generate(request):
            self.requests.append(request)
            return '{"status": "determined", "status": "tentative"}'
        with self.assertRaises(WorkflowError) as error:
            run_workflow(self.rag, generate, max_retries=1)
        self.assertEqual(error.exception.stage, "classification")
        self.assertEqual(len(self.requests), 2)
        self.assertIn("Duplicate JSON key", str(error.exception))

    def test_model_error_stops_immediately_with_stage(self):
        def generate(request):
            self.requests.append(request)
            raise TimeoutError("private transport details")
        with self.assertRaises(WorkflowError) as error:
            run_workflow(self.rag, generate)
        self.assertEqual(error.exception.stage, "classification")
        self.assertNotIn("private transport", str(error.exception))
        self.assertEqual(len(self.requests), 1)

    def test_model_cannot_mutate_authoritative_input(self):
        original = copy.deepcopy(self.rag)
        def generate(request):
            answer = self.generate(request)
            if request["stage"] == "analysis":
                request["data"]["rag_input"]["question"] = "tampered"
            if request["stage"] == "presentation":
                request["data"]["analysis"]["sections"][0]["body"] = "tampered"
            return answer
        self.assertEqual(run_workflow(self.rag, generate),
                         load_json(ROOT / "examples/mixed-policy.presentation.json"))
        self.assertEqual(self.rag, original)

    def test_module_must_match_referenced_sections_candidates(self):
        # bar_chart is allowed for outcomes, but not the implementation slot.
        plan = self.responses["presentation"]
        chart = next(m for m in plan["modules"] if m["module_id"] == "bar_chart")
        chart["section_ids"] = ["s_execution"]
        with self.assertRaises(WorkflowError) as error:
            run_workflow(self.rag, self.generate, max_retries=0)
        self.assertEqual(error.exception.stage, "presentation")
        self.assertIn("slot candidates", str(error.exception))

    def test_no_sources_can_follow_unclassified_missing_roles(self):
        self.rag["sources"] = []
        selection = dict(status="undetermined", primary=None, secondary=[])
        analysis = self.responses["analysis"]
        analysis.update(status="insufficient", sources=[], evidence=[])
        analysis["classification"].update(**selection, evidence_ids=[])
        analysis["sections"] = [dict(id="s1", heading="資料不足", body="缺少新聞來源。", evidence_ids=[])]
        analysis["limitations"] = [dict(code="missing_data", text="缺少來源。", evidence_ids=[])]
        analysis["article_structure"] = dict(
            structure_version="1.0.0", templates=["unclassified"], composition_reason="缺資料。",
            nodes=[dict(id="n1", roles=[dict(type="unclassified", slot="answer"),
                                       dict(type="unclassified", slot="limits")],
                        reader_question="可回答什麼？", status="missing", reason="沒有來源。",
                        section_ids=["s1"], evidence_ids=[])])
        plan = {"modules": [dict(module_id="text", id="b1", title="資料不足", section_ids=["s1"],
                                 evidence_ids=[], decision="insufficient_data", decision_reason="缺少來源。",
                                 notes=[], data={})]}
        self.responses.update(classification=selection, presentation=plan)
        output = run_workflow(self.rag, self.generate)
        self.assertEqual(output["blocks"][0]["body"], "缺少新聞來源。")
        self.assertEqual(self.requests[2]["data"]["section_modules"], {"s1": ["text"]})

    def test_command_adapter_and_cli(self):
        command = [sys.executable, str(ROOT / "examples/replay_model.py")]
        output = run_workflow(self.rag, CommandModel(command))
        self.assertEqual(output, load_json(ROOT / "examples/mixed-policy.presentation.json"))
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/pipeline.py"),
             str(ROOT / "examples/mixed-policy.input.json"),
             "--model-command", sys.executable + " " + str(ROOT / "examples/replay_model.py")],
            cwd="/tmp", capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), output)


if __name__ == "__main__":
    unittest.main()
