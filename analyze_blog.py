"""
Blog Quality Diagnostic Analyzer
=================================
Analyzes generated blog files for SEO readiness, engagement quality, 
and E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) signals.

Usage:
    python analyze_blog.py                           # Uses default latest blog
    python analyze_blog.py path/to/blog.md           # Analyzes specific file
    python analyze_blog.py --latest                  # Auto-finds latest blog
"""
import re
import sys
import json
from pathlib import Path
from datetime import datetime


# Default blog path (can be overridden via command line)
DEFAULT_BLOG_DIR = Path(__file__).parent / "content_output" / "blogs"
DEFAULT_BLOG = DEFAULT_BLOG_DIR / "best-motherboard-for-ryzen-9-9800x3d.md"


def find_latest_blog() -> Path:
    """Find the most recently modified blog file."""
    if not DEFAULT_BLOG_DIR.exists():
        return DEFAULT_BLOG
    
    blogs = list(DEFAULT_BLOG_DIR.glob("*.md"))
    if not blogs:
        return DEFAULT_BLOG
    
    # Sort by modification time, return newest
    return max(blogs, key=lambda p: p.stat().st_mtime)


def analyze_blog(blog_path: Path) -> dict:
    """Analyze blog quality across multiple dimensions."""
    
    if not blog_path.exists():
        print(f"❌ Blog file not found: {blog_path}")
        sys.exit(1)
    
    with open(blog_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    results = {
        "file": str(blog_path),
        "analyzed_at": datetime.now().isoformat(),
        "basic_stats": {},
        "quality_checks": {},
        "structure": [],
        "score": 0,
        "max_score": 10,
        "verdict": "",
    }
    
    # === BASIC STATS ===
    words = len(content.split())
    sections_h1 = re.findall(r'^# .+', content, re.MULTILINE)
    sections_h2 = re.findall(r'^## .+', content, re.MULTILINE)
    sections_h3 = re.findall(r'^### .+', content, re.MULTILINE)
    sections_h4 = re.findall(r'^#### .+', content, re.MULTILINE)
    
    results["basic_stats"] = {
        "words": words,
        "h1_count": len(sections_h1),
        "h2_count": len(sections_h2),
        "h3_count": len(sections_h3),
        "h4_count": len(sections_h4),
        "total_sections": len(sections_h2) + len(sections_h3),
        "reading_time_minutes": round(words / 250, 1),  # 250 wpm
    }
    
    print("=" * 70)
    print(f"📊 BLOG QUALITY ANALYSIS")
    print(f"📁 File: {blog_path.name}")
    print(f"⏰ Analyzed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print(f"📏 Total words: {words:,} (~{results['basic_stats']['reading_time_minutes']} min read)")
    print(f"📋 Structure: {len(sections_h1)} H1 | {len(sections_h2)} H2 | {len(sections_h3)} H3 | {len(sections_h4)} H4")
    print()
    
    score = 0
    max_score = 10
    
    # === CHECK 1: OPENING HOOK (first 500 chars) ===
    print("1. OPENING HOOK ANALYSIS")
    print("-" * 70)
    first_500 = content[:500]
    has_question = "?" in first_500
    has_stat = bool(re.search(r'\d+%', first_500))
    has_bold = "**" in first_500
    has_hook_phrase = any(p in first_500.lower() for p in [
        "struggling", "wondering", "tired of", "looking for", 
        "need to know", "here's why", "you need"
    ])
    
    hook_score = sum([has_question, has_stat, has_bold, has_hook_phrase])
    hook_score = min(hook_score, 2)  # Max 2 points
    score += hook_score
    
    print(f"   {'✅' if has_question else '❌'} Question mark (curiosity gap)")
    print(f"   {'✅' if has_stat else '❌'} Statistic (authority signal)")
    print(f"   {'✅' if has_bold else '❌'} Bold text (emphasis)")
    print(f"   {'✅' if has_hook_phrase else '❌'} Hook phrase (pain point)")
    print(f"   Score: {hook_score}/2")
    print()
    results["quality_checks"]["opening_hook"] = {
        "score": hook_score,
        "has_question": has_question,
        "has_stat": has_stat,
        "has_bold": has_bold,
        "has_hook_phrase": has_hook_phrase,
    }
    
    # === CHECK 2: E-E-A-T SIGNALS ===
    print("2. E-E-A-T SIGNALS (Experience, Expertise, Authority, Trust)")
    print("-" * 70)
    eeat_phrases = {
        "first_person_testing": ["In our testing", "We benchmarked", "We tested", "we measured", "we found"],
        "experience_markers": ["In our experience", "hands-on", "first-hand", "personally", "we used"],
        "expertise_signals": ["Our tests show", "Our analysis", "Based on testing", "Our recommendation"],
        "authority_markers": ["expert", "specialist", "industry", "professional", "certified"],
    }
    
    eeat_total = 0
    eeat_breakdown = {}
    for category, phrases in eeat_phrases.items():
        count = sum(content.lower().count(p.lower()) for p in phrases)
        eeat_breakdown[category] = count
        eeat_total += count
        icon = "✅" if count >= 2 else ("⚠️" if count >= 1 else "❌")
        print(f"   {icon} {category.replace('_', ' ').title()}: {count} mentions")
    
    eeat_score = min(eeat_total // 3, 2)  # Max 2 points (need 6+ total)
    score += eeat_score
    print(f"   Total E-E-A-T phrases: {eeat_total}")
    print(f"   Score: {eeat_score}/2")
    print()
    results["quality_checks"]["eeat"] = {
        "score": eeat_score,
        "total_phrases": eeat_total,
        "breakdown": eeat_breakdown,
    }
    
    # === CHECK 3: COMPARISON TABLES ===
    print("3. COMPARISON TABLES (Featured Snippet Gold)")
    print("-" * 70)
    # Match markdown tables (3+ columns)
    tables = re.findall(r'\|[^\n]+\|[^\n]+\|[^\n]+\|', content)
    unique_tables = len(set(tables))
    table_score = min(unique_tables, 1)  # Max 1 point
    score += table_score
    print(f"   {'✅' if unique_tables >= 2 else '⚠️' if unique_tables >= 1 else '❌'} Tables found: {unique_tables}")
    print(f"   Score: {table_score}/1")
    print()
    results["quality_checks"]["tables"] = {
        "score": table_score,
        "count": unique_tables,
    }
    
    # === CHECK 4: PROS/CONS STRUCTURE ===
    print("4. PROS/CONS BREAKDOWNS (Decision-Making Aid)")
    print("-" * 70)
    pros_patterns = [r'\*\*Pros\*\*:', r'### Pros', r'#### Pros', r'Pros:', r'✅\s*\*\*Pros\*\*']
    cons_patterns = [r'\*\*Cons\*\*:', r'### Cons', r'#### Cons', r'Cons:', r'❌\s*\*\*Cons\*\*']
    
    pros_count = sum(len(re.findall(p, content, re.IGNORECASE)) for p in pros_patterns)
    cons_count = sum(len(re.findall(p, content, re.IGNORECASE)) for p in cons_patterns)
    
    pros_cons_score = 0
    if pros_count >= 3 and cons_count >= 3:
        pros_cons_score = 1
    elif pros_count >= 1 and cons_count >= 1:
        pros_cons_score = 0.5
    
    score += pros_cons_score
    print(f"   {'✅' if pros_count >= 3 else '⚠️' if pros_count >= 1 else '❌'} Pros sections: {pros_count}")
    print(f"   {'✅' if cons_count >= 3 else '⚠️' if cons_count >= 1 else '❌'} Cons sections: {cons_count}")
    print(f"   Score: {pros_cons_score}/1")
    print()
    results["quality_checks"]["pros_cons"] = {
        "score": pros_cons_score,
        "pros_count": pros_count,
        "cons_count": cons_count,
    }
    
    # === CHECK 5: SPECIFIC METRICS (Numbers build trust) ===
    print("5. SPECIFIC METRICS (Trust Signals)")
    print("-" * 70)
    metric_patterns = [
        (r'\b\d+(?:\.\d+)?°C\b', "Temperatures (°C)"),
        (r'\b\d+(?:\.\d+)?GHz\b', "Clock speeds (GHz)"),
        (r'\b\d+(?:\.\d+)?GB\b', "Memory (GB)"),
        (r'\b\d+(?:\.\d+)?TB\b', "Storage (TB)"),
        (r'\b\d+(?:\.\d+)?MB\b', "Cache/size (MB)"),
        (r'\b\d+W\b', "Power (W)"),
        (r'\b\d+MHz\b', "Frequency (MHz)"),
        (r'\b\d+\s*(?:hours?|hrs?)\b', "Duration (hours)"),
        (r'\b\d+\s*phases?\b', "VRM phases"),
    ]
    
    metric_counts = {}
    total_metrics = 0
    for pattern, label in metric_patterns:
        count = len(re.findall(pattern, content))
        if count > 0:
            metric_counts[label] = count
            total_metrics += count
    
    for label, count in sorted(metric_counts.items(), key=lambda x: -x[1]):
        print(f"   ✓ {label}: {count}")
    
    metrics_score = min(total_metrics // 5, 1)  # Max 1 point (need 5+ metrics)
    score += metrics_score
    print(f"   Total metrics: {total_metrics}")
    print(f"   Score: {metrics_score}/1")
    print()
    results["quality_checks"]["metrics"] = {
        "score": metrics_score,
        "total": total_metrics,
        "breakdown": metric_counts,
    }
    
    # === CHECK 6: USER SIGNALS (Shopping intelligence) ===
    print("6. USER SIGNALS (Real Feedback Integration)")
    print("-" * 70)
    signal_phrases = {
        "user_feedback": ["users praise", "users report", "user feedback", "users mention"],
        "owner_experience": ["owners mention", "owners report", "real-world users"],
        "community_signals": ["reddit", "forums", "community", "users online"],
        "sentiment_words": ["reliable", "solid", "durable", "flawless", "disappointing", "frustrating"],
    }
    
    signal_total = 0
    signal_breakdown = {}
    for category, phrases in signal_phrases.items():
        count = sum(content.lower().count(p.lower()) for p in phrases)
        signal_breakdown[category] = count
        signal_total += count
        icon = "✅" if count >= 2 else ("⚠️" if count >= 1 else "❌")
        print(f"   {icon} {category.replace('_', ' ').title()}: {count}")
    
    signal_score = min(signal_total // 3, 1)  # Max 1 point
    score += signal_score
    print(f"   Total signal phrases: {signal_total}")
    print(f"   Score: {signal_score}/1")
    print()
    results["quality_checks"]["user_signals"] = {
        "score": signal_score,
        "total": signal_total,
        "breakdown": signal_breakdown,
    }
    
    # === CHECK 7: FEATURED SNIPPET STRUCTURES ===
    print("7. FEATURED SNIPPET STRUCTURES (Position 0 Targets)")
    print("-" * 70)
    
    # Definition paragraphs (40-80 words starting with "is/are")
    definition_paras = re.findall(r'\b(?:is|are|refers to)\b[^.]{40,120}\.', content)
    
    # Numbered lists
    numbered_lists = re.findall(r'^\s*\d+\.\s+[A-Z].+', content, re.MULTILINE)
    
    # Bullet lists (3+ consecutive bullets)
    bullet_sequences = re.findall(r'(?:^|\n)\s*[-*]\s+.+(?:\n\s*[-*]\s+.+){2,}', content, re.MULTILINE)
    
    # Q&A style (### Question?)
    qa_headings = re.findall(r'^###\s+[A-Z][^#\n]*\?', content, re.MULTILINE)
    
    snippet_count = {
        "definition_paragraphs": len(definition_paras),
        "numbered_lists": len(numbered_lists),
        "bullet_sequences": len(bullet_sequences),
        "qa_headings": len(qa_headings),
    }
    
    for structure, count in snippet_count.items():
        icon = "✅" if count >= 2 else ("⚠️" if count >= 1 else "❌")
        print(f"   {icon} {structure.replace('_', ' ').title()}: {count}")
    
    snippet_score = min(sum(1 for c in snippet_count.values() if c >= 1), 1)
    score += snippet_score
    print(f"   Score: {snippet_score}/1")
    print()
    results["quality_checks"]["featured_snippets"] = {
        "score": snippet_score,
        "structures": snippet_count,
    }
    
    # === CHECK 8: TRANSITION HOOKS (Reader flow) ===
    print("8. TRANSITION HOOKS (Reader Engagement)")
    print("-" * 70)
    transition_phrases = [
        "Now that", "With that", "Let's dive", "Moving on",
        "Next, let's", "Here's what", "Now let's", "But what about",
        "You might wonder", "Here's the catch", "The good news",
    ]
    
    transition_count = sum(content.count(p) for p in transition_phrases)
    transition_score = min(transition_count // 3, 1)  # Max 1 point
    score += transition_score
    print(f"   {'✅' if transition_count >= 3 else '⚠️' if transition_count >= 1 else '❌'} Transition phrases: {transition_count}")
    print(f"   Score: {transition_score}/1")
    print()
    results["quality_checks"]["transitions"] = {
        "score": transition_score,
        "count": transition_count,
    }
    
    # === CONTENT STRUCTURE PREVIEW ===
    print("=" * 70)
    print("📋 CONTENT STRUCTURE (H2 Sections)")
    print("=" * 70)
    for h2 in sections_h2:
        print(f"   {h2}")
    print()
    
    # === FINAL VERDICT ===
    results["score"] = score
    results["max_score"] = max_score
    
    print("=" * 70)
    print(f"🎯 OVERALL SCORE: {score}/{max_score}")
    print("=" * 70)
    
    # Visual score bar
    filled = "█" * score
    empty = "░" * (max_score - score)
    print(f"[{filled}{empty}] {score * 10}%")
    print()
    
    if score >= 9:
        verdict = "🏆 EXCELLENT: Blog ready to rank #1 and outperform competitors"
        results["verdict"] = "excellent"
    elif score >= 7:
        verdict = "✅ GREAT: Strong content with minor optimization opportunities"
        results["verdict"] = "great"
    elif score >= 5:
        verdict = "⚠️ GOOD: Decent content but needs strategic improvements to compete"
        results["verdict"] = "good"
    elif score >= 3:
        verdict = "⚠️ NEEDS WORK: Significant gaps that will hurt ranking potential"
        results["verdict"] = "needs_work"
    else:
        verdict = "❌ POOR: Major content quality issues, substantial rewrite needed"
        results["verdict"] = "poor"
    
    print(verdict)
    print()
    
    # === RECOMMENDATIONS ===
    print("=" * 70)
    print("💡 RECOMMENDATIONS (Priority Order)")
    print("=" * 70)
    
    recommendations = []
    if hook_score < 2:
        recommendations.append("🔥 Add a pain-point question or surprising statistic in first 100 words")
    if eeat_score < 2:
        recommendations.append("💼 Add 'In our testing...' or 'We benchmarked...' phrases (aim for 6+ E-E-A-T phrases)")
    if unique_tables < 2:
        recommendations.append("📊 Add 2+ comparison tables with 5+ columns each (featured snippet gold)")
    if pros_count < 3 or cons_count < 3:
        recommendations.append("⚖️ Add explicit **Pros:** and **Cons:** for every product review")
    if total_metrics < 5:
        recommendations.append("🔢 Add specific numbers: temperatures, clock speeds, VRM phases, hours tested")
    if signal_total < 3:
        recommendations.append("💬 Weave in user feedback: 'users praise', 'owners mention', 'common complaints'")
    if sum(snippet_count.values()) < 3:
        recommendations.append("⭐ Add featured snippet structures: definition paragraphs, numbered lists, Q&A headings")
    if transition_count < 3:
        recommendations.append("🔗 Add transition hooks: 'Now that...', 'Let's dive into...', 'Here's what...'")
    
    if not recommendations:
        print("   🎉 No critical improvements needed! Content is ready to publish.")
    else:
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
    
    print()
    
    # Save detailed results to JSON
    json_output = blog_path.with_suffix('.analysis.json')
    try:
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"💾 Detailed analysis saved to: {json_output.name}")
    except Exception as e:
        print(f"⚠️ Could not save JSON: {e}")
    
    return results


def main():
    """Main entry point with CLI argument parsing."""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + "🔬 CONTENTFORGE BLOG QUALITY ANALYZER".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--latest":
            blog_path = find_latest_blog()
            print(f"🔍 Auto-detected latest blog: {blog_path.name}")
            print()
        else:
            blog_path = Path(sys.argv[1])
    else:
        blog_path = DEFAULT_BLOG
    
    analyze_blog(blog_path)


if __name__ == "__main__":
    main()
