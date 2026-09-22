# SeatSafe visual learning pack

These files are editable Excalidraw sources, not flattened screenshots. Open a file in
Excalidraw, move or rewrite any element, and export it as PNG, SVG, or PDF.

Open `00-seatsafe-master-learning-pack.excalidraw` when you want every diagram on one
large canvas. The numbered individual files remain useful when you want a smaller canvas
or need to export only one topic.

## Diagram index

| File | What it teaches | Project truth represented |
|---|---|---|
| `00-seatsafe-master-learning-pack.excalidraw` | All seven diagrams on one large editable canvas | Same content as the individual files, arranged for panning and presentation |
| `01-decision-map.excalidraw` | How ADR-001 through ADR-012 relate | ADR-002 and ADR-012 are accepted; Phase 2 client implementation is starting |
| `02-backend-architecture.excalidraw` | The route → service → repository → PostgreSQL boundaries | Current backend read and hold paths; iOS is marked future |
| `03-seat-lifecycle-and-race.excalidraw` | Seat states and why row locking prevents a race | Competing hold requests, winner confirmation, and same-hold confirmation races are tested against PostgreSQL |
| `04-idempotency-flow.excalidraw` | Why retries need both idempotency and uniqueness | Implemented ADR-007 confirmation and exact-response replay flow |
| `05-quality-strategy.excalidraw` | Which test layer proves which behavior | Current 41-test checkpoint plus explicit non-claims |
| `06-learning-roadmap.excalidraw` | Why the project phases happen in this order | Phases 0 and 1 complete; ADR-002 and ADR-012 accepted; Phase 2 implementation is starting |
| `07-database-model.excalidraw` | How stable venue data connects to hold, reservation, and retry history | Current PostgreSQL schema and its important uniqueness boundaries |

## How to use the files

1. Open Excalidraw.
2. Choose **Open** and select one `.excalidraw` file.
3. Edit the shapes and words as needed.
4. Use **Export image** to create PNG or SVG, or print/export to PDF.

Keep the `.excalidraw` source in the repository after exporting. The source is what
makes future updates reviewable rather than forcing someone to redraw a flattened image.

## Junior-friendly legend

- **Accepted:** the owner agreed to the tradeoff and the ADR records it.
- **Proposed:** a recommendation exists, but it is not yet an approved project rule.
- **Implemented:** matching code and tests exist now.
- **Planned/future:** accepted or expected behavior that must not be presented as done.
- **Solid outline/arrow:** current or accepted.
- **Dashed outline/arrow:** proposed or future.

## The six ideas to be able to explain

1. A seat availability response is a snapshot, not a guarantee.
2. The application locks the stable `EventSeat` row before changing seat state.
3. PostgreSQL constraints remain the final protection against invalid committed data.
4. Idempotency gives one retried request a stable answer; uniqueness protects the seat.
5. Tests use different layers because a fake repository cannot prove a real database lock.
6. Deterministic clocks, identifiers, data, and environments make failures reproducible.

## Updating the diagrams

The diagrams are generated deterministically from:

```bash
python3 tools/generate_excalidraw_diagrams.py
```

After regeneration, review labels against `docs/decisions/`, `docs/roadmap.md`, and the
latest evidence documents. A diagram must never imply that proposed or planned work is
already implemented.
