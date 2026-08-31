---
title: ContentForge AI
emoji: 🎯
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7861
pinned: false
---

# ContentForge AI

Self-optimizing multi-agent content engine.

## Local Run

```bash
pip install -r requirements.txt
copy .env.example .env
python main.py
```

## Interactive Step-by-Step Architecture (NEW)

ContentForge AI now supports an interactive 4-phase workflow:

### Phase 1: Data Gathering
- Keyword research + Competitor analysis
- Outputs: Target keywords, competitor metrics, content gaps

### Phase 2: Sub-Prompt Generation
- LLM analyzes research → generates 5-10 section sub-prompts
- Each prompt includes: title, word target, key points, detailed instructions

### Phase 3: Iterative Section Execution
- User clicks "Execute Next Section" button
- LLM writes 500-1000 words per section with accumulated context
- Context summaries auto-populate for next section

### Phase 4: Blog Assembly
- All sections merged into final blog
- Includes: metadata header, engaging intro, TOC, footer
- Download as .md file

### Technical Highlights
- **Gemini-only**: Uses `gemini-3.5-flash-lite` (15 RPM / 500 RPD free tier)
- **LangGraph interrupts**: Graph pauses after each phase for user interaction
- **SQLite checkpointer**: State persists across sessions
- **Global session management**: Single InteractiveSession handles all threads
