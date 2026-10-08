# Integration checks

`current_pipeline_check.py` is the canonical offline smoke test for the code
currently in this repository. It verifies the FastAPI health route, fixture
ASR, diarization alignment, and evidence retrieval without requiring API keys
or model downloads.

Run it from the repository root:

```bash
python3 integration/current_pipeline_check.py
```

The `week_01` through `week_08` scripts are historical checks from an older
`weekly/` artifact layout. They are retained for project history, but are not
part of the current test command until their source artifacts are restored or
their assertions are migrated to the current layout.
