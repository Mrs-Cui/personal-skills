#!/bin/bash
# 为测试文件添加 build tag，实现 AI 测试与普通测试的隔离
# 用法: ./add_build_tags.sh <dir1> [dir2] [dir3] ...
# 示例: ./add_build_tags.sh ./internal ./pkg
#
# 处理逻辑:
#   1. _ai_test.go 文件 → 添加 //go:build ai_test
#   2. 非 AI 的 _test.go 文件 → 添加 //go:build !ai_test
#   3. 已有 //go:build 行的文件 → 跳过
#
# 这样可以确保:
#   - go test ./...              只运行普通测试（不含 AI 测试）
#   - go test -tags ai_test ./... 只运行 AI 测试（不含普通测试）

set -e

# 检查参数
if [ $# -eq 0 ]; then
    echo "错误: 请提供至少一个目录路径"
    echo "用法: $0 <dir1> [dir2] [dir3] ..."
    echo "示例: $0 ./internal ./pkg"
    exit 1
fi

# 验证目录是否存在
for dir in "$@"; do
    if [ ! -d "$dir" ]; then
        echo "警告: 目录不存在: $dir"
    fi
done

echo "========================================="
echo "为测试文件添加 build tag（AI 隔离）"
echo "========================================="
echo ""
echo "扫描目录: $*"
echo ""

# 统计变量
ai_total=0
ai_tagged=0
ai_skipped=0
non_ai_total=0
non_ai_tagged=0
non_ai_skipped=0

# 为文件添加 build tag 的函数
# 参数: $1=文件路径, $2=tag 内容 (如 "ai_test" 或 "!ai_test")
add_tag() {
    local file="$1"
    local tag="$2"
    local temp_file
    temp_file=$(mktemp)
    echo "//go:build ${tag}" > "$temp_file"
    echo "" >> "$temp_file"
    cat "$file" >> "$temp_file"
    mv "$temp_file" "$file"
}

# 遍历所有指定目录
for dir in "$@"; do
    if [ ! -d "$dir" ]; then
        continue
    fi

    echo "处理目录: $dir"
    echo "─────────────────────────────────────────"

    # 处理 _ai_test.go 文件 → ai_test tag
    while IFS= read -r file; do
        ai_total=$((ai_total + 1))
        if grep -q "//go:build" "$file"; then
            echo "  ⊘ 跳过 (已有 tag): $file"
            ai_skipped=$((ai_skipped + 1))
        else
            add_tag "$file" "ai_test"
            echo "  ✓ 已添加 ai_test tag: $file"
            ai_tagged=$((ai_tagged + 1))
        fi
    done < <(find "$dir" -name "*_ai_test.go" 2>/dev/null)

    # 处理所有非 AI 的 _test.go 文件 → !ai_test tag
    while IFS= read -r file; do
        # 排除 _ai_test.go 文件
        if [[ "$file" == *_ai_test.go ]]; then
            continue
        fi
        non_ai_total=$((non_ai_total + 1))
        if grep -q "//go:build" "$file"; then
            echo "  ⊘ 跳过 (已有 tag): $file"
            non_ai_skipped=$((non_ai_skipped + 1))
        else
            add_tag "$file" "!ai_test"
            echo "  ✓ 已添加 !ai_test tag: $file"
            non_ai_tagged=$((non_ai_tagged + 1))
        fi
    done < <(find "$dir" -name "*_test.go" 2>/dev/null)

    echo ""
done

# 输出总结
echo "========================================="
echo "处理完成!"
echo "========================================="
echo ""
echo "AI 测试文件 (_ai_test.go):"
echo "  总文件数: $ai_total"
echo "  已添加 ai_test tag: $ai_tagged"
echo "  已跳过 (已有 tag): $ai_skipped"
echo ""
echo "非 AI 测试文件 (_test.go):"
echo "  总文件数: $non_ai_total"
echo "  已添加 !ai_test tag: $non_ai_tagged"
echo "  已跳过 (已有 tag): $non_ai_skipped"
echo ""

total_tagged=$((ai_tagged + non_ai_tagged))
if [ "$total_tagged" -gt 0 ]; then
    echo "✓ 成功为 $total_tagged 个文件添加 build tag"
    echo ""
    echo "提示: 这些文件可以直接 commit。"
    echo "  - go test ./...               只运行普通测试"
    echo "  - go test -tags ai_test ./... 只运行 AI 测试"
else
    echo "✓ 所有文件都已有 build tag，无需修改"
fi
