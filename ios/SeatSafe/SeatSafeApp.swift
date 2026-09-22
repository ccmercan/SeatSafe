import Observation
import SwiftUI

private let demoEventID = UUID(uuidString: "00000000-0000-4000-8000-000000000020")!

struct EventSeat: Decodable, Identifiable, Equatable, Sendable {
    enum Status: String, Decodable, Sendable {
        case available
        case held
        case reserved
    }

    let eventSeatID: UUID
    let section: String
    let row: String
    let number: String
    let priceCents: Int
    let status: Status

    enum CodingKeys: String, CodingKey {
        case eventSeatID = "event_seat_id"
        case section, row, number, status
        case priceCents = "price_cents"
    }

    var id: UUID { eventSeatID }
    var displayName: String { "Section \(section), Row \(row), Seat \(number)" }
    var price: String { "$\(priceCents / 100).\(String(format: "%02d", priceCents % 100))" }
}

struct SeatSnapshot: Decodable, Sendable {
    let eventID: UUID
    let seats: [EventSeat]

    enum CodingKeys: String, CodingKey {
        case eventID = "event_id"
        case seats
    }
}

protocol SeatService: Sendable {
    func seats(for eventID: UUID) async throws -> [EventSeat]
}

struct HTTPSeatService: SeatService {
    let baseURL: URL
    var session: URLSession = .shared

    func seats(for eventID: UUID) async throws -> [EventSeat] {
        let url = baseURL.appending(path: "v1/events/\(eventID.uuidString.lowercased())/seats")
        let (data, response) = try await session.data(from: url)
        guard let response = response as? HTTPURLResponse,
            (200..<300).contains(response.statusCode)
        else {
            throw SeatServiceError.invalidResponse
        }
        return try JSONDecoder().decode(SeatSnapshot.self, from: data).seats
    }
}

enum SeatServiceError: Error {
    case invalidResponse
}

@Observable @MainActor
final class SeatListModel {
    enum State: Equatable {
        case idle
        case loading
        case loaded([EventSeat])
        case failed
    }

    enum HoldState: Equatable {
        case idle
        case creating
        case uncertain
        case created(CreatedHold)
        case unavailable
        case keyRejected
        case failed(statusCode: Int)
    }

    private(set) var state: State = .idle
    private(set) var selectedSeatID: UUID?
    private(set) var holdState: HoldState
    private let service: any SeatService
    private let holdService: any HoldService
    private let pendingAttemptStore: any PendingHoldAttemptStore
    private let idempotencyKeyFactory: () -> String
    private(set) var pendingAttempt: PendingHoldAttempt?
    private var currentEventID: UUID?

    init(
        service: any SeatService,
        holdService: any HoldService,
        pendingAttemptStore: any PendingHoldAttemptStore = UserDefaultsPendingHoldAttemptStore(),
        idempotencyKeyFactory: @escaping () -> String = { UUID().uuidString.lowercased() }
    ) {
        self.service = service
        self.holdService = holdService
        self.pendingAttemptStore = pendingAttemptStore
        self.idempotencyKeyFactory = idempotencyKeyFactory
        let restoredAttempt = pendingAttemptStore.load()
        pendingAttempt = restoredAttempt
        selectedSeatID = restoredAttempt?.eventSeatID
        holdState = restoredAttempt == nil ? .idle : .uncertain
    }

    func load(eventID: UUID) async {
        currentEventID = eventID
        selectedSeatID = pendingAttempt?.eventSeatID
        state = .loading
        do {
            state = .loaded(try await service.seats(for: eventID))
        } catch is CancellationError {
            // Leaving or replacing this screen is not shown as a product failure.
        } catch {
            state = .failed
        }
    }

    var selectedSeat: EventSeat? {
        guard case .loaded(let seats) = state else { return nil }
        return seats.first { $0.id == selectedSeatID }
    }

    var hasCreatedHold: Bool {
        if case .created = holdState { return true }
        return false
    }

    var canCreateHold: Bool {
        guard let selectedSeat, holdState != .creating, !hasCreatedHold else { return false }
        if case .keyRejected = holdState { return false }
        if pendingAttempt != nil { return true }
        return selectedSeat.status == .available && holdState != .unavailable
    }

    func toggleSelection(for seatID: UUID) {
        // Keep an unknown attempt stable and keep a successful hold for the next flow step.
        guard pendingAttempt == nil, !hasCreatedHold else { return }
        guard case .loaded(let seats) = state,
            let seat = seats.first(where: { $0.id == seatID }),
            seat.status == .available
        else {
            return
        }

        selectedSeatID = selectedSeatID == seatID ? nil : seatID
        holdState = .idle
    }

    func createHold() async {
        guard let selectedSeat, canCreateHold else { return }

        let attempt =
            pendingAttempt
            ?? PendingHoldAttempt(
                eventSeatID: selectedSeat.id,
                idempotencyKey: idempotencyKeyFactory()
            )
        if pendingAttempt == nil {
            // Persist before sending: the request might succeed even if its reply is lost.
            pendingAttemptStore.save(attempt)
            pendingAttempt = attempt
        }

        holdState = .creating
        do {
            let hold = try await holdService.createHold(
                for: attempt.eventSeatID,
                idempotencyKey: attempt.idempotencyKey
            )
            pendingAttemptStore.clear()
            pendingAttempt = nil
            holdState = .created(hold)
        } catch is CancellationError {
            // Cancelling a local Swift task does not prove the server stopped processing.
            holdState = .uncertain
        } catch let error as HoldServiceError {
            switch error {
            case .seatUnavailable:
                pendingAttemptStore.clear()
                pendingAttempt = nil
                holdState = .unavailable
                // Refresh the snapshot so the stale seat does not still look available.
                if let currentEventID,
                    let refreshedSeats = try? await service.seats(for: currentEventID)
                {
                    state = .loaded(refreshedSeats)
                }
            case .idempotencyKeyReused:
                holdState = .keyRejected
            case .rejected(let statusCode):
                // Conservatively keep the key: a server error can follow a committed write.
                holdState = .failed(statusCode: statusCode)
            case .invalidResponse:
                holdState = .uncertain
            }
        } catch {
            // A transport error is ambiguous; retry the persisted pair, never a new key.
            holdState = .uncertain
        }
    }
}

struct SeatListView: View {
    @State private var model = SeatListModel(
        service: HTTPSeatService(baseURL: URL(string: "http://127.0.0.1:8000")!),
        holdService: HTTPHoldService(baseURL: URL(string: "http://127.0.0.1:8000")!)
    )

    var body: some View {
        NavigationStack {
            Group {
                switch model.state {
                case .idle, .loading:
                    ProgressView("Loading seats…")
                        .accessibilityIdentifier("seat-list.loading")
                case .failed:
                    ContentUnavailableView {
                        Label("Couldn’t load seats", systemImage: "wifi.exclamationmark")
                    } description: {
                        Text("Check that the SeatSafe API is running, then try again.")
                    } actions: {
                        Button("Try Again") { Task { await model.load(eventID: demoEventID) } }
                    }
                    .accessibilityIdentifier("seat-list.error")
                case .loaded(let seats) where seats.isEmpty:
                    ContentUnavailableView("No seats found", systemImage: "chair.lounge")
                case .loaded(let seats):
                    List(seats) { seat in
                        let isSelected = model.selectedSeatID == seat.id
                        Button {
                            model.toggleSelection(for: seat.id)
                        } label: {
                            HStack {
                                VStack(alignment: .leading) {
                                    Text(seat.displayName).font(.headline)
                                    Text(seat.status.rawValue.capitalized).font(.subheadline)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(seat.price).monospacedDigit()
                                if isSelected {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundStyle(.tint)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                        .buttonStyle(.plain)
                        .disabled(
                            seat.status != .available
                                || model.pendingAttempt != nil
                                || model.hasCreatedHold
                        )
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(
                            "\(seat.displayName), \(seat.status.rawValue), \(seat.price)"
                        )
                        .accessibilityValue(isSelected ? "Selected" : "Not selected")
                        .accessibilityIdentifier("seat-row.\(seat.id.uuidString.lowercased())")
                    }
                    .accessibilityIdentifier("seat-list.results")
                    .safeAreaInset(edge: .bottom) {
                        if let selectedSeat = model.selectedSeat {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Selected: \(selectedSeat.displayName)")
                                    .font(.headline)
                                holdStatus(for: model.holdState)
                                if model.canCreateHold {
                                    Button(model.pendingAttempt == nil ? "Hold seat" : "Retry hold")
                                    {
                                        Task { await model.createHold() }
                                    }
                                    .buttonStyle(.borderedProminent)
                                    .disabled(model.holdState == .creating)
                                    .accessibilityIdentifier("seat-selection.hold")
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                            .background(.bar)
                            .accessibilityIdentifier("seat-selection.summary")
                        }
                    }
                }
            }
            .navigationTitle("Demo Event Seats")
        }
        .task { await model.load(eventID: demoEventID) }
    }

    @ViewBuilder
    private func holdStatus(for state: SeatListModel.HoldState) -> some View {
        switch state {
        case .idle:
            Text(
                "Selection only so far. Choose Hold seat to ask the server to reserve it temporarily."
            )
            .font(.footnote)
            .foregroundStyle(.secondary)
        case .creating:
            ProgressView("Asking the server to hold this seat…")
        case .uncertain:
            Text(
                "We couldn’t confirm the result. Retry safely: the app will reuse the same request key."
            )
            .font(.footnote)
            .foregroundStyle(.orange)
            .accessibilityIdentifier("seat-selection.uncertain")
        case .created(let hold):
            Text("Seat held until \(hold.expiresAt). Hold ID: \(hold.id.uuidString)")
                .font(.footnote)
                .foregroundStyle(.green)
                .accessibilityIdentifier("seat-selection.created")
        case .unavailable:
            Text("This seat is no longer available. Choose another available seat.")
                .font(.footnote)
                .foregroundStyle(.orange)
        case .keyRejected:
            Text(
                "The saved retry key conflicts with another request. The same key is being preserved for safety."
            )
            .font(.footnote)
            .foregroundStyle(.red)
        case .failed(let statusCode):
            Text(
                "The server returned HTTP \(statusCode). You can retry safely with the saved request key."
            )
            .font(.footnote)
            .foregroundStyle(.orange)
        }
    }
}

@main
struct SeatSafeApp: App {
    var body: some Scene {
        WindowGroup { SeatListView() }
    }
}
