# API Reference

Complete reference for the Bookshop API. Every endpoint the service exposes is
listed below.

## List books

`GET /books`

Returns every book in the catalog.

**Parameters:** none.

**Returns:** an array of book objects, each with `id`, `title` and `author_id`.

**Example**

```bash
curl https://api.example.com/books
```

## Get book

`GET /books/{book_id}`

Retrieves a single book by its identifier.

**Parameters:** `book_id` (integer, required) — the book's identifier.

**Returns:** a book object.

**Errors:** returns `404` when no book has the given identifier.

**Example**

```bash
curl https://api.example.com/books/1
```

## Create book

`POST /books`

Adds a new book to the catalog.

**Parameters:** a JSON body containing `title` (string, required) and
`author_id` (integer, required).

**Returns:** the newly created book object, including its assigned `id`.

**Errors:** returns `422` when the body is missing a required field.

**Example**

```bash
curl -X POST https://api.example.com/books -d '{"title": "Dune", "author_id": 1}'
```

## Delete book

`DELETE /books/{book_id}`

Removes a book from the catalog. This operation cannot be undone.

**Parameters:** `book_id` (integer, required).

**Returns:** an object confirming the deleted identifier.

**Errors:** returns `404` when no book has the given identifier.

**Example**

```bash
curl -X DELETE https://api.example.com/books/1
```

## List authors

`GET /authors`

Returns every author known to the catalog.

**Parameters:** none.

**Returns:** an array of author objects, each with `id` and `name`.

**Example**

```bash
curl https://api.example.com/authors
```

## Get author

`GET /authors/{author_id}`

Retrieves a single author by their identifier.

**Parameters:** `author_id` (integer, required).

**Returns:** an author object.

**Errors:** returns `404` when no author has the given identifier.

**Example**

```bash
curl https://api.example.com/authors/1
```
