# Change Plan: Dynamic Product Extraction

**Date:** 2026-09-25
**Status:** PENDING REVIEW
**Risk Level:** LOW
**Files Affected:** core/selectors/product_selector.py

## 🎯 Problem Statement
Current product extraction forces a hardcoded target of 20 products (target_count * 2), causing LLMs to hallucinate and invent non-existent or discontinued products (e.g. Dell Alienware 15) when competitor articles contain fewer real products. This plan transitions Stage 1a extraction to dynamic "ALL products mentioned" extraction, supported by post-extraction validation and hallucination detection.

## 📍 Changes Required

### Change #1: Update Extraction Prompt Template
- **File:** core/selectors/product_selector.py
- **Function:** EXTRACTION_PROMPT_TEMPLATE
- **Line:** 145
- **Type:** REPLACE

**BEFORE:**
```python
5. Target: Extract {target_count} products (or fewer if competitors mention fewer)
```

**AFTER:**
```python
5. TARGET: Extract ALL specific products mentioned in the competitor content.
   - There may be anywhere from 5 to 30 products — extract what's actually there
   - Do NOT invent products to reach a target number
   - Do NOT add products not mentioned in the content
   - Quality over quantity: better to extract 8 real products than 20 with fake ones
   - Minimum: Extract at least 5 products if available
   - Maximum: No limit — extract every specific product mentioned
```

**Rationale:** Removes hardcoded quantity constraints from the LLM prompt, preventing hallucinations.

### Change #2: Remove target_count * 2 from prompt format call
- **File:** core/selectors/product_selector.py
- **Function:** extract_products_universal
- **Line:** 261
- **Type:** REPLACE / DELETE

**BEFORE:**
```python
            prompt = EXTRACTION_PROMPT_TEMPLATE.format(
                topic=topic,
                competitor_count=competitor_count,
                competitor_content=competitor_content,
                structure_content=structure_content,
                target_count=target_count * 2,
            )
```

**AFTER:**
```python
            prompt = EXTRACTION_PROMPT_TEMPLATE.format(
                topic=topic,
                competitor_count=competitor_count,
                competitor_content=competitor_content,
                structure_content=structure_content,
                # target_count removed - extraction is now dynamic
            )
```

**Rationale:** Eliminates the hardcoded multiplier from prompt formatting.

### Change #3: Add Hallucination Detection in Validation
- **File:** core/selectors/product_selector.py
- **Function:** _validate_and_enrich
- **Line:** 1019-1030
- **Type:** ADD

**BEFORE:**
```python
    # Sort by popularity score (highest first)
    validated.sort(key=lambda x: x.get("popularity_score", 0), reverse=True)
    
    return validated[:target_count]
```

**AFTER:**
```python
    # Sort by popularity score (highest first)
    validated.sort(key=lambda x: x.get("popularity_score", 0), reverse=True)

    # After validating products, flag suspicious ones
    suspicious = []
    for p in validated:
        name = p.get("name", "")
        # Flag discontinued/generic names
        if any(word in name.lower() for word in ["discontinued", "legacy", "old"]):
            suspicious.append(p["name"])
        # Flag very short names (likely generic)
        if len(name.split()) < 2:
            suspicious.append(p["name"])

    if suspicious:
        logger.warning(f"⚠️ Potentially hallucinated products: {suspicious}")
    
    return validated[:target_count]
```

**Rationale:** Adds safety monitoring to detect and warn about potentially outdated or hallucinated product entries.

## ⚠️ Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Fewer products extracted than expected | Medium | Stage 1b intelligent selection and Stage 3 top-up ensure fallback generation if candidate count falls below target_count. |
| False positive warnings in hallucination detection | Low | Logging only warnings; does not reject products automatically unless caught by freshness filter. |

## 🧪 Verification Plan
1. Run pytest suite (`venv\Scripts\pytest.exe tests/test_stage1a_extraction.py tests/test_product_extraction.py tests/test_smart_selection.py tests/test_product_freshness.py`).
2. Verify test cases pass successfully.
3. Review expected log outputs showing dynamic extraction counts and Stage 1b intelligent selection.

## 🔄 Rollback Plan
Revert changes to `core/selectors/product_selector.py` via git checkout if any regression occurs.

## 📊 Expected Outcome
- Before: Hardcoded extraction of 20 candidate products, leading to LLM hallucinations on older/discontinued models.
- After: Dynamic extraction of actual products mentioned in competitor content (e.g., 8-15 authentic products), intelligently filtered and topped up.
