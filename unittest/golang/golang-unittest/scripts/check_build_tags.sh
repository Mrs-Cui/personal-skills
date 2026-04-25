#!/bin/bash
# 检查测试文件的 build tag 状态（只读，不修改任何文件）
# 用法: ./check_build_tags.sh <dir1> [dir2] [dir3] ...
# 示例: ./check_build_tags.sh ./internal ./pkg
#
# 检查逻辑:
#   1. _ai_test.go 文件 → 应有 //go:build ai_test
#   2. 非 AI 的 _test.go 文件 → 应有 //go:build !ai_test
#
# 退出码:
#   0 = 所有文件 tag 完整
#   1 = 有文件缺少 tag

set -e

# 检查参数
if [ $# -eq 0 ]; then
    echo "错误: 请提供至少一个目录路径"
    echo "用法: $0 <dir1> [dir2] [dir3] ..."
    echo "示例: $0 ./internal ./pkg"
    exit 2
fi

missing_ai=0
missing_non_ai=0

# 遍历所有指定目录
for dir in "$@"; do
    if [ ! -d "$dir" ]; then
        echo "警告: 目录不存在: $dir"
        continue
    fi

    echo "检查目录: $dir"
    echo ""

    # 检查 _ai_test.go 文件
    while IFS= read -r file; do
        if ! grep -q "//go:build" "$file"; then
            echo "  [AI]   缺少 tag: $file"
            missing_ai=$((missing_ai + 1))
        fi
    done < <(find "$dir" -name "*_ai_test.go" 2>/dev/null)

    # 检查所有非 AI 的 _test.go 文件
    while IFS= read -r file; do
        if [[ "$file" == *_ai_test.go ]]; then
            continue
        fi
        if ! grep -q "//go:build" "$file"; then
            echo "  [非AI] 缺少 tag: $file"
            missing_non_ai=$((missing_non_ai + 1))
        fi
    done < <(find "$dir" -name "*_test.go" 2>/dev/null)
done

# 输出总结
total_missing=$((missing_ai + missing_non_ai))

echo ""
if [ "$total_missing" -gt 0 ]; then
    echo "总计: ${total_missing} 个文件缺少 build tag (${missing_ai} AI, ${missing_non_ai} 非AI)"
    exit 1
else
    echo "✓ 所有测试文件 build tag 完整"
    exit 0
fi
