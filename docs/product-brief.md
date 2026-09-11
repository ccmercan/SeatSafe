# Product brief

## Product statement

SeatSafe helps a user discover a local event, temporarily hold a specific seat, confirm a reservation, retrieve that reservation while offline, and cancel it when needed.

The product is fictional and uses deterministic data. It does not sell real tickets or process real payments.

## User problem

Seat reservation looks simple in a user interface but becomes difficult when inventory changes concurrently, requests are retried, holds expire, devices lose connectivity, or cached data becomes stale. SeatSafe makes these failure modes first-class product behavior.

## Primary user

A mobile user reserving one seat at a small concert, talk, or community event.

## Core journey

1. Browse or search upcoming events.
2. Open an event and inspect its details.
3. View the event's seat map.
4. Select an available seat.
5. Receive a temporary hold with an expiration time.
6. Confirm the hold as a reservation.
7. Retrieve the reservation online or from a local cache.
8. Cancel the reservation when necessary.

## Product states that matter

- Initial loading, successful loading, empty results, and recoverable failure
- Online, offline with cached data, and offline without cached data
- Available, selected, held, reserved, cancelled, and expired seats
- Successful reservation, idempotent retry, and reservation conflict
- Current data, stale cached data, and data awaiting synchronization
- Rapid navigation while earlier requests are still running
- Repeated taps while a reservation operation is already in progress

## Seat lifecycle

```text
Available -> Held -> Reserved -> Cancelled
                |
                +-> Expired -> Available
```

The backend is authoritative. The client may display cached availability, but it cannot guarantee a seat until the backend creates a hold.

The client must also remain internally consistent while asynchronous work overlaps. A late response for an event the user has left must not overwrite the current screen, and repeated user actions must not launch uncontrolled duplicate work.

## Initial screens

### Explore

- Upcoming event list
- Search and a small set of filters
- Loading, empty, error, and cached-data states

### Event details

- Title, time, venue, description, availability, and starting price
- Sold-out and available states
- Entry point to seat selection

### Seat selection

- Accessible seat grid
- Availability legend
- Selected seat and price
- Hold countdown and conflict recovery

### Reservations

- Upcoming and cancelled reservations
- Offline availability and last-sync information
- Cancellation flow

## Explicitly out of scope for the first release

- Real payments or financial data
- Real ticketing-provider integration
- Social features
- Push notifications
- Maps and location tracking
- A production administration portal
- Multiple-seat checkout
- App Store publication

These can be revisited only when the initial quality goals are demonstrably complete.

## Success criteria

The first portfolio release is successful when a reviewer can:

1. Run the system locally with documented commands.
2. Complete the critical reservation journey in the iOS simulator.
3. Observe correct behavior under simultaneous reservation attempts.
4. Inspect maintainable tests at multiple layers.
5. See trustworthy CI results and useful failure artifacts.
6. Understand the project's decisions, risks, defects, and measured outcomes from its documentation.
