# DocZot Expert Reviewer

A manual review interface for validating and improving DocZot's documentation coverage judgments.

## Quick Start

### 1. Generate Analysis Results

```bash
# From project root
./venv/bin/python scripts/run_on_repo.py <repo_path> --save-for-review
```

This creates a `review_session_YYYYMMDD_HHMMSS.json` file.

### 2. Start Backend

```bash
cd doczot_reviewer/backend
../../venv/bin/uvicorn app:app --reload --port 8001
```

### 3. Start Frontend

```bash
cd doczot_reviewer/frontend  
npm run dev
```

Frontend will open at `http://localhost:5173`

### 4. Create Review Session

Use the API to create a session:

```bash
curl -X POST "http://localhost:8001/sessions" \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "test_repos/fastapi-users", "results_file": "review_session_20251122_143844.json"}'
```

Copy the returned `session_id`.

### 5. Load Session in UI

Paste the `session_id` in the frontend and click "Load Session".

## Usage

### Keyboard Shortcuts

- **A** - Approve current match
- **R** - Reject current match  
- **S** - Skip to next endpoint
- **← →** - Navigate between endpoints

### Review Workflow

1. Review endpoint details (method, path, docstring, parameters)
2. Check the match info (analysis method, confidence score)
3. Make judgment:
   - **Approve**: Match is correct
   - **Reject**: Match is incorrect
   - **Adjust**: Match is partially correct, adjust confidence
   - **Skip**: Unsure, come back later

### Export Results

```bash
curl "http://localhost:8001/sessions/{session_id}/export" > reviewed_results.json
```

## API Endpoints

- `POST /sessions` - Create review session
- `GET /sessions/{id}` - Get session details
- `GET /sessions/{id}/endpoints/{endpoint_id}` - Get specific endpoint
- `POST /sessions/{id}/judgments` - Submit judgment
- `GET /sessions/{id}/export` - Export results with statistics

## Architecture

```
doczot_reviewer/
├── models.py           # Pydantic models for sessions, judgments
├── backend/
│   └── app.py         # FastAPI backend
├── frontend/
│   ├── src/
│   │   ├── App.tsx    # Main review interface
│   │   └── App.css    # Styling
│   └── package.json
└── tests/             # Test suite (TBD)
```

## Future Enhancements (Phase 2)

- Project-level semantic map visualization
- 2D embedding visualization (UMAP/t-SNE)
- Coverage heatmap
- Divergence detection
- Bulk approval workflows
- Export to golden dataset
