@echo off
echo ========================================
echo   B站情感分析 Chrome 扩展安装向导
echo ========================================
echo.

setlocal

set "URL=chrome://extensions/"
set "CHROME_EXE="

echo 尝试定位 Chrome 可执行文件...

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if defined CHROME_EXE (
    echo 找到 Chrome: "%CHROME_EXE%"
    echo 正在使用 Chrome 打开扩展页面...
    start "" "%CHROME_EXE%" "%URL%"
) else (
    echo 未能自动定位 Chrome 可执行文件。
    echo 将在默认浏览器中打开 Chrome 下载页面，或请手动打开 Chrome 并访问：chrome://extensions/
    echo.
    echo 下载地址: https://www.google.com/chrome/
    start "" "https://www.google.com/chrome/"
)

echo.
echo 扩展文件位置: %~dp0chrome_extension
echo 使用说明：
echo 1) 在 Chrome 的扩展页面（chrome://extensions/）开启“开发者模式”
echo 2) 点击“加载已解压的扩展程序”，选择上面显示的文件夹
echo.
pause

endlocal
