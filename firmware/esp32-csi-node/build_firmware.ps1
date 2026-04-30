# build_firmware.ps1
# Build ESP32-S3 CSI Node firmware using Docker (ESP-IDF v5.2)
# Requires: Docker Desktop, ESP-IDF container espressif/idf:v5.2

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FirmwareDir = Join-Path $ProjectRoot "firmware\esp32-csi-node"

Write-Host "Building ESP32-S3 CSI Node firmware..."
Write-Host "Firmware directory: $FirmwareDir"

$dockerCmd = @"
docker run --rm -v "${FirmwareDir}:/project" -w /project espressif/idf:v5.2 bash -c "rm -rf build sdkconfig && idf.py set-target esp32s3 && idf.py build"
"@

Invoke-Expression $dockerCmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build successful!" -ForegroundColor Green
    $BinPath = Join-Path $FirmwareDir "build\esp32-csi-node.bin"
    if (Test-Path $BinPath) {
        $Size = (Get-Item $BinPath).Length
        Write-Host "Binary: $BinPath ($Size bytes)"
    }
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
