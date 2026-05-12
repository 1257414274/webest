@echo off
chcp 65001 >nul
:: ==========================================
:: WeBest 项目一键启动脚本 (Windows)
:: ==========================================

cd /d "%~dp0"
set PROJECT_ROOT=%cd%

echo ==========================================
echo     WeBest (Domain Admin + All4Win)       
echo ==========================================

:: 1. 检查日志目录
if not exist "server\domain-admin-master\logs" mkdir "server\domain-admin-master\logs"
if not exist "all4win\logs" mkdir "all4win\logs"

echo [*] 环境准备完毕，准备启动服务...

:: 2. 启动后端 Web 服务 (Waitress / Flask)
cd server\domain-admin-master

:: 忽略字节码缓存，防止某些环境报错
set PYTHONDONTWRITEBYTECODE=1 

echo [*] 正在启动 WeBest 后端服务 (端口 8000)...
:: Windows 下使用 Waitress 启动生产环境
start "WeBest Server" cmd /c "python -m waitress --port=8000 domain_admin.main:app"

echo.
echo [√] WeBest 服务已在新窗口中启动！
echo     - 访问地址: http://127.0.0.1:8000
echo.
echo ==========================================
echo   资产拉取与分类工具使用说明 (Hunter + AI)
echo ==========================================
echo 1. 从 Hunter 平台采集资产 (导出为 CSV)
echo    请在项目根目录下打开新的终端执行:
echo    cd all4win
echo    python hunter_icp_asset_collector.py "备案主体名称" -n 数量
echo    示例: python hunter_icp_asset_collector.py 腾讯科技 -n 100
echo.
echo 2. 将 CSV 导入 WeBest 系统
echo    - 登录 Web 界面 (http://127.0.0.1:8000)
echo    - 找到 Hunter 资产相关导入入口，上传刚生成的 CSV 文件。
echo.
echo 3. 执行 AI 智能战术分类 (DeepSeek)
echo    - 方式一：等待系统调度器自动在后台触发
echo    - 方式二：在前端/接口请求触发 POST /api/triggerAssetClassification
echo    - 方式三：手动在命令行执行分类程序:
echo      cd all4win
echo      python hunter_asset_classifier.py
echo ==========================================
pause
