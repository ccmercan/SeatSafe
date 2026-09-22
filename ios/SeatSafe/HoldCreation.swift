import Foundation

struct PendingHoldAttempt: Codable, Equatable, Sendable {
    let eventSeatID: UUID
    let idempotencyKey: String

    enum CodingKeys: String, CodingKey {
        case eventSeatID = "event_seat_id"
        case idempotencyKey = "idempotency_key"
    }
}

@MainActor
protocol ReservationFlowStore {
    func load() -> PersistedReservationFlow?
    func save(_ flow: PersistedReservationFlow)
    func clear()
}

@MainActor
struct UserDefaultsReservationFlowStore: ReservationFlowStore {
    private let defaults: UserDefaults
    private let key = "seatsafe.reservationFlow"
    private let legacyHoldAttemptKey = "seatsafe.pendingHoldAttempt"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func load() -> PersistedReservationFlow? {
        guard let data = defaults.data(forKey: key) else {
            // Migrate a retry attempt saved by the previous single-operation format.
            guard let legacyData = defaults.data(forKey: legacyHoldAttemptKey),
                let attempt = try? JSONDecoder().decode(PendingHoldAttempt.self, from: legacyData)
            else {
                return nil
            }
            let flow = PersistedReservationFlow.pendingHold(attempt)
            save(flow)
            return flow
        }
        do {
            return try JSONDecoder().decode(PersistedReservationFlow.self, from: data)
        } catch {
            // Invalid local state cannot be used safely as an idempotent retry.
            defaults.removeObject(forKey: key)
            return nil
        }
    }

    func save(_ flow: PersistedReservationFlow) {
        guard let data = try? JSONEncoder().encode(flow) else { return }
        defaults.set(data, forKey: key)
        defaults.removeObject(forKey: legacyHoldAttemptKey)
    }

    func clear() {
        defaults.removeObject(forKey: key)
        defaults.removeObject(forKey: legacyHoldAttemptKey)
    }
}

struct CreatedHold: Codable, Equatable, Sendable {
    let id: UUID
    let eventSeatID: UUID
    let status: String
    let expiresAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case eventSeatID = "event_seat_id"
        case status
        case expiresAt = "expires_at"
    }
}

struct PendingReservationConfirmation: Codable, Equatable, Sendable {
    let hold: CreatedHold
    let idempotencyKey: String

    enum CodingKeys: String, CodingKey {
        case hold
        case idempotencyKey = "idempotency_key"
    }
}

enum PersistedReservationFlow: Codable, Equatable, Sendable {
    case pendingHold(PendingHoldAttempt)
    case pendingConfirmation(PendingReservationConfirmation)
}

enum HoldServiceError: Error, Equatable, Sendable {
    case invalidResponse
    case seatUnavailable
    case idempotencyKeyReused
    case rejected(statusCode: Int)
}

protocol HoldService: Sendable {
    func createHold(for eventSeatID: UUID, idempotencyKey: String) async throws -> CreatedHold
}

struct HTTPHoldService: HoldService {
    let baseURL: URL
    var session: URLSession = .shared

    func createHold(for eventSeatID: UUID, idempotencyKey: String) async throws -> CreatedHold {
        var request = URLRequest(url: baseURL.appending(path: "v1/holds"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(idempotencyKey, forHTTPHeaderField: "Idempotency-Key")
        request.httpBody = try JSONEncoder().encode(HoldRequest(eventSeatID: eventSeatID))

        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else {
            throw HoldServiceError.invalidResponse
        }

        guard response.statusCode == 201 else {
            if response.statusCode == 409,
                let problem = try? JSONDecoder().decode(HoldProblem.self, from: data)
            {
                switch problem.code {
                case "seat_unavailable": throw HoldServiceError.seatUnavailable
                case "idempotency_key_reused": throw HoldServiceError.idempotencyKeyReused
                default: break
                }
            }
            throw HoldServiceError.rejected(statusCode: response.statusCode)
        }

        return try JSONDecoder().decode(CreatedHold.self, from: data)
    }
}

private struct HoldRequest: Encodable {
    let eventSeatID: UUID

    enum CodingKeys: String, CodingKey {
        case eventSeatID = "event_seat_id"
    }
}

private struct HoldProblem: Decodable {
    let code: String
}

struct CreatedReservation: Codable, Equatable, Sendable {
    let id: UUID
    let holdID: UUID
    let eventSeatID: UUID
    let status: String
    let confirmedAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case holdID = "hold_id"
        case eventSeatID = "event_seat_id"
        case status
        case confirmedAt = "confirmed_at"
    }
}

enum ReservationServiceError: Error, Equatable, Sendable {
    case invalidResponse
    case holdExpired
    case seatUnavailable
    case idempotencyKeyReused
    case rejected(statusCode: Int)
}

protocol ReservationService: Sendable {
    func confirm(holdID: UUID, idempotencyKey: String) async throws -> CreatedReservation
}

struct HTTPReservationService: ReservationService {
    let baseURL: URL
    var session: URLSession = .shared

    func confirm(holdID: UUID, idempotencyKey: String) async throws -> CreatedReservation {
        var request = URLRequest(url: baseURL.appending(path: "v1/reservations"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(idempotencyKey, forHTTPHeaderField: "Idempotency-Key")
        request.httpBody = try JSONEncoder().encode(ConfirmReservationRequest(holdID: holdID))

        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else {
            throw ReservationServiceError.invalidResponse
        }

        guard response.statusCode == 201 else {
            if response.statusCode == 409,
                let problem = try? JSONDecoder().decode(HoldProblem.self, from: data)
            {
                switch problem.code {
                case "hold_expired": throw ReservationServiceError.holdExpired
                case "seat_unavailable": throw ReservationServiceError.seatUnavailable
                case "idempotency_key_reused":
                    throw ReservationServiceError.idempotencyKeyReused
                default: break
                }
            }
            throw ReservationServiceError.rejected(statusCode: response.statusCode)
        }

        return try JSONDecoder().decode(CreatedReservation.self, from: data)
    }
}

private struct ConfirmReservationRequest: Encodable {
    let holdID: UUID

    enum CodingKeys: String, CodingKey {
        case holdID = "hold_id"
    }
}
