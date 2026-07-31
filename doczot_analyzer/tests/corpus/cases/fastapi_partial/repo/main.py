"""Ticketing API — an event ticketing service.

Exactly half of these endpoints are documented in docs/api.md:

    documented    GET  /events
                  GET  /events/{event_id}
                  POST /tickets

    undocumented  DELETE /tickets/{ticket_id}
                  GET    /venues
                  POST   /venues

The two halves are deliberately interleaved across the same resources so a
tool cannot get the right answer by reasoning at whole-resource granularity.
"""

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Ticketing API")


# --- documented ------------------------------------------------------------

@app.get("/events")
def list_events():
    """List all events."""
    return [{"id": 1, "name": "Concert"}]


@app.get("/events/{event_id}")
def get_event(event_id: int):
    """Retrieve one event."""
    if event_id <= 0:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"id": event_id, "name": "Concert"}


@app.post("/tickets")
def create_ticket(payload: dict):
    """Purchase a ticket for an event."""
    return {"id": 1, "event_id": payload.get("event_id")}


# --- undocumented ----------------------------------------------------------

@app.delete("/tickets/{ticket_id}")
def delete_ticket(ticket_id: int):
    """Refund a ticket."""
    return {"refunded": ticket_id}


@app.get("/venues")
def list_venues():
    """List venues."""
    return [{"id": 1, "name": "Arena"}]


@app.post("/venues")
def create_venue(payload: dict):
    """Create a venue."""
    return {"id": 2}
