"""Deterministic Markdown and static HTML renderers."""

from __future__ import annotations

import html
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Dict

from evidence_travel.model import Itinerary, by_id
from evidence_travel.validator import Issue, count_by_severity


def summary(issues: Sequence[Issue]) -> Dict[str, Any]:
    counts = count_by_severity(issues)
    return {
        "status": "invalid"
        if counts["error"]
        else "review"
        if counts["warning"]
        else "valid",
        "errors": counts["error"],
        "warnings": counts["warning"],
        "issues": [
            {
                "code": issue.code,
                "severity": issue.severity,
                "entity_id": issue.entity_id,
                "message": issue.message,
                "constraint": issue.constraint,
                "source_ids": list(issue.source_ids),
            }
            for issue in issues
        ],
    }


def render_markdown(itinerary: Itinerary, issues: Sequence[Issue]) -> str:
    result = summary(issues)
    sources = by_id(itinerary.sources)
    lines = [
        "# Itinerary validation report",
        "",
        f"**Status:** {str(result['status']).upper()}  ",
        f"**Errors:** {result['errors']}  ",
        f"**Warnings:** {result['warnings']}  ",
        f"**Planning snapshot:** {itinerary.planning_as_of.isoformat()}",
        "",
        "## Findings",
        "",
    ]
    if not issues:
        lines.append("No validation findings.")
    for issue in issues:
        lines.extend(
            [
                f"### [{issue.severity.upper()}] {issue.code} — `{issue.entity_id}`",
                "",
                issue.message,
                "",
                f"- Constraint: {issue.constraint}",
            ]
        )
        if issue.source_ids:
            lines.append("- Evidence:")
            for source_id in issue.source_ids:
                source = sources.get(source_id)
                reference = (
                    source.get("reference", "undefined") if source else "undefined"
                )
                lines.append(f"  - `{source_id}` — {reference}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_html(itinerary: Itinerary, issues: Sequence[Issue]) -> str:
    result = summary(issues)
    activities = sorted(
        itinerary.activities, key=lambda item: (str(item["start"]), str(item["id"]))
    )
    issue_cards = (
        "".join(
            "<article class='issue {severity}'><h3>{severity}: {code}</h3>"
            "<p><code>{entity}</code> — {message}</p><p><strong>Constraint:</strong> {constraint}</p>"
            "<p><strong>Evidence:</strong> {sources}</p></article>".format(
                severity=html.escape(issue.severity),
                code=html.escape(issue.code),
                entity=html.escape(issue.entity_id),
                message=html.escape(issue.message),
                constraint=html.escape(issue.constraint),
                sources=html.escape(", ".join(issue.source_ids) or "none"),
            )
            for issue in issues
        )
        or "<p>No validation findings.</p>"
    )
    timeline = "".join(
        "<li><time>{start}</time><div><strong>{name}</strong><br><small>{place}</small></div></li>".format(
            start=html.escape(str(item["start"])),
            name=html.escape(str(item["name"])),
            place=html.escape(str(item["place_id"])),
        )
        for item in activities
    )
    payload = html.escape(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Itinerary validation report</title>
  <style>
    :root {{ color-scheme: light; --ink:#172033; --muted:#667085; --paper:#f6f8fb; --card:#fff; --red:#b42318; --amber:#b54708; --line:#d0d5dd; }}
    body {{ margin:0; font:16px/1.55 system-ui,sans-serif; color:var(--ink); background:var(--paper); }}
    main {{ max-width:980px; margin:auto; padding:3rem 1.25rem 5rem; }}
    header {{ display:grid; grid-template-columns:1fr auto; gap:1rem; align-items:end; border-bottom:1px solid var(--line); }}
    .status {{ font-size:1.4rem; font-weight:800; text-transform:uppercase; }}
    .metrics {{ display:flex; gap:1rem; color:var(--muted); }}
    ol {{ list-style:none; padding:0; border-left:3px solid #6172f3; margin-left:.7rem; }}
    li {{ display:grid; grid-template-columns:minmax(13rem,auto) 1fr; gap:1rem; padding:0 0 1.4rem 1.2rem; position:relative; }}
    li::before {{ content:""; width:.65rem; height:.65rem; border-radius:50%; background:#6172f3; position:absolute; left:-.42rem; top:.35rem; }}
    time, small {{ color:var(--muted); }}
    .issue {{ background:var(--card); border:1px solid var(--line); border-left:5px solid; border-radius:.5rem; padding:1rem 1.2rem; margin:1rem 0; }}
    .issue.error {{ border-left-color:var(--red); }} .issue.warning {{ border-left-color:var(--amber); }}
    code {{ overflow-wrap:anywhere; }}
    @media (max-width:650px) {{ header, li {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body><main>
  <header><div><p>Evidence-first travel planner</p><h1>Validation report</h1></div><p class="status">{html.escape(str(result["status"]))}</p></header>
  <p class="metrics"><span>{result["errors"]} errors</span><span>{result["warnings"]} warnings</span></p>
  <section><h2>Timeline</h2><ol>{timeline}</ol></section>
  <section><h2>Explainable findings</h2>{issue_cards}</section>
  <script type="application/json" id="validation-summary">{payload}</script>
</main></body></html>"""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
