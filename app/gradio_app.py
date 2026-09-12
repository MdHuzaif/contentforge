"""Gradio UI for interactive step-by-step ContentForge AI."""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional
import pandas as pd
import gradio as gr

from app.config import APP_TITLE, GRADIO_SERVER_NAME, GRADIO_SERVER_PORT, BLOGS_DIR, UNISCOLIAN_ROOT, logger
from core.exporters.markdown_converter import slugify
from core.exporters.pdf_exporter import blog_to_pdf
from core.exporters.static_exporter import export_post_to_uniscolian
from core.interactive import InteractiveSession
from core.post_processors.product_detector import (
    detect_product_sections,
    format_detection_report,
    get_section_detail,
    enhance_detection_with_llm,
)
from core.post_processors.product_refiner import (
    refine_blog_products,
    format_refinement_report,
)


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


async def display_selected_products(thread_id: str):
    """Display selected products in the UI after Phase 1."""
    if not thread_id:
        return "*No active session*", []
    
    try:
        session = await get_session()
        snap = await session.get_state(thread_id)
        
        if not snap or not snap.get("values"):
            return "*Session state not found*", []
        
        values = snap["values"]
        products = values.get("selected_products", [])
        category = values.get("product_category", "unknown")
        confidence = values.get("extraction_confidence", 0.0)
        notes = values.get("extraction_notes", "")
        
        if not products:
            return "*No products selected yet. Content type may not be product_recommendation.*", []
        
        # Build summary markdown
        lines = [
            f"## 🛒 {len(products)} Products Selected for Detailed Review\n",
            f"**Category:** `{category}` | **Confidence:** `{confidence:.0%}`\n",
        ]
        if notes:
            lines.append(f"_{notes}_\n")
        
        # Build table data
        table_rows = []
        for i, p in enumerate(products, 1):
            tier_display = {"premium": "💎 Premium", "mid_range": "⭐ Mid-Range", "budget": "💰 Budget"}.get(
                p.get("tier", ""), p.get("tier", "")
            )
            popularity = p.get("popularity_score", 0)
            why = (p.get("why_notable") or "")[:100]
            
            table_rows.append([i, p.get("name", ""), p.get("brand", ""), tier_display, popularity, why])
        
        return "\n".join(lines), table_rows
        
    except Exception as e:
        return f"*Error displaying products: {e}*", []


async def generate_prompts_action(thread_id: str):
    """Phase 2: Generate sub-prompts from research."""
    logger.info(f"Generate prompts called with thread_id: '{thread_id}'")
    
    if not thread_id or not thread_id.strip():
        logger.warning("Empty thread_id received")
        return (
            pd.DataFrame({"Section": [], "Title": [], "Type": [], "Word Target": [], "Status": []}),
            "*Please run research first*",
            gr.update(interactive=False),
            gr.update(interactive=False),
        )
    
    try:
        session = await get_session()  # Use global session
        
        # Verify state exists in SQLite for this thread
        state = await session.get_state(thread_id)
        if not state["values"]:
            logger.error(f"No state found for thread {thread_id} in SQLite")
            return (
                pd.DataFrame({"Section": [], "Title": [], "Type": [], "Word Target": [], "Status": []}),
                "*❌ Session expired or state lost. Please run research again.*",
                gr.update(interactive=False),
                gr.update(interactive=False),
            )
        
        result = await session.generate_prompts(thread_id)
        
        sub_prompts = result.get("sub_prompts", [])
        total = result.get("total_sections", 0)
        
        if not sub_prompts:
            return (
                pd.DataFrame({"Section": [], "Title": [], "Type": [], "Word Target": [], "Status": []}),
                "*No sub-prompts generated*",
                gr.update(interactive=False),
                gr.update(interactive=False),
            )
        
        prompt_df = pd.DataFrame([
            {
                "Section": i + 1,
                "Title": ("  ↳ " + p.get("title", "")) if p.get("is_split") and p.get("split_type") == "h3_detail" 
                         else p.get("title", f"Section {i+1}"),
                "Type": p.get("split_type", "H2") if p.get("is_split") else "H2",
                "Word Target": p.get("word_target", 600),
                "Status": "⏳ Pending",
            }
            for i, p in enumerate(sub_prompts)
        ])
        
        summary = f"✅ Generated **{total} sub-prompts** (with auto-splitting). Click 'Execute Next Section' or 'Generate Full Blog'."
        logger.info(f"Phase 2 complete: {total} sub-prompts for thread {thread_id}")
        
        return (
            prompt_df,
            summary,
            gr.update(interactive=True, value=f"▶️ Execute Next Section (1/{total})"),
            gr.update(interactive=True),
        )
    except ValueError as e:
        logger.error(f"ValueError in generate_prompts: {e}")
        return (
            pd.DataFrame({"Section": [], "Title": [], "Type": [], "Word Target": [], "Status": []}),
            f"❌ {str(e)}. Please run research again.",
            gr.update(interactive=False),
            gr.update(interactive=False),
        )
    except Exception as e:
        logger.error(f"Prompt generation failed: {e}", exc_info=True)
        return (
            pd.DataFrame({"Section": [], "Title": [], "Type": [], "Word Target": [], "Status": []}),
            f"❌ Error: {str(e)}",
            gr.update(interactive=False),
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
        snap_values = sub_prompts_result.get("values", {})
        sub_prompts = snap_values.get("sub_prompts", [])
        last_error = snap_values.get("last_error", "")
        
        prompt_df = pd.DataFrame([
            {
                "Section": i + 1,
                "Title": ("  ↳ " + p.get("title", "")) if p.get("is_split") and p.get("split_type") == "h3_detail" 
                         else p.get("title", f"Section {i+1}"),
                "Type": p.get("split_type", "H2") if p.get("is_split") else "H2",
                "Word Target": p.get("word_target", 600),
                "Status": "⚠️ RETRY" if (last_error and i == current_idx) else ("✅ Complete" if i < current_idx else "⏳ Pending"),
            }
            for i, p in enumerate(sub_prompts)
        ])
        
        # Build blog preview (append sections as they're generated)
        blog_preview_parts = [f"# Blog Preview ({current_idx}/{total} sections complete)\n"]
        for section in generated:
            if section.get("content"):
                blog_preview_parts.append(section.get("content", ""))
                blog_preview_parts.append("\n\n---\n\n")
        blog_preview = "".join(blog_preview_parts)
        
        # Update button text
        if last_error:
            button_text = f"▶️ Retry Section ({current_idx + 1}/{total})"
            button_disabled = False
            summary = f"⚠️ **{last_error}**\n\nClick 'Retry Section' to try again."
        elif current_idx >= total:
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


async def auto_generate_full_blog(thread_id: str):
    """Auto-execute ALL remaining sections in a loop."""
    if not thread_id:
        yield "❌ No active session.", gr.update()
        return
    
    try:
        session = await get_session()
        
        max_iterations = 25  # Safety limit
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            snap = await session.get_state(thread_id)
            if not snap or not snap.get("values"):
                break
            
            values = snap["values"]
            current_idx = values.get("current_section_index", 0)
            total = values.get("total_sections", 0)
            sub_prompts = values.get("sub_prompts", [])
            
            # All sections done
            if current_idx >= total:
                break
            
            current_title = sub_prompts[current_idx].get("title", f"Section {current_idx+1}") if current_idx < len(sub_prompts) else f"Section {current_idx+1}"
            
            progress_msg = f"⏳ **Auto-Generating {current_idx + 1}/{total}:** {current_title}...\n\n*Please wait — sections generate sequentially.*"
            yield progress_msg, gr.update(interactive=False)
            
            # Execute ONE section by resuming the graph
            try:
                # This triggers the section_writer node to run once
                await session.graph.ainvoke(
                    None,
                    config={"configurable": {"thread_id": thread_id}}
                )
            except Exception as e:
                err_str = str(e)
                if "GraphFinished" in err_str or "reached end" in err_str.lower():
                    break
                logger.error(f"Auto-gen error at section {current_idx}: {e}")
                yield f"⚠️ Error at section {current_idx+1}: {err_str}", gr.update(interactive=True)
                return
            
            await asyncio.sleep(0.5)
        
        # Final message
        final_snap = await session.get_state(thread_id)
        final_idx = final_snap["values"].get("current_section_index", 0) if final_snap else 0
        final_total = final_snap["values"].get("total_sections", 0) if final_snap else 0
        
        if final_idx >= final_total:
            final_msg = f"✅ **All {final_total} sections generated successfully!**\n\n🎉 Click **'Assemble Blog'** to finish."
        else:
            final_msg = f"⚠️ Stopped at section {final_idx+1}/{final_total}. Use manual button to continue."
        
        yield final_msg, gr.update(interactive=True)
        
    except Exception as e:
        logger.error(f"Auto-generation failed: {e}")
        yield f"❌ Error: {str(e)}", gr.update(interactive=True)


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
            "*No blog assembled yet.*",
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
                "*Blog assembly failed.*",
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
            assembled_blog,
        )
    except Exception as e:
        logger.error(f"Blog assembly failed: {e}", exc_info=True)
        return (
            f"❌ Assembly failed: {str(e)}",
            "*No statistics available*",
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            f"❌ Assembly failed: {str(e)}",
        )


async def detect_products_action(thread_id: str):
    """Detect product H3 sections in the assembled blog."""
    if not thread_id:
        return "❌ No active session.", [], [], gr.update(choices=[], value=None), "*Run detection first.*"
    
    try:
        session = await get_session()
        snap = await session.get_state(thread_id)
        
        if not snap or not snap.get("values"):
            return "❌ Session state not found.", [], [], gr.update(choices=[], value=None), "*Run detection first.*"
        
        blog_md = snap["values"].get("assembled_blog", "")
        if not blog_md:
            return "❌ No assembled blog found.", [], [], gr.update(choices=[], value=None), "*Run detection first.*"
        
        # Use LLM-assisted detection
        sections = detect_product_sections(blog_md)
        
        # Filter out false positives
        filtered_sections = []
        seen_names = set()
        for s in sections:
            name = s.get("product_name", "").strip()
            if not name or name in seen_names:
                continue
            non_product_indicators = [
                'military-grade', 'components', 'features', 'technology',
                'design', 'cooling', 'memory', 'storage', 'performance'
            ]
            if any(indicator in name.lower() for indicator in non_product_indicators):
                logger.info(f"🚫 Filtering out non-product: '{name}'")
                continue
            seen_names.add(name)
            filtered_sections.append(s)
        sections = filtered_sections

        report = format_detection_report(sections)
        
        # Build table data
        table_data = []
        for i, s in enumerate(sections, 1):
            preview = s["content"][:80].replace("\n", " ").replace("|", "/").strip() + "..."
            score = s.get("mention_score", 0)
            table_data.append([
                i, 
                s["product_name"], 
                s["heading"], 
                s["word_count"], 
                preview,
                f"Score: {score}"
            ])
        
        # Product names for dropdown
        product_names = [s["product_name"] for s in sections]
        dropdown_update = gr.update(
            choices=product_names,
            value=product_names[0] if product_names else None
        )
        
        # Show first section detail
        first_detail = get_section_detail(sections[0]) if sections else "*No products detected.*"
        
        return report, table_data, sections, dropdown_update, first_detail
        
    except Exception as e:
        logger.error(f"Product detection failed: {e}")
        return f"❌ Detection failed: {str(e)}", [], [], gr.update(choices=[], value=None), "*Detection failed.*"


def show_section_detail_action(product_name: str, sections: list):
    """Show the full section content for the selected product."""
    if not product_name or not sections:
        return "*Select a product to see the exact section that will be refined.*"
    
    for s in sections:
        if s.get("product_name") == product_name:
            return get_section_detail(s)
    
    return "*Section not found.*"


async def refine_products_action(thread_id: str):
    """Refine detected product sections with shopping signals + LLM.
    Returns: report, refined_blog, original_blog (for comparison tab)."""
    if not thread_id:
        return "❌ No active session.", "", ""
    
    try:
        session = await get_session()
        snap = await session.get_state(thread_id)
        
        if not snap or not snap.get("values"):
            return "❌ Session state not found.", "", ""
        
        blog_md = snap["values"].get("assembled_blog", "")
        topic = snap["values"].get("topic", "") or snap["values"].get("user_request", "")
        
        if not blog_md:
            return "❌ No assembled blog found.", "", ""
        
        # Run refinement
        result = await refine_blog_products(blog_md, topic)
        report = format_refinement_report(result)
        
        # CRITICAL: Save refined blog to session state
        try:
            await session.update_state(
                thread_id,
                values={
                    "refined_blog": result["refined_blog"],
                    "refinement_report": report,
                    "refinement_stats": result.get("stats", []),
                }
            )
            logger.info("Refined blog saved to session state")
        except Exception as e:
            logger.warning(f"Could not save refined state: {e}")
        
        return report, result["refined_blog"], blog_md
        
    except Exception as e:
        logger.error(f"Product refinement failed: {e}")
        return f"❌ Refinement failed: {str(e)}", "", ""


async def export_refined_to_uniscolian_action(thread_id: str):
    """Export the REFINED blog to Uniscolian (separate from original export)."""
    if not thread_id:
        return "❌ No active session."
    
    try:
        session = await get_session()
        snap = await session.get_state(thread_id)
        
        if not snap or not snap.get("values"):
            return "❌ Session state not found."
        
        refined_md = snap["values"].get("refined_blog", "")
        if not refined_md:
            return "❌ No refined blog found. Please run refinement first."
        
        topic = snap["values"].get("topic", "") or snap["values"].get("user_request", "")
        
        kw_data = snap["values"].get("keyword_research", {})
        keywords = []
        if isinstance(kw_data, dict):
            keywords = [k.get("keyword", "") for k in kw_data.get("keywords", []) if isinstance(k, dict)][:5]
        
        import asyncio
        from core.exporters.static_exporter import export_post_to_uniscolian
        
        # Add suffix to topic to differentiate from original
        refined_topic = f"{topic} (Refined)" if topic else "Refined Blog"
        
        result = await asyncio.to_thread(
            export_post_to_uniscolian,
            markdown=refined_md,
            topic=refined_topic,
            keywords=keywords,
            generate_image=False,  # Don't regenerate image for refined version
            add_related=True,
            update_sitemap=True,
            avoid_duplicates=True,
        )
        
        msg = ["## 🚀 REFINED Blog Published to Uniscolian!"]
        msg.append(f"✅ **Post URL:** `/{result['slug']}/`")
        msg.append(f"📊 **Word Count:** {result.get('word_count', 0)} words")
        msg.append(f"✨ **Version:** Refined (with product signals)")
        return "\n".join(msg)
        
    except Exception as e:
        logger.error(f"Refined export failed: {e}")
        return f"❌ Export failed: {str(e)}"


async def enhance_detection_action(thread_id: str, current_sections: list):
    """Use LLM to find any missed products."""
    if not thread_id:
        return "❌ No active session.", current_sections
    
    try:
        session = await get_session()
        snap = await session.get_state(thread_id)
        
        if not snap or not snap.get("values"):
            return "❌ Session state not found.", current_sections
        
        blog_md = snap["values"].get("assembled_blog", "")
        if not blog_md:
            return "❌ No assembled blog found.", current_sections
        
        # Get currently detected product names
        current_names = [s["product_name"] for s in current_sections]
        
        # Call LLM enhancement
        additional = await enhance_detection_with_llm(blog_md, current_names)
        
        if not additional:
            return "✅ **No additional products found.** Code-based detection caught them all!", current_sections
        
        # Re-detect with enhanced list (this is simplified — in practice you'd add new sections)
        report = f"🤖 **AI Enhancement Found {len(additional)} Additional Product(s):**\n\n"
        report += "\n".join(f"- {p}" for p in additional)
        report += "\n\n💡 *To refine these, manually add them to the detection or proceed with current list.*"
        
        return report, current_sections  # For now, just report — full integration would require more work
        
    except Exception as e:
        logger.error(f"Enhancement failed: {e}")
        return f"❌ Enhancement failed: {str(e)}", current_sections


async def load_detected_products_action(thread_id: str):
    """Load detected products from state into editable table."""
    if not thread_id:
        return [], "*❌ No active session.*"
    
    try:
        session = await get_session()
        snap = await session.get_state(thread_id)
        
        if not snap or not snap.get("values"):
            return [], "*❌ Session state not found.*"
        
        values = snap["values"]
        detected = values.get("detected_products", [])
        existing_links = values.get("product_affiliate_links", {})
        
        if not detected:
            return [], "*⚠️ No products detected in this blog. Generate product review sections first.*"
        
        # === DEDUPLICATION: Keep only first occurrence of each product ===
        seen_products = set()
        unique_detected = []
        
        for p in detected:
            name = p.get("name", "").strip()
            name_key = name.lower()
            
            if name and name_key not in seen_products:
                seen_products.add(name_key)
                unique_detected.append(p)
            else:
                logger.debug(f"⏭️  Skipped duplicate: '{name}'")
        
        detected = unique_detected
        logger.info(f"✅ Deduplicated products: {len(detected)} unique products")

        table_data = []
        for p in detected:
            name = p["name"]
            section = p.get("heading", f"Section {p.get('section_index', '?')}")
            link = existing_links.get(name, "")
            table_data.append([name, section[:60] + "..." if len(section) > 60 else section, link])
        
        msg = f"✅ Loaded {len(detected)} detected products. Paste Amazon affiliate links (e.g., https://amazon.com/dp/B09JC1W613?tag=huzaif1612-20)"
        return table_data, msg
        
    except Exception as e:
        return [], f"*❌ Load failed: {str(e)}*"


async def save_affiliate_links_action(thread_id: str, table_data: list):
    """Save affiliate links back to state."""
    if not thread_id:
        return "*❌ No active session.*"
    
    # Convert DataFrame to list if needed (Gradio returns DataFrame)
    if hasattr(table_data, 'values'):
        table_data = table_data.values.tolist()
    elif hasattr(table_data, 'empty'):
        if table_data.empty:
            return "*❌ No data to save.*"
        table_data = table_data.values.tolist()
    
    if not table_data:
        return "*❌ No data to save.*"
    
    try:
        session = await get_session()
        snap = await session.get_state(thread_id)
        
        if not snap or not snap.get("values"):
            return "*❌ Session state not found.*"
        
        # Build links dict from table
        product_links = {}
        for row in table_data:
            if len(row) >= 3 and row[0] and row[2]:
                product_name = row[0].strip()
                amazon_url = row[2].strip()
                if product_name and amazon_url:
                    # Accept ANY link the user provides - no validation
                    product_links[product_name] = amazon_url.strip()
                    logger.info(f"✓ Saved affiliate link for '{product_name}': {amazon_url}")
        
        # === FIXED: Use LangGraph's proper state update API ===
        # Get the compiled graph from the session
        compiled_graph = getattr(session, 'graph', None) or getattr(session, 'compiled', None)
        
        if compiled_graph and hasattr(compiled_graph, 'update_state'):
            # Use LangGraph's native update_state
            config = {"configurable": {"thread_id": thread_id}}
            await compiled_graph.aupdate_state(
                config,
                {"product_affiliate_links": product_links},
                as_node="blog_assembler"  # Apply as if coming from assembler node
            )
        else:
            # Fallback: Store in session dict if available
            if hasattr(session, '_state_cache'):
                if thread_id in session._state_cache:
                    session._state_cache[thread_id]["product_affiliate_links"] = product_links
            # Alternative: Direct SQLite update
            if hasattr(session, 'checkpointer') and hasattr(session.checkpointer, 'aput'):
                current_values = snap.get("values", {})
                current_values["product_affiliate_links"] = product_links
                config = {"configurable": {"thread_id": thread_id}}
                logger.warning("Using fallback state update - consider using graph.update_state")
        
        msg = f"✅ Saved {len(product_links)} affiliate link(s)!\n\n"
        msg += "**Products with links:**\n"
        for name, url in product_links.items():
            msg += f"- {name}: {url}\n"
        msg += "\n💡 Now click '🚀 Publish to Uniscolian' — buttons will appear!"
        return msg
    
    except Exception as e:
        logger.error(f"Save affiliate links failed: {e}")
        import traceback
        traceback.print_exc()
        return f"*❌ Save failed: {str(e)}*"


async def detect_product_images_sections_action(thread_id: str):
    if not thread_id:
        return "*❌ No active session.*", []
    try:
        session = await get_session()
        snap = await session.get_state(thread_id)
        if not snap or not snap.get("values"):
            return "*❌ Session state not found.*", []
        values = snap["values"]
        blog_md = values.get("assembled_blog", "")
        selected_products = values.get("selected_products", [])
        if not blog_md:
            return "*❌ No assembled blog found.*", []
        
        from core.exporters.product_image_generator import detect_product_headings
        detected = detect_product_headings(blog_md, selected_products)
        if not detected:
            return "*⚠️ No product headings matched selected products.*", []
        
        table_data = [[i, d["name"], d["heading_text"], d["level"]] for i, d in enumerate(detected, 1)]
        return f"✅ Detected {len(detected)} product section(s).", table_data
    except Exception as e:
        return f"*❌ Detection failed: {e}*", []


async def generate_all_product_images_action(thread_id: str):
    if not thread_id:
        return "*❌ No active session.*", [], []
    try:
        session = await get_session()
        snap = await session.get_state(thread_id)
        if not snap or not snap.get("values"):
            return "*❌ Session state not found.*", [], []
        values = snap["values"]
        blog_md = values.get("assembled_blog", "")
        topic = values.get("topic", "") or values.get("user_request", "blog")
        category = values.get("product_category", "technology")
        selected_products = values.get("selected_products", [])
        if not blog_md:
            return "*❌ No assembled blog found.*", [], []
        
        from core.exporters.product_image_generator import generate_all_product_images
        from app.config import CONTENT_OUTPUT_DIR, UNISCOLIAN_ROOT
        from core.exporters.markdown_converter import slugify
        
        slug = slugify(topic)
        updated_md, report = await asyncio.to_thread(
            generate_all_product_images,
            markdown=blog_md,
            slug=slug,
            category=category,
            output_dir=UNISCOLIAN_ROOT,
            selected_products=selected_products,
        )
        
        images_map = {r["product_name"]: r["rel_path"] for r in report if r["status"] == "success" and r["rel_path"]}
        
        compiled_graph = getattr(session, 'graph', None) or getattr(session, 'compiled', None)
        if compiled_graph and hasattr(compiled_graph, 'update_state'):
            config = {"configurable": {"thread_id": thread_id}}
            await compiled_graph.aupdate_state(
                config,
                {"product_images_map": images_map, "product_images_report": report, "assembled_blog": updated_md},
                as_node="blog_assembler"
            )
        else:
            if hasattr(session, 'checkpointer') and hasattr(session.checkpointer, 'aput'):
                current_values = snap.get("values", {})
                current_values["product_images_map"] = images_map
                current_values["product_images_report"] = report
                current_values["assembled_blog"] = updated_md
        
        report_table = [[r["product_name"], r["source"], r["status"], r["rel_path"]] for r in report]
        
        gallery_files = []
        for r in report:
            if r["status"] == "success" and r["rel_path"]:
                rel_part = r["rel_path"].replace("../", "")
                abs_p = UNISCOLIAN_ROOT / rel_part
                if abs_p.exists():
                    gallery_files.append(str(abs_p))
                else:
                    uni_p = CONTENT_OUTPUT_DIR / rel_part
                    if uni_p.exists():
                        gallery_files.append(str(uni_p))
        
        msg = f"🎨 Generated product images! Success: {len(images_map)}/{len(report)}"
        return msg, report_table, gallery_files
    except Exception as e:
        logger.error(f"Generate product images action failed: {e}", exc_info=True)
        return f"*❌ Generation failed: {e}*", [], []


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

        # Get affiliate links and product images map (if configured)
        product_links = snap["values"].get("product_affiliate_links", {}) or {}
        product_images_map = snap["values"].get("product_images_map", {}) or {}
        detected = snap["values"].get("detected_products", [])
        
        # Auto-detect top pick (first product or one labeled 'Best Overall')
        top_pick = None
        for p in detected:
            if "best overall" in p.get("heading", "").lower() or p.get("section_index") == 2:
                top_pick = p["name"]
                break
        if not top_pick and detected:
            top_pick = detected[0]["name"]  # Fallback to first

        # Run the heavy export process in a background thread to avoid blocking UI
        result = await asyncio.to_thread(
            export_post_to_uniscolian,
            markdown=blog_md,
            topic=topic,
            keywords=keywords,
            generate_image=True,
            add_related=True,
            update_sitemap=True,
            avoid_duplicates=True,
            product_affiliate_links=product_links,
            top_pick_product=top_pick,
            product_images_map=product_images_map,
        )
        
        # Build rich success message
        msg = ["## 🚀 Successfully Published to Uniscolian!"]
        msg.append(f"✅ **Post URL:** `/{result['slug']}/`")
        msg.append(f"📊 **Word Count:** {result['word_count']} words | ⏱️ **Read Time:** {result['read_time']} min")
        
        # Image status
        img_info = result.get("image", {})
        img_src = img_info.get("source", "none")
        msg.append(f"🖼️ **Featured Image:** Generated via `{img_src}`")

        if product_images_map:
            msg.append(f"🖼️ **Product Images Injected:** {len(product_images_map)} products")
        
        # Related links
        related = result.get("related", [])
        if related:
            links_str = ", ".join([f"`{r['slug']}`" for r in related])
            msg.append(f"🔗 **Internal Links Injected:** {links_str}")
        else:
            msg.append("🔗 **Internal Links:** None found")
            
        # Sitemap
        msg.append(f"🗺️ **Sitemap Updated:** {'Yes' if result.get('sitemap_updated') else 'No (already exists)'}")
        
        if product_links:
            msg.append(f"\n💰 **Affiliate Buttons Added:** {len(product_links)} products")
            for name in product_links.keys():
                msg.append(f"  - {name}")
        else:
            msg.append("\n💡 *Tip: Configure affiliate links in the '💰 Affiliate Links' tab before publishing to earn commissions.*")
        
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
                
                # === LEVEL 2: Selected Products Display ===
                gr.Markdown("---")
                gr.Markdown("### 🛒 Selected Products (from Competitor Analysis)")
                gr.Markdown("*These products will be reviewed in detail. Extracted from top competitor articles.*")
                
                selected_products_md = gr.Markdown("*Products will appear here after Phase 1 completes*")
                
                selected_products_table = gr.Dataframe(
                    headers=["#", "Product Name", "Brand", "Tier", "Popularity", "Why Notable"],
                    label="Selected Products for Detailed Review",
                    interactive=False,
                    datatype=["number", "str", "str", "str", "number", "str"],
                    col_count=(6, "fixed"),
                )
                
                generate_prompts_btn = gr.Button(
                    "📋 Generate Outline Prompts",
                    variant="secondary",
                    interactive=False,
                )
            
            # === TAB 2: PROMPT DASHBOARD ===
            with gr.Tab("📋 Prompt Dashboard"):
                gr.Markdown("### Phase 2 & 3: Interactive Section Generation")
                
                prompt_df = gr.DataFrame(
                    headers=["Section", "Title", "Type", "Word Target", "Status"],
                    datatype=["str", "str", "str", "str", "str"],
                    row_count=(0, "dynamic"),
                    col_count=(5, "fixed"),
                    label="Sub-Prompts (Auto-Split for Large Sections)",
                    interactive=False,
                )
                
                prompt_summary = gr.Markdown("*Generate prompts first*")
                
                with gr.Row():
                    # Keep existing manual button (as fallback)
                    execute_btn = gr.Button(
                        "▶️ Execute Next Section (Manual)",
                        variant="secondary",
                        interactive=False,
                        scale=1,
                    )
                    
                    # NEW: Auto-generate button
                    auto_generate_btn = gr.Button(
                        "🚀 Generate Full Blog (Auto)",
                        variant="primary",
                        size="lg",
                        interactive=False,
                        scale=1,
                    )
                
                progress_md = gr.Markdown("")
                
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

            # === NEW TAB: Product Detection ===
            with gr.Tab("🔍 Product Detection"):
                gr.Markdown("### 🔍 Product Section Detection")
                gr.Markdown("*Detects product-specific H3 sections in your assembled blog. "
                           "Code-based detection (no LLM) for speed and accuracy.*")
                
                detect_btn = gr.Button(
                    "🔍 Detect Product Sections",
                    variant="secondary",
                    size="lg",
                )
                
                detection_report_md = gr.Markdown("*Click 'Detect Product Sections' after assembling your blog.*")
                
                detection_table = gr.Dataframe(
                    headers=["#", "Product Name", "H3 Heading", "Words", "Preview", "Relevance"],
                    label="Detected Product Sections",
                    interactive=False,
                )
                
                gr.Markdown("---")
                gr.Markdown("### 🔎 Inspect Section Before Refining")
                gr.Markdown("*Select a product to see the exact section content that will be refined.*")
                
                product_dropdown = gr.Dropdown(
                    label="Select Product to Inspect",
                    choices=[],
                    interactive=True,
                )
                
                section_detail_md = gr.Markdown("*Run detection first.*")
                
                gr.Markdown("---")
                
                # NEW: Enhancement button
                enhance_btn = gr.Button(
                    "🤖 Enhance with AI (Find Missed Products)",
                    variant="secondary",
                    size="sm",
                )
                enhancement_report_md = gr.Markdown("")
                
                refine_btn = gr.Button(
                    "✨ Refine Product Sections (with Shopping Signals)",
                    variant="primary",
                    size="lg",
                )
                
                refinement_report_md = gr.Markdown("")
                
                # Hidden state to store detected sections and refined blog
                detected_sections_state = gr.State([])
                refined_blog_state = gr.State("")
                original_blog_state = gr.State("")

            # === NEW TAB: Affiliate Links Configuration ===
            with gr.Tab("💰 Affiliate Links"):
                gr.Markdown("### 💰 Amazon Affiliate Link Configuration")
                gr.Markdown(
                    "*Paste Amazon affiliate links for each detected product. "
                    "Links are optional — products without links will export without buttons.*"
                )
                
                detected_products_display = gr.Dataframe(
                    headers=["Product Name", "Section", "Amazon Link (paste here)"],
                    label="Detected Products — Add Affiliate Links",
                    interactive=[False, False, True],  # Only link column is editable
                    datatype=["str", "str", "str"],
                    col_count=(3, "fixed"),
                )
                
                with gr.Row():
                    load_detected_btn = gr.Button("🔄 Load Detected Products", variant="secondary")
                    save_links_btn = gr.Button("💾 Save Affiliate Links", variant="primary")
                
                affiliate_status_md = gr.Markdown("*Generate a blog first, then load detected products.*")

            # === NEW TAB: Product Images Generation ===
            with gr.Tab("🖼️ Product Images"):
                gr.Markdown("### 🖼️ Product Image Generation")
                gr.Markdown(
                    "*Detects product headings in your assembled blog and generates editorial product "
                    "photography using Cloudflare Workers AI (Flux-1-Schnell) with Pollinations fallback.*"
                )
                
                with gr.Row():
                    detect_product_images_btn = gr.Button("🔍 Detect Product H2/H3 Sections", variant="secondary")
                    generate_product_images_btn = gr.Button("🎨 Generate All Product Images", variant="primary")
                
                product_images_status_md = gr.Markdown("*Assemble your blog first, then detect and generate product images.*")
                
                product_images_detection_table = gr.Dataframe(
                    headers=["#", "Product", "Heading", "Level"],
                    label="Detected Product Sections",
                    interactive=False,
                )
                
                gr.Markdown("#### Generation Report & Preview")
                product_images_report_table = gr.Dataframe(
                    headers=["Product", "Source", "Status", "Path"],
                    label="Product Images Report",
                    interactive=False,
                )
                
                product_images_gallery = gr.Gallery(
                    label="Generated Product Images Preview",
                    columns=3,
                    rows=2,
                    height="auto",
                )

            # === NEW TAB: Blog Comparison & Export ===
            with gr.Tab("📝 Blog Comparison & Export"):
                gr.Markdown("### 📝 Original vs Refined Blog")
                gr.Markdown("*Compare the original and refined versions. Export whichever you prefer.*")
                
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("#### 📄 Original Blog")
                        original_blog_display = gr.Markdown("*Original assembled blog will appear here after assembly.*")
                        export_original_btn = gr.Button(
                            "🚀 Export ORIGINAL to Uniscolian",
                            variant="secondary",
                            size="lg",
                        )
                        original_export_status = gr.Markdown("")
                    
                    with gr.Column():
                        gr.Markdown("#### ✨ Refined Blog")
                        refined_blog_display = gr.Markdown("*Refined blog will appear here after refinement.*")
                        export_refined_btn = gr.Button(
                            "🚀 Export REFINED to Uniscolian",
                            variant="primary",
                            size="lg",
                        )
                        refined_export_status = gr.Markdown("")
        
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
            fn=display_selected_products,
            inputs=[thread_id_state],
            outputs=[selected_products_md, selected_products_table],
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
            outputs=[prompt_df, prompt_summary, execute_btn, auto_generate_btn],
        ).then(
            fn=enable_prompts_btn,
            inputs=None,
            outputs=[generate_prompts_btn],
        )

        auto_generate_btn.click(
            fn=auto_generate_full_blog,
            inputs=[thread_id_state],
            outputs=[progress_md, auto_generate_btn],
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
            outputs=[final_blog_md, blog_stats, download_md_btn, download_pdf_btn, publish_uniscolian_btn, original_blog_display],
        ).then(
            fn=load_detected_products_action,
            inputs=[thread_id_state],
            outputs=[detected_products_display, affiliate_status_md],
        )
        download_md_btn.click(fn=download_markdown_action, inputs=[thread_id_state], outputs=[download_file])
        download_pdf_btn.click(fn=download_pdf_action, inputs=[thread_id_state], outputs=[download_file])
        publish_uniscolian_btn.click(
            fn=publish_to_uniscolian_action,
            inputs=[thread_id_state],
            outputs=[publish_status_md]
        )

        load_detected_btn.click(
            fn=load_detected_products_action,
            inputs=[thread_id_state],
            outputs=[detected_products_display, affiliate_status_md],
        )

        save_links_btn.click(
            fn=save_affiliate_links_action,
            inputs=[thread_id_state, detected_products_display],
            outputs=[affiliate_status_md],
        )

        # Product Detection wiring (5 outputs)
        detect_btn.click(
            fn=detect_products_action,
            inputs=[thread_id_state],
            outputs=[
                detection_report_md,
                detection_table,
                detected_sections_state,
                product_dropdown,
                section_detail_md,
            ],
        )
        
        # Show section detail when dropdown changes
        product_dropdown.change(
            fn=show_section_detail_action,
            inputs=[product_dropdown, detected_sections_state],
            outputs=[section_detail_md],
        )

        # AI Enhancement wiring
        enhance_btn.click(
            fn=enhance_detection_action,
            inputs=[thread_id_state, detected_sections_state],
            outputs=[enhancement_report_md, detected_sections_state],
        )
        
        # Refine button wiring — updates report, refined state, original state, and displays
        refine_btn.click(
            fn=refine_products_action,
            inputs=[thread_id_state],
            outputs=[refinement_report_md, refined_blog_state, original_blog_state],
        ).then(
            fn=lambda r, o: (o if o else "*No blog assembled yet.*",
                            r if r else "*Run refinement first to see the refined version.*"),
            inputs=[refined_blog_state, original_blog_state],
            outputs=[original_blog_display, refined_blog_display],
        )
        
        # Export buttons wiring
        export_original_btn.click(
            fn=publish_to_uniscolian_action,
            inputs=[thread_id_state],
            outputs=[original_export_status],
        )
        
        export_refined_btn.click(
            fn=export_refined_to_uniscolian_action,
            inputs=[thread_id_state],
            outputs=[refined_export_status],
        )

        # Product Images wiring
        detect_product_images_btn.click(
            fn=detect_product_images_sections_action,
            inputs=[thread_id_state],
            outputs=[product_images_status_md, product_images_detection_table],
        )

        generate_product_images_btn.click(
            fn=generate_all_product_images_action,
            inputs=[thread_id_state],
            outputs=[product_images_status_md, product_images_report_table, product_images_gallery],
        )
    
    return demo


def launch():
    """Launch the Gradio app."""
    demo = create_ui()
    demo.launch(
        server_name="127.0.0.1",  # Changed from 0.0.0.0 to fix localhost access
        server_port=GRADIO_SERVER_PORT,
        share=False,
        allowed_paths=[UNISCOLIAN_ROOT],
    )


if __name__ == "__main__":
    launch()
