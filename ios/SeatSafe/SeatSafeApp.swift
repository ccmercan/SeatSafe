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
              (200..<300).contains(response.statusCode) else {
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

    private(set) var state: State = .idle
    private(set) var selectedSeatID: UUID?
    private let service: any SeatService

    init(service: any SeatService) {
        self.service = service
    }

    func load(eventID: UUID) async {
        selectedSeatID = nil
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

    func toggleSelection(for seatID: UUID) {
        guard case .loaded(let seats) = state,
              let seat = seats.first(where: { $0.id == seatID }),
              seat.status == .available else {
            return
        }

        selectedSeatID = selectedSeatID == seatID ? nil : seatID
    }
}

struct SeatListView: View {
    @State private var model = SeatListModel(
        service: HTTPSeatService(baseURL: URL(string: "http://127.0.0.1:8000")!)
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
                        .disabled(seat.status != .available)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(seat.displayName), \(seat.status.rawValue), \(seat.price)")
                        .accessibilityValue(isSelected ? "Selected" : "Not selected")
                        .accessibilityIdentifier("seat-row.\(seat.id.uuidString.lowercased())")
                    }
                    .accessibilityIdentifier("seat-list.results")
                    .safeAreaInset(edge: .bottom) {
                        if let selectedSeat = model.selectedSeat {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Selected: \(selectedSeat.displayName)")
                                    .font(.headline)
                                Text("This is only a local selection; the seat is not held yet.")
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
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
}

@main
struct SeatSafeApp: App {
    var body: some Scene {
        WindowGroup { SeatListView() }
    }
}
