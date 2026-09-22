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
protocol PendingHoldAttemptStore {
    func load() -> PendingHoldAttempt?
    func save(_ attempt: PendingHoldAttempt)
    func clear()
}

@MainActor
struct UserDefaultsPendingHoldAttemptStore: PendingHoldAttemptStore {
    private let defaults: UserDefaults
    private let key = "seatsafe.pendingHoldAttempt"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func load() -> PendingHoldAttempt? {
        guard let data = defaults.data(forKey: key) else { return nil }
        do {
            return try JSONDecoder().decode(PendingHoldAttempt.self, from: data)
        } catch {
            // Invalid local state cannot be used safely as an idempotent retry.
            defaults.removeObject(forKey: key)
            return nil
        }
    }

    func save(_ attempt: PendingHoldAttempt) {
        guard let data = try? JSONEncoder().encode(attempt) else { return }
        defaults.set(data, forKey: key)
    }

    func clear() {
        defaults.removeObject(forKey: key)
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
