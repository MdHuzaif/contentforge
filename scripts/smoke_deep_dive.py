import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv; load_dotenv()
from core.post_processors.product_deep_dive import deep_dive_product
out = asyncio.run(deep_dive_product("ASUS ROG Crosshair X870E Hero", "motherboard"))
print(json.dumps(out, indent=2, ensure_ascii=False))
