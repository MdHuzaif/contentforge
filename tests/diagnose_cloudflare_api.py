"""Diagnose Cloudflare Workers AI API calls - FIXED VERSION."""
import os
import sys
import base64
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv
import httpx

# Load environment
load_dotenv()

account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()

print("=" * 80)
print("CLOUDFLARE WORKERS AI DIAGNOSTIC (FIXED - No width/height)")
print("=" * 80)

if not account_id or not api_token:
    print("❌ ERROR: CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN not found in .env")
    sys.exit(1)

print(f"✓ Account ID: {account_id[:8]}...{account_id[-4:]}")
print(f"✓ API Token: {api_token[:8]}...{api_token[-4:]}")

# Test 1: Simple text-to-image request (NO width/height!)
print("\n" + "=" * 80)
print("TEST 1: Simple Cloudflare API Call (payload without width/height)")
print("=" * 80)

url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-1-schnell"
print(f"URL: {url}")

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json",
}

# CRITICAL: No width/height in payload!
payload = {
    "prompt": "a red apple on a wooden table, studio lighting",
    "steps": 4,
}

print(f"\nPayload: {payload}")
print(f"Sending request...")

try:
    resp = httpx.post(url, headers=headers, json=payload, timeout=60)
    
    print(f"Status Code: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('content-type', 'N/A')}")
    print(f"Response Size: {len(resp.content)} bytes")
    
    if resp.status_code == 200:
        content_type = resp.headers.get("content-type", "")
        
        if content_type.startswith("image/"):
            print("✓ SUCCESS: Direct image response")
            print(f"  Image format: {content_type}")
            
            # Save test image
            test_path = root_dir / "content_output" / "cloudflare-test.jpg"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_bytes(resp.content)
            print(f"  Saved to: {test_path}")
            print(f"  ✅ CLOUDFLARE WORKS! Image generated successfully.")
            
        elif content_type.startswith("application/json"):
            print("✓ SUCCESS: JSON response")
            data = resp.json()
            print(f"  JSON keys: {list(data.keys())}")
            
            if "result" in data:
                result = data["result"]
                print(f"  Result keys: {list(result.keys())}")
                
                if "image" in result:
                    b64_str = result["image"]
                    print(f"  Base64 image length: {len(b64_str)} chars")
                    
                    # Decode and save
                    image_bytes = base64.b64decode(b64_str)
                    test_path = root_dir / "content_output" / "cloudflare-test.jpg"
                    test_path.parent.mkdir(parents=True, exist_ok=True)
                    test_path.write_bytes(image_bytes)
                    print(f"  Decoded image size: {len(image_bytes)} bytes")
                    print(f"  Saved to: {test_path}")
                    print(f"  ✅ CLOUDFLARE WORKS! Image generated successfully.")
                else:
                    print("  ❌ No 'image' key in result")
                    print(f"  Result: {result}")
            else:
                print("  ❌ No 'result' key in response")
                print(f"  Response: {data}")
        else:
            print(f"❌ Unexpected content type: {content_type}")
            print(f"Response preview: {resp.text[:500]}")
    else:
        print(f"❌ FAILED: HTTP {resp.status_code}")
        print(f"Error response: {resp.text[:500]}")
        
except Exception as e:
    print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)