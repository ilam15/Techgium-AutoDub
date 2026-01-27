"""
Test script for YouTube download fixes
Tests the updated download_video endpoint with retry logic and better format selection
"""

import requests
import json
import time

# API endpoint
BASE_URL = "http://localhost:8000"

def test_fetch_video_info(url):
    """Test fetching video information"""
    print(f"\n{'='*60}")
    print("TEST 1: Fetching Video Info")
    print(f"{'='*60}")
    
    response = requests.post(
        f"{BASE_URL}/fetch_video_info",
        json={"url": url}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success!")
        print(f"Title: {data.get('title')}")
        print(f"Duration: {data.get('duration')} seconds")
        print(f"Uploader: {data.get('uploader')}")
        print(f"\nAvailable formats:")
        for fmt in data.get('formats', [])[:5]:  # Show first 5
            print(f"  - {fmt['quality']}: Format ID {fmt['format_id']}, "
                  f"HLS: {fmt.get('is_hls', False)}, "
                  f"Has Audio: {fmt['has_audio']}")
        return data
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
        return None

def test_download_video(url, format_id=None):
    """Test downloading video"""
    print(f"\n{'='*60}")
    print("TEST 2: Downloading Video")
    print(f"{'='*60}")
    
    payload = {"url": url}
    if format_id:
        payload["format_id"] = format_id
    
    print(f"Downloading with format_id: {format_id or 'auto (best quality)'}")
    print("This may take a while...")
    
    start_time = time.time()
    
    response = requests.post(
        f"{BASE_URL}/download_video",
        json=payload,
        timeout=300  # 5 minute timeout
    )
    
    elapsed = time.time() - start_time
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success! (took {elapsed:.1f} seconds)")
        print(f"File: {data.get('file_name')}")
        print(f"Size: {data.get('file_size'):,} bytes ({data.get('file_size')/1024/1024:.2f} MB)")
        print(f"Path: {data.get('file_path')}")
        return data
    else:
        print(f"❌ Failed: {response.status_code} (took {elapsed:.1f} seconds)")
        print(response.text)
        return None

def main():
    # Test URL - the one that was failing
    test_url = "https://youtu.be/T-qFT5OKHqk?si=vySmo6RHPad20-Qg"
    
    print(f"\n{'#'*60}")
    print("YouTube Download Fix - Test Suite")
    print(f"{'#'*60}")
    print(f"\nTesting URL: {test_url}")
    
    # Check if API is running
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code != 200:
            print(f"\n❌ API is not running at {BASE_URL}")
            print("Please start the API server first:")
            print("  cd BackEnd/Multilingual-Dubbing-main/Multilingual-Dubbing-main")
            print("  python api.py")
            return
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to API at {BASE_URL}")
        print("Please start the API server first:")
        print("  cd BackEnd/Multilingual-Dubbing-main/Multilingual-Dubbing-main")
        print("  python api.py")
        return
    
    print(f"✅ API is running at {BASE_URL}")
    
    # Test 1: Fetch video info
    video_info = test_fetch_video_info(test_url)
    
    if not video_info:
        print("\n❌ Cannot proceed with download test - info fetch failed")
        return
    
    # Test 2: Download video (auto-select best format)
    # This will use the new retry logic and format selection
    download_result = test_download_video(test_url)
    
    if download_result:
        print(f"\n{'='*60}")
        print("✅ ALL TESTS PASSED!")
        print(f"{'='*60}")
        print("\nThe YouTube download fix is working correctly.")
        print("The following improvements were applied:")
        print("  ✓ Retry logic with exponential backoff")
        print("  ✓ FFmpeg external downloader with reconnection")
        print("  ✓ Better format selection (avoiding HLS/DASH)")
        print("  ✓ Browser-like headers to avoid rate limiting")
        print("  ✓ Fragment retry options")
    else:
        print(f"\n{'='*60}")
        print("❌ DOWNLOAD TEST FAILED")
        print(f"{'='*60}")
        print("\nPlease check:")
        print("  1. Is yt-dlp updated? (pip install --upgrade yt-dlp)")
        print("  2. Is Node.js installed? (node --version)")
        print("  3. Is FFmpeg installed? (ffmpeg -version)")
        print("  4. Check the API logs for detailed error messages")
        print("\nSee YOUTUBE_DOWNLOAD_FIX.md for more troubleshooting steps.")

if __name__ == "__main__":
    main()
