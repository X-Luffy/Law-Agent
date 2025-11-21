#!/bin/bash
# 系统测试脚本

echo "=========================================="
echo "Agent系统测试脚本"
echo "=========================================="
echo ""

# 1. 激活conda环境
echo "[1/4] 激活conda环境..."

# 尝试多种方式初始化conda
if [ -f ~/miniconda3/etc/profile.d/conda.sh ]; then
    source ~/miniconda3/etc/profile.d/conda.sh
elif [ -f ~/anaconda3/etc/profile.d/conda.sh ]; then
    source ~/anaconda3/etc/profile.d/conda.sh
elif [ -f /opt/conda/etc/profile.d/conda.sh ]; then
    source /opt/conda/etc/profile.d/conda.sh
elif [ -f /usr/local/anaconda3/etc/profile.d/conda.sh ]; then
    source /usr/local/anaconda3/etc/profile.d/conda.sh
else
    echo "⚠️  未找到conda初始化脚本，尝试直接使用conda命令"
fi

# 尝试激活conda环境
if command -v conda &> /dev/null; then
    conda activate /home/mnt/xieqinghongbing/env/open_manus 2>/dev/null || {
        echo "⚠️  无法使用conda activate，尝试直接使用Python路径"
        # 如果conda activate失败，尝试直接使用Python路径
        if [ -f /home/mnt/xieqinghongbing/env/open_manus/bin/python ]; then
            export PATH="/home/mnt/xieqinghongbing/env/open_manus/bin:$PATH"
            echo "✅ 已设置Python路径"
        else
            echo "⚠️  未找到conda环境，使用系统Python"
        fi
    }
else
    echo "⚠️  conda命令不可用，使用系统Python"
fi

echo "✅ 环境准备完成"
echo ""

# 2. 设置环境变量
echo "[2/4] 设置环境变量..."
export DASHSCOPE_API_KEY="sk-5d4975fe68f24d83809ac3c7bf7468ba"
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
echo "✅ 环境变量已设置"
echo ""

# 3. 检查依赖
echo "[3/4] 检查依赖..."
python -c "import dashscope; import chromadb; import openai; print('✅ 所有依赖已安装')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  部分依赖可能未安装，尝试安装..."
    pip install -q dashscope chromadb openai 2>/dev/null
fi
echo ""

# 4. 运行测试
echo "[4/4] 运行系统测试..."
echo ""
cd /home/mnt/xieqinghongbing/code/xiazhaoyuan/Agent
python test_system.py

echo ""
echo "=========================================="
echo "测试完成"
echo "=========================================="

