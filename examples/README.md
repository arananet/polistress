# Example output

This directory produces an example findings register using the **full
polistress pipeline** — ingest → persona synthesis → simulation → report —
over the synthetic organization in [`../data/synthetic_org/`](../data/synthetic_org/),
with **real Anthropic API calls** for every agent decision and for findings
synthesis. Nothing is mocked or faked.

## Generate it

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or ANTHROPIC_AUTH_TOKEN for OAuth tokens
python scripts/generate_org.py --seed 42
python examples/generate_example.py            # small subset, 2 ticks
python examples/generate_example.py --ticks 5  # scale up as your rate limits allow
```

This writes:

| File | What it is |
|---|---|
| `findings.json` | The findings register (JSON), one object per finding. |
| `findings.csv` | The same findings flattened for GRC-tool import. |
| `run_summary.md` | Action distribution, finding index, and a sample cited Q&A. |

The script defaults to a small, archetype-diverse agent subset (ciso, auditor,
developers, AI copilots, employees, sysadmin, attacker) over a short horizon so
it completes quickly within modest rate limits. For the full 150-person /
30-tick scenario, use the CLI directly:

```bash
polistress ingest data/synthetic_org
polistress simulate --scenario scenarios/ai_usage_policy.yaml --ticks 30
polistress report --run <run_id>
polistress ask --run <run_id> "where did shadow AI emerge?"
```

> All underlying seed data is **synthetic** — see the repository README disclaimer.
