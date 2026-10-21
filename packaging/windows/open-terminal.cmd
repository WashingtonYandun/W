@echo off
set "PATH=%~dp0;%PATH%"
echo Wysna Language
"%~dp0wysna.exe" version
echo.
echo Run: wysna run hello.wysna
echo Build: wysna build hello.wysna -o hello.exe
echo.
