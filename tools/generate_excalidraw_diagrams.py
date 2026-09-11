"""Generate editable Excalidraw teaching diagrams for SeatSafe.

The output intentionally uses only basic Excalidraw rectangles, text, and arrows so
the files remain easy to edit after import. Run this script whenever the documented
architecture changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "diagrams"

INK = "#1e1e1e"
MUTED = "#5f6368"
BLUE = "#a5d8ff"
GREEN = "#b2f2bb"
YELLOW = "#ffec99"
ORANGE = "#ffd8a8"
PURPLE = "#d0bfff"
RED = "#ffc9c9"
GRAY = "#e9ecef"
WHITE = "#ffffff"


@dataclass
class Drawing:
    elements: list[dict[str, Any]]
    counter: int = 0

    def _base(self, kind: str, x: float, y: float, width: float, height: float) -> dict[str, Any]:
        self.counter += 1
        return {
            "id": f"seatsafe-{self.counter}",
            "type": kind,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "angle": 0,
            "strokeColor": INK,
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 2,
            "strokeStyle": "solid",
            "roughness": 1,
            "opacity": 100,
            "groupIds": [],
            "frameId": None,
            "seed": 1000 + self.counter,
            "version": 1,
            "versionNonce": 5000 + self.counter,
            "isDeleted": False,
            "boundElements": None,
            "updated": 1,
            "link": None,
            "locked": False,
        }

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        fill: str = WHITE,
        stroke: str = INK,
        style: str = "solid",
        roughness: int = 1,
    ) -> None:
        item = self._base("rectangle", x, y, width, height)
        item.update(
            {
                "backgroundColor": fill,
                "strokeColor": stroke,
                "strokeStyle": style,
                "roughness": roughness,
                "roundness": {"type": 3},
            }
        )
        self.elements.append(item)

    def text(
        self,
        x: float,
        y: float,
        value: str,
        *,
        size: int = 20,
        color: str = INK,
        align: str = "left",
    ) -> None:
        lines = value.splitlines() or [""]
        width = max(len(line) for line in lines) * size * 0.56
        height = len(lines) * size * 1.25
        item = self._base("text", x, y, width, height)
        item.update(
            {
                "strokeColor": color,
                "fontSize": size,
                "fontFamily": 1,
                "text": value,
                "rawText": value,
                "textAlign": align,
                "verticalAlign": "top",
                "containerId": None,
                "originalText": value,
                "autoResize": True,
                "lineHeight": 1.25,
                "roughness": 0,
                "strokeWidth": 1,
            }
        )
        self.elements.append(item)

    def arrow(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        color: str = INK,
        style: str = "solid",
        start: str | None = None,
        end: str | None = "arrow",
    ) -> None:
        item = self._base("arrow", x1, y1, abs(x2 - x1), abs(y2 - y1))
        item.update(
            {
                "strokeColor": color,
                "strokeStyle": style,
                "points": [[0, 0], [x2 - x1, y2 - y1]],
                "lastCommittedPoint": None,
                "startBinding": None,
                "endBinding": None,
                "startArrowhead": start,
                "endArrowhead": end,
                "roundness": {"type": 2},
                "elbowed": False,
            }
        )
        self.elements.append(item)

    def card(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        title: str,
        body: str,
        *,
        fill: str = WHITE,
        style: str = "solid",
        title_size: int = 20,
        body_size: int = 16,
    ) -> None:
        self.rect(x, y, width, height, fill=fill, style=style)
        self.text(x + 18, y + 14, title, size=title_size)
        self.text(x + 18, y + 48, body, size=body_size, color=MUTED)


def document(elements: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://github.com/ccmercan/SeatSafe",
        "elements": elements,
        "appState": {"gridSize": 20, "viewBackgroundColor": WHITE},
        "files": {},
    }


def heading(drawing: Drawing, title: str, subtitle: str) -> None:
    drawing.text(60, 40, title, size=34)
    drawing.text(60, 90, subtitle, size=18, color=MUTED)


def decision_map() -> list[dict[str, Any]]:
    d = Drawing([])
    heading(
        d,
        "SeatSafe decision map",
        "ADR = a written record of why an important choice was made. Solid = accepted; dashed = proposed.",
    )

    groups = [
        (40, 150, 350, 730, "Product and client", BLUE),
        (420, 150, 350, 730, "Correctness and data", RED),
        (800, 150, 350, 730, "Architecture and API", PURPLE),
        (1180, 150, 350, 730, "Testing and runtime", GREEN),
    ]
    for x, y, width, height, title, color in groups:
        d.rect(x, y, width, height, fill=color, stroke=MUTED, roughness=0)
        d.text(x + 18, y + 14, title, size=24)

    d.card(65, 210, 300, 130, "ADR-001 · Accepted", "Own a small FastAPI backend\nfor deterministic behavior", fill=WHITE)
    d.card(
        65,
        375,
        300,
        155,
        "ADR-002 · Proposed",
        "Use Swift structured concurrency\nand main-actor UI state\n(not accepted or built yet)",
        fill=YELLOW,
        style="dashed",
    )

    d.card(445, 210, 300, 135, "ADR-003 · Accepted", "Serialize seat changes with\nrow locks + constraints", fill=WHITE)
    d.card(445, 380, 300, 135, "ADR-006 · Accepted", "Keep EventSeat, SeatHold, and\nReservation as separate records", fill=WHITE)
    d.card(445, 550, 300, 150, "ADR-007 · Accepted", "Store idempotency results so\nsafe retries get the same answer\n(not implemented yet)", fill=WHITE)

    d.card(825, 210, 300, 135, "ADR-005 · Accepted", "Thin HTTP routes → services →\nPostgreSQL repositories", fill=WHITE)
    d.card(825, 380, 300, 135, "ADR-008 · Accepted", "Inject one server-configured\ndemo user in Phase 1", fill=WHITE)
    d.card(825, 550, 300, 135, "ADR-009 · Accepted", "Use Problem Details + stable\nerror and correlation codes", fill=WHITE)
    d.card(825, 720, 300, 135, "ADR-011 · Accepted", "Return one ordered seat-status\nsnapshot per event", fill=WHITE)

    d.card(1205, 210, 300, 150, "ADR-004 · Accepted", "Disposable PostgreSQL + direct,\nguarded reset/seed fixtures", fill=WHITE)
    d.card(1205, 410, 300, 150, "ADR-010 · Accepted", "Docker Desktop runs the local\nPostgreSQL container", fill=WHITE)

    d.arrow(365, 275, 445, 275)
    d.arrow(745, 278, 825, 278)
    d.arrow(595, 345, 595, 380)
    d.arrow(595, 515, 595, 550)
    d.arrow(1125, 278, 1205, 278)
    d.arrow(1355, 360, 1355, 410)
    d.arrow(745, 618, 825, 618)
    d.arrow(975, 685, 975, 720)
    d.text(50, 920, "How to read this: follow arrows to see which decisions support later decisions.", size=18, color=MUTED)
    return d.elements


def backend_architecture() -> list[dict[str, Any]]:
    d = Drawing([])
    heading(
        d,
        "SeatSafe system design — current backend",
        "Blue path reads a snapshot. Red path changes inventory inside a short transaction.",
    )

    d.card(60, 180, 260, 130, "Future iOS client", "Phase 2 — not built yet\nMust handle stale snapshots", fill=GRAY, style="dashed")
    d.card(390, 180, 260, 130, "FastAPI routes", "Validate HTTP input\nMap domain errors to HTTP", fill=BLUE)
    d.card(720, 180, 300, 130, "Application services", "Coordinate one use case\nOwn business decisions", fill=PURPLE)
    d.card(1090, 180, 300, 130, "Repositories", "Express purpose-specific SQL\nHide persistence mechanics", fill=ORANGE)
    d.card(1460, 180, 260, 130, "PostgreSQL 17", "Authoritative state\nConstraints protect invariants", fill=GREEN)

    d.arrow(320, 245, 390, 245, style="dashed")
    d.arrow(650, 225, 720, 225, color="#1971c2")
    d.arrow(1020, 225, 1090, 225, color="#1971c2")
    d.arrow(1390, 225, 1460, 225, color="#1971c2")
    d.text(688, 145, "GET /events/{id}/seats", size=16, color="#1971c2")

    d.arrow(650, 280, 720, 280, color="#c92a2a")
    d.arrow(1020, 280, 1090, 280, color="#c92a2a")
    d.arrow(1390, 280, 1460, 280, color="#c92a2a")
    d.text(690, 322, "POST /holds", size=16, color="#c92a2a")

    d.card(720, 410, 300, 120, "Injected boundaries", "Clock · ID factory · CurrentUser\nTests replace these deterministically", fill=YELLOW)
    d.arrow(870, 410, 870, 310)

    d.card(390, 410, 260, 120, "Cross-cutting HTTP", "Correlation ID middleware\nRFC 9457 Problem Details", fill=GRAY)
    d.arrow(520, 410, 520, 310)

    d.card(1090, 410, 300, 120, "Hold unit of work", "One transaction wraps lock,\nchecks, state change, and commit", fill=RED)
    d.arrow(1240, 410, 1240, 310, color="#c92a2a")

    d.card(1460, 410, 260, 120, "Database protection", "FOR UPDATE row lock\nPartial unique indexes", fill=GREEN)
    d.arrow(1590, 410, 1590, 310)

    d.rect(380, 610, 1350, 240, fill=WHITE, stroke=MUTED, roughness=0)
    d.text(410, 630, "Junior mental model", size=24)
    d.text(
        410,
        680,
        "Route = receptionist: understands HTTP.\n"
        "Service = coordinator: decides the order of the business steps.\n"
        "Repository = database translator: turns those steps into SQL.\n"
        "PostgreSQL = final authority: locks and constraints prevent impossible committed states.\n"
        "A GET response says what was observed; only POST /holds attempts to claim the seat.",
        size=19,
        color=MUTED,
    )
    return d.elements


def lifecycle_and_race() -> list[dict[str, Any]]:
    d = Drawing([])
    heading(
        d,
        "Seat lifecycle and the double-booking race",
        "The lifecycle explains state; the race explains why a normal read-then-write check is unsafe.",
    )

    states = [
        (80, 190, "Available", GREEN),
        (390, 190, "Held", YELLOW),
        (700, 190, "Reserved", PURPLE),
        (1010, 190, "Cancelled", GRAY),
    ]
    for x, y, label, fill in states:
        d.card(x, y, 220, 100, label, "Stored history remains", fill=fill)
    d.arrow(300, 240, 390, 240)
    d.text(310, 205, "create hold", size=15)
    d.arrow(610, 240, 700, 240)
    d.text(620, 205, "confirm", size=15)
    d.arrow(920, 240, 1010, 240)
    d.text(930, 205, "cancel", size=15)
    d.card(390, 350, 220, 100, "Expired", "Old hold stays as history", fill=ORANGE)
    d.arrow(500, 290, 500, 350)
    d.arrow(390, 400, 300, 280)
    d.text(520, 315, "clock reaches expiry", size=15)
    d.text(165, 365, "another user may hold", size=15)

    d.text(80, 520, "Two users try the same seat", size=28)
    d.card(80, 590, 260, 115, "Alice transaction", "1. Lock EventSeat\n2. Check state\n3. Create hold", fill=BLUE)
    d.card(80, 760, 260, 115, "Bob transaction", "1. Wait for same lock\n2. Re-check after Alice\n3. Receive conflict", fill=RED)
    d.card(470, 650, 280, 150, "EventSeat row lock", "Only one transaction enters the\ncritical section at a time.\nKeep this section short.", fill=YELLOW)
    d.card(880, 650, 300, 150, "Database constraints", "Final safety net:\n≤ 1 active hold\n≤ 1 active reservation", fill=GREEN)
    d.card(1310, 650, 300, 150, "Observable outcome", "Winner: 201 Created\nLoser: 409 seat_unavailable\nNever: two active bookings", fill=PURPLE)
    d.arrow(340, 647, 470, 690, color="#1971c2")
    d.arrow(340, 817, 470, 760, color="#c92a2a")
    d.arrow(750, 725, 880, 725)
    d.arrow(1180, 725, 1310, 725)

    d.text(
        80,
        930,
        "Implemented now: lock-based hold creation and database constraints. Still required: controlled simultaneous-request proof and confirmation flow.",
        size=18,
        color=MUTED,
    )
    return d.elements


def idempotency_flow() -> list[dict[str, Any]]:
    d = Drawing([])
    heading(
        d,
        "Reservation confirmation and idempotency",
        "Accepted design from ADR-007. This flow is planned next; it is not implemented yet.",
    )

    d.card(70, 190, 270, 140, "Client", "Hold H1\nIdempotency key K1\nPOST /reservations", fill=BLUE)
    d.card(430, 190, 300, 140, "Confirmation service", "Fingerprint relevant input\nStart one transaction", fill=PURPLE)
    d.card(820, 150, 330, 140, "Key lookup", "Scope: owner + operation + K1\nCompare stored fingerprint", fill=YELLOW)
    d.card(820, 360, 330, 160, "Seat transition", "Lock EventSeat\nValidate owner + hold expiry\nCreate Reservation", fill=RED)
    d.card(1240, 250, 340, 180, "Atomic PostgreSQL commit", "Reservation + completed\nidempotency record commit together\nor both roll back", fill=GREEN)
    d.arrow(340, 260, 430, 260)
    d.arrow(730, 240, 820, 220)
    d.arrow(730, 285, 820, 420)
    d.arrow(1150, 220, 1240, 300)
    d.arrow(1150, 440, 1240, 380)

    d.card(80, 650, 330, 150, "Same K1 + same input", "Return the original reservation.\nDo not create new work.", fill=GREEN)
    d.card(500, 650, 330, 150, "Same K1 + changed input", "Reject idempotency_key_reused.\nA receipt cannot mean two things.", fill=ORANGE)
    d.card(920, 650, 330, 150, "Different key, same seat", "Seat lock + active-reservation\nconstraint choose one winner.", fill=RED)
    d.card(1340, 650, 330, 150, "Response was lost", "Client retries with K1 and gets\nthe stable original result.", fill=BLUE)

    d.text(
        80,
        865,
        "Junior distinction: uniqueness protects the seat; idempotency protects the meaning and answer of one logical request.",
        size=20,
        color=MUTED,
    )
    return d.elements


def quality_strategy() -> list[dict[str, Any]]:
    d = Drawing([])
    heading(
        d,
        "SeatSafe quality strategy",
        "Test behavior at the lowest useful layer; use PostgreSQL and UI tests only where their realism adds evidence.",
    )

    d.card(80, 190, 340, 130, "Unit / service tests", "Fast · deterministic\nRules, boundaries, clocks, IDs", fill=GREEN)
    d.card(510, 190, 340, 130, "API contract tests", "HTTP status and schema\nProblem codes + correlation IDs", fill=BLUE)
    d.card(940, 190, 340, 130, "PostgreSQL integration", "Migrations · SQL · locks\nconstraints · committed visibility", fill=ORANGE)
    d.card(1370, 190, 340, 130, "XCUITest journeys", "Few critical user flows\nreal accessibility + diagnostics", fill=PURPLE, style="dashed")
    d.text(1430, 330, "Phase 3 — future", size=16, color=MUTED)

    d.arrow(420, 255, 510, 255)
    d.arrow(850, 255, 940, 255)
    d.arrow(1280, 255, 1370, 255, style="dashed")
    d.text(500, 135, "slower + more realistic →", size=18, color=MUTED)

    d.card(80, 470, 340, 180, "Deterministic inputs", "Fixed UUIDs\nInjected clock and ID factory\nControlled fakes\nNo arbitrary sleeps", fill=YELLOW)
    d.card(510, 470, 340, 180, "Disposable environment", "Pinned PostgreSQL container\nProduction migrations\nGuarded direct reset + seed\nTeardown removes data", fill=GREEN)
    d.card(940, 470, 340, 180, "Useful failure evidence", "Stable error codes\nCorrelation identifiers\nTest layer shows fault location\nNo blind retries", fill=BLUE)
    d.card(1370, 470, 340, 180, "Risk-to-test matching", "Race → real PostgreSQL\nRule → service test\nHTTP mapping → API test\nJourney → UI smoke test", fill=PURPLE)

    d.rect(80, 750, 1630, 160, fill=WHITE, stroke=MUTED, roughness=0)
    d.text(110, 775, "What the current green suite proves", size=24)
    d.text(
        110,
        825,
        "28 tests passed at the seat-retrieval checkpoint. They prove current rules, API contracts, migrations, constraints, deterministic seed behavior, and repository queries.\nThey do not yet prove simultaneous-request behavior, reservation confirmation, iOS behavior, CI behavior, performance, or production scale.",
        size=18,
        color=MUTED,
    )
    return d.elements


def roadmap() -> list[dict[str, Any]]:
    d = Drawing([])
    heading(
        d,
        "SeatSafe learning roadmap",
        "Each phase ends with evidence, not just more code. The current focus is finishing the reservation core.",
    )
    phases = [
        (60, 220, "Phase 0", "Foundation\ncomplete", GREEN, "Accepted ADR-001\nrequirements + risks"),
        (310, 220, "Phase 1", "Reservation core\nin progress", YELLOW, "Seats + holds built\nconfirmation + race next"),
        (560, 220, "Phase 2", "Native iOS\nfuture", GRAY, "SwiftUI flow\ncontrolled async state"),
        (810, 220, "Phase 3", "UI automation\nfuture", GRAY, "Stable identifiers\ndeterministic scenarios"),
        (1060, 220, "Phase 4", "CI signals\nfuture", GRAY, "PR gates\nretained diagnostics"),
        (1310, 220, "Phase 5", "Quality depth\nfuture", GRAY, "Offline · accessibility\nperformance baselines"),
        (1560, 220, "Phase 6", "Portfolio release\nfuture", GRAY, "Case studies\ndiagrams + demo"),
    ]
    for index, (x, y, phase, label, fill, body) in enumerate(phases):
        d.card(x, y, 205, 180, f"{phase} · {label}", body, fill=fill, style="solid" if index < 2 else "dashed", title_size=19, body_size=16)
        if index < len(phases) - 1:
            d.arrow(x + 205, y + 90, x + 250, y + 90, style="solid" if index == 0 else "dashed")

    d.card(310, 520, 455, 240, "Phase 1 exit condition", "Automated concurrent test proves:\n\n• competing requests target one seat\n• exactly one logical winner\n• loser receives defined conflict\n• database contains at most one active reservation", fill=RED)
    d.arrow(412, 400, 412, 520)
    d.card(900, 520, 455, 240, "Why this order matters", "Backend correctness comes before UI polish.\nThe iOS client can be tested against a stable\ncontract instead of guessing unfinished behavior.\nCI arrives after meaningful checks exist.", fill=BLUE)
    d.card(1490, 520, 340, 240, "Learning loop", "Explain → compare → decide\n→ build → verify → reflect\n→ defend in an interview", fill=PURPLE)
    return d.elements


def data_model() -> list[dict[str, Any]]:
    d = Drawing([])
    heading(
        d,
        "SeatSafe database model",
        "Stable things describe the venue; lifecycle records preserve what happened over time.",
    )

    d.card(70, 180, 280, 130, "User", "id\ndisplay_name", fill=BLUE)
    d.card(70, 420, 280, 130, "Venue", "id\nname", fill=BLUE)
    d.card(450, 350, 300, 150, "Event", "id · venue_id\ntitle · starts_at", fill=PURPLE)
    d.card(450, 590, 300, 170, "Seat", "id · venue_id\nsection · row_label\nseat_number", fill=PURPLE)
    d.card(850, 450, 320, 170, "EventSeat", "id · event_id · seat_id\nprice_cents\nLOCK THIS stable row", fill=YELLOW)
    d.card(1270, 250, 330, 190, "SeatHold", "id · event_seat_id · owner_id\nstatus · created_at · expires_at\n≤ 1 active per EventSeat", fill=ORANGE)
    d.card(1270, 560, 330, 200, "Reservation", "id · event_seat_id · hold_id\nowner_id · status · confirmed_at\ncancelled_at\n≤ 1 active per EventSeat", fill=GREEN)
    d.card(1700, 405, 350, 210, "IdempotencyRecord", "owner_id · operation · key\nrequest fingerprint\nresponse status + body\nreservation_id · completed_at\nunique scoped key", fill=GRAY)

    d.arrow(350, 475, 450, 425)
    d.text(355, 430, "hosts", size=15)
    d.arrow(350, 505, 450, 650)
    d.text(355, 555, "contains", size=15)
    d.arrow(750, 425, 850, 500)
    d.text(770, 430, "event", size=15)
    d.arrow(750, 650, 850, 570)
    d.text(770, 610, "physical seat", size=15)
    d.arrow(1170, 500, 1270, 350)
    d.text(1175, 390, "temporary claims", size=15)
    d.arrow(1170, 570, 1270, 650)
    d.text(1175, 610, "confirmed result", size=15)
    d.arrow(350, 245, 1270, 300, style="dashed")
    d.text(700, 255, "owns holds and reservations", size=15)
    d.arrow(1600, 650, 1700, 540)
    d.text(1605, 585, "stable retry result", size=15)
    d.arrow(1435, 440, 1435, 560)
    d.text(1450, 485, "one hold can create\nat most one reservation", size=15)

    d.rect(70, 840, 1980, 150, fill=WHITE, stroke=MUTED, roughness=0)
    d.text(100, 865, "Junior mental model", size=24)
    d.text(
        100,
        915,
        "Venue, Event, Seat, and EventSeat describe what exists. SeatHold and Reservation describe actions over time. We update statuses instead of deleting history.\nEventSeat is the shared coordination point: competing transactions lock the same stable row before changing related lifecycle records.",
        size=18,
        color=MUTED,
    )
    return d.elements


def master_learning_pack() -> list[dict[str, Any]]:
    """Place every teaching diagram on one large canvas with unique element IDs."""

    panels = [
        (decision_map, 0, 0),
        (backend_architecture, 2200, 0),
        (lifecycle_and_race, 0, 1200),
        (idempotency_flow, 2200, 1200),
        (quality_strategy, 0, 2400),
        (roadmap, 2200, 2400),
        (data_model, 0, 3600),
    ]
    combined: list[dict[str, Any]] = []
    next_id = 0
    for build, offset_x, offset_y in panels:
        for element in build():
            next_id += 1
            translated = element.copy()
            translated["id"] = f"seatsafe-master-{next_id}"
            translated["x"] += offset_x
            translated["y"] += offset_y
            translated["seed"] = 20000 + next_id
            translated["versionNonce"] = 30000 + next_id
            combined.append(translated)
    return combined


DIAGRAMS = {
    "00-seatsafe-master-learning-pack.excalidraw": master_learning_pack,
    "01-decision-map.excalidraw": decision_map,
    "02-backend-architecture.excalidraw": backend_architecture,
    "03-seat-lifecycle-and-race.excalidraw": lifecycle_and_race,
    "04-idempotency-flow.excalidraw": idempotency_flow,
    "05-quality-strategy.excalidraw": quality_strategy,
    "06-learning-roadmap.excalidraw": roadmap,
    "07-database-model.excalidraw": data_model,
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, build in DIAGRAMS.items():
        target = OUTPUT / filename
        target.write_text(json.dumps(document(build()), indent=2) + "\n", encoding="utf-8")
        print(f"generated {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
