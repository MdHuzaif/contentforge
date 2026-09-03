"""Post-processing modules for blog refinement."""
from core.post_processors.product_detector import (
    detect_product_sections,
    format_detection_report,
    get_section_detail,
)
from core.post_processors.product_refiner import (
    refine_blog_products,
    format_refinement_report,
)

__all__ = [
    "detect_product_sections",
    "format_detection_report",
    "get_section_detail",
    "refine_blog_products",
    "format_refinement_report",
]
