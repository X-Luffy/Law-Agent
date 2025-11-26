#!/bin/bash
# Streamlit应用启动脚本

echo "=========================================="
echo "启动 Legal Agent System"
echo "=========================================="
echo ""

# 1. 激活conda环境
echo "[1/3] 激活conda环境..."

# 尝试多种方式初始化conda
if [ -f ~/miniconda3/etc/profile.d/conda.sh ]; then
    source ~/miniconda3/etc/profile.d/conda.sh
elif [ -f ~/anaconda3/etc/profile.d/conda.sh ]; then
    source ~/anaconda3/etc/profile.d/conda.sh
elif [ -f /opt/conda/etc/profile.d/conda.sh ]; then
    source /opt/conda/etc/profile.d/conda.sh
elif [ -f /usr/local/anaconda3/etc/profile.d/conda.sh ]; then
    source /usr/local/anaconda3/etc/profile.d/conda.sh
fi

# 尝试激活conda环境
if command -v conda &> /dev/null; then
    conda activate /home/mnt/xieqinghongbing/env/open_manus 2>/dev/null || {
        # 如果conda activate失败，尝试直接使用Python路径
        if [ -f /home/mnt/xieqinghongbing/env/open_manus/bin/python ]; then
            export PATH="/home/mnt/xieqinghongbing/env/open_manus/bin:$PATH"
        fi
    }
fi

echo "✅ 环境准备完成"
echo ""

# 2. 设置环境变量
echo "[2/3] 设置环境变量..."
export DASHSCOPE_API_KEY="sk-5d4975fe68f24d83809ac3c7bf7468ba"
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export BOCHA_API_KEY="sk-abc3ef836fd9487c867cc58df5f76c31"
echo "✅ 环境变量已设置"
echo ""

# 3. 启动Streamlit应用
echo "[3/3] 启动Streamlit应用..."
echo ""
cd /home/mnt/xieqinghongbing/code/xiazhaoyuan/Agent

# 检查streamlit是否安装
if ! python -c "import streamlit" 2>/dev/null; then
    echo "⚠️  streamlit未安装，正在安装..."
    pip install -q streamlit
fi

# 启动应用
echo "🚀 正在启动应用..."
echo "📝 应用将在浏览器中自动打开"
echo "🔗 如果未自动打开，请访问: http://localhost:8501"
echo ""
echo "按 Ctrl+C 停止应用"
echo ""

streamlit run app.py

