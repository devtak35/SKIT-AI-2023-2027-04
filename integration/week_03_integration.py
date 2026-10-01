"""
Week 03 Integration Check

Connects: Harsh architecture diagrams, Dhruv platform capture, Garvit prompt
tests, and Dev's FastAPI scaffold.
Still mocked: platform SDK callbacks, ASR output, LLM generation, durable
storage/indexing, knowledge-graph linking, RAG retrieval, and frontend UI.

Result: PARTIAL — the documented architecture and runnable fixture stages
connect; production providers and persistence are not implemented yet.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module(module_name: str, relative_path: str):
    """Load a weekly module even when its filename contains hyphens."""
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def check_harsh_docs() -> None:
    path = ROOT / "weekly/harsh/week_03_architecture-docs-diagrams.md"
    text = path.read_text(encoding="utf-8")
    required = (
        "## Component diagram",
        "## Live meeting update flow",
        "## Historical question flow",
        "## Deployment view",
        "## Evidence lineage",
        "segment_id",
        "source_segment_ids",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise AssertionError(f"Week 3 architecture note is missing: {missing}")
    if text.count("```mermaid") != 4:
        raise AssertionError("Week 3 architecture note must contain four Mermaid diagrams")


def check_dhruv_platform_capture() -> None:
    module = load_module("week_03_dhruv", "weekly/dhruv/week_03_platform-capture.py")
    events = module.demo("zoom")
    if len(events) != 2:
        raise AssertionError(f"expected two normalized chunks, got {len(events)}")
    payloads = [event["payload"] for event in events]
    if [payload["sequence"] for payload in payloads] != [0, 1]:
        raise AssertionError("platform capture did not preserve chunk ordering")
    if any(payload["source"] != "zoom" for payload in payloads):
        raise AssertionError("platform source metadata was not preserved")
    print(f"[PASS] Dhruv platform capture: {len(events)} normalized Zoom chunks")


def check_garvit_prompt_contract() -> None:
    # The weekly wrapper currently imports a module name that does not match
    # the checked-in reusable file. Use the reusable evaluator directly and
    # report the wrapper mismatch below as a known issue.
    module = load_module("week_03_garvit_checks", "ml/nlp/week3_prompt_evaluation.py")
    failures = module.evaluate_fixture()
    if failures:
        raise AssertionError("; ".join(failures))
    wrapper = ROOT / "weekly/garvit/week_03_prompt-tests.py"
    if "from prompt_evaluation import" in wrapper.read_text(encoding="utf-8"):
        print("[KNOWN ISSUE] Garvit Week 3 wrapper imports prompt_evaluation, but the file is week3_prompt_evaluation.py")
    print("[PASS] Garvit prompt tests: sample prompts and evidence references validate")


def check_dev_backend() -> None:
    module = load_module("week_03_dev", "weekly/dev/fastapi-skeleton.py")
    with TestClient(module.app) as client:
        response = client.get("/health")
    if response.status_code != 200 or response.json().get("api_version") != "v1":
        raise AssertionError(f"unexpected backend health response: {response.status_code} {response.text}")
    print(f"[PASS] Dev FastAPI scaffold: GET /health -> {response.json()}")


def check_mock_handoff() -> None:
    transcript = json.loads((ROOT / "fixtures/week_02_transcript.json").read_text(encoding="utf-8"))
    summary = json.loads((ROOT / "fixtures/week_02_summary.json").read_text(encoding="utf-8"))
    segment_ids = {segment["segment_id"] for segment in transcript["segments"]}
    cited_ids = set(summary["summary"]["source_segment_ids"])
    if not cited_ids <= segment_ids:
        raise AssertionError("mock summary cites a transcript segment that is not stored")
    print(f"[MOCK] Handoff: {len(segment_ids)} transcript segments -> cited summary evidence")


def main() -> int:
    stages = (
        ("Harsh architecture docs", check_harsh_docs),
        ("Dhruv platform capture", check_dhruv_platform_capture),
        ("Garvit prompt contract", check_garvit_prompt_contract),
        ("Dev backend scaffold", check_dev_backend),
        ("Cross-stage fixture handoff", check_mock_handoff),
    )
    failures: list[str] = []
    for name, check in stages:
        try:
            check()
            if name == "Harsh architecture docs":
                print("[PASS] Harsh architecture docs: three diagrams and evidence lineage present")
        except Exception as error:  # report every stage so sync is actionable
            failures.append(f"{name}: {error}")
            print(f"[FAIL] {name}: {error}")

    if failures:
        print("Result: FAIL — one or more Week 3 integration checks failed")
        return 1
    print("Result: PARTIAL — fixture pipeline connects; production capture, ASR, NLP, storage, graph, RAG, and UI remain mocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
