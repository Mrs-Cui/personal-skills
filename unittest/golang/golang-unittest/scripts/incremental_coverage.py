#!/usr/bin/env python3
"""
incremental_coverage.py — Git diff 增量覆盖率计算脚本

仅统计 diff 新增的可执行行的覆盖情况，输出 JSON 格式结果。

用法:
    python3 incremental_coverage.py \
        --diff-spec "master...HEAD" \
        --coverage-file coverage.out \
        --target 80 \
        --project-root .

算法:
    1. git diff {diff_spec} -U0 -- '*.go' 解析新增行（排除 _test.go/wire_gen.go/testmocks//mock_*）
    2. 读 go.mod 获取 module path，解析 coverage.out 映射到相对路径的逐行覆盖数据
    3. 交叉：diff 新增行 ∩ coverage 可执行行 → 已覆盖/未覆盖
    4. go tool cover -func=coverage.out 获取函数名+行号，与未覆盖增量行交叉 → uncovered_functions
    5. 输出 JSON，exit code 0=达标 1=不达标
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys


# ---------------------------------------------------------------------------
# Git diff 解析
# ---------------------------------------------------------------------------

# 匹配 unified diff hunk header: @@ -a,b +c,d @@
_RE_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

# 排除的文件模式
_EXCLUDE_PATTERNS = (
    "_test.go",
    "wire_gen.go",
)
_EXCLUDE_DIR_PREFIXES = (
    "testmocks/",
)
_EXCLUDE_BASENAME_PREFIXES = (
    "mock_",
)


def _should_exclude(filepath: str) -> bool:
    """判断文件是否应被排除。"""
    basename = os.path.basename(filepath)
    for suffix in _EXCLUDE_PATTERNS:
        if basename.endswith(suffix):
            return True
    for prefix in _EXCLUDE_BASENAME_PREFIXES:
        if basename.startswith(prefix):
            return True
    for dir_prefix in _EXCLUDE_DIR_PREFIXES:
        if dir_prefix in filepath:
            return True
    return False


def parse_diff_added_lines(diff_spec: str, project_root: str) -> dict[str, set[int]]:
    """
    解析 git diff，提取每个文件的新增行号。

    Returns:
        dict: {relative_file_path: {line_number, ...}}
    """
    try:
        result = subprocess.run(
            ["git", "diff", diff_spec, "-U0", "--", "*.go"],
            capture_output=True, text=True, check=True,
            cwd=project_root,
        )
    except subprocess.CalledProcessError as e:
        print(json.dumps({"error": f"git diff failed: {e.stderr.strip()}"}),
              file=sys.stderr)
        sys.exit(2)

    added_lines: dict[str, set[int]] = {}
    current_file: str | None = None

    for line in result.stdout.splitlines():
        # 新文件路径: +++ b/path/to/file.go
        if line.startswith("+++ b/"):
            filepath = line[6:]
            if _should_exclude(filepath):
                current_file = None
            else:
                current_file = filepath
            continue

        # hunk header
        if current_file and line.startswith("@@"):
            m = _RE_HUNK.match(line)
            if not m:
                continue
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) else 1
            if count == 0:
                continue
            for ln in range(start, start + count):
                added_lines.setdefault(current_file, set()).add(ln)

    return added_lines


# ---------------------------------------------------------------------------
# coverage.out 解析
# ---------------------------------------------------------------------------

# coverage.out 行格式: module/path/file.go:startLine.startCol,endLine.endCol numStmt count
_RE_COVERAGE = re.compile(
    r"^(.+):(\d+)\.\d+,(\d+)\.\d+\s+(\d+)\s+(\d+)$"
)


def read_module_path(project_root: str) -> str:
    """从 go.mod 读取 module path。"""
    gomod = os.path.join(project_root, "go.mod")
    try:
        with open(gomod, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("module "):
                    return line[len("module "):].strip()
    except FileNotFoundError:
        pass
    print(json.dumps({"error": f"go.mod not found in {project_root}"}),
          file=sys.stderr)
    sys.exit(2)
    return ""  # unreachable


def parse_coverage_file(coverage_path: str, module_path: str) -> dict[str, dict[int, bool]]:
    """
    解析 coverage.out，返回每个文件每行的覆盖状态。

    Returns:
        dict: {relative_file_path: {line_number: is_covered}}
        is_covered = True 表示该行被执行过（count > 0）
    """
    coverage: dict[str, dict[int, bool]] = {}

    try:
        with open(coverage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("mode:") or not line:
                    continue

                m = _RE_COVERAGE.match(line)
                if not m:
                    continue

                full_path = m.group(1)
                start_line = int(m.group(2))
                end_line = int(m.group(3))
                # num_stmt = int(m.group(4))  # not used directly
                count = int(m.group(5))

                # 将 module path 转为相对路径
                if full_path.startswith(module_path + "/"):
                    rel_path = full_path[len(module_path) + 1:]
                else:
                    rel_path = full_path

                if rel_path not in coverage:
                    coverage[rel_path] = {}

                is_covered = count > 0
                for ln in range(start_line, end_line + 1):
                    # 如果同一行被多个 coverage block 覆盖，只要有一个 count > 0 就算覆盖
                    if ln in coverage[rel_path]:
                        coverage[rel_path][ln] = coverage[rel_path][ln] or is_covered
                    else:
                        coverage[rel_path][ln] = is_covered

    except FileNotFoundError:
        print(json.dumps({"error": f"coverage file not found: {coverage_path}"}),
              file=sys.stderr)
        sys.exit(2)

    return coverage


# ---------------------------------------------------------------------------
# go tool cover -func 解析
# ---------------------------------------------------------------------------

# 输出格式: path/file.go:42:  FunctionName  85.7%
_RE_COVER_FUNC = re.compile(
    r"^(.+):(\d+):\s+(\S+)\s+[\d.]+%$"
)


def parse_cover_func(coverage_path: str, project_root: str, module_path: str) -> dict[str, list[dict]]:
    """
    运行 go tool cover -func 并解析输出，获取函数名和起始行号。

    Returns:
        dict: {relative_file_path: [{"function": name, "line": start_line}, ...]}
    """
    try:
        result = subprocess.run(
            ["go", "tool", "cover", f"-func={coverage_path}"],
            capture_output=True, text=True, check=True,
            cwd=project_root,
        )
    except subprocess.CalledProcessError as e:
        # 非致命错误，返回空
        print(f"Warning: go tool cover -func failed: {e.stderr.strip()}",
              file=sys.stderr)
        return {}

    func_map: dict[str, list[dict]] = {}

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("total:"):
            continue

        m = _RE_COVER_FUNC.match(line)
        if not m:
            continue

        full_path = m.group(1)
        start_line = int(m.group(2))
        func_name = m.group(3)

        # 转相对路径
        if full_path.startswith(module_path + "/"):
            rel_path = full_path[len(module_path) + 1:]
        else:
            rel_path = full_path

        func_map.setdefault(rel_path, []).append({
            "function": func_name,
            "line": start_line,
        })

    return func_map


# ---------------------------------------------------------------------------
# 增量覆盖率计算
# ---------------------------------------------------------------------------

def compute_incremental_coverage(
    added_lines: dict[str, set[int]],
    coverage: dict[str, dict[int, bool]],
    func_map: dict[str, list[dict]],
) -> dict:
    """
    计算增量覆盖率。

    交叉逻辑：
    - diff 新增行 ∩ coverage 可执行行 → executable_lines
    - executable_lines 中 count > 0 → covered_lines
    - executable_lines 中 count == 0 → uncovered_lines

    Returns:
        dict with files detail and uncovered_functions
    """
    files_detail: list[dict] = []
    total_added = 0
    total_executable = 0
    total_covered = 0
    total_uncovered = 0

    # 收集所有文件的未覆盖行，用于后续匹配函数
    all_uncovered: dict[str, set[int]] = {}

    for filepath, lines in sorted(added_lines.items()):
        file_cov = coverage.get(filepath, {})

        added_count = len(lines)
        executable_lines = set()
        covered_lines = set()
        uncovered_lines = set()

        for ln in lines:
            if ln in file_cov:
                executable_lines.add(ln)
                if file_cov[ln]:
                    covered_lines.add(ln)
                else:
                    uncovered_lines.add(ln)

        exec_count = len(executable_lines)
        cov_count = len(covered_lines)
        uncov_count = len(uncovered_lines)
        pct = round(cov_count / exec_count * 100, 2) if exec_count > 0 else 100.0

        files_detail.append({
            "file": filepath,
            "added_lines": added_count,
            "executable_lines": exec_count,
            "covered_lines": cov_count,
            "uncovered_lines": uncov_count,
            "coverage_percent": pct,
        })

        total_added += added_count
        total_executable += exec_count
        total_covered += cov_count
        total_uncovered += uncov_count

        if uncovered_lines:
            all_uncovered[filepath] = uncovered_lines

    total_pct = round(total_covered / total_executable * 100, 2) if total_executable > 0 else 100.0

    # 匹配未覆盖行到函数
    uncovered_functions = _match_uncovered_to_functions(all_uncovered, func_map)

    return {
        "summary": {
            "total_added_lines": total_added,
            "total_executable_lines": total_executable,
            "total_covered_lines": total_covered,
            "total_uncovered_lines": total_uncovered,
            "coverage_percent": total_pct,
        },
        "files": files_detail,
        "uncovered_functions": uncovered_functions,
    }


def _match_uncovered_to_functions(
    all_uncovered: dict[str, set[int]],
    func_map: dict[str, list[dict]],
) -> list[dict]:
    """
    将未覆盖的增量行匹配到函数。

    策略：对每个文件的未覆盖行，找到 go tool cover -func 输出中
    起始行号 <= 未覆盖行号的最近函数（函数按起始行号排序后二分查找）。
    """
    result: list[dict] = []

    for filepath, uncov_lines in sorted(all_uncovered.items()):
        funcs = func_map.get(filepath, [])
        if not funcs:
            # 没有函数信息，整体记录
            result.append({
                "file": filepath,
                "function": "(unknown)",
                "uncovered_incremental_lines": len(uncov_lines),
            })
            continue

        # 按起始行号排序
        funcs_sorted = sorted(funcs, key=lambda f: f["line"])
        func_starts = [f["line"] for f in funcs_sorted]

        # 统计每个函数的未覆盖行数
        func_uncov_count: dict[str, int] = {}

        for ln in uncov_lines:
            # 二分查找：找到 start_line <= ln 的最后一个函数
            lo, hi = 0, len(func_starts) - 1
            idx = -1
            while lo <= hi:
                mid = (lo + hi) // 2
                if func_starts[mid] <= ln:
                    idx = mid
                    lo = mid + 1
                else:
                    hi = mid - 1

            if idx >= 0:
                fname = funcs_sorted[idx]["function"]
                func_uncov_count[fname] = func_uncov_count.get(fname, 0) + 1

        for fname, count in sorted(func_uncov_count.items(), key=lambda x: -x[1]):
            result.append({
                "file": filepath,
                "function": fname,
                "uncovered_incremental_lines": count,
            })

    return result


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Git diff 增量覆盖率计算脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--diff-spec",
        required=True,
        help="Git diff 规范，如 'master...HEAD' 或 'main..HEAD'",
    )
    parser.add_argument(
        "--coverage-file",
        required=True,
        help="go test -coverprofile 生成的覆盖率文件路径",
    )
    parser.add_argument(
        "--target",
        type=float,
        default=80.0,
        help="覆盖率目标百分比（默认: 80）",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="项目根目录（默认: 当前目录）",
    )

    args = parser.parse_args()

    project_root = os.path.abspath(args.project_root)
    coverage_path = args.coverage_file
    if not os.path.isabs(coverage_path):
        coverage_path = os.path.join(project_root, coverage_path)

    # 1. 读取 module path
    module_path = read_module_path(project_root)

    # 2. 解析 git diff 新增行
    added_lines = parse_diff_added_lines(args.diff_spec, project_root)

    if not added_lines:
        output = {
            "diff_spec": args.diff_spec,
            "target": args.target,
            "pass": True,
            "summary": {
                "total_added_lines": 0,
                "total_executable_lines": 0,
                "total_covered_lines": 0,
                "total_uncovered_lines": 0,
                "coverage_percent": 100.0,
            },
            "files": [],
            "uncovered_functions": [],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        sys.exit(0)

    # 3. 解析 coverage.out
    coverage = parse_coverage_file(coverage_path, module_path)

    # 4. 解析 go tool cover -func
    func_map = parse_cover_func(coverage_path, project_root, module_path)

    # 5. 计算增量覆盖率
    result = compute_incremental_coverage(added_lines, coverage, func_map)

    # 6. 组装输出
    passed = result["summary"]["coverage_percent"] >= args.target

    output = {
        "diff_spec": args.diff_spec,
        "target": args.target,
        "pass": passed,
        **result,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
