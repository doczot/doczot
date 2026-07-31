"""Subscription routes."""

from fastapi import APIRouter

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/")
def list_subscriptions():
    """List the account's subscriptions."""
    return []


@router.delete("/{subscription_id}")
def cancel_subscription(subscription_id: int):
    """Cancel a subscription."""
    return {"cancelled": subscription_id}
