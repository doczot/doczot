# Golden Dataset - Source Repository Licenses

This document tracks the licenses of all repositories used to build the golden dataset.

## Purpose

The golden dataset consists of:
- Code snippets (FastAPI endpoints)
- Documentation excerpts
- Human ratings/annotations

We only include repositories with permissive licenses that allow research/analysis use.

---

## Approved Licenses for Dataset Use

✅ **Safe to use** for building golden dataset:
- MIT License
- Apache License 2.0
- BSD Licenses (2-clause, 3-clause)
- ISC License
- Unlicense / Public Domain

⚠️ **Need to review**:
- GPL licenses (may require derivative works to be GPL)
- LGPL licenses
- MPL licenses

❌ **Do not use**:
- Proprietary/closed source
- "All Rights Reserved"
- No license specified (copyright protected by default)

---

## Repositories in Golden Dataset

### 1. FastAPI (tiangolo/fastapi)
- **License**: MIT License
- **Copyright**: 2018 Sebastián Ramírez
- **URL**: https://github.com/tiangolo/fastapi
- **Status**: ✅ Approved
- **Date Added**: 2025-10-20
- **Notes**: Permissive MIT license allows analysis, research, and dataset creation

---

## License Compliance

### What we're doing:
1. **Analyzing** code and documentation (fair use for research)
2. **Extracting** structural information (endpoints, methods, paths)
3. **Creating annotations** (our expert ratings)
4. **Not redistributing** source code

### Our dataset contains:
- Metadata about endpoints (method, path, parameters)
- Short excerpts from documentation (fair use)
- Our human ratings (our original work)

### What we're NOT doing:
- Redistributing full source code
- Claiming ownership of analyzed code
- Removing license/copyright notices
- Creating derivative works for redistribution

---

## Adding New Repositories

Before scanning a new repository:

1. **Check for LICENSE file**:
   ```bash
   cat /path/to/repo/LICENSE
   ```

2. **Verify it's on approved list** (MIT, Apache 2.0, BSD)

3. **Document it in this file**:
   ```markdown
   ### N. [Repo Name] ([owner/repo])
   - **License**: [License Name]
   - **Copyright**: [Copyright Holder]
   - **URL**: [GitHub URL]
   - **Status**: ✅ Approved / ⚠️ Review / ❌ Rejected
   - **Date Added**: [YYYY-MM-DD]
   - **Notes**: [Any relevant notes]
   ```

4. **If uncertain, skip the repo** - plenty of MIT/Apache 2.0 projects available

---

## Legal Notes

**Disclaimer**: This is for research/development purposes. The golden dataset is:
- Used internally for development/validation
- Not sold or commercially licensed
- Contains minimal excerpts (fair use)
- Clearly attributes source repositories

If publishing research/results:
- Cite source repositories
- Include license information
- Respect original copyrights
- Consider anonymizing if needed

---

## Future Considerations

If DocZot becomes commercial:
- Review dataset usage rights
- Consider creating synthetic examples
- Get legal review if needed
- Possibly reach out to repo owners for explicit permission

For now (research/development phase):
- Use only permissively licensed repos
- Document all sources
- Keep excerpts minimal
- Maintain attribution

---

## Quick Reference

Safe to scan:
```bash
# Always MIT/Apache 2.0
- FastAPI and related projects
- Most Python ecosystem tools
- Many popular open-source APIs
```

Always check first:
```bash
cat /path/to/repo/LICENSE
# or
cat /path/to/repo/COPYING
```

When in doubt:
- Skip the repo
- Plenty of other options available
- Better safe than sorry
