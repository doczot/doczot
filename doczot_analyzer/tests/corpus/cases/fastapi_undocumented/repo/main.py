"""Inventory API — a warehouse stock service.

Nothing in this module is documented. The README covers installation only and
never describes a single endpoint. This case is the negative control: DocZot
should report near-zero coverage, and any endpoint it credits as documented is
a false negative for gap detection.
"""

from fastapi import FastAPI

app = FastAPI(title="Inventory API")


@app.get("/warehouses")
def list_warehouses():
    """List warehouses."""
    return []


@app.get("/warehouses/{warehouse_id}")
def get_warehouse(warehouse_id: int):
    """Get a warehouse."""
    return {"id": warehouse_id}


@app.post("/shipments")
def create_shipment(payload: dict):
    """Create a shipment."""
    return {"id": 1}


@app.get("/shipments/{shipment_id}")
def get_shipment(shipment_id: int):
    """Get a shipment."""
    return {"id": shipment_id}


@app.patch("/shipments/{shipment_id}")
def update_shipment(shipment_id: int, payload: dict):
    """Update a shipment."""
    return {"id": shipment_id}
