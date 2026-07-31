"""Invoice routes."""

from fastapi import APIRouter

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("/")
def list_invoices():
    """List every invoice for the current account."""
    return []


@router.get("/{invoice_id}")
def get_invoice(invoice_id: int):
    """Retrieve a single invoice by identifier."""
    return {"id": invoice_id}


@router.post("/")
def create_invoice(payload: dict):
    """Issue a new invoice."""
    return {"id": 1}
