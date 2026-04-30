$ErrorActionPreference = "Stop"

if (-not $env:LLM_API_KEY) {
    throw "LLM_API_KEY is not set."
}

if (-not $env:LLM_MODEL) {
    throw "LLM_MODEL is not set."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$taskFile = Join-Path $PSScriptRoot "swebench_task_example.json"

& python (Join-Path $repoRoot "agent_lightllm.py") `
    --swe-bench-task $taskFile
