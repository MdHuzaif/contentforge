import asyncio, json
from core.post_processors.product_deep_dive import deep_dive_product

out = asyncio.run(deep_dive_product("MacBook Air M4", "laptop"))
print(json.dumps(out, indent=2, ensure_ascii=False))
print(f"\nUser quotes count: {len(out.get('user_quotes', []))}")
