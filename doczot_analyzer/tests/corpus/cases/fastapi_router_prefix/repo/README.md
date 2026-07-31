# Billing API

Invoicing and subscription management.

All endpoints are served under the `/api/v1` prefix.

## Invoices

An invoice is a billing record issued to an account.

### List invoices

`GET /api/v1/invoices/` returns every invoice for the current account.

### Get invoice

`GET /api/v1/invoices/{invoice_id}` retrieves a single invoice by identifier.
Returns `404` when the invoice does not exist.

## Subscriptions

A subscription is a recurring charge against an account.

### List subscriptions

`GET /api/v1/subscriptions/` returns the account's active subscriptions.
