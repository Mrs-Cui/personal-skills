#!/bin/bash
# 确保接口文件包含正确的 go:generate mockgen 注释并执行生成
#
# 用法: ./ensure_mock_generate.sh <项目根目录> [--tags "tag1,tag2"] <接口文件1> [接口文件2] ...
#   - 项目根目录: go.mod 所在目录的绝对路径或相对路径
#   - --tags:     可选，用于编译验证的 build tags（如 "primary,local,ai_test"）
#   - 接口文件:   相对于项目根目录的路径，如 internal/repo/user_repository.go
#
# 示例:
#   ./ensure_mock_generate.sh /path/to/project internal/repo/user.go
#   ./ensure_mock_generate.sh /path/to/project --tags "primary,local,ai_test" internal/repo/user.go
#
# 功能:
#   1. 扫描文件中的 interface 定义
#   2. 检查是否已有 //go:generate mockgen 注释
#   3. 如果没有，自动计算正确的 -destination 路径并添加注释（-source 模式）
#   4. 在项目根目录执行 go generate 生成 Mock 文件
#   5. 验证生成的 Mock 文件能否编译
#   6. 如果编译失败（通常因为接口引用了未导出符号），自动回退到 reflect 模式重新生成
#
# 路径规则:
#   - internal/repo/user.go       → testmocks/repo/mock_user.go        (去掉 internal/)
#   - internal/svc/channel/svc.go → testmocks/svc/channel/mock_svc.go  (去掉 internal/)
#   - infra/database/conn.go      → testmocks/infra/database/mock_conn.go (保留原路径)

set -e

# ========== 参数校验 ==========

if [ $# -lt 2 ]; then
    echo "错误: 参数不足"
    echo "用法: $0 <项目根目录> [--tags \"tag1,tag2\"] <接口文件1> [接口文件2] ..."
    exit 1
fi

PROJECT_ROOT="$1"
shift

# 解析可选的 --tags 参数
BUILD_TAGS=""
if [ "$1" = "--tags" ]; then
    BUILD_TAGS="$2"
    shift 2
fi

if [ ! -f "$PROJECT_ROOT/go.mod" ]; then
    echo "错误: $PROJECT_ROOT 下未找到 go.mod，请确认项目根目录路径"
    exit 1
fi

# 从 go.mod 读取 module 路径
GO_MODULE=$(grep '^module ' "$PROJECT_ROOT/go.mod" | head -1 | awk '{print $2}')
if [ -z "$GO_MODULE" ]; then
    echo "错误: go.mod 中未找到 module 声明"
    exit 1
fi

# ========== mockgen 版本检查 ==========

# 检查 mockgen 是否已安装
if ! command -v mockgen &>/dev/null; then
    echo "错误: mockgen 未安装"
    echo "安装命令: go install go.uber.org/mock/mockgen@latest"
    exit 1
fi

# 检查 mockgen 是否来自 go.uber.org/mock（旧版 github.com/golang/mock 已停止维护）
mockgen_path=$(which mockgen)
mockgen_mod=$(go version -m "$mockgen_path" 2>&1 | grep '^\s*path' | awk '{print $2}')
if [[ "$mockgen_mod" == github.com/golang/mock/* ]]; then
    echo "错误: 检测到旧版 mockgen (github.com/golang/mock)，该项目已停止维护"
    echo "当前路径: $mockgen_path"
    echo "模块来源: $mockgen_mod"
    echo "请卸载旧版并安装新版:"
    echo "  go install go.uber.org/mock/mockgen@latest"
    exit 1
fi
mockgen_version=$(mockgen -version 2>&1 || true)
echo "mockgen 版本: $mockgen_version (来源: $mockgen_mod)"

# ========== go.mod 依赖检查 ==========

# 确保项目 go.mod 中有 go.uber.org/mock 依赖（新版 mockgen 生成的代码需要）
if ! grep -q 'go.uber.org/mock' "$PROJECT_ROOT/go.mod"; then
    echo "go.mod 中未找到 go.uber.org/mock，自动添加..."
    if ! (cd "$PROJECT_ROOT" && go get go.uber.org/mock@latest) 2>&1; then
        echo "⚠ go get go.uber.org/mock@latest 失败，请手动添加依赖"
    else
        echo "✓ 已添加 go.uber.org/mock 依赖"
    fi
fi

# ========== 工具函数 ==========

# 计算从源文件目录到项目根目录需要的 ../ 层数
calc_relative_prefix() {
    local file_dir="$1"
    local depth
    depth=$(echo "$file_dir" | awk -F/ '{print NF}')
    local prefix=""
    for ((i = 0; i < depth; i++)); do
        prefix="../$prefix"
    done
    echo "$prefix"
}

# 根据源文件路径计算 Mock 目标路径（相对于项目根目录）
calc_mock_dest_from_root() {
    local src_path="$1"
    local src_dir
    src_dir=$(dirname "$src_path")
    local src_file
    src_file=$(basename "$src_path")

    # 去掉 internal/ 前缀
    local mock_dir
    if [[ "$src_dir" == internal/* ]]; then
        mock_dir="${src_dir#internal/}"
    elif [[ "$src_dir" == "internal" ]]; then
        mock_dir=""
    else
        mock_dir="$src_dir"
    fi

    # 拼接 testmocks 路径
    if [ -n "$mock_dir" ]; then
        echo "testmocks/$mock_dir/mock_$src_file"
    else
        echo "testmocks/mock_$src_file"
    fi
}

# 计算 -destination 的相对路径（从源文件位置出发）
calc_destination_relative() {
    local src_path="$1"
    local src_dir
    src_dir=$(dirname "$src_path")
    local prefix
    prefix=$(calc_relative_prefix "$src_dir")
    local mock_from_root
    mock_from_root=$(calc_mock_dest_from_root "$src_path")
    echo "${prefix}${mock_from_root}"
}

# 获取 Mock 包名（目标目录的最后一级目录名）
calc_package_name() {
    local src_path="$1"
    local src_dir
    src_dir=$(dirname "$src_path")

    # 去掉 internal/ 前缀后取最后一级目录
    local mock_dir
    if [[ "$src_dir" == internal/* ]]; then
        mock_dir="${src_dir#internal/}"
    elif [[ "$src_dir" == "internal" ]]; then
        mock_dir=""
    else
        mock_dir="$src_dir"
    fi

    if [ -n "$mock_dir" ]; then
        basename "$mock_dir"
    else
        echo "testmocks"
    fi
}

# 计算源文件所在包的完整 import path
calc_import_path() {
    local src_path="$1"
    local src_dir
    src_dir=$(dirname "$src_path")
    echo "${GO_MODULE}/${src_dir}"
}

# 从源文件提取所有接口名，逗号分隔
extract_interface_names() {
    local file="$1"
    grep 'type .* interface {' "$file" | sed 's/.*type \([A-Za-z_][A-Za-z0-9_]*\) interface.*/\1/' | paste -sd, -
}

# 检查文件中是否已有 go:generate mockgen 注释
has_generate_comment() {
    local file="$1"
    grep -q '//go:generate mockgen' "$file" 2>/dev/null
}

# 检查文件中是否包含 interface 定义
has_interface() {
    local file="$1"
    grep -q 'type .* interface {' "$file" 2>/dev/null
}

# 移除文件中的 go:generate mockgen 注释（mockey 回退时清理）
remove_generate_comment() {
    local file="$1"
    local temp_file
    temp_file=$(mktemp)
    grep -v '^//go:generate mockgen' "$file" > "$temp_file"
    mv "$temp_file" "$file"
    echo "  ✓ 已移除 go:generate 注释"
}

# 为文件添加 go:generate 注释（在第一个 interface 定义之前）
add_generate_comment() {
    local file="$1"
    local comment="$2"

    # 找到第一个 type ... interface { 的行号
    local line_num
    line_num=$(grep -n 'type .* interface {' "$file" | head -1 | cut -d: -f1)

    if [ -z "$line_num" ]; then
        echo "  ⚠ 未找到 interface 定义，跳过: $file"
        return 1
    fi

    # 在 interface 定义行之前插入注释
    local temp_file
    temp_file=$(mktemp)
    {
        head -n $((line_num - 1)) "$file"
        echo "$comment"
        tail -n +"$line_num" "$file"
    } > "$temp_file"
    mv "$temp_file" "$file"

    echo "  ✓ 已添加注释: $comment"
    return 0
}

# 替换文件中已有的 go:generate mockgen 注释
update_generate_comment() {
    local file="$1"
    local new_comment="$2"

    local temp_file
    temp_file=$(mktemp)
    sed "s|^//go:generate mockgen .*|${new_comment}|" "$file" > "$temp_file"
    mv "$temp_file" "$file"

    echo "  ✓ 已更新注释为 reflect 模式: $new_comment"
}

# 验证 mock 文件能否编译
verify_mock_compiles() {
    local mock_dir="$1"
    local build_output

    if [ -n "$BUILD_TAGS" ]; then
        build_output=$(cd "$PROJECT_ROOT" && go build -tags "$BUILD_TAGS" "./$mock_dir/..." 2>&1) || true
    else
        build_output=$(cd "$PROJECT_ROOT" && go build "./$mock_dir/..." 2>&1) || true
    fi

    if [ -z "$build_output" ]; then
        return 0  # 编译成功
    fi

    # 检查是否包含 undefined 错误（未导出符号问题的典型特征）
    if echo "$build_output" | grep -q "undefined:"; then
        echo "  ⚠ 编译失败 (未导出符号问题):"
        echo "$build_output" | grep "undefined:" | head -5 | sed 's/^/    /'
        return 1
    fi

    # 其他编译错误也视为失败
    if echo "$build_output" | grep -qE "^.+\.go:[0-9]+:[0-9]+:"; then
        echo "  ⚠ 编译失败:"
        echo "$build_output" | head -5 | sed 's/^/    /'
        return 1
    fi

    return 0  # 没有明确的错误输出，视为成功
}

# 用 reflect 模式重新生成 mock
generate_reflect_mode() {
    local src_file="$1"
    local mock_dest_from_root="$2"
    local pkg_name="$3"
    local import_path="$4"
    local interface_names="$5"

    echo "  → 使用 reflect 模式重新生成..."

    # 构建 mockgen 命令参数
    local build_flags_arg=""
    if [ -n "$BUILD_TAGS" ]; then
        build_flags_arg="-build_flags=-tags=$BUILD_TAGS"
    fi

    echo "    mockgen -destination=$mock_dest_from_root -package=$pkg_name ${build_flags_arg:+$build_flags_arg }$import_path $interface_names"

    # reflect 模式必须在项目根目录下执行（需要 go.mod）
    if (cd "$PROJECT_ROOT" && mockgen \
        -destination="$mock_dest_from_root" \
        -package="$pkg_name" \
        ${build_flags_arg:+"$build_flags_arg"} \
        "$import_path" "$interface_names") 2>&1; then
        return 0
    else
        echo "  ✗ reflect 模式生成也失败"
        return 1
    fi
}

# ========== 主流程 ==========

echo "========================================="
echo "Mock 生成器: 检查并添加 go:generate 注释"
echo "========================================="
echo "项目根目录: $PROJECT_ROOT"
echo "Go module:  $GO_MODULE"
if [ -n "$BUILD_TAGS" ]; then
    echo "Build tags: $BUILD_TAGS"
fi
echo ""

added_count=0
skipped_count=0
error_count=0
files_to_generate=()

for src_file in "$@"; do
    full_path="$PROJECT_ROOT/$src_file"
    echo "处理: $src_file"

    # 检查文件是否存在
    if [ ! -f "$full_path" ]; then
        echo "  ✗ 文件不存在: $full_path"
        error_count=$((error_count + 1))
        continue
    fi

    # 检查是否包含 interface
    if ! has_interface "$full_path"; then
        echo "  ⊘ 跳过 (无 interface 定义)"
        skipped_count=$((skipped_count + 1))
        continue
    fi

    # 检查是否已有 go:generate 注释
    if has_generate_comment "$full_path"; then
        echo "  ⊘ 跳过 (已有 go:generate 注释)"
        skipped_count=$((skipped_count + 1))
        files_to_generate+=("$src_file")
        continue
    fi

    # 计算路径
    destination=$(calc_destination_relative "$src_file")
    pkg_name=$(calc_package_name "$src_file")

    # 验证目标路径不包含 testmocks/internal/
    mock_from_root=$(calc_mock_dest_from_root "$src_file")
    if [[ "$mock_from_root" == testmocks/internal/* ]]; then
        echo "  ✗ 路径计算异常，目标包含 testmocks/internal/: $mock_from_root"
        error_count=$((error_count + 1))
        continue
    fi

    # 添加 -source 模式的 go:generate 注释
    src_basename=$(basename "$src_file")
    comment="//go:generate mockgen -source=$src_basename -destination=$destination -package=$pkg_name"

    if add_generate_comment "$full_path" "$comment"; then
        added_count=$((added_count + 1))
        files_to_generate+=("$src_file")
    else
        error_count=$((error_count + 1))
    fi
done

echo ""
echo "========================================="
echo "注释处理完成"
echo "========================================="
echo "新增注释: $added_count"
echo "已跳过:   $skipped_count"
echo "错误:     $error_count"

# 执行 go generate + 编译验证 + 自动回退
if [ ${#files_to_generate[@]} -gt 0 ]; then
    echo ""
    echo "========================================="
    echo "执行 go generate 生成 Mock 文件"
    echo "========================================="

    generate_errors=0
    fallback_count=0
    mockey_fallback=()

    for src_file in "${files_to_generate[@]}"; do
        src_dir=$(dirname "$src_file")
        full_path="$PROJECT_ROOT/$src_file"
        echo "  生成: ./$src_dir/..."

        # 确保 testmocks 目标目录存在
        mock_from_root=$(calc_mock_dest_from_root "$src_file")
        mock_dir=$(dirname "$mock_from_root")
        mkdir -p "$PROJECT_ROOT/$mock_dir"

        # Step 1: 用 -source 模式生成（通过 go generate）
        source_gen_ok=true
        if ! (cd "$PROJECT_ROOT" && go generate "./$src_dir/...") 2>&1; then
            echo "  ⚠ go generate 失败，尝试 reflect 模式..."
            source_gen_ok=false
        fi

        # Step 2: 验证编译（仅当 source 模式生成成功时）
        need_fallback=false
        if [ "$source_gen_ok" = true ]; then
            if verify_mock_compiles "$mock_dir"; then
                echo "  ✓ 成功 (source 模式)"
                continue
            else
                need_fallback=true
            fi
        else
            need_fallback=true
        fi

        # Step 3: 回退到 reflect 模式
        if [ "$need_fallback" = true ]; then
            pkg_name=$(calc_package_name "$src_file")
            import_path=$(calc_import_path "$src_file")
            interface_names=$(extract_interface_names "$full_path")

            if [ -z "$interface_names" ]; then
                echo "  ✗ 无法提取接口名，跳过"
                generate_errors=$((generate_errors + 1))
                continue
            fi

            # 用 reflect 模式重新生成
            reflect_ok=false
            if generate_reflect_mode "$src_file" "$mock_from_root" "$pkg_name" "$import_path" "$interface_names"; then
                # 再次验证编译
                if verify_mock_compiles "$mock_dir"; then
                    echo "  ✓ 成功 (reflect 模式回退)"
                    fallback_count=$((fallback_count + 1))
                    reflect_ok=true

                    # 更新源文件中的 go:generate 注释为 reflect 模式
                    destination=$(calc_destination_relative "$src_file")
                    new_comment="//go:generate mockgen -destination=$destination -package=$pkg_name $import_path $interface_names"
                    update_generate_comment "$full_path" "$new_comment"
                fi
            fi

            # Step 4: 两种模式都失败 → 标记为 mockey 回退
            if [ "$reflect_ok" = false ]; then
                echo "  ⚠ gomock 无法生成此接口的 Mock（接口方法签名引用了未导出类型）"
                echo "  → 标记为 mockey 回退: $interface_names"

                # 删除生成失败的 mock 文件
                if [ -f "$PROJECT_ROOT/$mock_from_root" ]; then
                    rm "$PROJECT_ROOT/$mock_from_root"
                fi
                # 删除空目录
                local_mock_dir="$PROJECT_ROOT/$mock_dir"
                if [ -d "$local_mock_dir" ] && [ -z "$(ls -A "$local_mock_dir")" ]; then
                    rmdir "$local_mock_dir"
                fi

                # 移除源文件中添加的 go:generate 注释
                remove_generate_comment "$full_path"

                mockey_fallback+=("$src_file:$interface_names")
            fi
        fi
    done

    echo ""
    echo "========================================="
    echo "生成结果"
    echo "========================================="
    mockey_count=${#mockey_fallback[@]}
    source_ok=$((${#files_to_generate[@]} - generate_errors - fallback_count - mockey_count))
    echo "source 模式成功: $source_ok"
    if [ "$fallback_count" -gt 0 ]; then
        echo "reflect 回退成功: $fallback_count"
    fi
    if [ "$mockey_count" -gt 0 ]; then
        echo "mockey 回退:      $mockey_count"
        for entry in "${mockey_fallback[@]}"; do
            file="${entry%%:*}"
            ifaces="${entry#*:}"
            echo "  - $file → 接口: $ifaces"
        done
    fi
    if [ "$generate_errors" -gt 0 ]; then
        echo "失败: $generate_errors"
        echo ""
        echo "⚠ $generate_errors 个文件生成失败，请检查 mockgen 是否已安装"
        echo "  安装命令: go install go.uber.org/mock/mockgen@latest"
    fi

    # 输出 JSON 摘要（供主控解析）
    # 使用 python3 生成合法 JSON，避免特殊字符破坏格式
    echo ""
    echo "--- MOCK_GENERATE_RESULT_JSON ---"
    python3 -c "
import json, sys
fallback = []
for entry in sys.argv[1:]:
    parts = entry.split(':', 1)
    fallback.append({'file': parts[0], 'interfaces': parts[1] if len(parts) > 1 else ''})
print(json.dumps({
    'source_ok': $source_ok,
    'reflect_fallback': $fallback_count,
    'errors': $generate_errors,
    'mockey_fallback': fallback
}, ensure_ascii=False, indent=2))
" "${mockey_fallback[@]}"
    echo "--- END_MOCK_GENERATE_RESULT_JSON ---"

    if [ "$generate_errors" -gt 0 ] && [ "$mockey_count" -eq 0 ]; then
        exit 1
    fi
else
    echo ""
    echo "无需生成 Mock 文件"
fi
