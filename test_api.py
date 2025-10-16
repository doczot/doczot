from fastapi import FastAPI

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Get a user by ID."""
    return {"user_id": user_id}

@app.post("/users")
async def create_user():
    """Create a new user."""
    return {"created": True}
