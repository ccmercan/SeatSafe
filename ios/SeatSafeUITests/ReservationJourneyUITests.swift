import XCTest

@MainActor
final class ReservationJourneyUITests: XCTestCase {
    func testAvailableSeatCanBeHeldAndConfirmed() {
        let app = XCUIApplication()
        app.launchArguments.append("--uitesting-reset-reservation-flow")
        app.launch()

        let seat = app.buttons["seat-row.00000000-0000-4000-8000-000000000040"]
        guard seat.waitForExistence(timeout: 15) else {
            XCTFail("The seeded seat list should load; accessibility tree: \(app.debugDescription)")
            return
        }
        XCTAssertTrue(seat.isHittable, "The seeded seat should be available to select")
        // SwiftUI's plain-style List row includes a spacer; tap the visible seat label,
        // not the empty middle of the row, so the synthesized touch hits its content.
        seat.coordinate(withNormalizedOffset: CGVector(dx: 0.2, dy: 0.5)).tap()
        let selectionApplied = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "value == %@", "Selected"), object: seat)
        XCTAssertEqual(
            XCTWaiter.wait(for: [selectionApplied], timeout: 5),
            .completed,
            "Tapping the available seat should update its selection state; accessibility tree: \(app.debugDescription)"
        )

        let holdButton = app.buttons["seat-selection.hold"]
        guard holdButton.waitForExistence(timeout: 5) else {
            XCTFail(
                "Selecting an available seat should show Hold; accessibility tree: \(app.debugDescription)"
            )
            return
        }
        holdButton.tap()

        let confirmButton = app.buttons["reservation.confirm"]
        guard confirmButton.waitForExistence(timeout: 5) else {
            XCTFail(
                "A successful hold should show Confirm; accessibility tree: \(app.debugDescription)"
            )
            return
        }
        let confirmButtonIsActionable = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "isHittable == true AND isEnabled == true"),
            object: confirmButton
        )
        XCTAssertEqual(XCTWaiter.wait(for: [confirmButtonIsActionable], timeout: 5), .completed)
        confirmButton.tap()

        let confirmation = app.staticTexts["reservation.confirmed"]
        let confirming = app.descendants(matching: .any)["reservation.confirming"]
        let confirmationStarted = XCTNSPredicateExpectation(
            predicate: NSPredicate { _, _ in confirmation.exists || confirming.exists },
            object: nil
        )
        XCTAssertEqual(
            XCTWaiter.wait(for: [confirmationStarted], timeout: 10),
            .completed,
            "Confirm should enter a confirming or confirmed state; accessibility tree: \(app.debugDescription)"
        )
        XCTAssertTrue(confirmation.waitForExistence(timeout: 10))
        let confirmationPrefix = "Reservation confirmed. ID: "
        XCTAssertTrue(confirmation.label.hasPrefix(confirmationPrefix))
        let reservationID = String(confirmation.label.dropFirst(confirmationPrefix.count))
        XCTAssertNotNil(
            UUID(uuidString: reservationID), "The displayed reservation ID should be a UUID")
    }
}
