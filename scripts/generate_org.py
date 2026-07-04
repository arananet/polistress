#!/usr/bin/env python3
"""Generate a synthetic organization for polistress.

Deterministic given ``--seed``. Produces ~150 people across 8 teams, 40 assets,
25 controls, 10 historical findings, and 5 policies under ``data/synthetic_org/``.

ALL output is synthetic — fabricated for simulation. It does not describe any
real organization or person.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

TEAMS = [
    ("team:exec", "Executive"),
    ("team:security", "Security"),
    ("team:platform_eng", "Platform Engineering"),
    ("team:growth_eng", "Growth Engineering"),
    ("team:data_platform", "Data Platform"),
    ("team:sales", "Sales"),
    ("team:finance", "Finance"),
    ("team:people_ops", "People Ops"),
]

# team_id -> list of (archetype, role, weight)
TEAM_ROLES: dict[str, list[tuple[str, str, int]]] = {
    "team:exec": [
        ("ciso", "Chief Information Security Officer", 1),
        ("employee", "Executive", 4),
    ],
    "team:security": [
        ("auditor", "Security Auditor", 3),
        ("sysadmin", "Security Engineer", 4),
        ("employee", "Security Analyst", 3),
    ],
    "team:platform_eng": [
        ("sysadmin", "Site Reliability Engineer", 4),
        ("developer", "Platform Developer", 8),
    ],
    "team:growth_eng": [("developer", "Growth Developer", 12)],
    "team:data_platform": [
        ("developer", "Data Engineer", 8),
        ("sysadmin", "Data Platform Administrator", 3),
    ],
    "team:sales": [("employee", "Account Executive", 14)],
    "team:finance": [("employee", "Finance Analyst", 10)],
    "team:people_ops": [("employee", "People Ops Specialist", 8)],
}

FIRST = [
    "Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie",
    "Avery", "Quinn", "Devon", "Reese", "Skyler", "Cameron", "Rowan", "Emerson",
    "Harper", "Finley", "Dakota", "Hayden", "Parker", "Sawyer", "Kendall", "Blake",
]
LAST = [
    "Nguyen", "Patel", "Garcia", "Kim", "Okafor", "Silva", "Haddad", "Rossi",
    "Novak", "Andersson", "Costa", "Mensah", "Ivanov", "Yamamoto", "Dubois",
    "Fischer", "Moreau", "Santos", "Larsen", "Petrov",
]

ASSET_KINDS = [
    "SaaS App", "Internal Service", "Database", "Data Warehouse", "Repository",
    "Endpoint Fleet", "CI/CD Pipeline", "Identity Provider", "File Store",
    "Model Endpoint",
]

CONTROL_NAMES = [
    "MFA enforcement", "Least-privilege access review", "Endpoint hardening",
    "Data loss prevention", "Secrets scanning", "Change management approval",
    "Vendor security review", "Logging and monitoring", "Network segmentation",
    "Backup and recovery", "Encryption at rest", "Encryption in transit",
    "Access recertification", "Vulnerability scanning", "Patch management",
    "Incident response runbook", "Security awareness training", "Code review gate",
    "Approved-software allowlist", "AI tool review board", "Prompt-injection filter",
    "Model output logging", "PII redaction", "Egress filtering", "Phishing simulation",
]

POLICIES = [
    (
        "policy:acceptable_use",
        "Acceptable Use Policy",
        "Defines acceptable use of company systems, networks, and data.",
    ),
    (
        "policy:access_control",
        "Access Control Policy",
        "Requires least-privilege access and periodic recertification.",
    ),
    (
        "policy:data_classification",
        "Data Classification Policy",
        "Classifies data as public, internal, confidential, or restricted.",
    ),
    (
        "policy:vendor_risk",
        "Vendor Risk Management Policy",
        "Requires security review of third-party vendors before onboarding.",
    ),
    (
        "policy:change_management",
        "Change Management Policy",
        "Requires approval and testing before production changes.",
    ),
]


def _weighted_roles(team_id: str, count: int, rng: random.Random) -> list[tuple[str, str]]:
    specs = TEAM_ROLES[team_id]
    pool: list[tuple[str, str]] = []
    for archetype, role, weight in specs:
        pool.extend([(archetype, role)] * weight)
    return [rng.choice(pool) for _ in range(count)]


def generate(seed: int, out_dir: Path) -> None:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "policies").mkdir(parents=True, exist_ok=True)

    # ---- people, teams, ai agents ----
    team_nodes = [
        {"id": tid, "type": "Team", "name": name} for tid, name in TEAMS
    ]
    # Distribute ~150 people across teams roughly by role weight totals.
    per_team = [6, 13, 16, 16, 13, 24, 20, 42]  # sums to 150
    people_nodes: list[dict] = []
    org_edges: list[dict] = []
    managers: dict[str, str] = {}
    pid = 0
    for (tid, _), n in zip(TEAMS, per_team, strict=True):
        roles = _weighted_roles(tid, n, rng)
        team_people: list[str] = []
        for archetype, role in roles:
            pid += 1
            node_id = f"person:{pid:04d}"
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            people_nodes.append(
                {
                    "id": node_id,
                    "type": "Person",
                    "name": name,
                    "role": role,
                    "archetype": archetype,
                    "team": tid,
                }
            )
            team_people.append(node_id)
        # first person of team is the manager; others report to them
        manager = team_people[0]
        managers[tid] = manager
        for member in team_people[1:]:
            org_edges.append({"source": member, "target": manager, "type": "reports_to"})

    # cross-team reporting: team managers report to the exec manager
    exec_manager = managers["team:exec"]
    for tid, mgr in managers.items():
        if tid != "team:exec":
            org_edges.append({"source": mgr, "target": exec_manager, "type": "reports_to"})

    # AI copilots owned by a sample of developers/employees
    ai_nodes: list[dict] = []
    candidates = [p for p in people_nodes if p["archetype"] in ("developer", "employee")]
    rng.shuffle(candidates)
    for i, person in enumerate(candidates[:15]):
        aid = f"ai:{i + 1:04d}"
        ai_nodes.append(
            {
                "id": aid,
                "type": "AIAgent",
                "name": f"Copilot for {person['name']}",
                "role": "AI copilot",
                "team": person["team"],
                "principal": person["id"],
            }
        )
        org_edges.append({"source": person["id"], "target": aid, "type": "owns"})

    _dump(
        out_dir / "org.json",
        {"nodes": team_nodes + people_nodes + ai_nodes, "edges": org_edges},
    )

    # ---- assets (40) ----
    asset_nodes: list[dict] = []
    asset_edges: list[dict] = []
    team_ids = [tid for tid, _ in TEAMS]
    person_ids = [p["id"] for p in people_nodes]
    for a in range(1, 41):
        aid = f"asset:{a:04d}"
        kind = rng.choice(ASSET_KINDS)
        owner_team = rng.choice(team_ids)
        asset_nodes.append(
            {
                "id": aid,
                "type": "Asset",
                "name": f"{kind} {a}",
                "kind": kind,
                "classification": rng.choice(
                    ["public", "internal", "confidential", "restricted"]
                ),
            }
        )
        asset_edges.append({"source": owner_team, "target": aid, "type": "owns"})
        # a named person co-owns the asset, giving people direct graph adjacency
        asset_edges.append(
            {"source": rng.choice(person_ids), "target": aid, "type": "owns"}
        )
    # dependency edges between assets
    asset_ids = [n["id"] for n in asset_nodes]
    for aid in asset_ids:
        for dep in rng.sample(asset_ids, rng.randint(0, 2)):
            if dep != aid:
                asset_edges.append({"source": aid, "target": dep, "type": "depends_on"})
    # governed_by: each asset governed by 1-2 policies
    policy_ids = [pid for pid, _, _ in POLICIES]
    for aid in asset_ids:
        for pol in rng.sample(policy_ids, rng.randint(1, 2)):
            asset_edges.append({"source": aid, "target": pol, "type": "governed_by"})
    _dump(out_dir / "assets.json", {"nodes": asset_nodes, "edges": asset_edges})

    # ---- controls (25) ----
    control_nodes: list[dict] = []
    control_edges: list[dict] = []
    for c, cname in enumerate(CONTROL_NAMES, start=1):
        cid = f"control:{c:04d}"
        control_nodes.append({"id": cid, "type": "Control", "name": cname})
        # each control mitigates 1-3 assets
        for asset in rng.sample(asset_ids, rng.randint(1, 3)):
            control_edges.append({"source": cid, "target": asset, "type": "mitigates"})
    # some assets carry an exception to a control (has_exception)
    control_ids = [n["id"] for n in control_nodes]
    for asset in rng.sample(asset_ids, 8):
        control_edges.append(
            {"source": asset, "target": rng.choice(control_ids), "type": "has_exception"}
        )
    _dump(out_dir / "controls.json", {"nodes": control_nodes, "edges": control_edges})

    # ---- historical findings (10) ----
    finding_nodes: list[dict] = []
    finding_edges: list[dict] = []
    sev = ["critical", "high", "medium", "low"]
    for f in range(1, 11):
        fid = f"finding:{f:04d}"
        target_asset = rng.choice(asset_ids)
        finding_nodes.append(
            {
                "id": fid,
                "type": "Finding",
                "name": f"Historical finding {f}",
                "severity": rng.choice(sev),
                "status": rng.choice(["open", "remediated", "accepted"]),
            }
        )
        finding_edges.append(
            {"source": fid, "target": rng.choice(control_ids), "type": "mitigates"}
        )
        finding_edges.append(
            {"source": target_asset, "target": fid, "type": "has_exception"}
        )
    _dump(out_dir / "findings.json", {"nodes": finding_nodes, "edges": finding_edges})

    # ---- policies (markdown) ----
    for pid_, title, summary in POLICIES:
        slug = pid_.split(":", 1)[1]
        (out_dir / "policies" / f"{slug}.md").write_text(
            f"---\nid: {pid_}\ntitle: {title}\ndomain: cyber\n---\n\n"
            f"# {title}\n\n> SYNTHETIC seed document.\n\n{summary}\n",
            encoding="utf-8",
        )

    (out_dir / "README.md").write_text(
        "# Synthetic organization (seed data)\n\n"
        "**All data in this directory is SYNTHETIC** — generated by "
        "`scripts/generate_org.py` for simulation. It does not describe any real "
        "organization or person.\n\n"
        "Files: org.json, assets.json, controls.json, "
        "findings.json, and policies/*.md.\n",
        encoding="utf-8",
    )

    total_people = len(people_nodes)
    print(
        f"Generated synthetic org at {out_dir}: {total_people} people, "
        f"{len(team_nodes)} teams, {len(asset_nodes)} assets, "
        f"{len(control_nodes)} controls, {len(finding_nodes)} findings, "
        f"{len(POLICIES)} policies, {len(ai_nodes)} AI copilots."
    )


def _dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="deterministic seed")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/synthetic_org"),
        help="output directory",
    )
    args = parser.parse_args()
    generate(args.seed, args.out)


if __name__ == "__main__":
    main()
