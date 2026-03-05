#!/usr/bin/env python3
"""Quick test to verify language endpoint integration"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path("/home/hongda/eb/elastic-bilara/backend")
sys.path.insert(0, str(backend_path))

print("=" * 60)
print("Language Integration Test")
print("=" * 60)

# Test 1: Check if languages.py can be imported
print("\n1. Testing language endpoint module import...")
try:
    from app.api.api_v1.endpoints import languages
    print("   ✓ Language module imported successfully")
except ImportError as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Check if _language.json exists
print("\n2. Checking _language.json file...")
language_file = backend_path / "checkouts" / "published" / "_language.json"
if language_file.exists():
    print(f"   ✓ File found at {language_file}")
else:
    print(f"   ✗ File not found at {language_file}")
    sys.exit(1)

# Test 3: Check if languages can be loaded
print("\n3. Testing language data loading...")
try:
    langs = languages._load_languages()
    print(f"   ✓ Successfully loaded {len(langs)} languages")
    if langs:
        # Show first 3 languages
        for i, (code, data) in enumerate(list(langs.items())[:3]):
            print(f"      - {code}: {data.get('name', 'N/A')}")
        if len(langs) > 3:
            print(f"      ... and {len(langs) - 3} more")
except Exception as e:
    print(f"   ✗ Failed to load languages: {e}")
    sys.exit(1)

# Test 4: Check if api router registration is correct
print("\n4. Testing API router...")
try:
    from app.api.api_v1 import api
    print("   ✓ API module imported successfully")
except ImportError as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("All integration tests passed! ✓")
print("=" * 60)
print("\nYou can now:")
print("1. Start the backend server")
print("2. Test the /languages/ endpoint")
print("3. The admin panel dropdown should populate with languages")
