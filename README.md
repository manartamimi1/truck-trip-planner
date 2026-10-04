# Truck Trip Planner

A full-stack assessment project that plans a truck route, estimates a driver schedule using the supplied hours-of-service inputs, and presents a route map and daily ELD-style logs.

## Features

- Route planning through current location, pickup, and dropoff
- HOS-aware schedule with driving, rest, pickup, dropoff, and fuel events
- Interactive route map with locations and schedule stop markers
- Daily ELD-style duty graphs, remarks, and 24-hour totals

## Tech Stack

- **Frontend:** React, Vite, Leaflet, React Leaflet
- **Backend:** Django, Django REST Framework, SQLite
- **External services:** OpenStreetMap Nominatim for geocoding and OSRM for driving routes

## Project Structure

```text
backend/
  config/       Django project settings and URL configuration
  trips/        API, routing services, and isolated HOS engine
  manage.py
frontend/
  src/          React UI, map, ELD components, API client, and utilities
```

## Local Setup

### Backend (Windows PowerShell)

From the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
cd backend
python manage.py migrate
python manage.py runserver
```

If PowerShell blocks virtual-environment activation, run the Python executable directly as `..\.venv\Scripts\python.exe` from `backend/`.

### Backend (macOS / Linux)

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
python manage.py migrate
python manage.py runserver
```

The API runs at <http://127.0.0.1:8000/>.

### Frontend

In another terminal, from the project root:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (usually <http://localhost:5173/>). The frontend uses `http://127.0.0.1:8000` as its default API base. Set `VITE_API_BASE_URL` in a local frontend environment file to override it.

## Usage

Enter the driver's current location, pickup location, dropoff location, and on-duty hours already used in the current cycle. For example:

```text
Current location: Chicago, IL
Pickup:            Indianapolis, IN
Dropoff:           Atlanta, GA
Current cycle used: 15 hours
```

Submit the form to view the routed distance, schedule, map, stops, and daily logs.

## HOS Assumptions

The schedule models a property-carrying driver using these assessment rules:

- Up to 11 driving hours after a qualifying 10-hour sleeper rest
- A 14-hour duty window, reset by the qualifying sleeper rest
- A 30-minute break after 8 cumulative driving hours without a qualifying break
- 10 hours for a sleeper rest
- A 70-hour / 8-day cycle limit
- One hour on duty for pickup and one hour on duty for dropoff
- A 30-minute fuel event at least every 1,000 route miles

The assessment supplies only the driver's current cycle-used hours. At trip start, the planner therefore assumes a fresh driving clock, 14-hour window, and break clock. It cannot reconstruct the driver's prior eight-day rolling history because that information is not provided. These are planning assumptions, not a complete determination of regulatory compliance.

The ELD visualization fills the final day's time after trip completion as Off Duty because post-trip activity is unknown. Its day labels are elapsed trip days, not calendar dates.

## API

`POST /api/trips/plan/` accepts JSON such as:

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Indianapolis, IN",
  "dropoff_location": "Atlanta, GA",
  "current_cycle_used": 15
}
```

The response contains resolved locations, route distance/duration and GeoJSON geometry, route legs, the HOS timeline, summary, and (when the cycle limit is reached) remaining-trip details.

## Testing

From `backend/`:

```bash
python manage.py test
```

From `frontend/`:

```bash
npm test
npm run build
```

The frontend utility tests use Node's built-in test assertions and add no test framework dependency.

## Limitations

- Public Nominatim and OSRM services may be rate-limited, unavailable, or changed; they are best-effort services. This backend throttles Nominatim requests to at most one per second. Review the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/) and [OSRM demo-server policy](https://github.com/Project-OSRM/osrm-backend/wiki/Api-usage-policy) before relying on these public services.
- HOS and fuel-stop marker positions are interpolated along route geometry. They are estimates, not named rest areas or real fuel-station searches.
- Authentication and trip persistence are not included because they are outside the assessment scope.
- Historical ELD state beyond the supplied current cycle-used hours is unavailable to the planner.
