# Example output

This directory holds an example findings register produced by the **full
polistress pipeline** — ingest → persona synthesis → simulation → report —
over the synthetic organization in [`../data/synthetic_org/`](../data/synthetic_org/).

## Files

| File | What it is |
|---|---|
| `findings.json` | The findings register (JSON), one object per finding. |
| `findings.csv` | The same findings flattened for GRC-tool import. |
| `run_summary.md` | Action distribution and finding index for the run. |
| `generate_example.py` | Reproduces all of the above. |

## Provenance & reproducibility

A real `polistress simulate` run drives every agent decision through **live
Anthropic API calls** (`ANTHROPIC_API_KEY` required) — `claude-sonnet-4-6` for
ciso/auditor/attacker agents and `claude-haiku-4-5-20251001` for the crowd.

So that this example reproduces anywhere (CI, no API key), `generate_example.py`
substitutes a **deterministic, trait-driven offline decider** for those LLM
calls, and uses the report agent's deterministic (non-LLM) findings path. The
world graph, persona synthesis, the append-only event log, signal extraction,
framework mappings, and event-id citations are all produced by the real
pipeline code — only the model calls are stood in for. That offline decider
lives here, in `examples/`, **not** in `src/`: runtime code never mocks the LLM.

To regenerate:

```bash
python scripts/generate_org.py --seed 42
python examples/generate_example.py
```

To produce the equivalent with real LLM decisions:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
polistress ingest data/synthetic_org
polistress simulate --scenario scenarios/ai_usage_policy.yaml --ticks 30
polistress report --run <run_id>
```

> All underlying seed data is **synthetic** — see the repository README disclaimer.
