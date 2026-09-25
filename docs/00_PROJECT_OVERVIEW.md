# ContentForge AI — Project Overview

**What:** AI-powered SEO blog generator deployed on HuggingFace Spaces.

**Input:** A topic (e.g., "best budget laptops 2026")
**Output:** A fully-researched, SEO-optimized blog article with authentic product recommendations, verified specs, pros/cons, and user quotes.

**Tech Stack:**
- Frontend/UI: Gradio 6.28.0
- Orchestration: LangGraph
- LLM: Gemini (via LLMRouter, task-based routing)
- Search: Tavily API
- Scraping: Firecrawl + httpx + BeautifulSoup
- Transcripts: youtube-transcript-api (pinned 0.6.2)
- Storage: SQLite (short-term memory, git-ignored)
- Deploy: HuggingFace Space (zero-a10g hardware)

**Repository:**
- GitHub: https://github.com/MdHuzaif/contentforge.git
- HuggingFace: https://huggingface.co/spaces/Huzaif-Enan/ContentForge

**Pipeline Phases:**
1. Phase 1 (data_gathering): keyword research → competitor analysis → content classification → product selection → deep dive
2. Phase 2 (subprompt_generator): Generate section sub-prompts
3. Phase 3 (section_writer): Write each section
4. Phase 4 (refinement): Apply shopping signals, SEO, internal links
