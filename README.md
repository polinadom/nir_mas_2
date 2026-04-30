# OpenHands + LangGraph Multi-Agent Prototype

This prototype uses:

- two OpenHands agents with different role prompts: `architect` and `coder`
- LangGraph for orchestration
- A2A envelopes for handoff between agents
- an artifact registry as the main accounting layer for workspace outputs

## Architecture

### `mas/openhands_roles.py`

Wraps real OpenHands agents and runs each role inside the shared workspace.

### `mas/orchestrator.py`

Uses LangGraph `StateGraph` to execute the flow:

1. architect
2. coder
3. finalize

The graph state stores:

- A2A messages
- artifact records
- references produced by the architect
- references produced by the coder

### `mas/artifacts.py`

Tracks files created or changed after every stage and writes a manifest to:

- `.mas/artifacts.json`

This is the main source of truth for artifact accounting.

### `mas/a2a.py`

Defines:

- `A2AMessage`
- `ArtifactRef`
- `Performative`

The orchestrator does not guess handoffs implicitly. It passes explicit A2A
payloads between stages.

## Workspace Conventions

The shared workspace contains at least:

- `docs/`
- `src/`
- `tests/`
- `.mas/`

Expected outputs:

- `docs/architecture.md`
- `docs/implementation_plan.md`
- code in `src/`
- tests in `tests/`
- `docs/delivery_report.md`
- `.mas/artifacts.json`

## Run

Set:

- `LLM_API_KEY`
- `LLM_MODEL`
- optionally `LLM_BASE_URL`

These variables can be provided either through the shell environment or through
a local `.env` file in the repository root.

Then run:

```bash
python agent_lightllm.py --workspace demo_workspace --brief "Build a task tracker service"
```

## SWE-bench Example

The repository includes a sample SWE-bench-style task file:

- [examples/swebench_task_example.json](examples/swebench_task_example.json)

The task fields follow the official SWE-bench dataset structure, including
`instance_id`, `repo`, `base_commit`, `problem_statement`, `FAIL_TO_PASS`, and
`PASS_TO_PASS`.

Run the example like this:

```bash
python agent_lightllm.py --swe-bench-task examples/swebench_task_example.json
```

For PowerShell there is also a ready-to-run wrapper:

```powershell
./examples/run_swebench_example.ps1
```

If you pass a `.jsonl` file with multiple instances, also provide
`--instance-id`:

```bash
python agent_lightllm.py --swe-bench-task swebench_verified.jsonl --instance-id sympy__sympy-20590
```

What happens in this mode:

- the SWE-bench instance is converted into a structured brief for the agents
- the workspace name defaults to `swebench_<repo>_<instance_id>` if you did not
  override `--workspace`
- the architect receives the issue statement and writes architecture artifacts
- the coder receives the architect's artifact references and implements the task
- every changed file is recorded in `.mas/artifacts.json`

This example is for task execution and artifact tracking. It does not yet clone
the target repository or check out `base_commit`; you should prepare the
repository contents in the workspace before running the agents if you want to
work on a real SWE-bench instance.
