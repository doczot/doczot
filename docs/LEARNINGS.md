# Learnings from Real Codebase Testing

This document captures important insights discovered while testing DocZot on real-world codebases.

## Date: 2025-10-20

### Testing FastAPI Repository

**Repository:** https://github.com/tiangolo/fastapi (MIT License)

**Dataset Size:** 1,258 endpoints initially detected

---

## Key Findings

### 1. Test Files Should Be Excluded

**Problem:** The scanner was detecting endpoints in test files as if they were production endpoints.

**Example:**
```python
# File: tests/test_datastructures.py
@app.post("/uploadfile/")
def create_upload_file(file: UploadFile):
    testing_file_store.append(file)
    return {"filename": file.filename}
```

**Why this matters:**
- Test files often create **fixture endpoints** just to test functionality
- These are NOT meant to be documented for end users
- They create false positives in coverage analysis
- The same endpoint path might exist in both tests AND docs (as tutorial examples)

**Solution Implemented:**
- Exclude entire `tests/` and `test/` directories
- Exclude files matching `test_*.py` and `*_test.py` patterns
- Updated in: `doczot_analyzer/scanner.py`

**Code change:**
```python
skip_dirs = {"__pycache__", ".venv", "venv", ".git", "node_modules", "tests", "test"}

# Skip test files (test_*.py, *_test.py)
if py_file.name.startswith("test_") or py_file.name.endswith("_test.py"):
    continue
```

---

### 2. Translation Documentation Should Be Excluded

**Problem:** Documentation often exists in multiple languages, creating massive duplicate matches.

**Example:**
- FastAPI has docs in: zh, ja, pt, de, fr, ru, es, ko, vi, uk, em, fa, tr, zh-hant
- A single endpoint had **184 documentation matches** initially
- 87% of matches were translations of the same English doc

**Why this matters:**
- Translations are exact copies of English docs (for analysis purposes)
- They pollute the matching process with duplicate information
- They make manual review/rating extremely time-consuming
- The LLM doesn't need to see the same doc in 15 languages

**Solution Implemented:**
- Exclude common translation directories: `docs/zh/`, `docs/ja/`, etc.
- Keep only English docs: `docs/en/`, root `README.md`, or no language prefix
- Updated in: `doczot_analyzer/docs_parser.py`

**Results:**
- Before: 823 documentation references
- After: 105 documentation references (87% reduction)
- Example endpoint matches reduced from 184 → 26

**Code change:**
```python
TRANSLATION_DIRS = {
    "zh", "ja", "pt", "de", "fr", "ru", "es", "ko", "vi", "uk", "em",
    "fa", "tr", "it", "nl", "pl", "ar", "hi", "id", "th", "cs", "sv",
    "zh-hant", "zh-hans", "pt-br", "es-es", "en-gb",
}

# Skip translation directories
if any(part in TRANSLATION_DIRS for part in parts):
    continue
```

---

## Impact on Product

### Before Changes
- **Total endpoints detected:** 1,258 (many were test fixtures)
- **Documentation references:** 823 (mostly translations)
- **Average matches per endpoint:** 15-50+ (including duplicates)
- **Manual review:** Nearly impossible due to noise

### After Changes
- **Total endpoints detected:** TBD (will exclude tests)
- **Documentation references:** 105 (English only)
- **Average matches per endpoint:** 1-10 (much more reasonable)
- **Manual review:** Feasible and productive

---

## Lessons for Product Development

### 1. Real Codebases Reveal Edge Cases
- Synthetic examples don't capture real-world complexity
- Testing on popular open source projects is essential
- Always validate assumptions with actual data

### 2. Filtering is Critical for UX
- Too much noise = unusable product
- Better to exclude edge cases than overwhelm users
- Precision > Recall for documentation coverage tools

### 3. Configuration Should Be Flexible
Users might want to:
- Include/exclude test files based on their use case
- Support multi-language docs (some teams DO maintain translations)
- Customize which directories to scan

**Future enhancement:** Add configuration options for these exclusions.

---

## Test Cases to Add

Based on these findings, we should add tests for:

1. **Test file exclusion:**
   - Verify `tests/test_foo.py` is skipped
   - Verify `test_bar.py` in root is skipped
   - Verify `foo_test.py` is skipped
   - Verify `tests/` directory is completely excluded

2. **Translation exclusion:**
   - Verify `docs/zh/api.md` is skipped
   - Verify `docs/en/api.md` is included
   - Verify `docs/api.md` (no language) is included
   - Verify all language codes in TRANSLATION_DIRS are excluded

3. **Real-world validation:**
   - Test scanner on 3-5 popular FastAPI projects
   - Measure endpoint detection accuracy
   - Verify no false positives from test files

---

## Documentation Updates Needed

1. **Feature specs:**
   - Update `docs/features/endpoint-detection.md` to document test exclusion
   - Update `docs/features/documentation-parsing.md` to document translation exclusion

2. **Configuration docs:**
   - Document how to override exclusions (when we add config support)
   - Explain why tests and translations are excluded by default

3. **Self-hosting guide:**
   - Add section on customizing scanner behavior
   - Provide examples of when to include test files (if ever)

---

## Next Steps

- [x] Implement test file exclusion in scanner
- [x] Implement translation exclusion in docs parser
- [ ] Write unit tests for both exclusions
- [ ] Update feature specifications
- [ ] Test on additional real-world repositories
- [ ] Consider adding configuration support for exclusions

---

## Credits

These insights came from manually testing the dataset building process on the FastAPI repository and attempting to rate endpoint/doc pairs. This real-world validation was essential for discovering these issues.

**Methodology:** Build in public, test on real code, iterate based on actual usage.
