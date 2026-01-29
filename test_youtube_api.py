import requests
import json

# Test YouTube info endpoint
print("Testing YouTube Info Endpoint...")
print("-" * 50)

url = "http://localhost:8000/youtube/info"
payload = {
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ SUCCESS!")
        print(f"\nVideo Title: {data['data']['title']}")
        print(f"Duration: {data['data']['duration']} seconds")
        print(f"Uploader: {data['data']['uploader']}")
        print(f"\nAvailable Formats:")
        for fmt in data['data']['formats'][:8]:  # Show first 8
            print(f"  - {fmt['quality']}")
    else:
        print(f"❌ ERROR: {response.text}")
        
except Exception as e:
    print(f"❌ Connection Error: {e}")
    print("\nMake sure the backend server is running on http://localhost:8000")
