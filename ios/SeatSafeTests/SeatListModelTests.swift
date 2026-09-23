import XCTest

@testable import SeatSafe

private struct StubSeatService: SeatService {
    let result: Result<[EventSeat], TestFailure>

    func seats(for eventID: UUID) async throws -> [EventSeat] {
        try result.get()
    }
}

private struct StubHoldService: HoldService {
    let hold: CreatedHold

    func createHold(for eventSeatID: UUID, idempotencyKey: String) async throws -> CreatedHold {
        hold
    }
}

private struct StubReservationService: ReservationService {
    let reservation: CreatedReservation

    func confirm(holdID: UUID, idempotencyKey: String) async throws -> CreatedReservation {
        reservation
    }
}

private actor ScriptedHoldService: HoldService {
    enum Outcome: Sendable {
        case success(CreatedHold)
        case unavailable
        case transportFailure
    }

    private var outcomes: [Outcome]
    private var requests: [PendingHoldAttempt] = []

    init(outcomes: [Outcome]) {
        self.outcomes = outcomes
    }

    func createHold(for eventSeatID: UUID, idempotencyKey: String) async throws -> CreatedHold {
        requests.append(
            PendingHoldAttempt(eventSeatID: eventSeatID, idempotencyKey: idempotencyKey)
        )
        switch outcomes.removeFirst() {
        case .success(let hold): return hold
        case .unavailable: throw HoldServiceError.seatUnavailable
        case .transportFailure: throw URLError(.timedOut)
        }
    }

    func recordedRequests() -> [PendingHoldAttempt] { requests }
}

private actor ScriptedReservationService: ReservationService {
    enum Outcome: Sendable {
        case success(CreatedReservation)
        case expired
        case transportFailure
    }

    private var outcomes: [Outcome]
    private var requests: [(holdID: UUID, key: String)] = []

    init(outcomes: [Outcome]) {
        self.outcomes = outcomes
    }

    func confirm(holdID: UUID, idempotencyKey: String) async throws -> CreatedReservation {
        requests.append((holdID, idempotencyKey))
        switch outcomes.removeFirst() {
        case .success(let reservation): return reservation
        case .expired: throw ReservationServiceError.holdExpired
        case .transportFailure: throw URLError(.timedOut)
        }
    }

    func recordedRequests() -> [(holdID: UUID, key: String)] { requests }
}

/// Deliberately ignores task cancellation so a late response can be delivered on command.
private actor ControlledSeatService: SeatService {
    private var pending: [UUID: CheckedContinuation<[EventSeat], Error>] = [:]
    private var requestWaiters: [UUID: [CheckedContinuation<Void, Never>]] = [:]

    func seats(for eventID: UUID) async throws -> [EventSeat] {
        try await withCheckedThrowingContinuation { continuation in
            pending[eventID] = continuation
            for waiter in requestWaiters.removeValue(forKey: eventID) ?? [] {
                waiter.resume()
            }
        }
    }

    func waitUntilRequested(_ eventID: UUID) async {
        if pending[eventID] != nil { return }
        await withCheckedContinuation { continuation in
            requestWaiters[eventID, default: []].append(continuation)
        }
    }

    func respond(to eventID: UUID, with seats: [EventSeat]) {
        pending.removeValue(forKey: eventID)?.resume(returning: seats)
    }
}

/// Holds writes in flight until the test explicitly cancels or completes them.
private actor InFlightHoldService: HoldService {
    private(set) var requests: [PendingHoldAttempt] = []
    private var pending: CheckedContinuation<CreatedHold, Error>?
    private var requestWaiters: [(count: Int, continuation: CheckedContinuation<Void, Never>)] = []

    func createHold(for eventSeatID: UUID, idempotencyKey: String) async throws -> CreatedHold {
        requests.append(
            PendingHoldAttempt(eventSeatID: eventSeatID, idempotencyKey: idempotencyKey))
        resumeReadyWaiters()
        return try await withCheckedThrowingContinuation { pending = $0 }
    }

    func waitForRequestCount(_ count: Int) async {
        if requests.count >= count { return }
        await withCheckedContinuation { requestWaiters.append((count, $0)) }
    }

    func cancelCurrentRequest() {
        pending?.resume(throwing: CancellationError())
        pending = nil
    }

    func completeCurrentRequest(with hold: CreatedHold) {
        pending?.resume(returning: hold)
        pending = nil
    }

    private func resumeReadyWaiters() {
        let ready = requestWaiters.filter { $0.count <= requests.count }
        requestWaiters.removeAll { $0.count <= requests.count }
        for waiter in ready {
            waiter.continuation.resume()
        }
    }
}

private actor InFlightReservationService: ReservationService {
    private(set) var requests: [(holdID: UUID, key: String)] = []
    private var pending: CheckedContinuation<CreatedReservation, Error>?
    private var requestWaiters: [(count: Int, continuation: CheckedContinuation<Void, Never>)] = []

    func confirm(holdID: UUID, idempotencyKey: String) async throws -> CreatedReservation {
        requests.append((holdID, idempotencyKey))
        resumeReadyWaiters()
        return try await withCheckedThrowingContinuation { pending = $0 }
    }

    func waitForRequestCount(_ count: Int) async {
        if requests.count >= count { return }
        await withCheckedContinuation { requestWaiters.append((count, $0)) }
    }

    func cancelCurrentRequest() {
        pending?.resume(throwing: CancellationError())
        pending = nil
    }

    func completeCurrentRequest(with reservation: CreatedReservation) {
        pending?.resume(returning: reservation)
        pending = nil
    }

    private func resumeReadyWaiters() {
        let ready = requestWaiters.filter { $0.count <= requests.count }
        requestWaiters.removeAll { $0.count <= requests.count }
        for waiter in ready {
            waiter.continuation.resume()
        }
    }
}

private enum TestFailure: Error, Sendable { case expected }

@MainActor
private final class InMemoryReservationFlowStore: ReservationFlowStore {
    private(set) var flow: PersistedReservationFlow?

    init(flow: PersistedReservationFlow? = nil) {
        self.flow = flow
    }

    func load() -> PersistedReservationFlow? { flow }
    func save(_ flow: PersistedReservationFlow) { self.flow = flow }
    func clear() { flow = nil }
}

private final class MockURLProtocolState: @unchecked Sendable {
    private let lock = NSLock()
    private var storedRequest: URLRequest?
    private var storedStatusCode = 201
    private var storedBody = Data()

    func configure(statusCode: Int, body: Data) {
        lock.lock()
        storedStatusCode = statusCode
        storedBody = body
        storedRequest = nil
        lock.unlock()
    }

    func record(_ request: URLRequest) {
        lock.lock()
        storedRequest = request
        lock.unlock()
    }

    func request() -> URLRequest? {
        lock.lock()
        defer { lock.unlock() }
        return storedRequest
    }

    func response() -> (statusCode: Int, body: Data) {
        lock.lock()
        defer { lock.unlock() }
        return (storedStatusCode, storedBody)
    }
}

private final class HoldMockURLProtocol: URLProtocol, @unchecked Sendable {
    static let state = MockURLProtocolState()

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.state.record(request)
        let result = Self.state.response()
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: result.statusCode,
            httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: result.body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

@MainActor
final class SeatListModelTests: XCTestCase {
    func testSeatSnapshotDecodesBackendJSONContract() throws {
        let data = Data(
            #"{"event_id":"00000000-0000-4000-8000-000000000020","seats":[{"event_seat_id":"00000000-0000-4000-8000-000000000040","section":"Main","row":"A","number":"1","price_cents":2500,"status":"available"}]}"#
                .utf8
        )

        let snapshot = try JSONDecoder().decode(SeatSnapshot.self, from: data)

        XCTAssertEqual(
            snapshot.eventID.uuidString.lowercased(), "00000000-0000-4000-8000-000000000020")
        XCTAssertEqual(snapshot.seats.first?.displayName, "Section Main, Row A, Seat 1")
        XCTAssertEqual(snapshot.seats.first?.price, "$25.00")
        XCTAssertEqual(snapshot.seats.first?.status, .available)
    }

    func testLoadPublishesSeatsReturnedByService() async {
        let seat = EventSeat(
            eventSeatID: UUID(uuidString: "00000000-0000-4000-8000-000000000040")!,
            section: "Main", row: "A", number: "1", priceCents: 2500, status: .available
        )
        let model = makeModel(seats: [seat])

        await model.load(eventID: UUID())

        XCTAssertEqual(model.state, .loaded([seat]))
    }

    func testLoadPublishesFailureInsteadOfLeakingTransportError() async {
        let model = SeatListModel(
            service: StubSeatService(result: .failure(.expected)),
            holdService: makeHoldService(),
            reservationService: makeReservationService()
        )

        await model.load(eventID: UUID())

        XCTAssertEqual(model.state, .failed)
    }

    func testOlderSeatResponseCannotReplaceNewerEventSelection() async {
        let firstEvent = UUID()
        let secondEvent = UUID()
        let firstSeat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .available)
        let secondSeat = makeSeat(id: "00000000-0000-4000-8000-000000000041", status: .available)
        let service = ControlledSeatService()
        let model = SeatListModel(
            service: service,
            holdService: makeHoldService(),
            reservationService: makeReservationService()
        )

        let olderLoad = Task { await model.load(eventID: firstEvent) }
        await service.waitUntilRequested(firstEvent)
        let newerLoad = Task { await model.load(eventID: secondEvent) }
        await service.waitUntilRequested(secondEvent)

        await service.respond(to: secondEvent, with: [secondSeat])
        await newerLoad.value
        await service.respond(to: firstEvent, with: [firstSeat])
        await olderLoad.value

        XCTAssertEqual(model.state, .loaded([secondSeat]))
    }

    func testCancelledSeatLoadDoesNotPublishLateResponseOrShowFailure() async {
        let eventID = UUID()
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .available)
        let service = ControlledSeatService()
        let model = SeatListModel(
            service: service,
            holdService: makeHoldService(),
            reservationService: makeReservationService()
        )
        let load = Task { await model.load(eventID: eventID) }
        await service.waitUntilRequested(eventID)

        load.cancel()
        await service.respond(to: eventID, with: [seat])
        await load.value

        XCTAssertEqual(model.state, .idle)
    }

    func testAvailableSeatCanBeSelectedAndDeselected() async {
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .available)
        let model = makeModel(seats: [seat])
        await model.load(eventID: UUID())

        model.toggleSelection(for: seat.id)
        XCTAssertEqual(model.selectedSeat, seat)

        model.toggleSelection(for: seat.id)
        XCTAssertNil(model.selectedSeat)
    }

    func testUnavailableSeatCannotBeSelected() async {
        let heldSeat = makeSeat(id: "00000000-0000-4000-8000-000000000041", status: .held)
        let reservedSeat = makeSeat(id: "00000000-0000-4000-8000-000000000042", status: .reserved)
        let model = makeModel(seats: [heldSeat, reservedSeat])
        await model.load(eventID: UUID())

        model.toggleSelection(for: heldSeat.id)
        model.toggleSelection(for: reservedSeat.id)

        XCTAssertNil(model.selectedSeat)
    }

    func testAmbiguousFailureRetryReusesSameSeatAndKeyThenClearsSavedAttempt() async {
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .available)
        let otherSeat = makeSeat(id: "00000000-0000-4000-8000-000000000041", status: .available)
        let hold = makeHold(for: seat.id)
        let holdService = ScriptedHoldService(
            outcomes: [.transportFailure, .success(hold)]
        )
        let attemptStore = InMemoryReservationFlowStore()
        let model = SeatListModel(
            service: StubSeatService(result: .success([seat, otherSeat])),
            holdService: holdService,
            reservationService: makeReservationService(),
            flowStore: attemptStore,
            idempotencyKeyFactory: { "stable-key" },
            confirmationKeyFactory: { "confirmation-key" }
        )
        await model.load(eventID: UUID())
        model.toggleSelection(for: seat.id)

        await model.createHold()

        XCTAssertEqual(model.holdState, .uncertain)
        XCTAssertEqual(
            attemptStore.load(),
            .pendingHold(PendingHoldAttempt(eventSeatID: seat.id, idempotencyKey: "stable-key"))
        )

        await model.createHold()

        let requests = await holdService.recordedRequests()
        XCTAssertEqual(requests.count, 2)
        XCTAssertEqual(requests[0], requests[1])
        XCTAssertEqual(requests[0].eventSeatID, seat.id)
        XCTAssertEqual(requests[0].idempotencyKey, "stable-key")
        XCTAssertEqual(
            attemptStore.load(),
            .pendingConfirmation(
                PendingReservationConfirmation(hold: hold, idempotencyKey: "confirmation-key")
            ))
        XCTAssertEqual(model.holdState, .created(hold))
        model.toggleSelection(for: otherSeat.id)
        XCTAssertEqual(model.selectedSeat?.id, seat.id)
        XCTAssertEqual(model.holdState, .created(hold))
    }

    func testRepeatedHoldActionWhileRequestIsInFlightSendsOnlyOneRequest() async {
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .available)
        let hold = makeHold(for: seat.id)
        let service = InFlightHoldService()
        let model = SeatListModel(
            service: StubSeatService(result: .success([seat])),
            holdService: service,
            reservationService: makeReservationService(),
            flowStore: InMemoryReservationFlowStore(),
            idempotencyKeyFactory: { "one-hold-key" },
            confirmationKeyFactory: { "confirm-key" }
        )
        await model.load(eventID: UUID())
        model.toggleSelection(for: seat.id)

        let firstAction = Task { await model.createHold() }
        await service.waitForRequestCount(1)
        await model.createHold()

        let requestsBeforeResponse = await service.requests
        XCTAssertEqual(requestsBeforeResponse.count, 1)
        await service.completeCurrentRequest(with: hold)
        await firstAction.value

        let requests = await service.requests
        XCTAssertEqual(requests.count, 1)
        XCTAssertEqual(model.holdState, .created(hold))
    }

    func testCancelledHoldKeepsSameAttemptAndCanRetry() async {
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .available)
        let hold = makeHold(for: seat.id)
        let service = InFlightHoldService()
        let store = InMemoryReservationFlowStore()
        let model = SeatListModel(
            service: StubSeatService(result: .success([seat])),
            holdService: service,
            reservationService: makeReservationService(),
            flowStore: store,
            idempotencyKeyFactory: { "same-hold-key" },
            confirmationKeyFactory: { "confirm-key" }
        )
        await model.load(eventID: UUID())
        model.toggleSelection(for: seat.id)

        let firstAction = Task { await model.createHold() }
        await service.waitForRequestCount(1)
        firstAction.cancel()
        await service.cancelCurrentRequest()
        await firstAction.value

        let savedAttempt = PendingHoldAttempt(eventSeatID: seat.id, idempotencyKey: "same-hold-key")
        XCTAssertEqual(model.holdState, .uncertain)
        XCTAssertEqual(store.load(), .pendingHold(savedAttempt))

        let retry = Task { await model.createHold() }
        await service.waitForRequestCount(2)
        let requestsBeforeResponse = await service.requests
        XCTAssertEqual(requestsBeforeResponse, [savedAttempt, savedAttempt])
        await service.completeCurrentRequest(with: hold)
        await retry.value

        XCTAssertEqual(model.holdState, .created(hold))
        XCTAssertEqual(
            store.load(),
            .pendingConfirmation(
                PendingReservationConfirmation(hold: hold, idempotencyKey: "confirm-key")
            ))
    }

    func testRestoredAttemptCanRetryWhenSnapshotAlreadyShowsSeatHeld() async {
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .held)
        let hold = makeHold(for: seat.id)
        let holdService = ScriptedHoldService(outcomes: [.success(hold)])
        let attemptStore = InMemoryReservationFlowStore()
        let attempt = PendingHoldAttempt(eventSeatID: seat.id, idempotencyKey: "restored-key")
        attemptStore.save(.pendingHold(attempt))
        let model = SeatListModel(
            service: StubSeatService(result: .success([seat])),
            holdService: holdService,
            reservationService: makeReservationService(),
            flowStore: attemptStore,
            confirmationKeyFactory: { "confirmation-key" }
        )

        await model.load(eventID: UUID())

        XCTAssertEqual(model.selectedSeat, seat)
        XCTAssertEqual(model.holdState, .uncertain)
        await model.createHold()

        let requests = await holdService.recordedRequests()
        XCTAssertEqual(requests, [attempt])
        XCTAssertEqual(model.holdState, .created(hold))
        XCTAssertEqual(
            attemptStore.load(),
            .pendingConfirmation(
                PendingReservationConfirmation(hold: hold, idempotencyKey: "confirmation-key")
            ))
    }

    func testDefinitiveUnavailableResponseClearsAttemptForANewTry() async {
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .available)
        let hold = makeHold(for: seat.id)
        let holdService = ScriptedHoldService(outcomes: [.unavailable, .success(hold)])
        let attemptStore = InMemoryReservationFlowStore()
        var keys = ["first-key", "new-key"].makeIterator()
        let model = SeatListModel(
            service: StubSeatService(result: .success([seat])),
            holdService: holdService,
            reservationService: makeReservationService(),
            flowStore: attemptStore,
            idempotencyKeyFactory: { keys.next()! },
            confirmationKeyFactory: { "confirmation-key" }
        )
        await model.load(eventID: UUID())
        model.toggleSelection(for: seat.id)

        await model.createHold()

        XCTAssertEqual(model.holdState, .unavailable)
        XCTAssertNil(attemptStore.load())

        model.toggleSelection(for: seat.id)
        model.toggleSelection(for: seat.id)
        await model.createHold()

        let requests = await holdService.recordedRequests()
        XCTAssertEqual(requests.map(\.idempotencyKey), ["first-key", "new-key"])
        XCTAssertEqual(model.holdState, .created(hold))
    }

    func testPendingAttemptPersistsAcrossUserDefaultsStoreInstances() throws {
        let suiteName = "SeatSafeTests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        let firstStore = UserDefaultsReservationFlowStore(defaults: defaults)
        let expected = PendingHoldAttempt(
            eventSeatID: UUID(uuidString: "00000000-0000-4000-8000-000000000040")!,
            idempotencyKey: "persisted-key"
        )
        defer { defaults.removePersistentDomain(forName: suiteName) }

        firstStore.save(.pendingHold(expected))

        let reopenedStore = UserDefaultsReservationFlowStore(defaults: defaults)
        XCTAssertEqual(reopenedStore.load(), .pendingHold(expected))
        reopenedStore.clear()
        XCTAssertNil(firstStore.load())
    }

    func testPendingConfirmationPersistsAcrossUserDefaultsStoreInstances() throws {
        let suiteName = "SeatSafeTests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let hold = makeHold(for: UUID(uuidString: "00000000-0000-4000-8000-000000000040")!)
        let expected = PersistedReservationFlow.pendingConfirmation(
            PendingReservationConfirmation(hold: hold, idempotencyKey: "durable-confirm-key")
        )

        UserDefaultsReservationFlowStore(defaults: defaults).save(expected)

        let reopenedStore = UserDefaultsReservationFlowStore(defaults: defaults)
        XCTAssertEqual(reopenedStore.load(), expected)
    }

    func testHTTPHoldServiceSendsExpectedMethodHeaderAndSeatBody() async throws {
        let seatID = UUID(uuidString: "00000000-0000-4000-8000-000000000040")!
        let hold = makeHold(for: seatID)
        HoldMockURLProtocol.state.configure(
            statusCode: 201,
            body: try JSONEncoder().encode(hold)
        )
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [HoldMockURLProtocol.self]
        let service = HTTPHoldService(
            baseURL: URL(string: "https://seatsafe.test")!,
            session: URLSession(configuration: configuration)
        )

        let returnedHold = try await service.createHold(for: seatID, idempotencyKey: "request-key")

        let request = try XCTUnwrap(HoldMockURLProtocol.state.request())
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Idempotency-Key"), "request-key")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Content-Type"), "application/json")
        let body: Data
        if let requestBody = request.httpBody {
            body = requestBody
        } else {
            body = try readBody(from: XCTUnwrap(request.httpBodyStream))
        }
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: String])
        XCTAssertEqual(json["event_seat_id"], seatID.uuidString.lowercased())
        XCTAssertEqual(returnedHold, hold)
    }

    func testHTTPHoldServiceMapsSeatConflictCode() async {
        HoldMockURLProtocol.state.configure(
            statusCode: 409,
            body: Data(#"{"code":"seat_unavailable"}"#.utf8)
        )
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [HoldMockURLProtocol.self]
        let service = HTTPHoldService(
            baseURL: URL(string: "https://seatsafe.test")!,
            session: URLSession(configuration: configuration)
        )

        do {
            _ = try await service.createHold(for: UUID(), idempotencyKey: "request-key")
            XCTFail("Expected the seat conflict to be mapped")
        } catch {
            XCTAssertEqual(error as? HoldServiceError, .seatUnavailable)
        }
    }

    func testConfirmationRetryAfterModelRecreationKeepsTheSameHoldAndKey() async {
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .held)
        let hold = makeHold(for: seat.id)
        let pending = PendingReservationConfirmation(hold: hold, idempotencyKey: "confirm-key")
        let store = InMemoryReservationFlowStore(flow: .pendingConfirmation(pending))
        let reservation = makeReservation(for: hold)
        let service = ScriptedReservationService(outcomes: [
            .transportFailure, .success(reservation),
        ])

        let firstModel = SeatListModel(
            service: StubSeatService(result: .success([seat])),
            holdService: makeHoldService(),
            reservationService: service,
            flowStore: store
        )
        await firstModel.load(eventID: UUID())
        await firstModel.confirmReservation()
        XCTAssertEqual(firstModel.confirmationState, .uncertain)
        XCTAssertEqual(store.load(), .pendingConfirmation(pending))

        // Simulates the app model being recreated after it was closed or replaced.
        let reopenedModel = SeatListModel(
            service: StubSeatService(result: .success([seat])),
            holdService: makeHoldService(),
            reservationService: service,
            flowStore: store
        )
        await reopenedModel.load(eventID: UUID())
        await reopenedModel.confirmReservation()

        let requests = await service.recordedRequests()
        XCTAssertEqual(requests.map(\.holdID), [hold.id, hold.id])
        XCTAssertEqual(requests.map(\.key), ["confirm-key", "confirm-key"])
        XCTAssertEqual(reopenedModel.confirmationState, .confirmed(reservation))
        XCTAssertNil(store.load())
    }

    func testRepeatedConfirmationActionWhileRequestIsInFlightSendsOnlyOneRequest() async {
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .held)
        let hold = makeHold(for: seat.id)
        let reservation = makeReservation(for: hold)
        let pending = PendingReservationConfirmation(hold: hold, idempotencyKey: "one-confirm-key")
        let service = InFlightReservationService()
        let model = SeatListModel(
            service: StubSeatService(result: .success([seat])),
            holdService: makeHoldService(),
            reservationService: service,
            flowStore: InMemoryReservationFlowStore(flow: .pendingConfirmation(pending))
        )
        await model.load(eventID: UUID())

        let firstAction = Task { await model.confirmReservation() }
        await service.waitForRequestCount(1)
        await model.confirmReservation()

        let requestsBeforeResponse = await service.requests
        XCTAssertEqual(requestsBeforeResponse.count, 1)
        await service.completeCurrentRequest(with: reservation)
        await firstAction.value

        let requests = await service.requests
        XCTAssertEqual(requests.count, 1)
        XCTAssertEqual(model.confirmationState, .confirmed(reservation))
    }

    func testCancelledConfirmationKeepsSameHoldAndKeyForRetry() async {
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .held)
        let hold = makeHold(for: seat.id)
        let reservation = makeReservation(for: hold)
        let pending = PendingReservationConfirmation(hold: hold, idempotencyKey: "same-confirm-key")
        let service = InFlightReservationService()
        let store = InMemoryReservationFlowStore(flow: .pendingConfirmation(pending))
        let model = SeatListModel(
            service: StubSeatService(result: .success([seat])),
            holdService: makeHoldService(),
            reservationService: service,
            flowStore: store
        )
        await model.load(eventID: UUID())

        let firstAction = Task { await model.confirmReservation() }
        await service.waitForRequestCount(1)
        firstAction.cancel()
        await service.cancelCurrentRequest()
        await firstAction.value

        XCTAssertEqual(model.confirmationState, .uncertain)
        XCTAssertEqual(store.load(), .pendingConfirmation(pending))

        let retry = Task { await model.confirmReservation() }
        await service.waitForRequestCount(2)
        let requestsBeforeResponse = await service.requests
        XCTAssertEqual(
            requestsBeforeResponse.map(\.holdID), [hold.id, hold.id])
        XCTAssertEqual(
            requestsBeforeResponse.map(\.key), ["same-confirm-key", "same-confirm-key"])
        await service.completeCurrentRequest(with: reservation)
        await retry.value

        XCTAssertEqual(model.confirmationState, .confirmed(reservation))
        XCTAssertNil(store.load())
    }

    func testExpiredConfirmationClearsThePendingFlow() async {
        let seat = makeSeat(id: "00000000-0000-4000-8000-000000000040", status: .held)
        let hold = makeHold(for: seat.id)
        let store = InMemoryReservationFlowStore(
            flow: .pendingConfirmation(
                PendingReservationConfirmation(hold: hold, idempotencyKey: "confirm-key")
            ))
        let service = ScriptedReservationService(outcomes: [.expired])
        let model = SeatListModel(
            service: StubSeatService(result: .success([seat])),
            holdService: makeHoldService(),
            reservationService: service,
            flowStore: store
        )

        await model.load(eventID: UUID())
        await model.confirmReservation()

        XCTAssertEqual(model.confirmationState, .expired)
        XCTAssertNil(store.load())
        XCTAssertFalse(model.canConfirmReservation)
    }

    func testHTTPReservationServiceSendsExpectedRequestContract() async throws {
        let hold = makeHold(for: UUID(uuidString: "00000000-0000-4000-8000-000000000040")!)
        let reservation = makeReservation(for: hold)
        HoldMockURLProtocol.state.configure(
            statusCode: 201,
            body: try JSONEncoder().encode(reservation)
        )
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [HoldMockURLProtocol.self]
        let service = HTTPReservationService(
            baseURL: URL(string: "https://seatsafe.test")!,
            session: URLSession(configuration: configuration)
        )

        let result = try await service.confirm(holdID: hold.id, idempotencyKey: "confirm-key")

        let request = try XCTUnwrap(HoldMockURLProtocol.state.request())
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/v1/reservations")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Idempotency-Key"), "confirm-key")
        let body: Data
        if let requestBody = request.httpBody {
            body = requestBody
        } else {
            body = try readBody(from: XCTUnwrap(request.httpBodyStream))
        }
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: String])
        XCTAssertEqual(json["hold_id"], hold.id.uuidString.lowercased())
        XCTAssertEqual(result, reservation)
    }

    private func makeModel(
        seats: [EventSeat],
        store: InMemoryReservationFlowStore = InMemoryReservationFlowStore()
    ) -> SeatListModel {
        SeatListModel(
            service: StubSeatService(result: .success(seats)),
            holdService: makeHoldService(),
            reservationService: makeReservationService(),
            flowStore: store
        )
    }

    private func readBody(from stream: InputStream) throws -> Data {
        stream.open()
        defer { stream.close() }
        var body = Data()
        var buffer = [UInt8](repeating: 0, count: 1_024)
        while stream.hasBytesAvailable {
            let count = buffer.withUnsafeMutableBufferPointer { bufferPointer in
                stream.read(bufferPointer.baseAddress!, maxLength: bufferPointer.count)
            }
            if count <= 0 { break }
            body.append(contentsOf: buffer.prefix(count))
        }
        return body
    }

    private func makeHoldService() -> StubHoldService {
        StubHoldService(
            hold: makeHold(for: UUID(uuidString: "00000000-0000-4000-8000-000000000040")!))
    }

    private func makeReservationService() -> StubReservationService {
        StubReservationService(
            reservation: CreatedReservation(
                id: UUID(uuidString: "00000000-0000-4000-8000-000000000060")!,
                holdID: UUID(uuidString: "00000000-0000-4000-8000-000000000050")!,
                eventSeatID: UUID(uuidString: "00000000-0000-4000-8000-000000000040")!,
                status: "confirmed",
                confirmedAt: "2026-09-22T12:01:00Z"
            ))
    }

    private func makeHold(for eventSeatID: UUID) -> CreatedHold {
        CreatedHold(
            id: UUID(uuidString: "00000000-0000-4000-8000-000000000050")!,
            eventSeatID: eventSeatID,
            status: "active",
            expiresAt: "2026-09-22T12:05:00Z"
        )
    }

    private func makeReservation(for hold: CreatedHold) -> CreatedReservation {
        CreatedReservation(
            id: UUID(uuidString: "00000000-0000-4000-8000-000000000060")!,
            holdID: hold.id,
            eventSeatID: hold.eventSeatID,
            status: "confirmed",
            confirmedAt: "2026-09-22T12:01:00Z"
        )
    }

    private func makeSeat(id: String, status: EventSeat.Status) -> EventSeat {
        EventSeat(
            eventSeatID: UUID(uuidString: id)!,
            section: "Main", row: "A", number: "1", priceCents: 2500, status: status
        )
    }
}
