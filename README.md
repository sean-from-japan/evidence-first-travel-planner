# Evidence-First Travel Planner

[![CI](https://github.com/sean-from-japan/evidence-first-travel-planner/actions/workflows/ci.yml/badge.svg)](https://github.com/sean-from-japan/evidence-first-travel-planner/actions/workflows/ci.yml)

Travel research becomes fragile when facts lose their provenance and opening times, bookings, transfers, and fallback conditions are checked only mentally. Evidence-First Travel Planner is a deterministic Python CLI that keeps those facts attached to their sources and turns contradictions into explainable findings.

The project demonstrates evidence modelling, freshness policies, time-zone-aware constraint validation, privacy-preserving generalization, deterministic reports, and tests at rule, CLI, schema, and end-to-end levels.

## Honest origin

I independently researched, planned, and completed travel in roughly fifteen European countries outside the UK during a university exchange. The recurring workflow was to find official and local sources, compare multilingual evidence, preserve provenance, translate constraints into Japanese action steps, and keep alternatives for uncertain legs.

This software was built **after** that travel. It did not power the historical trips. The committed demonstration is entirely synthetic and does not reproduce, redact, or encode a real itinerary.

## Run the demo

Python 3.9 or newer is supported. The runtime has no third-party dependencies and the demo performs no network access.

```bash
python -m pip install -e .
evidence-travel demo --output-dir build/demo
```

The fixture deliberately contains valid decisions and contradictions, so the command exits with code `2` and writes:

- `build/demo/report.md` — recruiter-readable explanations;
- `build/demo/report.html` — a dependency-free responsive timeline;
- `build/demo/summary.json` — stable machine-readable output.

Exit codes are part of the CLI contract: `0` no findings, `2` validation findings, `3` invalid input, and `4` unexpected internal failure.

## What it validates

Each warning or error names the affected entity, the violated constraint, and the evidence identifiers involved.

| Rule | Why it matters |
|---|---|
| Missing or stale evidence | A correct fact can become unsafe after a timetable or policy change. |
| Closed activity | The whole visit must fit a local opening window; closure dates win. |
| Impossible transfer | Duration and minimum connection time must fit both transfer and activity deadlines. |
| Overlapping reservations | Confirmed half-open reservation intervals must not overlap. |
| Missing required booking | A required activity must resolve to a confirmed reservation. |
| Geographic inconsistency | Place changes require a transfer and declared distance cannot beat the great-circle lower bound. |
| Fragile dependency without fallback | Weather- or service-sensitive plans need an explicit activation condition and action. |
| Conflicting facts | Sources that disagree stay visible instead of being averaged into false certainty. |

Opening windows also support overnight service, and all event timestamps require explicit UTC offsets plus an itinerary-level IANA time zone.

## Data model

The versioned [JSON Schema](schemas/itinerary.schema.json) documents:

- activities, places, required/optional status, opening windows, and closures;
- evidence reference or URL, publisher/type, checked-at time, freshness policy, verification status, and categorical confidence;
- reservations, deadlines, confirmation state, and cancellation constraints;
- transfers, departure/arrival bounds, duration, connection buffer, distance, and mode;
- fragile dependencies, fallback actions, and activation conditions;
- source facts that can be checked for unresolved disagreement.

```json
{
  "id": "activity_museum",
  "place_id": "place_museum",
  "start": "2032-05-03T09:00:00+02:00",
  "end": "2032-05-03T10:00:00+02:00",
  "booking_required": true,
  "source_ids": ["src_city_museum"]
}
```

Confidence is categorical (`high`, `medium`, `low`, `unknown`). The tool does not invent decimal probabilities that the evidence cannot support.

## Architecture

```text
versioned JSON -> structural parser -> local-time normalization
                                      |
                                      v
                              pure rule engine
                         / evidence / time / geo /
                                      |
                                      v
                           Markdown + HTML + JSON
```

The core model and rule engine are deterministic and offline. Live Maps or search support belongs behind the protocols in [`adapters.py`](src/evidence_travel/adapters.py). Provider results must enter as timestamped evidence; adapters cannot silently override a human-reviewed constraint. Tests can replace those protocols with simple fakes without an API key, paid service, account, browser, or network.

See [architecture and rule semantics](docs/architecture.md) for interval and transfer definitions.

## Engineering decisions

- **Standard library at runtime:** installation and the committed demo remain small and offline. A validation library could enforce more JSON Schema keywords, but the core loader intentionally checks the invariants it consumes while publishing the complete interchange schema separately.
- **Immutable findings:** rules return sorted values, which keeps reports and automation stable.
- **Explain, do not auto-repair:** choosing between conflicting sources or changing a booking is a human decision.
- **Straight-line lower bound:** geographic validation catches impossible declarations without pretending to provide live routing.
- **Static HTML:** one portable file is easier to inspect and archive than a hosted dashboard.

## Development and verification

Development tools are exactly pinned in `pyproject.toml`.

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy src
pytest
python scripts/audit_repository.py . --git-history
```

Tests include closing-time and overnight boundaries, independent minute-set and epoch-arithmetic oracles for interval and transfer logic, deterministic output ordering, CLI exit codes, schema structure, and the full fictional demo. GitHub Actions runs on Linux, macOS, and Windows, with the supported Python range sampled from 3.9 through 3.13.

## Privacy model

This is an original tool, not a sanitized travel archive. It contains fictional place names, synthetic coordinates and times, invented source descriptions, reserved example domains, and newly authored diagrams and wording. It excludes real schedules, reservations, tickets, messages, identity documents, addresses, exact location history, financial records, photos, private links, private repository history, and third-party prose.

The repository audit scans both the working tree and Git blobs for likely secrets, contact details, local paths, identifiers, and booking references. That is defense in depth, not proof that arbitrary future contributions are safe; every new fixture still needs human review.

## Limitations

- The built-in loader validates consumed structural invariants, not every JSON Schema keyword.
- Opening windows do not model exceptional holiday calendars beyond explicit closure dates.
- The geographic rule is a lower-bound sanity check, not route planning.
- Live provider adapters are interfaces only; no vendor implementation is shipped.
- Conflicts are detected by exact fact keys and values; semantic equivalence still needs human review.
- The validator reports contradictions but never books, cancels, purchases, or edits a trip.

## License

All repository code, fixtures, diagrams, and prose were newly authored for this project. They are available under the [MIT License](LICENSE).

