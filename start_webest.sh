#!/bin/bash

# ==========================================
# WeBest 项目一键启动脚本 (Linux/macOS)
# ==========================================

# 确保在脚本所在目录执行
cd "$(dirname "$0")"
PROJECT_ROOT=$(pwd)

echo "=========================================="
echo "    WeBest       "
echo "=========================================="

# 1. 检查虚拟环境
if [ ! -d "server/domain-admin-master/venv" ]; then
    echo "[*] 未找到虚拟环境，正在创建..."
    cd server/domain-admin-master
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements/production.txt
    cd $PROJECT_ROOT
else
    source server/domain-admin-master/venv/bin/activate
fi

# 2. 检查日志目录
mkdir -p server/domain-admin-master/logs
mkdir -p all4win/logs

echo "[*] 环境准备完毕，准备启动服务..."

# 3. 启动后端 Web 服务 (Flask/Gunicorn)
cd server/domain-admin-master

# 杀掉可能残余的 gunicorn 进程 (按需)
pkill -f "domain_admin.main:app" 2>/dev/null || true

# 忽略字节码缓存，防止沙盒报错
export PYTHONDONTWRITEBYTECODE=1 

echo "[*] 正在启动 WeBest 后端服务 (端口 8000)..."
nohup gunicorn --bind '0.0.0.0:8000' --timeout 120 'domain_admin.main:app' > logs/server.log 2>&1 &

echo ""
echo "[√] WeBest 服务已在后台启动！"
echo "    - 访问地址: http://127.0.0.1:8000"
echo "    - 服务日志: server/domain-admin-master/logs/server.log"
echo ""
echo "=========================================="
echo "  资产拉取与分类工具使用说明 (Hunter + AI)"
echo "=========================================="
echo "1. 从 Hunter 平台采集资产 (导出为 CSV)"
echo "   请在项目根目录下执行:"
echo "   cd all4win"
echo "   python hunter_icp_asset_collector.py <备案主体名称> -n <数量>"
echo "   示例: python hunter_icp_asset_collector.py 腾讯科技 -n 100"
echo ""
echo "2. 将 CSV 导入 WeBest 系统"
echo "   - 登录 Web 界面 (http://127.0.0.1:8000)"
echo "   - 在【Hunter资产】模块通过页面上传刚生成的 CSV"
echo ""
echo "3. 执行 AI 智能战术分类 (DeepSeek)"
echo "   - 方式一：等待系统调度器自动在后台触发"
echo "   - 方式二：调用API手动触发 POST http://127.0.0.1:8000/api/triggerAssetClassification"
echo "   - 方式三：手动在命令行执行分类程序:"
echo "     cd all4win && python hunter_asset_classifier.py"
echo "=========================================="
