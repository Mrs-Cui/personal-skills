#!/usr/bin/env bash

# Claude Code Skills 安装工具
# 用途：从 market-skills 仓库一键安装或更新 skills 到目标项目

set -euo pipefail

# ============================================================================
# 配置
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKET_SKILLS_REPO="https://git.tigerbrokers.net/astro/market-skills"
DEFAULT_BRANCH="master"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_error()   { echo -e "${RED}✗ $1${NC}" >&2; }
log_warn()    { echo -e "${YELLOW}⚠ $1${NC}"; }
log_info()    { echo -e "${BLUE}ℹ $1${NC}"; }
log_success() { echo -e "${GREEN}✓ $1${NC}"; }

# ============================================================================
# 帮助信息
# ============================================================================

usage() {
    cat <<EOF
用法：
  install-skills.sh [选项] [skill名称...]

选项：
  -g, --global          安装到全局 (~/.claude/skills/)，默认安装到当前项目
  -u, --update          仅更新已安装的 skill（跳过未安装的）
  -l, --list            列出仓库中所有可用的 skill
  -s, --source <路径>   指定 market-skills 本地路径（默认从远程拉取）
  -h, --help            显示帮助

示例：
  # 安装所有 skill 到当前项目
  install-skills.sh

  # 安装指定 skill
  install-skills.sh claude-context ai-code-review

  # 更新已安装的所有 skill
  install-skills.sh --update

  # 安装到全局
  install-skills.sh --global

  # 使用本地仓库（无需网络）
  install-skills.sh --source ~/market-skills
EOF
}

# ============================================================================
# 获取 skills 源目录
# ============================================================================

get_skills_source() {
    local source_path="$1"

    # 优先用脚本自身所在目录（脚本在 skills/ 下，说明已在本地仓库里）
    if [[ -d "$SCRIPT_DIR" && "$(basename "$SCRIPT_DIR")" == "skills" ]]; then
        echo "$SCRIPT_DIR"
        return
    fi

    # 使用指定的本地路径
    if [[ -n "$source_path" ]]; then
        if [[ ! -d "$source_path/skills" ]]; then
            log_error "指定路径不存在或不是 market-skills 仓库：$source_path"
            exit 1
        fi
        echo "$source_path/skills"
        return
    fi

    # 从远程拉取
    local tmp_dir
    tmp_dir=$(mktemp -d)
    trap "rm -rf $tmp_dir" EXIT

    log_info "从远程仓库拉取 skills..."
    if ! git clone --depth=1 -b "$DEFAULT_BRANCH" "$MARKET_SKILLS_REPO" "$tmp_dir" 2>/dev/null; then
        log_error "拉取失败，请检查网络或使用 --source 指定本地路径"
        exit 1
    fi

    echo "$tmp_dir/skills"
}

# ============================================================================
# 核心操作
# ============================================================================

list_available() {
    local skills_dir="$1"
    echo ""
    echo "可用的 Skills："
    echo ""
    for skill_dir in "$skills_dir"/*/; do
        local name
        name=$(basename "$skill_dir")
        # 跳过脚本文件本身
        [[ "$name" == *.sh ]] && continue
        [[ ! -f "$skill_dir/SKILL.md" ]] && continue

        # 从 SKILL.md frontmatter 里读 description 第一行
        local desc
        desc=$(awk '/^description:/{found=1; next} found && /^[a-zA-Z-]+:/{exit} found{print; exit}' \
            "$skill_dir/SKILL.md" 2>/dev/null | sed 's/^[[:space:]]*//' | sed 's/^|//')
        printf "  %-30s %s\n" "$name" "$desc"
    done
    echo ""
}

install_skill() {
    local skill_name="$1"
    local skills_dir="$2"
    local target_dir="$3"
    local update_only="$4"

    local src="$skills_dir/$skill_name"
    local dst="$target_dir/$skill_name"

    if [[ ! -d "$src" || ! -f "$src/SKILL.md" ]]; then
        log_error "skill 不存在：$skill_name"
        return 1
    fi

    if [[ "$update_only" == "true" && ! -d "$dst" ]]; then
        log_info "跳过（未安装）：$skill_name"
        return 0
    fi

    if [[ -d "$dst" ]]; then
        rm -rf "$dst"
        cp -r "$src" "$dst"
        log_success "已更新：$skill_name"
    else
        cp -r "$src" "$dst"
        log_success "已安装：$skill_name"
    fi
}

# ============================================================================
# 主流程
# ============================================================================

main() {
    local global=false
    local update_only=false
    local source_path=""
    local list_only=false
    local selected_skills=()

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -g|--global)   global=true; shift ;;
            -u|--update)   update_only=true; shift ;;
            -l|--list)     list_only=true; shift ;;
            -s|--source)   source_path="$2"; shift 2 ;;
            -h|--help)     usage; exit 0 ;;
            -*)            log_error "未知选项：$1"; usage; exit 1 ;;
            *)             selected_skills+=("$1"); shift ;;
        esac
    done

    # 确定 skills 源目录
    local skills_dir
    skills_dir=$(get_skills_source "$source_path")

    # 仅列出
    if [[ "$list_only" == "true" ]]; then
        list_available "$skills_dir"
        exit 0
    fi

    # 确定安装目标目录
    local target_dir
    if [[ "$global" == "true" ]]; then
        target_dir="$HOME/.claude/skills"
        log_info "安装目标：全局 ($target_dir)"
    else
        # 找项目根目录
        local project_root
        project_root=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
        target_dir="$project_root/.claude/skills"
        log_info "安装目标：项目 ($target_dir)"
    fi

    mkdir -p "$target_dir"

    # 确定要安装的 skill 列表
    local skills_to_install=()
    if [[ ${#selected_skills[@]} -gt 0 ]]; then
        skills_to_install=("${selected_skills[@]}")
    else
        # 安装所有
        for skill_dir in "$skills_dir"/*/; do
            local name
            name=$(basename "$skill_dir")
            [[ "$name" == *.sh ]] && continue
            [[ ! -f "$skill_dir/SKILL.md" ]] && continue
            skills_to_install+=("$name")
        done
    fi

    if [[ ${#skills_to_install[@]} -eq 0 ]]; then
        log_warn "没有找到可安装的 skill"
        exit 0
    fi

    echo ""
    local success=0
    local failed=0
    for skill in "${skills_to_install[@]}"; do
        if install_skill "$skill" "$skills_dir" "$target_dir" "$update_only"; then
            ((success++)) || true
        else
            ((failed++)) || true
        fi
    done

    echo ""
    log_info "完成：$success 个成功，$failed 个失败"
    echo ""
    echo "已安装的 skills："
    ls "$target_dir"
}

main "$@"
