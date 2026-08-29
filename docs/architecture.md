# Architecture and rule semantics

The core accepts a versioned JSON document and produces a sorted list of immutable findings. It performs no network access.

```text
JSON input -> parser / structural checks -> normalized local times
                                      |
                                      v
                         deterministic rule engine
                         /        |          \
                  evidence     schedule     geography
                         \        |          /
                                      v
                         Markdown / HTML / JSON
```

Provider-specific route and place lookup belongs behind the protocols in `adapters.py`. An adapter may create a source observation, but it must not silently mutate the itinerary or bypass freshness rules.

Intervals are half-open: `[start, end)`. Reservations that touch at one boundary do not overlap. Opening windows require the whole activity interval to fit. A closing time equal to or earlier than the opening time represents an overnight window. Transfers use the later of the preceding activity end and `depart_after`, then require arrival before both `arrive_by` and the next activity's connection-adjusted start.

Confidence is categorical because the tool cannot justify fake numeric probabilities. Conflicting facts remain visible until a human resolves them.

