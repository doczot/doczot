"""Order routes."""

from fastapi import APIRouter

router = APIRouter(tags=["Orders"])


@router.get("/")
def list_orders():
    """List every order for the current account."""
    return []


@router.delete("/{order_id}")
def cancel_order(order_id: int):
    """Cancel an order."""
    return {"cancelled": order_id}
