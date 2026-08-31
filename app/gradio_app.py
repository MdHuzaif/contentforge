"""Gradio UI for interactive step-by-step ContentForge AI."""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional
import pandas as pd
import gradio as gr

from app.config import APP_TITLE, GRADIO_SERVER_NAME, GRADIO_SERVER_PORT, BLOGS_DIR, logger
from core.exporters.markdown_converter import slugify
from core.exporters.pdf_exporter import blog_to_pdf
from core.exporters.static_exporter import export_post_to_uniscolian
from core.interactive import InteractiveSession


# Global session manager (single global session with SQLite checkpointer)
_global_session: Optional[InteractiveSession] = None
_session_lock = asyncio.Lock()


async def get_session() -> InteractiveSession:
    """Get the single global InteractiveSession (created on first use)."""
    global _global_session
    if _global_session is None:
        async with _session_lock:
            if _global_session is None:
                session = InteractiveSession()
                await session.initialize()
                _global_session = session
                logger.info("Global InteractiveSession initialized")
    return _global_session


async def start_research_action(topic: str):
    """Phase 1: Run keyword research and competitor analysis."""
    if not topic or not topic.strip():
        return (
            "⚠️ Please enter a topic",
            pd.DataFrame({"Keyword": [], "Intent": [], "Difficulty": []}),
            pd.DataFrame({"Metric": [], "Value": []}),
            "*Gap analysis will appear here after research*",
            gr.update(interactive=False),
            "",
        )
    
    try:
        thread_id = str(uuid.uuid4())
        session = await get_session()  # Use global session
        logger.info(f"Starting research for new thread: {thread_id}")
        
        result = await session.start_research(topic.strip(), thread_id=thread_id)
        
        # Build keyword DataFrame
        kw_data = result.get("keyword_research", {})
        keywords_list = kw_data.get("keywords", [])
        if keywords_list and isinstance(keywords_list, list):
            kw_df = pd.DataFrame([
                {
                    "Keyword": k.get("keyword", "") if isinstance(k, dict) else str(k),
                    "Intent": k.get("intent", "N/A") if isinstance(k, dict) else "N/A",
                    "Difficulty": k.get("difficulty", "N/A") if isinstance(k, dict) else "N/A",
                }
                for k in keywords_list
            ])
        else:
            kw_df = pd.DataFrame({"Keyword": ["No keywords found"], "Intent": ["-"], "Difficulty": ["-"]})
        
        # Build competitor metrics
        comp_data = result.get("competitor_analysis", {})
        metrics = comp_data.get("metrics", {})
        if metrics and isinstance(metrics, dict):
            metrics_df = pd.DataFrame([
                {"Metric": k.replace("_", " ").title(), "Value": str(v)}
                for k, v in metrics.items()
            ])
        else:
            metrics_df = pd.DataFrame({"Metric": ["No metrics"], "Value": ["-"]})
        
        gap_analysis = comp_data.get("gap_analysis", "*No gap analysis available*")
        
        logger.info(f"Phase 1 complete for thread {thread_id}")
        
        return (
            f"✅ Research complete for: **{topic}**\n\n🆔 Thread: `{thread_id[:8]}...`",
            kw_df,
            metrics_df,
            gap_analysis,
            gr.update(interactive=True),
            thread_id,
        )
    except Exception as e:
        logger.error(f"Research failed: {e}", exc_info=True)
        return (
            f"❌ Research failed: {str(e)}",
            pd.DataFrame({"Keyword": [], "Intent": [], "Difficulty": []}),
            pd.DataFrame({"Metric": [], "Value": []}),
            "*Error during research*",
            gr.update(interactive=False),
            "",
        )


async def generate_prompts_action(thread_id: str):
    """Phase 2: Generate sub-prompts from research."""
    logger.info(f"Generate prompts called with thread_id: '{thread_id}'")
    
    if not thread_id or not thread_id.strip():
        logger.warning("Empty thread_id received")
        return (
            pd.DataFrame({"Section": [], "Title": [], "Word Target": [], "Status": []}),
            "*Please run research first*",
            gr.update(interactive=False),
        )
    
    try:
        session = await get_session()  # Use global session
        
        # Verify state exists in SQLite for this thread
        state = await session.get_state(thread_id)
        if not state["values"]:
            logger.error(f"No state found for thread {thread_id} in SQLite")
            return (
                pd.DataFrame({"Section": [], "Title": [], "Word Target": [], "Status": []}),
                "*❌ Session expired or state lost. Please run research again.*",
                gr.update(interactive=False),
            )
        
        result = await session.generate_prompts(thread_id)
        
        sub_prompts = result.get("sub_prompts", [])
        total = result.get("total_sections", 0)
        
        if not sub_prompts:
            return (
                pd.DataFrame({"Section": [], "Title": [], "Word Target": [], "Status": []}),
                "*No sub-prompts generated*",
                gr.update(interactive=False),
            )
        
        prompt_df = pd.DataFrame([
            {
                "Section": i + 1,
                "Title": p.get("title", f"Section {i+1}"),
                "Word Target": p.get("word_target", 600),
                "Status": "⏳ Pending",
            }
            for i, p in enumerate(sub_prompts)
        ])
        
        summary = f"✅ Generated **{total} sub-prompts**. Click 'Execute Next Section' to start writing."
        logger.info(f"Phase 2 complete: {total} sub-prompts for thread {thread_id}")
        
        return (
            prompt_df,
            summary,
            gr.update(interactive=True, value=f"▶️ Execute Next Section (1/{total})"),
        )
    except ValueError as e:
        logger.error(f"ValueError in generate_prompts: {e}")
        return (
            pd.DataFrame({"Section": [], "Title": [], "Word Target": [], "Status": []}),
            f"❌ {str(e)}. Please run research again.",
            gr.update(interactive=False),
        )
    except Exception as e:
        logger.error(f"Prompt generation failed: {e}", exc_info=True)
        return (
            pd.DataFrame({"Section": [], "Title": [], "Word Target": [], "Status": []}),
            f"❌ Error: {str(e)}",
            gr.update(interactive=False),
        )


async def execute_next_section_action(thread_id: str, current_button_text: str):
    """Phase 3: Execute one section at a time."""
    logger.info(f"Execute section called with thread_id: '{thread_id}'")
    
    if not thread_id or thread_id.strip() == "":
        return (
            None,
            "*No active session - please run research first*",
            gr.update(interactive=False),
            "*Blog will appear here as sections are generated*",
        )
    
    try:
        session = await get_session()
        result = await session.execute_next_section(thread_id)
        
        current_idx = result.get("current_section_index", 0)
        total = result.get("total_sections", 0)
        generated = result.get("generated_sections", [])
        
        # Update DataFrame to show completed sections
        sub_prompts_result = await session.get_state(thread_id)
        sub_prompts = sub_prompts_result["values"].get("sub_prompts", [])
        
        prompt_df = pd.DataFrame([
            {
                "Section": i + 1,
                "Title": p.get("title", f"Section {i+1}"),
                "Word Target": p.get("word_target", 600),
                "Status": "✅ Complete" if i < current_idx else "⏳ Pending",
            }
            for i, p in enumerate(sub_prompts)
        ])
        
        # Build blog preview (append sections as they're generated)
        blog_preview_parts = [f"# Blog Preview ({current_idx}/{total} sections complete)\n"]
        for section in generated:
            blog_preview_parts.append(section.get("content", ""))
            blog_preview_parts.append("\n\n---\n\n")
        blog_preview = "".join(blog_preview_parts)
        
        # Update button text
        if current_idx >= total:
            button_text = "✅ All Sections Complete"
            button_disabled = True
            summary = f"🎉 All **{total} sections** complete! Switch to 'Final Blog' tab and click 'Assemble Final Blog'."
        else:
            button_text = f"▶️ Execute Next Section ({current_idx + 1}/{total})"
            button_disabled = False
            summary = f"✅ Section {current_idx}/{total} complete. Words: {sum(s.get('word_count', 0) for s in generated)}"
        
        logger.info(f"Section {current_idx}/{total} complete")
        
        return (
            prompt_df,
            summary,
            gr.update(interactive=not button_disabled, value=button_text),
            blog_preview,
        )
    except Exception as e:
        logger.error(f"Section execution failed: {e}", exc_info=True)
        return (
            None,
            f"❌ Error: {str(e)}",
            gr.update(interactive=False),
            None,
        )


async def _get_blog_and_slug(thread_id: str):
    session = await get_session()
    snap = await session.get_state(thread_id)
    blog = snap["values"].get("assembled_blog", "")
    topic = snap["values"].get("user_request", "blog")
    return blog, slugify(topic)


async def download_markdown_action(thread_id: str):
    blog, slug = await _get_blog_and_slug(thread_id)
    if not blog:
        return None
    path = BLOGS_DIR / f"{slug}.md"
    path.write_text(blog, encoding="utf-8")
    logger.info("Markdown exported: %s", path)
    return gr.File(value=str(path))


async def download_pdf_action(thread_id: str):
    blog, slug = await _get_blog_and_slug(thread_id)
    if not blog:
        return None
    path = BLOGS_DIR / f"{slug}.pdf"
    # Run CPU-bound PDF rendering off the event loop
    await asyncio.to_thread(blog_to_pdf, blog, slug, path)
    return gr.File(value=str(path))


async def assemble_blog_action(thread_id: str):
    """Phase 4: Assemble final blog."""
    logger.info(f"Assemble blog called with thread_id: '{thread_id}'")
    
    if not thread_id or thread_id.strip() == "":
        return (
            "*Please complete all sections first*",
            "*No statistics available*",
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
        )
    
    try:
        session = await get_session()
        result = await session.assemble_blog(thread_id)
        
        assembled_blog = result.get("assembled_blog", "")
        
        if not assembled_blog:
            return (
                "*Blog assembly failed or no sections generated*",
                "*No statistics available*",
                gr.update(interactive=False),
                gr.update(interactive=False),
                gr.update(interactive=False),
            )
        
        # Calculate statistics
        word_count = len(assembled_blog.split())
        reading_time = max(1, round(word_count / 250))
        char_count = len(assembled_blog)
        
        stats = f"""
**Blog Statistics:**
- 📝 Word Count: **{word_count:,}** words
- ⏱️ Reading Time: **~{reading_time} minutes**
- 📄 Character Count: **{char_count:,}** characters
- ✅ Status: **Assembly Complete**
"""
        
        logger.info(f"Blog assembled: {word_count} words, {char_count} characters")
        
        return (
            assembled_blog,
            stats,
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
        )
    except Exception as e:
        logger.error(f"Blog assembly failed: {e}", exc_info=True)
        return (
            f"❌ Assembly failed: {str(e)}",
            "*No statistics available*",
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
        )


async def publish_to_uniscolian_action(thread_id: str):
    """One-click publish: Image + Links + Sitemap + HTML Export."""
    if not thread_id:
        return "❌ No active session. Please generate a blog first."
        
    try:
        session = await get_session()
        snap = await session.get_state(thread_id)
        
        if not snap or not snap.get("values"):
            return "❌ Session state not found."
            
        blog_md = snap["values"].get("assembled_blog", "")
        topic = snap["values"].get("topic", "") or snap["values"].get("user_request", "")
        
        if not blog_md:
            return "❌ No assembled blog found in state. Please assemble the blog first."
            
        # Extract keywords for internal linking
        kw_data = snap["values"].get("keyword_research", {})
        keywords = []
        if isinstance(kw_data, dict):
            keywords = [k.get("keyword", "") for k in kw_data.get("keywords", []) if isinstance(k, dict)][:5]
        elif isinstance(kw_data, list):
            keywords = [k.get("keyword", "") for k in kw_data if isinstance(k, dict)][:5]

        # Run the heavy export process in a background thread to avoid blocking UI
        result = await asyncio.to_thread(
            export_post_to_uniscolian,
            markdown=blog_md,
            topic=topic,
            keywords=keywords,
            generate_image=True,
            add_related=True,
            update_sitemap=True,
            avoid_duplicates=True
        )
        
        # Build rich success message
        msg = ["## 🚀 Successfully Published to Uniscolian!"]
        msg.append(f"✅ **Post URL:** `/{result['slug']}/`")
        msg.append(f"📊 **Word Count:** {result['word_count']} words | ⏱️ **Read Time:** {result['read_time']} min")
        
        # Image status
        img_info = result.get("image", {})
        img_src = img_info.get("source", "none")
        msg.append(f"🖼️ **Featured Image:** Generated via `{img_src}`")
        
        # Related links
        related = result.get("related", [])
        if related:
            links_str = ", ".join([f"`{r['slug']}`" for r in related])
            msg.append(f"🔗 **Internal Links Injected:** {links_str}")
        else:
            msg.append("🔗 **Internal Links:** None found")
            
        # Sitemap
        msg.append(f"🗺️ **Sitemap Updated:** {'Yes' if result.get('sitemap_updated') else 'No (already exists)'}")
        
        msg.append("\n---\n")
        msg.append("**👉 Next Steps:**")
        msg.append(f"1. Preview locally: `http://localhost:8000/{result['slug']}/`")
        msg.append("2. (Optional) Drop a custom 900x752 image into the expected path if you want to replace the AI one.")
        msg.append("3. Push the `uniscolian-website` folder to GitHub/Netlify to go LIVE!")
        
        return "\n".join(msg)
        
    except Exception as e:
        import traceback
        logger.error(f"Publish to Uniscolian failed: {e}\n{traceback.format_exc()}")
        return f"❌ **Publish Failed:** {str(e)}"


def create_ui():
    """Build the 3-tab Gradio interface."""
    with gr.Blocks(title=APP_TITLE, theme=gr.themes.Soft()) as demo:
        gr.Markdown(f"# 🎯 {APP_TITLE}\n**Interactive Step-by-Step SEO Blog Generator**")
        
        # Hidden state for thread_id
        thread_id_state = gr.State(value="")
        
        with gr.Tabs():
            # === TAB 1: RESEARCH ===
            with gr.Tab("🔍 Research"):
                gr.Markdown("### Phase 1: Data Gathering")
                
                with gr.Row():
                    topic_input = gr.Textbox(
                        label="Topic/Keyword",
                        placeholder="e.g., best budget laptop 2026",
                        scale=4,
                    )
                    research_btn = gr.Button("🔍 Start Research", variant="primary", scale=1)
                
                research_status = gr.Markdown("*Research status will appear here*")
                
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("#### Keyword Research")
                        keyword_df = gr.DataFrame(
                            headers=["Keyword", "Intent", "Difficulty"],
                            datatype=["str", "str", "str"],
                            row_count=(0, "dynamic"),
                            col_count=(3, "fixed"),
                            label="Target Keywords",
                        )
                    
                    with gr.Column():
                        gr.Markdown("#### Competitor Metrics")
                        competitor_df = gr.DataFrame(
                            headers=["Metric", "Value"],
                            datatype=["str", "str"],
                            row_count=(0, "dynamic"),
                            col_count=(2, "fixed"),
                            label="Competitor Analysis",
                        )
                
                gr.Markdown("#### Gap Analysis")
                gap_analysis_md = gr.Markdown("*Gap analysis will appear here*")
                
                generate_prompts_btn = gr.Button(
                    "📋 Generate Outline Prompts",
                    variant="secondary",
                    interactive=False,
                )
            
            # === TAB 2: PROMPT DASHBOARD ===
            with gr.Tab("📋 Prompt Dashboard"):
                gr.Markdown("### Phase 2 & 3: Interactive Section Generation")
                
                prompt_df = gr.DataFrame(
                    headers=["Section", "Title", "Word Target", "Status"],
                    datatype=["str", "str", "str", "str"],
                    row_count=(0, "dynamic"),
                    col_count=(4, "fixed"),
                    label="Sub-Prompts Table",
                )
                
                prompt_summary = gr.Markdown("*Generate prompts first*")
                
                with gr.Row():
                    execute_btn = gr.Button(
                        "▶️ Execute Next Section",
                        variant="primary",
                        interactive=False,
                        scale=2,
                    )
                
                gr.Markdown("#### Blog Preview (Real-time)")
                blog_preview_md = gr.Markdown("*Blog will appear here as sections are generated*")
            
            # === TAB 3: FINAL BLOG ===
            with gr.Tab("📝 Final Blog"):
                gr.Markdown("### Phase 4: Blog Assembly")
                
                assemble_btn = gr.Button("📦 Assemble Final Blog", variant="primary")
                
                final_blog_md = gr.Markdown("*Final blog will appear here*")
                
                blog_stats = gr.Markdown("*Statistics will appear here*")
                
                with gr.Row():
                    download_md_btn = gr.Button("📥 Download Markdown", interactive=False)
                    download_pdf_btn = gr.Button("📄 Download PDF", interactive=False)
                download_file = gr.File(label="📁 Your downloaded file", interactive=False)

                with gr.Row():
                    publish_uniscolian_btn = gr.Button(
                        "🚀 Publish to Uniscolian Website", 
                        variant="primary", 
                        size="lg",
                        interactive=False  # Will be enabled when blog is assembled
                    )
                publish_status_md = gr.Markdown("*Generate and assemble a blog first, then click publish.*")
        
        # === EVENT HANDLERS WITH DOUBLE-CLICK PREVENTION ===
        
        def disable_research_btn():
            return gr.update(interactive=False, value="⏳ Researching...")

        def enable_research_btn():
            return gr.update(interactive=True, value="🔍 Start Research")

        research_btn.click(
            fn=disable_research_btn,
            inputs=None,
            outputs=[research_btn],
        ).then(
            fn=start_research_action,
            inputs=[topic_input],
            outputs=[
                research_status,
                keyword_df,
                competitor_df,
                gap_analysis_md,
                generate_prompts_btn,
                thread_id_state,
            ],
        ).then(
            fn=enable_research_btn,
            inputs=None,
            outputs=[research_btn],
        )
        
        def disable_prompts_btn():
            return gr.update(interactive=False, value="⏳ Generating Prompts...")

        def enable_prompts_btn():
            return gr.update(interactive=True, value="📋 Generate Outline Prompts")

        generate_prompts_btn.click(
            fn=disable_prompts_btn,
            inputs=None,
            outputs=[generate_prompts_btn],
        ).then(
            fn=generate_prompts_action,
            inputs=[thread_id_state],
            outputs=[prompt_df, prompt_summary, execute_btn],
        ).then(
            fn=enable_prompts_btn,
            inputs=None,
            outputs=[generate_prompts_btn],
        )
        
        def disable_execute_btn():
            return gr.update(interactive=False, value="⏳ Writing Section...")

        execute_btn.click(
            fn=disable_execute_btn,
            inputs=None,
            outputs=[execute_btn],
        ).then(
            fn=execute_next_section_action,
            inputs=[thread_id_state, execute_btn],
            outputs=[prompt_df, prompt_summary, execute_btn, blog_preview_md],
        )
        
        # Phase 4: Assemble Blog
        assemble_btn.click(
            fn=assemble_blog_action,
            inputs=[thread_id_state],
            outputs=[final_blog_md, blog_stats, download_md_btn, download_pdf_btn, publish_uniscolian_btn],
        )
        download_md_btn.click(fn=download_markdown_action, inputs=[thread_id_state], outputs=[download_file])
        download_pdf_btn.click(fn=download_pdf_action, inputs=[thread_id_state], outputs=[download_file])
        publish_uniscolian_btn.click(
            fn=publish_to_uniscolian_action,
            inputs=[thread_id_state],
            outputs=[publish_status_md]
        )
    
    return demo


def launch():
    """Launch the Gradio app."""
    demo = create_ui()
    demo.launch(
        server_name="127.0.0.1",  # Changed from 0.0.0.0 to fix localhost access
        server_port=GRADIO_SERVER_PORT,
        share=False,
    )


if __name__ == "__main__":
    launch()
