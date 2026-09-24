import asyncio, os
os.environ['DEEP_DIVE_MODE'] = 'snippet-only'
os.environ['DEEP_DIVE_SEARCHES_PER_PRODUCT'] = '6'

from core.post_processors.product_refiner import (
    get_signals_for_product, 
    convert_deep_to_signals
)

deep_data = {
    'Test Product': {
        'found': True,
        'key_specs': ['Spec 1'],
        'real_pros': ['Pro 1'],
        'real_cons': ['Con 1'],
        'user_quotes': [{'quote': 'Great!', 'source': 'reddit.com'}],
        'price_range': '$999',
        'target_audience': 'testers',
    }
}

async def test():
    signals = await get_signals_for_product('Test Product', 'topic', deep_data)
    print(f"Signals found: {signals['found']}")
    print(f"Snippets count: {len(signals.get('snippets', []))}")
    print(f"Praise: {signals.get('praise', [])}")
    return signals

signals = asyncio.run(test())
assert signals['found'] is True
print("✅ Level 3 cleanup verified - Deep Dive data reuse working")
