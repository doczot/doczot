# API Reference

This reference covers event browsing and ticket purchase. Venue administration
endpoints are intentionally absent — they are internal and not yet documented.

## List events

`GET /events`

Returns every event currently on sale.

**Parameters:** none.

**Returns:** an array of event objects with `id` and `name`.

**Example**

```bash
curl https://api.example.com/events
```

## Get event

`GET /events/{event_id}`

Retrieves a single event by its identifier.

**Parameters:** `event_id` (integer, required).

**Returns:** an event object.

**Errors:** returns `404` when the event does not exist.

**Example**

```bash
curl https://api.example.com/events/1
```

## Purchase a ticket

`POST /tickets`

Purchases a ticket for an event.

**Parameters:** a JSON body with `event_id` (integer, required) and
`quantity` (integer, optional, defaults to 1).

**Returns:** the created ticket object.

**Errors:** returns `409` when the event is sold out.

**Example**

```bash
curl -X POST https://api.example.com/tickets -d '{"event_id": 1}'
```
