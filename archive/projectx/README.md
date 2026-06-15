# Project X: Browser Comparison Agent

This folder contains the project-specific layer for the Session 9 browser
comparison assignment. It reuses the existing runtime in `S9SharedCode/code`
and keeps the orchestrator source unchanged.

## Run

```bash
cd projectx
./run.sh "Compare top 3 Hugging Face text-generation models sorted by likes."
```

The runner prints the final answer and writes a replay report under
`projectx/reports/<session_id>/replay_report.md`.

Project X pins text-skill calls to Ollama by default. Browser calls default to
the gateway's normal provider routing because Browser needs reliable structured
action JSON and may escalate to vision.

```bash
PROJECTX_LLM_PROVIDER=auto ./run.sh "Compare 3 laptops under ₹80,000 from Croma."
```

Use `PROJECTX_LLM_PROVIDER=gemini` or another gateway provider name to pin
Project X text skills to a different provider.

An optional delay is still available for debugging:

```bash
PROJECTX_LLM_CALL_DELAY_SECONDS=3 ./run.sh "Compare 3 laptops under ₹80,000 from Croma."
```

To force Browser too, set `PROJECTX_BROWSER_LLM_PROVIDER`:

```bash
PROJECTX_LLM_PROVIDER=ollama PROJECTX_BROWSER_LLM_PROVIDER=gemini ./run.sh "Compare 3 laptops under ₹80,000 from Croma."
```

Strict all-Ollama mode is still available, but your Ollama model must survive
Browser's structured action calls:

```bash
PROJECTX_LLM_PROVIDER=ollama PROJECTX_BROWSER_LLM_PROVIDER=ollama ./run.sh "Compare 3 laptops under ₹80,000 from Croma."
```

## Canonical Prompts

```text
Compare 3 laptops under ₹80,000.
Compare top 3 Hugging Face text-generation models sorted by likes.
Compare 5 AI coding tools by free plan and paid plan.
Compare 5 CNC/VMC training institutes in Bangalore.
```

## Design

- `compare_agent.py` runs the existing `flow.Executor` with a local skill
  catalogue.
- `prompts/researcher.md` uses the existing S9 successor contract to emit
  Browser nodes once candidate URLs are known.
- `replay_report.py` reads the persisted Session 9 run and generates a
  report with the original goal, DAG, Browser path/actions/artifacts,
  extracted data, final table, turns, and cost.
