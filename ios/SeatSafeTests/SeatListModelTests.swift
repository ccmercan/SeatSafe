import XCTest
@testable import SeatSafe

private struct StubSeatService: SeatService {
    let result: Result<[EventSeat], TestFailure>

    func seats(for eventID: UUID) async throws -> [EventSeat] {
        try result.get()
    }
}

private enum TestFailure: Error { case expected }

@MainActor
final class SeatListModelTests: XCTestCase {
    func testSeatSnapshotDecodesBackendJSONContract() throws {
        let data = Data(
            #"{"event_id":"00000000-0000-4000-8000-000000000020","seats":[{"event_seat_id":"00000000-0000-4000-8000-000000000040","section":"Main","row":"A","number":"1","price_cents":2500,"status":"available"}]}"#.utf8
        )

        let snapshot = try JSONDecoder().decode(SeatSnapshot.self, from: data)

        XCTAssertEqual(snapshot.eventID.uuidString.lowercased(), "00000000-0000-4000-8000-000000000020")
        XCTAssertEqual(snapshot.seats.first?.displayName, "Section Main, Row A, Seat 1")
        XCTAssertEqual(snapshot.seats.first?.price, "$25.00")
        XCTAssertEqual(snapshot.seats.first?.status, .available)
    }

    func testLoadPublishesSeatsReturnedByService() async {
        let seat = EventSeat(
            eventSeatID: UUID(uuidString: "00000000-0000-4000-8000-000000000040")!,
            section: "Main", row: "A", number: "1", priceCents: 2500, status: .available
        )
        let model = SeatListModel(service: StubSeatService(result: .success([seat])))

        await model.load(eventID: UUID())

        XCTAssertEqual(model.state, .loaded([seat]))
    }

    func testLoadPublishesFailureInsteadOfLeakingTransportError() async {
        let model = SeatListModel(service: StubSeatService(result: .failure(.expected)))

        await model.load(eventID: UUID())

        XCTAssertEqual(model.state, .failed)
    }

    func testAvailableSeatCanBeSelectedAndDeselected() async {
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .available)
        let model = SeatListModel(service: StubSeatService(result: .success([seat])))
        await model.load(eventID: UUID())

        model.toggleSelection(for: seat.id)
        XCTAssertEqual(model.selectedSeat, seat)

        model.toggleSelection(for: seat.id)
        XCTAssertNil(model.selectedSeat)
    }

    func testUnavailableSeatCannotBeSelected() async {
        let heldSeat = makeSeat(id: "00000000-0000-4000-8000-000000000041", status: .held)
        let reservedSeat = makeSeat(id: "00000000-0000-4000-8000-000000000042", status: .reserved)
        let model = SeatListModel(service: StubSeatService(result: .success([heldSeat, reservedSeat])))
        await model.load(eventID: UUID())

        model.toggleSelection(for: heldSeat.id)
        model.toggleSelection(for: reservedSeat.id)

        XCTAssertNil(model.selectedSeat)
    }

    private func makeSeat(id: String, status: EventSeat.Status) -> EventSeat {
        EventSeat(
            eventSeatID: UUID(uuidString: id)!,
            section: "Main", row: "A", number: "1", priceCents: 2500, status: status
        )
    }
}
