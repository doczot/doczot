"""Bookshop API — a small catalog service.

Every endpoint in this module is documented in docs/api.md. This case is the
positive control: DocZot should report near-total coverage here, and any
endpoint it flags as undocumented is a false positive.
"""

from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Bookshop API",
    description="Catalog service for books and their authors",
)


@app.get("/books")
def list_books():
    """List every book in the catalog."""
    return [{"id": 1, "title": "Dune", "author_id": 1}]


@app.get("/books/{book_id}")
def get_book(book_id: int):
    """Retrieve a single book by its identifier."""
    if book_id <= 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"id": book_id, "title": "Dune", "author_id": 1}


@app.post("/books")
def create_book(payload: dict):
    """Add a new book to the catalog."""
    return {"id": 2, "title": payload.get("title")}


@app.delete("/books/{book_id}")
def delete_book(book_id: int):
    """Remove a book from the catalog."""
    return {"deleted": book_id}


@app.get("/authors")
def list_authors():
    """List every author known to the catalog."""
    return [{"id": 1, "name": "Frank Herbert"}]


@app.get("/authors/{author_id}")
def get_author(author_id: int):
    """Retrieve a single author by their identifier."""
    return {"id": author_id, "name": "Frank Herbert"}
