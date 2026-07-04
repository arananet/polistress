"""polistress command-line interface."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .personas import synthesize_agents
from .personas.agent import Agent, AgentTraits, Archetype
from .personas.memory import AgentMemory
from .report import ReportAgent
from .report.backend import AnthropicReportBackend
from .report.findings import write_csv, write_json
from .runstore import new_run_id, run_paths
from .simulation import EventLog, SimulationEngine, load_scenario
from .simulation.decider import AnthropicDecider
from .worldgraph import WorldGraph, ingest_directory

app = typer.Typer(add_completion=False, help="Swarm-based GRC policy simulation engine.")
console = Console()

DEFAULT_GRAPH = Path("runs/world.db")


@app.command()
def ingest(
    directory: str = typer.Argument(..., help="Directory of seed documents (json/md)."),
    db: Path = typer.Option(DEFAULT_GRAPH, help="Where to persist the graph."),
) -> None:
    """Ingest seed documents into the world graph and persist to SQLite."""
    graph = ingest_directory(directory)
    graph.save(db)
    table = Table(title="Ingested world graph")
    table.add_column("metric")
    table.add_column("count", justify="right")
    table.add_row("nodes", str(graph.count_nodes()))
    table.add_row("edges", str(graph.count_edges()))
    for nt in ("Person", "Team", "Asset", "Control", "Policy", "Finding", "AIAgent"):
        table.add_row(f"  {nt}", str(len(graph.nodes_of_type(nt))))
    console.print(table)
    console.print(f"[green]Saved graph to {db}[/green]")


@app.command()
def simulate(
    scenario: Path = typer.Option(..., help="Scenario YAML file."),
    graph_db: Path = typer.Option(DEFAULT_GRAPH, "--graph", help="Ingested graph db."),
    ticks: int = typer.Option(30, help="Number of simulated ticks (days)."),
    agents: int = typer.Option(200, help="Max crowd agents to synthesize."),
    seed: int = typer.Option(0, help="Deterministic synthesis seed."),
    attackers: int = typer.Option(3, help="Number of injected attacker agents."),
    concurrency: int = typer.Option(8, help="Max concurrent LLM calls."),
    run_id: str = typer.Option("", help="Run id (auto-generated if empty)."),
) -> None:
    """Run a policy-injection scenario. Requires ANTHROPIC_API_KEY."""
    if not graph_db.exists():
        raise typer.BadParameter(f"graph db not found: {graph_db}; run `ingest` first")
    rid = run_id or new_run_id()
    paths = run_paths(rid).ensure()

    graph = WorldGraph.load(graph_db)
    graph.save(paths.graph_db)  # snapshot into the run
    scen = load_scenario(scenario)
    ticks = ticks or scen.ticks

    agent_list = synthesize_agents(
        graph, seed=seed, max_agents=agents, n_attackers=attackers
    )
    paths.agents_json.write_text(
        json.dumps([a.to_dict() for a in agent_list], indent=2), encoding="utf-8"
    )
    paths.scenario_json.write_text(
        json.dumps(
            {
                "name": scen.name,
                "policy_title": scen.policy_title,
                "policy_body": scen.policy_body,
                "policy_node_id": scen.policy_node_id,
                "domain": scen.domain,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    console.print(
        f"[cyan]Run {rid}[/cyan]: {len(agent_list)} agents, {ticks} ticks, "
        f"scenario '{scen.name}'."
    )

    log = EventLog(paths.events_db)
    memory = AgentMemory(paths.memory_db)
    decider = AnthropicDecider(max_concurrency=concurrency)
    engine = SimulationEngine(graph, agent_list, log, memory, decider)

    with console.status("[bold]Running simulation (real LLM calls)…"):
        asyncio.run(engine.run(scen, ticks))

    counts = log.action_counts()
    log.close()
    memory.close()

    paths.write_meta(
        {
            "run_id": rid,
            "scenario": scen.name,
            "domain": scen.domain,
            "ticks": ticks,
            "agents": len(agent_list),
            "seed": seed,
            "events": sum(counts.values()),
            "action_counts": counts,
        }
    )

    table = Table(title=f"Run {rid} — action counts")
    table.add_column("action")
    table.add_column("count", justify="right")
    for action, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        table.add_row(action, str(n))
    console.print(table)
    console.print(f"[green]Run complete. Artifacts in {paths.dir}[/green]")
    console.print(f"Next: [bold]polistress report --run {rid}[/bold]")


@app.command()
def report(
    run: str = typer.Option(..., "--run", help="Run id to report on."),
) -> None:
    """Generate the findings register (JSON + CSV) for a run."""
    paths = run_paths(run)
    if not paths.events_db.exists():
        raise typer.BadParameter(f"no events for run {run} at {paths.events_db}")
    graph = WorldGraph.load(paths.graph_db)
    log = EventLog(paths.events_db)
    domain = paths.read_meta().get("domain", "ai_governance")
    backend = AnthropicReportBackend()
    agent = ReportAgent(graph, log, backend, domain=domain)

    with console.status("[bold]Synthesizing findings (real LLM calls)…"):
        findings = asyncio.run(agent.build_findings())
    log.close()

    write_json(findings, paths.findings_json)
    write_csv(findings, paths.findings_csv)

    table = Table(title=f"Findings register — run {run}")
    table.add_column("id")
    table.add_column("severity")
    table.add_column("title")
    table.add_column("citations", justify="right")
    for f in findings:
        table.add_row(f.id, f.severity, f.title, str(len(f.root_cause_events)))
    console.print(table)
    console.print(f"[green]Wrote {paths.findings_json} and {paths.findings_csv}[/green]")


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question about the run."),
    run: str = typer.Option(..., "--run", help="Run id to query."),
) -> None:
    """Ask a question about a run; the answer cites specific event ids."""
    paths = run_paths(run)
    if not paths.events_db.exists():
        raise typer.BadParameter(f"no events for run {run} at {paths.events_db}")
    graph = WorldGraph.load(paths.graph_db)
    log = EventLog(paths.events_db)
    domain = paths.read_meta().get("domain", "ai_governance")
    backend = AnthropicReportBackend()
    agent = ReportAgent(graph, log, backend, domain=domain)

    with console.status("[bold]Answering (real LLM call)…"):
        answer = asyncio.run(agent.answer(question))
    log.close()

    console.print(f"[bold cyan]Q:[/bold cyan] {question}")
    console.print(f"[bold]A:[/bold] {answer.text}")
    if answer.cited_event_ids:
        console.print(
            "[dim]Cited events: "
            + ", ".join(f"evt-{i}" for i in answer.cited_event_ids)
            + "[/dim]"
        )


# Re-exported so `python -m polistress.cli` and tests can import symbols cleanly.
__all__ = ["app", "Agent", "AgentTraits", "Archetype"]


if __name__ == "__main__":
    app()
