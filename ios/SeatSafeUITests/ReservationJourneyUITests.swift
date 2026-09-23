import XCTest

@MainActor
final class ReservationJourneyUITests: XCTestCase {
    private struct CompetingHoldRequest: Encodable {
        let eventSeatID: UUID

        enum CodingKeys: String, CodingKey {
            case eventSeatID = "event_seat_id"
        }
    }

    private struct SeatAvailabilitySnapshot: Decodable {
        struct Seat: Decodable {
            let eventSeatID: UUID
            let status: String

            enum CodingKeys: String, CodingKey {
                case eventSeatID = "event_seat_id"
                case status
            }
        }

        let seats: [Seat]
    }

    override func tearDownWithError() throws {
        if (testRun?.failureCount ?? 0) > 0 {
            let imageData = MainActor.assumeIsolated {
                XCUIScreen.main.screenshot().image.jpegData(compressionQuality: 0.8)
            }
            if let imageData {
                let screenshot = XCTAttachment(
                    data: imageData, uniformTypeIdentifier: "public.jpeg")
                screenshot.name = "\(name)-failure-screenshot"
                screenshot.lifetime = .keepAlways
                add(screenshot)
            }
        }

        try super.tearDownWithError()
    }

    func testAvailableSeatCanBeHeldAndConfirmed() {
        let app = XCUIApplication()
        app.launchArguments.append("--uitesting-reset-reservation-flow")
        app.launch()

        let seatID = UUID(uuidString: "00000000-0000-4000-8000-000000000040")!
        let seat = app.buttons["seat-row.\(seatID.uuidString.lowercased())"]
        guard seat.waitForExistence(timeout: 15) else {
            XCTFail("The seeded seat list should load; accessibility tree: \(app.debugDescription)")
            return
        }
        XCTAssertTrue(seat.isHittable, "The seeded seat should be available to select")
        let seatTitle = app.staticTexts["seat-row-title.\(seatID.uuidString.lowercased())"]
        guard seatTitle.waitForExistence(timeout: 5), seatTitle.isHittable else {
            XCTFail(
                "The seat's accessible title should be hittable; accessibility tree: \(app.debugDescription)"
            )
            return
        }
        seat.tap()
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

        let createdHold = app.staticTexts["seat-selection.created"]
        guard createdHold.waitForExistence(timeout: 15) else {
            XCTFail(
                "A successful hold should publish its created state; accessibility tree: \(app.debugDescription)"
            )
            return
        }

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

    func testSelectedSeatConflictIsShownAndAvailabilityIsRefreshed() async throws {
        let app = XCUIApplication()
        app.launchArguments.append("--uitesting-reset-reservation-flow")
        app.launch()

        let conflictSeatID = UUID(uuidString: "00000000-0000-4000-8000-000000000041")!
        let seat = app.buttons["seat-row.\(conflictSeatID.uuidString.lowercased())"]
        guard seat.waitForExistence(timeout: 15) else {
            XCTFail(
                "The seeded conflict seat should load; accessibility tree: \(app.debugDescription)")
            return
        }
        guard seat.isEnabled else {
            XCTFail("The conflict seat should initially be available")
            return
        }
        let seatTitle = app.staticTexts["seat-row-title.\(conflictSeatID.uuidString.lowercased())"]
        guard seatTitle.waitForExistence(timeout: 5), seatTitle.isHittable else {
            XCTFail(
                "The conflict seat's accessible title should be hittable; accessibility tree: \(app.debugDescription)"
            )
            return
        }
        seat.tap()

        let selectionApplied = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "value == %@", "Selected"), object: seat)
        guard await XCTWaiter.fulfillment(of: [selectionApplied], timeout: 5) == .completed else {
            XCTFail(
                "The conflict seat should become selected; accessibility tree: \(app.debugDescription)"
            )
            return
        }

        // Simulate another client winning after this app loaded its availability snapshot.
        let competingStatus = try await createCompetingHold(for: conflictSeatID)
        guard competingStatus == 201 else {
            XCTFail(
                "The competing client should acquire the seat first; got HTTP \(competingStatus)")
            return
        }
        XCTAssertTrue(seat.isEnabled, "The app should still hold its deliberately stale snapshot")

        let holdButton = app.buttons["seat-selection.hold"]
        guard holdButton.waitForExistence(timeout: 5) else {
            XCTFail(
                "Selecting the available seat should show Hold; accessibility tree: \(app.debugDescription)"
            )
            return
        }
        holdButton.tap()

        let unavailable = app.staticTexts["seat-selection.unavailable"]
        guard unavailable.waitForExistence(timeout: 5) else {
            XCTFail(
                "The app should explain that the seat is unavailable; accessibility tree: \(app.debugDescription)"
            )
            return
        }

        let refreshedSeat = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "label CONTAINS %@", ", held,"), object: seat)
        let refreshResult = await XCTWaiter.fulfillment(of: [refreshedSeat], timeout: 5)
        XCTAssertEqual(
            refreshResult,
            .completed,
            "The app should refresh the stale seat after the server rejects the hold; accessibility tree: \(app.debugDescription)"
        )
        XCTAssertFalse(seat.isEnabled, "A refreshed held seat must no longer be selectable")
    }

    func testExpiredHoldCannotBeConfirmed() async throws {
        let app = XCUIApplication()
        app.launchArguments.append("--uitesting-reset-reservation-flow")
        app.launch()

        let eventID = UUID(uuidString: "00000000-0000-4000-8000-000000000020")!
        let seatID = UUID(uuidString: "00000000-0000-4000-8000-000000000040")!
        let seat = app.buttons["seat-row.\(seatID.uuidString.lowercased())"]
        guard seat.waitForExistence(timeout: 15) else {
            XCTFail(
                "The seeded expiration seat should load; accessibility tree: \(app.debugDescription)"
            )
            return
        }
        guard seat.isEnabled else {
            XCTFail("The expiration seat should initially be available")
            return
        }
        let seatTitle = app.staticTexts["seat-row-title.\(seatID.uuidString.lowercased())"]
        guard seatTitle.waitForExistence(timeout: 5), seatTitle.isHittable else {
            XCTFail(
                "The expiration seat's accessible title should be hittable; accessibility tree: \(app.debugDescription)"
            )
            return
        }
        seat.tap()

        let selectionApplied = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "value == %@", "Selected"), object: seat)
        guard await XCTWaiter.fulfillment(of: [selectionApplied], timeout: 5) == .completed else {
            XCTFail(
                "The expiration seat should become selected; accessibility tree: \(app.debugDescription)"
            )
            return
        }

        let holdButton = app.buttons["seat-selection.hold"]
        guard holdButton.waitForExistence(timeout: 5), holdButton.isHittable, holdButton.isEnabled
        else {
            XCTFail(
                "Selecting the available seat should show Hold; accessibility tree: \(app.debugDescription)"
            )
            return
        }
        holdButton.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()

        let creatingHold = app.descendants(matching: .any)["seat-selection.creating"]
        let createdHold = app.staticTexts["seat-selection.created"]
        let holdAttemptStarted = XCTNSPredicateExpectation(
            predicate: NSPredicate { _, _ in creatingHold.exists || createdHold.exists },
            object: nil
        )
        guard await XCTWaiter.fulfillment(of: [holdAttemptStarted], timeout: 5) == .completed else {
            XCTFail(
                "Tapping Hold should start the request; accessibility tree: \(app.debugDescription)"
            )
            return
        }
        guard createdHold.waitForExistence(timeout: 15) else {
            XCTFail(
                "The server should create the temporary hold; accessibility tree: \(app.debugDescription)"
            )
            return
        }

        // Wait for the server's real clock to report expiry instead of guessing with a timer.
        guard
            try await waitForSeat(
                eventID: eventID, seatID: seatID, status: "available", timeout: .seconds(20))
        else {
            XCTFail("The hold did not expire within the configured test window")
            return
        }

        let confirmButton = app.buttons["reservation.confirm"]
        guard confirmButton.waitForExistence(timeout: 5) else {
            XCTFail(
                "The app should still offer confirmation until the server rejects the expired hold")
            return
        }
        confirmButton.tap()

        let expired = app.staticTexts["reservation.expired"]
        guard expired.waitForExistence(timeout: 10) else {
            XCTFail(
                "The app should explain that confirmation arrived after expiry; accessibility tree: \(app.debugDescription)"
            )
            return
        }

        let refreshedSeat = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "label CONTAINS %@", ", available,"), object: seat)
        let refreshResult = await XCTWaiter.fulfillment(of: [refreshedSeat], timeout: 5)
        XCTAssertEqual(
            refreshResult,
            .completed,
            "After expiry, the app should refresh the seat as available; accessibility tree: \(app.debugDescription)"
        )
        XCTAssertTrue(seat.isEnabled, "An expired hold should not leave the seat disabled")
    }

    func testUnavailableAPIShowsRetryableError() {
        let app = XCUIApplication()
        app.launchArguments.append("--uitesting-reset-reservation-flow")
        app.launch()

        let error = app.descendants(matching: .any)["seat-list.error"]
        XCTAssertTrue(
            error.waitForExistence(timeout: 15),
            "When the API is unavailable, the app should explain that seats could not load; accessibility tree: \(app.debugDescription)"
        )

        let retryButton = app.buttons["seat-list.retry"]
        XCTAssertTrue(retryButton.waitForExistence(timeout: 5))
        XCTAssertTrue(retryButton.isEnabled)
        retryButton.tap()

        XCTAssertTrue(
            error.waitForExistence(timeout: 10),
            "A failed retry should keep the recoverable error visible; accessibility tree: \(app.debugDescription)"
        )
        XCTAssertTrue(retryButton.exists)
    }

    private func createCompetingHold(for eventSeatID: UUID) async throws -> Int {
        var request = URLRequest(url: URL(string: "http://127.0.0.1:8000/v1/holds")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "Idempotency-Key")
        request.httpBody = try JSONEncoder().encode(CompetingHoldRequest(eventSeatID: eventSeatID))

        let (_, response) = try await URLSession.shared.data(for: request)
        guard let response = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        return response.statusCode
    }

    private func waitForSeat(
        eventID: UUID,
        seatID: UUID,
        status expectedStatus: String,
        timeout: Duration
    ) async throws -> Bool {
        let deadline = ContinuousClock.now.advanced(by: timeout)
        let url = URL(
            string:
                "http://127.0.0.1:8000/v1/events/\(eventID.uuidString.lowercased())/seats"
        )!

        while ContinuousClock.now < deadline {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let response = response as? HTTPURLResponse, response.statusCode == 200 else {
                throw URLError(.badServerResponse)
            }
            let snapshot = try JSONDecoder().decode(SeatAvailabilitySnapshot.self, from: data)
            if snapshot.seats.first(where: { $0.eventSeatID == seatID })?.status == expectedStatus {
                return true
            }
            try await Task.sleep(for: .milliseconds(250))
        }
        return false
    }
}
