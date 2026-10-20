@echo off
set "PATH=%~dp0;%PATH%"
echo W Language
"%~dp0w.exe" version
echo.
echo Run: w run hello.w
echo Build: w build hello.w -o hello.exe
echo.
