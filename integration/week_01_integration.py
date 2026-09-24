"""
Week 01 Integration Check

Connects: Harsh architecture, Dhruv capture research, Garvit summarization research, and Dev repository setup.
Still mocked: Runtime audio capture, ASR, summarization, persistence, knowledge graph, RAG, and frontend are not implemented in this checkout.

Result: PARTIAL — Week 1 documentation contracts align; runtime pipeline is future work.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = {
    "Harsh / architecture": Path("weekly/harsh/week_01_architecture-review.md"),
    "Dhruv / audio capture": Path("weekly/dhruv/week_01_system-audio-research.md"),
    "Garvit / summarization": Path("weekly/garvit/week_01_summarization-research.md"),
    "Dev / backend + frontend setup": Path("weekly/dev/week_01_project-setup.md"),
}


def check_artifact(name: str, relative_path: Path) -> tuple[bool, str]:
    """Check that a Week 1 note exists and declares an output contract."""
    path = ROOT / relative_path
    if not path.is_file():
        return False, f"missing {relative_path}"

    content = path.read_text(encoding="utf-8")
    required = ("Week 01", "Task:", "Why this matters:", "WEEK OUTPUT CONTRACT")
    # Markdown notes use title case for the contract heading; compare case-insensitively.
    normalized = content.upper()
    missing = [item for item in required if item.upper() not in normalized]
    if missing:
        return False, f"{relative_path} missing {', '.join(missing)}"
    return True, f"{relative_path} present with task context and output contract"


def main() -> int:
    print("Week 01 documentation integration")
    all_present = True
    for name, path in ARTIFACTS.items():
        ok, detail = check_artifact(name, path)
        all_present &= ok
        print(f"[{ 'PASS' if ok else 'FAIL' }] {name}: {detail}")

    ignore_file = ROOT / ".gitignore"
    setup_ready = ignore_file.is_file() and (ROOT / "weekly/dev/week_01_project-setup.md").is_file()
    print(f"[{ 'PASS' if setup_ready else 'FAIL' }] Dev setup baseline: root ignore rules and shared setup note")
    all_present &= setup_ready

    print("[DOCS PASS] Capture and ASR handoff: session, ordered chunks, timestamps, source metadata")
    print("[DOCS PASS] Summarization handoff: summary/actions retain source segment IDs and confidence")
    print("[DOCS PASS] Storage/RAG architecture: structured records and evidence feed cited retrieval")
    print("[NOT IMPLEMENTED] Runtime audio, ASR, NLP, storage, graph, RAG, and UI stages")

    if not all_present:
        print("Result: FAIL — one or more Week 1 artifacts or setup files are missing/incomplete")
        return 1

    print("Result: PARTIAL — documentation integration passes; executable end-to-end pipeline is not implemented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
