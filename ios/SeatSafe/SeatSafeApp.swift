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

    enum ConfirmationState: Equatable {
        case idle
        case confirming
        case uncertain
        case confirmed(CreatedReservation)
        case expired
        case unavailable
        case keyRejected
        case failed(statusCode: Int)
    }

    private(set) var state: State = .idle
    private(set) var selectedSeatID: UUID?
    private(set) var holdState: HoldState
    private(set) var confirmationState: ConfirmationState
    private let service: any SeatService
    private let holdService: any HoldService
    private let reservationService: any ReservationService
    private let flowStore: any ReservationFlowStore
    private let idempotencyKeyFactory: () -> String
    private let confirmationKeyFactory: () -> String
    private(set) var persistedFlow: PersistedReservationFlow?
    private var currentEventID: UUID?

    init(
        service: any SeatService,
        holdService: any HoldService,
        reservationService: any ReservationService,
        flowStore: any ReservationFlowStore = UserDefaultsReservationFlowStore(),
        idempotencyKeyFactory: @escaping () -> String = { UUID().uuidString.lowercased() },
        confirmationKeyFactory: @escaping () -> String = { UUID().uuidString.lowercased() }
    ) {
        self.service = service
        self.holdService = holdService
        self.reservationService = reservationService
        self.flowStore = flowStore
        self.idempotencyKeyFactory = idempotencyKeyFactory
        self.confirmationKeyFactory = confirmationKeyFactory
        let restoredFlow = flowStore.load()
        persistedFlow = restoredFlow
        switch restoredFlow {
        case .pendingHold(let attempt):
            selectedSeatID = attempt.eventSeatID
            holdState = .uncertain
            confirmationState = .idle
        case .pendingConfirmation(let pending):
            selectedSeatID = pending.hold.eventSeatID
            holdState = .created(pending.hold)
            confirmationState = .uncertain
        case nil:
            selectedSeatID = nil
            holdState = .idle
            confirmationState = .idle
        }
    }

    func load(eventID: UUID) async {
        currentEventID = eventID
        selectedSeatID = flowSeatID
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

    var pendingAttempt: PendingHoldAttempt? {
        guard case .pendingHold(let attempt) = persistedFlow else { return nil }
        return attempt
    }

    var pendingConfirmation: PendingReservationConfirmation? {
        guard case .pendingConfirmation(let pending) = persistedFlow else { return nil }
        return pending
    }

    private var flowSeatID: UUID? {
        if let pendingAttempt { return pendingAttempt.eventSeatID }
        return pendingConfirmation?.hold.eventSeatID
    }

    var canConfirmReservation: Bool {
        guard pendingConfirmation != nil, confirmationState != .confirming else { return false }
        if case .keyRejected = confirmationState { return false }
        if case .confirmed = confirmationState { return false }
        if confirmationState == .expired || confirmationState == .unavailable { return false }
        return true
    }

    var canCreateHold: Bool {
        guard let selectedSeat, holdState != .creating, !hasCreatedHold else { return false }
        if case .keyRejected = holdState { return false }
        if pendingAttempt != nil { return true }
        return selectedSeat.status == .available && holdState != .unavailable
    }

    func toggleSelection(for seatID: UUID) {
        // Keep an unknown attempt stable and keep a successful hold for the next flow step.
        guard persistedFlow == nil, !hasCreatedHold else { return }
        guard case .loaded(let seats) = state,
            let seat = seats.first(where: { $0.id == seatID }),
            seat.status == .available
        else {
            return
        }

        selectedSeatID = selectedSeatID == seatID ? nil : seatID
        holdState = .idle
        confirmationState = .idle
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
            let flow = PersistedReservationFlow.pendingHold(attempt)
            flowStore.save(flow)
            persistedFlow = flow
        }

        holdState = .creating
        do {
            let hold = try await holdService.createHold(
                for: attempt.eventSeatID,
                idempotencyKey: attempt.idempotencyKey
            )
            // Replace the hold attempt with its next-step data in one local write.
            let pending = PendingReservationConfirmation(
                hold: hold,
                idempotencyKey: confirmationKeyFactory()
            )
            let flow = PersistedReservationFlow.pendingConfirmation(pending)
            flowStore.save(flow)
            persistedFlow = flow
            holdState = .created(hold)
            confirmationState = .idle
        } catch is CancellationError {
            // Cancelling a local Swift task does not prove the server stopped processing.
            holdState = .uncertain
        } catch let error as HoldServiceError {
            switch error {
            case .seatUnavailable:
                flowStore.clear()
                persistedFlow = nil
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

    func confirmReservation() async {
        guard let pendingConfirmation, canConfirmReservation else { return }
        confirmationState = .confirming
        do {
            let reservation = try await reservationService.confirm(
                holdID: pendingConfirmation.hold.id,
                idempotencyKey: pendingConfirmation.idempotencyKey
            )
            flowStore.clear()
            persistedFlow = nil
            holdState = .idle
            confirmationState = .confirmed(reservation)
            await refreshSeats()
        } catch is CancellationError {
            // Local task cancellation cannot roll back an already accepted confirmation.
            confirmationState = .uncertain
        } catch let error as ReservationServiceError {
            switch error {
            case .holdExpired:
                await clearUnusableConfirmation(state: .expired)
            case .seatUnavailable:
                await clearUnusableConfirmation(state: .unavailable)
            case .idempotencyKeyReused:
                confirmationState = .keyRejected
            case .rejected(let statusCode):
                // Keep the key because a server error may follow a committed reservation.
                confirmationState = .failed(statusCode: statusCode)
            case .invalidResponse:
                confirmationState = .uncertain
            }
        } catch {
            confirmationState = .uncertain
        }
    }

    private func clearUnusableConfirmation(state: ConfirmationState) async {
        flowStore.clear()
        persistedFlow = nil
        holdState = .unavailable
        confirmationState = state
        await refreshSeats()
    }

    private func refreshSeats() async {
        guard let currentEventID,
            let refreshedSeats = try? await service.seats(for: currentEventID)
        else { return }
        state = .loaded(refreshedSeats)
    }
}

struct SeatListView: View {
    @State private var model = SeatListModel(
        service: HTTPSeatService(baseURL: URL(string: "http://127.0.0.1:8000")!),
        holdService: HTTPHoldService(baseURL: URL(string: "http://127.0.0.1:8000")!),
        reservationService: HTTPReservationService(
            baseURL: URL(string: "http://127.0.0.1:8000")!
        )
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
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 4)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .disabled(
                            seat.status != .available
                                || model.pendingAttempt != nil
                                || model.hasCreatedHold
                        )
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
                                confirmationStatus(for: model.confirmationState)
                                if model.canCreateHold {
                                    Button(model.pendingAttempt == nil ? "Hold seat" : "Retry hold")
                                    {
                                        Task { await model.createHold() }
                                    }
                                    .buttonStyle(.borderedProminent)
                                    .disabled(model.holdState == .creating)
                                    .accessibilityIdentifier("seat-selection.hold")
                                }
                                if model.canConfirmReservation {
                                    Button(confirmationButtonTitle) {
                                        Task { await model.confirmReservation() }
                                    }
                                    .buttonStyle(.borderedProminent)
                                    .disabled(model.confirmationState == .confirming)
                                    .accessibilityIdentifier("reservation.confirm")
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                            .background(.bar)
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
            Text("This hold is no longer active. Select an available seat to start over.")
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

    private var confirmationButtonTitle: String {
        switch model.confirmationState {
        case .uncertain, .failed:
            return "Retry confirmation"
        default:
            return "Confirm reservation"
        }
    }

    @ViewBuilder
    private func confirmationStatus(for state: SeatListModel.ConfirmationState) -> some View {
        switch state {
        case .idle:
            if model.hasCreatedHold {
                Text("Confirm the temporary hold to create your reservation.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        case .confirming:
            ProgressView("Confirming your reservation…")
                .accessibilityIdentifier("reservation.confirming")
        case .uncertain:
            Text("We couldn’t confirm the result. Retry will reuse the same hold and request key.")
                .font(.footnote)
                .foregroundStyle(.orange)
                .accessibilityIdentifier("reservation.confirmation-uncertain")
        case .confirmed(let reservation):
            Text("Reservation confirmed. ID: \(reservation.id.uuidString)")
                .font(.footnote)
                .foregroundStyle(.green)
                .accessibilityIdentifier("reservation.confirmed")
        case .expired:
            Text("The hold expired before confirmation. Select an available seat to try again.")
                .font(.footnote)
                .foregroundStyle(.orange)
        case .unavailable:
            Text("This hold can no longer be confirmed. Choose an available seat to start again.")
                .font(.footnote)
                .foregroundStyle(.orange)
        case .keyRejected:
            Text(
                "The saved confirmation key conflicts with another request; it is preserved for safety."
            )
            .font(.footnote)
            .foregroundStyle(.red)
        case .failed(let statusCode):
            Text(
                "The server returned HTTP \(statusCode). You can safely retry the saved confirmation."
            )
            .font(.footnote)
            .foregroundStyle(.orange)
        }
    }
}

@main
struct SeatSafeApp: App {
    init() {
        #if DEBUG
            if ProcessInfo.processInfo.arguments.contains("--uitesting-reset-reservation-flow") {
                UserDefaultsReservationFlowStore().clear()
            }
        #endif
    }

    var body: some Scene {
        WindowGroup { SeatListView() }
    }
}
