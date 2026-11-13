#!/usr/bin/env python3
"""Run RAG -> classification -> article sections -> module content -> presentation."""

import argparse
import copy
import json
import shlex
import subprocess
import sys

if __package__:
    from .validate import (SCHEMAS, ValidationError, load_json, parse_json, require,
                           schema_validate, validate)
    from .workflow import build, component_files, load_component, resolve
    from .prompts import build_prompt_request, inline_schema
else:
    from validate import (SCHEMAS, ValidationError, load_json, parse_json, require,
                          schema_validate, validate)
    from workflow import build, component_files, load_component, resolve
    from prompts import build_prompt_request, inline_schema


class WorkflowError(RuntimeError):
    """A failed stage, suitable for reporting without exposing full source content."""

    def __init__(self, stage, message):
        self.stage = stage
        super().__init__(stage + ": " + message)


# TODO(llm-api): 提供實際的 LLM API adapter，實作 generate(request) 介面；依 stage
# 設定模型、token 預算與 timeout，傳入 response_schema 並回傳 JSON，沿用下游驗證。
class CommandModel:
    """Adapter for a caller-supplied executable using one JSON request/reply over stdin/stdout."""

    def __init__(self, command, timeout=120):
        if not command or isinstance(command, str):
            raise ValueError("command must be a nonempty argv list")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.command = list(command)
        self.timeout = timeout

    def __call__(self, request):
        result = subprocess.run(
            self.command, input=json.dumps(request, ensure_ascii=False, allow_nan=False),
            text=True, encoding="utf-8", capture_output=True, timeout=self.timeout, check=False,
        )
        if result.returncode:
            # stderr may contain credentials or entire source documents from an adapter.
            raise RuntimeError("Model command exited with code " + str(result.returncode))
        return result.stdout


def generate_validated(generate, stage, data, schema, validate_result, max_retries,
                       *, rewritten_question=None):
    repair = None
    for attempt in range(max_retries + 1):
        try:
            request = build_prompt_request(stage, data, schema, rewritten_question=rewritten_question,
                                           attempt=attempt + 1, repair=repair)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise WorkflowError(stage, "Prompt preparation failed (" + type(exc).__name__ + ")") from exc
        try:
            # A model adapter may modify its input; it must not mutate authoritative state.
            response = generate(copy.deepcopy(request))
        except Exception as exc:
            raise WorkflowError(stage, "Model invocation failed (" + type(exc).__name__ + ")") from exc
        try:
            candidate = parse_json(response) if isinstance(response, str) else copy.deepcopy(response)
            schema_validate(candidate, schema, SCHEMAS / "analysis.schema.json")
            return validate_result(candidate)
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            if attempt == max_retries:
                raise WorkflowError(stage, "Validation failed after " + str(attempt + 1) +
                                    " attempt(s): " + str(exc)) from exc
            repair = {"validation_error": str(exc), "previous_response": response}


def section_candidates(analysis, context):
    roles = {(p["type"], s["id"]): s["presentation_modules"]
             for p in context["profiles"] for s in p["slots"]}
    candidates = {s["id"]: [] for s in analysis["sections"]}
    for node in analysis["article_structure"]["nodes"]:
        for role in node["roles"]:
            for module in roles[(role["type"], role["slot"])]:
                name = module["module_id"]
                if context["modules"][name]["availability"] != "supported":
                    continue
                for sid in node["section_ids"]:
                    if name not in candidates[sid]:
                        candidates[sid].append(name)
    return candidates


def run_workflow(rag_input, generate, *, max_retries=1, rewritten_question=None):
    """Call generate(request) for each stage and return validated frontend presentation.

    generate returns a JSON object or JSON string. Validation retries only repeat the
    failed stage; model/transport exceptions stop immediately. max_retries excludes
    the first attempt. Inputs and intermediates are isolated per invocation.
    """
    if type(max_retries) is not int or max_retries < 0:
        raise ValueError("max_retries must be a nonnegative integer")
    if rewritten_question is not None and (not isinstance(rewritten_question, str) or not rewritten_question.strip()):
        raise ValueError("rewritten_question must be a nonempty string")
    rag = copy.deepcopy(rag_input)
    try:
        require(isinstance(rag, dict) and rag.get("kind") == "rag_input", "Expected RAG input")
        validate(rag)
    except (ValueError, KeyError, TypeError) as exc:
        raise WorkflowError("input", str(exc)) from exc

    catalog = load_json(SCHEMAS / "article-templates.json")
    selection_schema = inline_schema(load_json(SCHEMAS / "classification.schema.json"),
                                     SCHEMAS / "classification.schema.json")

    def accept_selection(selection):
        validate(selection)
        return selection

    selection = generate_validated(
        generate, "classification",
        {"rag_input": rag, "categories": catalog["templates"]},
        selection_schema, accept_selection, max_retries, rewritten_question=rewritten_question,
    )
    context = resolve(selection)
    # TODO(slot-rag): 依各 slot 的 reader_question / evidence_requirements 判斷資料缺口，
    # 呼叫 RAG 補查；將新增 sources/chunks 去重併入 rag，保留來源 ID，再 validate(rag)。
    # 補查需限制次數；仍不足時保留 missing/partial 與 limitations，不補造內容。
    analysis_schema = inline_schema(load_json(SCHEMAS / "analysis.schema.json"), SCHEMAS / "analysis.schema.json")
    analysis_schema["required"].append("article_structure")

    def accept_analysis(analysis):
        validate(analysis, rag, expected_classification=selection)
        return analysis

    # TODO(slot-writing): 目前 analysis 階段以一次 LLM 呼叫撰寫全部段落；後續可按 slot
    # 用 prompts.build_slot_request 分別準備 LLM 請求，再合併並驗證 section/evidence ID
    # 及 article_structure 映射。text 模組仍從驗證完成的 section 取得正文。
    analysis = generate_validated(
        generate, "analysis", {"rag_input": rag, **context},
        analysis_schema, accept_analysis, max_retries, rewritten_question=rewritten_question,
    )
    candidates = section_candidates(analysis, context)
    names = dict.fromkeys(name for ids in candidates.values() for name in ids)
    files = component_files()
    components = {name: load_component(name, files) for name in names}
    # TODO(chart-rag): 圖表候選所需資料不足時，透過 RAG 找回原始完整表格或時間序列，
    # 不能只用搜尋摘要；確認期間、單位、統計口徑、資料完整性及 source_id/chunk_id。
    # TODO(module-data-llm): 將補回的原始資料交給 LLM 抽取、正規化為 analysis evidence，
    # 計算與聚合由程式執行；更新 rag、sections、evidence 後重新驗證 analysis，並重算
    # candidates/components。接著才依各模組 input_schema 產生輸入，交由 build 轉前端格式。
    # 若補查失敗或資料仍不足，沿用文字與 insufficient_data，不直接將新資料塞入圖表。
    plan_schema = {
        "type": "object", "required": ["modules"], "additionalProperties": False,
        "properties": {"modules": {"type": "array", "minItems": 1, "items": {
            "oneOf": [inline_schema(c["input_schema"], SCHEMAS / c["file"]) for c in components.values()],
        }}},
    }

    def accept_plan(plan):
        for module in plan["modules"]:
            allowed = {name for sid in module["section_ids"] for name in candidates.get(sid, [])}
            require(module["module_id"] in allowed, "Module is outside referenced sections' slot candidates")
        return build(selection, rag, analysis, plan)

    return generate_validated(
        generate, "presentation",
        {"analysis": analysis, "profiles": context["profiles"],
         "section_modules": candidates, "components": components},
        plan_schema, accept_plan, max_retries, rewritten_question=rewritten_question,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="RAG JSON following rag-input.schema.json")
    parser.add_argument("--model-command", required=True, help="Executable and arguments; receives JSON on stdin")
    parser.add_argument("--timeout", type=float, default=120, help="Timeout per model command in seconds")
    parser.add_argument("--max-retries", type=int, default=1, help="Validation repairs per stage")
    parser.add_argument("--rewritten-question", help="Resolved user question for the prompt; preserves original RAG")
    args = parser.parse_args()
    try:
        model = CommandModel(shlex.split(args.model_command), timeout=args.timeout)
        output = run_workflow(load_json(args.input), model, max_retries=args.max_retries,
                              rewritten_question=args.rewritten_question)
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
    except (WorkflowError, OSError, ValueError) as exc:
        print("FAILED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
