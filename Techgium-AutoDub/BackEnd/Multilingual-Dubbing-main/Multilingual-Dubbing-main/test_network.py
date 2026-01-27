"""
Simple network connectivity test for YouTube
"""

import socket

print("="*60)
print("Network Connectivity Test")
print("="*60)

# Test 1: DNS Resolution for YouTube
print("\n1. Testing DNS resolution for www.youtube.com...")
try:
    ip = socket.gethostbyname("www.youtube.com")
    print(f"   ✅ SUCCESS: www.youtube.com resolves to {ip}")
    print(f"   Your DNS is working!")
except socket.gaierror as e:
    print(f"   ❌ FAILED: Cannot resolve www.youtube.com")
    print(f"   Error: {e}")
    print("\n   🔧 TROUBLESHOOTING STEPS:")
    print("   1. Check if internet is connected")
    print("   2. Run: ipconfig /flushdns (as Administrator)")
    print("   3. Change DNS to Google's: 8.8.8.8")
    print("   4. Restart your network adapter")
    print("   5. Disable VPN/Proxy if using")
    print("   6. Check firewall settings")

# Test 2: DNS Resolution for Google
print("\n2. Testing DNS resolution for google.com...")
try:
    ip = socket.gethostbyname("google.com")
    print(f"   ✅ SUCCESS: google.com resolves to {ip}")
except socket.gaierror as e:
    print(f"   ❌ FAILED: Cannot resolve google.com")
    print(f"   ⚠️  Your internet connection may be down!")

# Test 3: Check default DNS
print("\n3. Checking your DNS configuration...")
print("   Run this command to check DNS:")
print("   ipconfig /all | findstr /C:\"DNS Servers\"")

print("\n" + "="*60)
print("Test Complete")
print("="*60)
print("\nIf YouTube DNS fails but Google works:")
print("  → YouTube may be blocked by firewall/ISP")
print("\nIf both fail:")
print("  → Check your internet connection")
print("  → Try: ipconfig /flushdns")
print("  → Change DNS to 8.8.8.8 and 8.8.4.4")
