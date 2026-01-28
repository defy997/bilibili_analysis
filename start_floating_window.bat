@echo off
echo ========================================
echo   B站视频情感分析悬浮窗口启动器
echo ========================================
echo.

cd electron

echo [1/3] 检查Node.js环境...
node --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未检测到Node.js，请先安装Node.js
    pause
    exit /b 1
)

echo [2/3] 检查依赖...
if not exist node_modules (
    echo 正在安装依赖，请稍候...
    npm install
    if errorlevel 1 (
        echo 错误: 依赖安装失败
        pause
        exit /b 1
    )
)

echo [3/3] 启动悬浮窗口...
echo.
echo 提示:
echo - 确保Django后端服务正在运行 (http://localhost:8000)
echo - 安装并启用Chrome插件
echo - 在B站上切换视频即可看到分析结果
echo.
echo 按Ctrl+C关闭窗口
echo.

npm start
