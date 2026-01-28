# DNS Fix Script for YouTube Access
# Run this as Administrator

Write-Host "="*60 -ForegroundColor Cyan
Write-Host "DNS Fix Script - Enable YouTube Access" -ForegroundColor Cyan
Write-Host "="*60 -ForegroundColor Cyan

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "`n❌ ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "`nRight-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host "Then run this script again.`n" -ForegroundColor Yellow
    pause
    exit
}

Write-Host "`n✅ Running as Administrator`n" -ForegroundColor Green

# Get active network adapter
$adapter = Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | Select-Object -First 1

if ($adapter) {
    $adapterName = $adapter.Name
    Write-Host "Found active network adapter: $adapterName" -ForegroundColor Green
    
    Write-Host "`nChanging DNS to Google Public DNS (8.8.8.8, 8.8.4.4)..." -ForegroundColor Yellow
    
    try {
        # Set primary DNS
        netsh interface ip set dns name="$adapterName" static 8.8.8.8
        
        # Set secondary DNS
        netsh interface ip add dns name="$adapterName" 8.8.4.4 index=2
        
        Write-Host "✅ DNS changed successfully!" -ForegroundColor Green
        
        # Flush DNS cache
        Write-Host "`nFlushing DNS cache..." -ForegroundColor Yellow
        ipconfig /flushdns | Out-Null
        Write-Host "✅ DNS cache flushed!" -ForegroundColor Green
        
        # Test YouTube access
        Write-Host "`nTesting YouTube access..." -ForegroundColor Yellow
        try {
            $result = Test-Connection -ComputerName www.youtube.com -Count 1 -ErrorAction Stop
            Write-Host "✅ SUCCESS! YouTube is now accessible!" -ForegroundColor Green
            Write-Host "   IP: $($result.IPV4Address)" -ForegroundColor Cyan
        }
        catch {
            Write-Host "⚠️  Still cannot reach YouTube" -ForegroundColor Yellow
            Write-Host "   This may be due to:" -ForegroundColor Yellow
            Write-Host "   - Firewall blocking" -ForegroundColor Yellow
            Write-Host "   - VPN interference" -ForegroundColor Yellow
            Write-Host "   - ISP blocking (try using a VPN)" -ForegroundColor Yellow
        }
        
    }
    catch {
        Write-Host "❌ Failed to change DNS: $_" -ForegroundColor Red
    }
    
} else {
    Write-Host "❌ No active network adapter found!" -ForegroundColor Red
}

Write-Host "`n" + "="*60 -ForegroundColor Cyan
Write-Host "DNS Fix Complete" -ForegroundColor Cyan
Write-Host "="*60 -ForegroundColor Cyan

Write-Host "`nTo revert to automatic DNS:" -ForegroundColor Yellow
Write-Host "  netsh interface ip set dns name=`"$adapterName`" dhcp`n" -ForegroundColor Cyan

pause
