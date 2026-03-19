#!/bin/bash
# Python 代码格式一键优化工具

echo "🔧 开始优化 Python 代码格式..."

# 检查是否安装了工具
if ! command -v black &> /dev/null; then
    echo "⚠️  未找到 black，正在安装..."
    pip install black --break-system-packages -q
fi

if ! command -v autoflake &> /dev/null; then
    echo "⚠️  未找到 autoflake，正在安装..."
    pip install autoflake --break-system-packages -q
fi

if ! command -v isort &> /dev/null; then
    echo "⚠️  未找到 isort，正在安装..."
    pip install isort --break-system-packages -q
fi

# 1. 清理未使用的导入和变量
echo "📝 清理未使用的导入和变量..."
autoflake --remove-all-unused-imports \
          --remove-unused-variables \
          --in-place \
          --recursive \
          --ignore-init-module-imports \
          *.py scripts/*.py 2>/dev/null

# 2. 排序导入
echo "📋 排序导入语句..."
isort --profile black *.py scripts/*.py 2>/dev/null

# 3. 格式化代码
echo "🎨 格式化代码..."
black --line-length 88 *.py scripts/*.py 2>/dev/null

echo ""
echo "✅ 代码格式优化完成!"
echo ""
echo "📊 统计:"
echo "   处理的文件数：$(find . -name '*.py' -not -path '*/__pycache__/*' | wc -l)"
echo ""
echo "💡 提示:"
echo "   - 在 VSCode 中按 Ctrl+S 自动格式化"
echo "   - 或按 Shift+Alt+F 手动格式化"
echo "   - 或运行此脚本：./format.sh"
