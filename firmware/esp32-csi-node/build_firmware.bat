@echo off
REM build_firmware.bat
REM Build ESP32-S3 CSI Node firmware using Docker (ESP-IDF v5.2)

echo Building ESP32-S3 CSI Node firmware...
set FIRMWARE_DIR=%~dp0

docker run --rm -v "%FIRMWARE_DIR%:/project" -w /project espressif/idf:v5.2 bash -c "rm -rf build sdkconfig && idf.py set-target esp32s3 && idf.py build"

if %ERRORLEVEL% == 0 (
    echo Build successful!
    if exist "%FIRMWARE_DIR%\build\esp32-csi-node.bin" (
        echo Binary: %FIRMWARE_DIR%\build\esp32-csi-node.bin
    )
) else (
    echo Build failed!
    exit /b 1
)
