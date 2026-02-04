# FastAPI Template Example

DocZot analysis output for [tiangolo/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template).

## Files

| File | Layer | Description |
|------|-------|-------------|
| `surface.json` | System Graph | Code structure: endpoints, entities, constraints, and their relationships |
| `itm.json` | Coverage Checklist | Auto-generated plan of what documentation topics should exist |
| `atm.json` | Content Inventory | What documentation actually exists, with match evidence |
| `gaps.json` | Drift Report | Divergence between code state and documentation state |
| `doczot-viz.html` | Visualization | Interactive HTML visualization (open in browser) |
| `MATCH_REVIEW.md` | Review | Human-readable coverage review for validation |

## Match Evidence

The `atm.json` includes `match_evidence` on each topic, recording:

- **Strategy**: `direct_reference` (explicit endpoint mention in docs) or `semantic` (vector similarity)
- **Confidence**: 0.0-1.0 score
- **Doc snippet**: The matching text from documentation
- **Match detail**: How the match was determined

The `doczot-viz.html` visualization shows this evidence when you click on graph nodes.

## Regenerating

```bash
doczot analyze /path/to/full-stack-fastapi-template --output examples/fastapi-template/
doczot visualize /path/to/full-stack-fastapi-template --output examples/fastapi-template/doczot-viz.html
```
