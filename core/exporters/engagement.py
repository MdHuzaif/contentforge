"""Reader-retention widgets + typography enforcement injected into exported posts."""
from __future__ import annotations

ENGAGEMENT_BLOCK = """
<style id="cf-post-engagement">
/* IMPORTANT: never use the shorthand margin property here — it would zero out
   margin-left/right and break WordPress auto-centering. Only vertical margins. */
.entry-content h1{font-size:clamp(30px,5vw,40px)!important;line-height:1.25!important;margin-top:1.1em!important;margin-bottom:.5em!important;font-weight:700!important;color:#192a3d}
.entry-content h2{font-size:clamp(24px,4.2vw,32px)!important;line-height:1.3!important;margin-top:1.4em!important;margin-bottom:.6em!important;font-weight:700!important;color:#192a3d}
.entry-content h3{font-size:clamp(20px,3.5vw,25px)!important;line-height:1.35!important;margin-top:1.2em!important;margin-bottom:.5em!important;font-weight:600!important;color:#23364a}
.entry-content h4{font-size:clamp(18px,3vw,21px)!important;margin-top:1em!important;margin-bottom:.4em!important;font-weight:600!important;color:#2c405a}
.entry-content p{font-size:17px!important;line-height:1.8!important;margin-top:0!important;margin-bottom:1.2em!important;color:#3a4f66}
.entry-content ul.wp-block-list,.entry-content ol.wp-block-list{margin-top:0!important;margin-bottom:1.3em!important;padding-left:1.6em!important}
.entry-content .wp-block-list li{margin-bottom:.55em!important;line-height:1.7!important;font-size:16.5px}
.entry-content figure.wp-block-table{margin-top:1.4em!important;margin-bottom:1.4em!important;overflow-x:auto}
.entry-content .wp-block-table table{width:100%!important;border-collapse:collapse!important;font-size:15.5px}
.entry-content .wp-block-table th{background:#2872fa!important;color:#fff!important;padding:10px 12px!important;text-align:left!important}
.entry-content .wp-block-table td{padding:10px 12px!important;border-bottom:1px solid #e1e8ed!important}
.entry-content .wp-block-table tr:nth-child(even) td{background:#f2f5f7}
.entry-content blockquote.wp-block-quote{border-left:4px solid #2872fa!important;background:#f2f7ff!important;padding:14px 20px!important;border-radius:0 8px 8px 0!important;margin-top:1.5em!important;margin-bottom:1.5em!important;font-style:normal!important}
#cf-progress{position:fixed;top:0;left:0;height:4px;width:0;background:linear-gradient(90deg,#2872fa,#1559ed);z-index:999999}
#cf-top{position:fixed;right:20px;bottom:20px;width:46px;height:46px;border-radius:50%;border:none;background:#2872fa;color:#fff;font-size:20px;cursor:pointer;display:none;align-items:center;justify-content:center;box-shadow:0 8px 20px rgba(21,89,237,.35);z-index:999999}
#cf-top:hover{background:#1559ed}
@media (max-width:690px){
.entry-content p{font-size:16px!important}
.entry-content .wp-block-table th,.entry-content .wp-block-table td{padding:8px 10px!important;font-size:14px}
#cf-top{right:14px;bottom:14px;width:42px;height:42px}
}

/* Amazon Affiliate Button Styles */
.affiliate-button-wrapper {
    text-align: center;
    margin: 2rem auto;
    padding: 1.5rem;
    background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
    border: 2px solid #FF9900;
    border-radius: 12px;
    max-width: 500px;
    box-shadow: 0 4px 12px rgba(255, 153, 0, 0.15);
    transition: all 0.3s ease;
}

.affiliate-button-wrapper:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(255, 153, 0, 0.25);
}

.affiliate-button-wrapper.best-deal {
    background: linear-gradient(135deg, #fff8e1 0%, #ffffff 100%);
    border-color: #FFD700;
    position: relative;
}

.best-deal-badge {
    position: absolute;
    top: -12px;
    left: 50%;
    transform: translateX(-50%);
    background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
    color: #1a1a1a;
    padding: 4px 16px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.85rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.amazon-affiliate-btn {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    background: linear-gradient(135deg, #FF9900 0%, #FFB347 100%);
    color: #1a1a1a !important;
    text-decoration: none !important;
    padding: 14px 28px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 1.05rem;
    transition: all 0.2s ease;
    box-shadow: 0 2px 6px rgba(255, 153, 0, 0.3);
}

.amazon-affiliate-btn:hover {
    background: linear-gradient(135deg, #FFB347 0%, #FF9900 100%);
    transform: scale(1.03);
    box-shadow: 0 4px 12px rgba(255, 153, 0, 0.4);
}

.amazon-affiliate-btn.best-deal-btn {
    background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
}

.btn-icon { font-size: 1.3rem; }
.btn-text { flex: 1; }
.btn-arrow { font-size: 1.4rem; font-weight: 900; }

.affiliate-disclosure-small {
    font-size: 0.75rem;
    color: #666;
    margin-top: 10px;
    font-style: italic;
}

/* Table button (compact) */
.amazon-btn-table {
    display: inline-block;
    background: #FF9900;
    color: #1a1a1a !important;
    text-decoration: none !important;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 0.85rem;
    font-weight: 600;
    white-space: nowrap;
    transition: background 0.2s;
}

.amazon-btn-table:hover {
    background: #FFB347;
}

/* Footer disclosure */
.affiliate-disclosure-footer {
    background: #f8f9fa;
    border-left: 4px solid #FF9900;
    padding: 1rem 1.25rem;
    margin: 2rem 0;
    font-size: 0.9rem;
    color: #555;
    border-radius: 4px;
}

.affiliate-disclosure-footer strong {
    color: #333;
}

/* Mobile responsive */
@media (max-width: 600px) {
    .affiliate-button-wrapper {
        padding: 1rem;
        margin: 1rem 0.5rem;
    }
    .amazon-affiliate-btn {
        padding: 12px 20px;
        font-size: 0.95rem;
    }
    .btn-text { font-size: 0.9rem; }
}
</style>
<div id="cf-progress"></div>
<button id="cf-top" aria-label="Back to top">&#8593;</button>
<script>
(function(){var p=document.getElementById('cf-progress'),t=document.getElementById('cf-top');if(!p||!t)return;
function u(){var d=document.documentElement,m=d.scrollHeight-d.clientHeight,s=m>0?(d.scrollTop/m)*100:0;p.style.width=s+'%';t.style.display=d.scrollTop>600?'flex':'none';}
document.addEventListener('scroll',u,{passive:true});u();
t.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});})();
</script>
"""
