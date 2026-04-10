@echo off
title AirPlay Receiver — Installer
color 0B

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║      AirPlay Receiver — Installer        ║
echo  ╚══════════════════════════════════════════╝
echo.

if not exist "%~dp0AirPlayReceiver.exe" (
    echo  [!] AirPlayReceiver.exe not found.
    pause & exit /b 1
)

set INSTALL_DIR=%ProgramData%\AirPlayReceiver
echo  [→] Installing to: %INSTALL_DIR%
mkdir "%INSTALL_DIR%" 2>nul

copy /Y "%~dp0AirPlayReceiver.exe" "%INSTALL_DIR%\" >nul
echo  [✓] Installed AirPlayReceiver.exe

:: Start Menu shortcut
set SM=%APPDATA%\Microsoft\Windows\Start Menu\Programs
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SM%\AirPlay Receiver.lnk');$s.TargetPath='%INSTALL_DIR%\AirPlayReceiver.exe';$s.WorkingDirectory='%INSTALL_DIR%';$s.Save()" 2>nul
echo  [✓] Start Menu shortcut created

:: Optional startup
echo.
set /p STARTUP="  [?] Start on Windows login? (y/n): "
if /i "%STARTUP%"=="y" (
    set SF=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
    powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SF%\AirPlay Receiver.lnk');$s.TargetPath='%INSTALL_DIR%\AirPlayReceiver.exe';$s.WindowStyle=7;$s.Save()" 2>nul
    echo  [✓] Added to Startup
)

:: Firewall
netsh advfirewall firewall delete rule name="AirPlay Receiver" >nul 2>&1
netsh advfirewall firewall add rule name="AirPlay Receiver TCP" dir=in action=allow protocol=TCP localport=7000-7020 >nul
netsh advfirewall firewall add rule name="AirPlay Receiver UDP" dir=in action=allow protocol=UDP localport=5353,6001-6050 >nul
echo  [✓] Firewall rules added

echo.
echo  ╔═══════════════════════════════════════════════╗
echo  ║  Done!  Data: %%ProgramData%%\AirPlayReceiver ║
echo  ╚═══════════════════════════════════════════════╝
echo.
set /p LAUNCH="  [?] Launch now? (y/n): "
if /i "%LAUNCH%"=="y" start "" "%INSTALL_DIR%\AirPlayReceiver.exe"
pause
