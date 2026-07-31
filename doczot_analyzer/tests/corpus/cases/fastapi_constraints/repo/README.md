# Workspace API

A collaboration service for shared workspaces and the documents inside them.

## Authentication

Every workspace endpoint requires a bearer token. Obtain one by posting
credentials to `POST /auth/login`; the returned `access_token` must be sent in
the `Authorization` header on subsequent requests.

## Rate limiting

`GET /workspaces` is limited to 60 requests per minute per token. Exceeding the
limit returns `429`.

## Workspaces

A workspace is a shared container that several users may collaborate in.

## Documents

A document is a file stored inside a workspace. Documents cannot exist outside
of a workspace.
