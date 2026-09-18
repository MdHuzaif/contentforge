---
title: ContentForge AI
emoji: 🎯
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: 5.20.0
python_version: 3.10.14
app_file: main.py
suggested_hardware: zero-a100-small
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

## 🚀 Deployment to Hugging Face

### Required Environment Variables

Set these in HF Space Settings → Variables and secrets:

| Variable | Type | Description |
|----------|------|-------------|
| `GITHUB_TOKEN` | Secret 🔒 | GitHub PAT with `repo` scope |
| `UNISCOLIAN_REPO_URL` | Variable 📝 | `https://github.com/MdHuzaif/uniscolian-website.git` |
| `CLOUDFLARE_ACCOUNT_ID` | Variable 📝 | Your Cloudflare account ID |
| `CLOUDFLARE_API_TOKEN` | Secret 🔒 | Cloudflare API token |
| `GEMINI_API_KEY` | Secret 🔒 | Google Gemini API key |
| `UNISCOLIAN_ROOT` | Variable 📝 | `/tmp/uniscolian-website` (for HF Space) |
| `SITE_BASE_URL` | Variable 📝 | `https://uniscolian.com` |

### Auto-Push Behavior

- **New posts**: Auto-pushed to GitHub → Netlify auto-deploys
- **Updated posts**: NOT auto-pushed (minor fixes only)
- **Local dev**: Auto-push skipped if credentials not set


