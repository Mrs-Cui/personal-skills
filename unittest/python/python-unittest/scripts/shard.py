#!/usr/bin/env python3
"""
Python 源码分片工具 — AST-based Source Code Sharding

用 Python ast 模块精确解析源码，按类/函数分组，支持大文件自动拆分。
供 python-unittest 编排器调用，输出结构化 JSON 供 Writer Agent 消费。

4 种模式:
    --file path.py                              单文件分片
    --file path.py --functions "func,Class.m"   指定函数
    --dir path/                                 目录递归
    --diff "master..HEAD"                       Git diff 映射

用法:
    python shard.py --file message/handler/email.py
    python shard.py --file message/handler/email.py --functions "post_email,EmailHandler.send_email"
    python shard.py --dir message/handler/
    python shard.py --diff "master..HEAD"
"""
import argparse
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# --- 阈值配置 ---
THRESHOLD_FILE_DIR = 1000   # file/dir 模式：总行数超过此值触发分片
THRESHOLD_FUNC_DIFF = 800   # func/diff 模式：组内函数总行数超过此值触发拆分
GROUP_MAX_LINES_FILE = 800  # file/dir 模式：单组最大行数
GROUP_MAX_LINES_FUNC = 600  # func/diff 模式：单组最大行数

# --- 排除模式 ---
EXCLUDE_DIRS = {"__pycache__", ".git", ".svn", "node_modules", ".tox", ".pytest_cache",
                "test_auto_generate", "tests", ".eggs", "*.egg-info"}
EXCLUDE_FILES = {"__init__.py", "conftest.py", "setup.py"}


# ============================================================
# AST 解析
# ============================================================

def parse_file(filepath: str) -> Optional[ast.Module]:
    """解析 Python 文件为 AST，失败返回 None"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        return ast.parse(source, filename=filepath)
    except (SyntaxError, UnicodeDecodeError, FileNotFoundError) as e:
        print(f"警告: 无法解析 {filepath}: {e}", file=sys.stderr)
        return None


def count_lines(filepath: str) -> int:
    """文件总行数"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def extract_header(tree: ast.Module) -> Dict[str, int]:
    """提取文件头部（module docstring + imports + 模块级赋值），返回行号范围"""
    last_header_line = 0

    for node in ast.iter_child_nodes(tree):
        # docstring
        if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Constant, ast.Str)):
            last_header_line = max(last_header_line, node.end_lineno or node.lineno)
        # import / from import
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            last_header_line = max(last_header_line, node.end_lineno or node.lineno)
        # 模块级赋值（如 logger = ...）紧跟在 import 后面的
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            line = node.lineno
            # 只包含紧接在 header 后面的赋值（间隔 <= 3 行）
            if line <= last_header_line + 3:
                last_header_line = max(last_header_line, node.end_lineno or node.lineno)
            else:
                break
        else:
            # 遇到 class/function 定义，header 结束
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                break

    return {"start": 1, "end": max(last_header_line, 1)}


def extract_imports(tree: ast.Module) -> List[Dict[str, str]]:
    """提取所有 import 语句"""
    imports = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "name": alias.asname or alias.name,
                    "source": alias.name,
                    "kind": "import",
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    imports.append({
                        "name": "*",
                        "source": module,
                        "kind": "from_star",
                    })
                else:
                    imports.append({
                        "name": alias.asname or alias.name,
                        "source": module,
                        "kind": "from",
                    })
    return imports


def _collect_used_names(node: ast.AST, import_names: Set[str]) -> List[str]:
    """收集 AST 节点内引用的导入名称（与 import_names 取交集）"""
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            if child.id in import_names:
                names.add(child.id)
        elif isinstance(child, ast.Attribute):
            val = child
            while isinstance(val, ast.Attribute):
                val = val.value
            if isinstance(val, ast.Name) and val.id in import_names:
                names.add(val.id)
    return sorted(names)


def _get_decorators(node) -> List[str]:
    """提取装饰器名"""
    decorators = []
    for d in node.decorator_list:
        if isinstance(d, ast.Name):
            decorators.append(d.id)
        elif isinstance(d, ast.Attribute):
            decorators.append(ast.dump(d))  # 简化处理
        elif isinstance(d, ast.Call):
            if isinstance(d.func, ast.Name):
                decorators.append(d.func.id)
            elif isinstance(d.func, ast.Attribute):
                decorators.append(d.func.attr)
    return decorators


def _func_start_line(node) -> int:
    """函数的起始行（含装饰器）"""
    if node.decorator_list:
        return node.decorator_list[0].lineno
    return node.lineno


def extract_functions_and_classes(tree: ast.Module) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    从 AST 提取：
    1. 模块级函数列表
    2. 类定义列表（含方法）
    3. 模块级类型（非含方法的类，如 Exception 子类、dataclass 等）
    """
    module_functions = []
    classes = []
    related_types = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            module_functions.append({
                "name": node.name,
                "kind": "function",
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "start": _func_start_line(node),
                "end": node.end_lineno,
                "decorators": _get_decorators(node),
            })
        elif isinstance(node, ast.ClassDef):
            methods = []
            has_methods = False
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    has_methods = True
                    kind = "method"
                    decs = _get_decorators(item)
                    if "classmethod" in decs:
                        kind = "classmethod"
                    elif "staticmethod" in decs:
                        kind = "staticmethod"
                    elif "property" in decs:
                        kind = "property"

                    methods.append({
                        "name": item.name,
                        "kind": kind,
                        "is_async": isinstance(item, ast.AsyncFunctionDef),
                        "start": _func_start_line(item),
                        "end": item.end_lineno,
                        "decorators": decs,
                    })

            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(f"{ast.dump(base)}")

            class_info = {
                "name": node.name,
                "bases": bases,
                "start": _func_start_line(node),
                "end": node.end_lineno,
                "methods": methods,
            }

            if has_methods:
                classes.append(class_info)
            else:
                # 无方法的类当作 related_type
                related_types.append({
                    "name": node.name,
                    "kind": "class",
                    "start": _func_start_line(node),
                    "end": node.end_lineno,
                })

    return module_functions, classes, related_types


# ============================================================
# 分组与拆分
# ============================================================

def _func_lines(func: Dict) -> int:
    """单个函数的行数"""
    return func["end"] - func["start"] + 1


def split_large_group(group: Dict, max_lines: int) -> List[Dict]:
    """
    如果组内函数总行数超过 max_lines，拆分为多个子组。
    保持源码顺序。
    """
    functions = group["functions"]
    total = sum(_func_lines(f) for f in functions)

    if total <= max_lines:
        group["total_func_lines"] = total
        return [group]

    sub_groups = []
    current_funcs = []
    current_lines = 0
    group_idx = 1
    base_name = group["name"]

    for func in functions:
        fl = _func_lines(func)
        # 单个函数超过阈值 → 独立成组
        if fl > max_lines:
            if current_funcs:
                sub_groups.append(_build_sub_group(base_name, group_idx, current_funcs, current_lines, group))
                group_idx += 1
                current_funcs = []
                current_lines = 0
            sub_groups.append(_build_sub_group(base_name, group_idx, [func], fl, group))
            group_idx += 1
            continue

        if current_lines + fl > max_lines and current_funcs:
            sub_groups.append(_build_sub_group(base_name, group_idx, current_funcs, current_lines, group))
            group_idx += 1
            current_funcs = []
            current_lines = 0

        current_funcs.append(func)
        current_lines += fl

    if current_funcs:
        sub_groups.append(_build_sub_group(base_name, group_idx, current_funcs, current_lines, group))

    return sub_groups


def _build_sub_group(base_name: str, idx: int, funcs: List[Dict], total_lines: int, parent: Dict) -> Dict:
    """构建子组"""
    result = {
        "name": f"{base_name}_group{idx}",
        "functions": funcs,
        "total_func_lines": total_lines,
    }
    # 继承 class_def 和 related_types
    if "class_def" in parent:
        result["class_def"] = parent["class_def"]
    if "related_types" in parent:
        result["related_types"] = parent["related_types"]
    return result


def build_groups(module_functions: List[Dict], classes: List[Dict],
                 related_types: List[Dict], max_lines: int,
                 filter_names: Optional[Set[str]] = None) -> List[Dict]:
    """
    构建分组：按类分组 + 模块级函数组。
    filter_names: 如果指定，只包含这些函数/方法。
    """
    groups = []

    # 模块级函数
    if module_functions:
        filtered = module_functions
        if filter_names:
            filtered = [f for f in module_functions if f["name"] in filter_names]
        if filtered:
            total = sum(_func_lines(f) for f in filtered)
            group = {
                "name": "_module_",
                "functions": filtered,
                "related_types": related_types,
                "total_func_lines": total,
            }
            groups.extend(split_large_group(group, max_lines))

    # 按类分组
    for cls in classes:
        methods = cls["methods"]
        if filter_names:
            methods = [m for m in methods
                       if m["name"] in filter_names
                       or f"{cls['name']}.{m['name']}" in filter_names]
        if not methods:
            continue

        total = sum(_func_lines(m) for m in methods)
        class_def = {
            "name": cls["name"],
            "bases": cls["bases"],
            "start": cls["start"],
            "end": cls["end"],
        }
        group = {
            "name": cls["name"],
            "functions": methods,
            "class_def": class_def,
            "related_types": related_types,
            "total_func_lines": total,
        }
        groups.extend(split_large_group(group, max_lines))

    return groups


# ============================================================
# 单文件处理
# ============================================================

def _enrich_groups_with_used_names(groups: List[Dict], tree: ast.Module,
                                    import_names: Set[str]) -> None:
    """为每个 group 的 functions 计算 used_names（引用的导入名称）"""
    # 建立函数名 → AST 节点的映射
    func_nodes: Dict[str, ast.AST] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_nodes[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_nodes[item.name] = item
                    func_nodes[f"{node.name}.{item.name}"] = item

    for group in groups:
        group_used = set()
        for func in group["functions"]:
            fname = func["name"]
            node = func_nodes.get(fname)
            if node:
                names = _collect_used_names(node, import_names)
                group_used.update(names)
        group["used_names"] = sorted(group_used)


def process_single_file(filepath: str, max_lines: int,
                        filter_names: Optional[Set[str]] = None) -> Optional[Dict]:
    """处理单个文件，返回文件级 JSON"""
    tree = parse_file(filepath)
    if tree is None:
        return None

    total_lines = count_lines(filepath)
    header = extract_header(tree)
    imports = extract_imports(tree)
    module_functions, classes, related_types = extract_functions_and_classes(tree)

    groups = build_groups(module_functions, classes, related_types, max_lines, filter_names)

    if not groups:
        return None

    # 为每个 group 计算 used_names
    import_names = {imp["name"] for imp in imports}
    _enrich_groups_with_used_names(groups, tree, import_names)

    # 判断是否需要分片
    needs_sharding = total_lines > THRESHOLD_FILE_DIR

    return {
        "file": filepath,
        "total_lines": total_lines,
        "needs_sharding": needs_sharding,
        "header": header,
        "groups": groups,
        "module_imports": {
            "start": header["start"],
            "end": header["end"],
            "imports": imports,
        },
    }


# ============================================================
# 4 种模式
# ============================================================

def mode_file(filepath: str, functions: Optional[str] = None) -> Dict:
    """file 模式：单文件分片"""
    filter_names = None
    if functions:
        max_lines = GROUP_MAX_LINES_FUNC
    else:
        max_lines = GROUP_MAX_LINES_FILE

    if functions:
        filter_names = set(f.strip() for f in functions.split(",") if f.strip())

    result = process_single_file(filepath, max_lines, filter_names)
    mode_name = "func" if functions else "file"

    if result is None:
        return {"mode": mode_name, "files": [], "error": f"无法解析文件: {filepath}"}

    # func 模式用不同的 needs_sharding 阈值
    if functions:
        total_func_lines = sum(g["total_func_lines"] for g in result["groups"])
        result["needs_sharding"] = total_func_lines > THRESHOLD_FUNC_DIFF

    return {"mode": mode_name, "files": [result]}


def mode_dir(dirpath: str) -> Dict:
    """dir 模式：递归目录"""
    files = []
    dirpath = os.path.normpath(dirpath)

    for root, dirs, filenames in os.walk(dirpath):
        # 排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]

        for fname in sorted(filenames):
            if not fname.endswith(".py"):
                continue
            if fname in EXCLUDE_FILES:
                continue
            if fname.startswith("test_"):
                continue

            fpath = os.path.join(root, fname)
            result = process_single_file(fpath, GROUP_MAX_LINES_FILE)
            if result:
                files.append(result)

    return {"mode": "dir", "files": files}


def mode_diff(diff_spec: str) -> Dict:
    """diff 模式：解析 git diff，映射变更到函数"""
    # 规范化 diff spec
    if ".." not in diff_spec:
        # 单个 commit → 转为 range
        diff_spec = f"{diff_spec}^..{diff_spec}"

    # 获取变更文件列表
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", diff_spec, "--", "*.py"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        return {"mode": "diff", "files": [], "error": f"git diff 失败: {e.stderr}"}

    changed_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    # 过滤掉测试文件和 __init__.py
    changed_files = [f for f in changed_files
                     if not os.path.basename(f).startswith("test_")
                     and os.path.basename(f) != "__init__.py"
                     and f.endswith(".py")]

    if not changed_files:
        return {"mode": "diff", "files": [], "message": "没有检测到 Python 源码变更"}

    files = []
    for fpath in changed_files:
        if not os.path.exists(fpath):
            continue

        # 获取变更函数
        touched = _map_hunks_to_functions(fpath, diff_spec)

        if not touched:
            continue

        file_result = process_single_file(fpath, GROUP_MAX_LINES_FUNC, touched)
        if file_result:
            file_result["changed_functions"] = sorted(touched)
            # diff 模式用 func 级阈值
            total_func_lines = sum(g["total_func_lines"] for g in file_result["groups"])
            file_result["needs_sharding"] = total_func_lines > THRESHOLD_FUNC_DIFF
            files.append(file_result)

    return {"mode": "diff", "files": files}


def _map_hunks_to_functions(filepath: str, diff_spec: str) -> Set[str]:
    """解析 diff hunk，映射到变更的函数名"""
    try:
        result = subprocess.run(
            ["git", "diff", "-U0", diff_spec, "--", filepath],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return set()

    # 解析 hunk 行号
    hunk_pattern = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
    hunks = []
    for match in hunk_pattern.finditer(result.stdout):
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) else 1
        if count == 0:
            continue
        hunks.append((start, start + count - 1))

    if not hunks:
        return set()

    # 解析文件 AST 获取所有函数
    tree = parse_file(filepath)
    if tree is None:
        return set()

    module_functions, classes, _ = extract_functions_and_classes(tree)
    touched = set()

    # 检查模块级函数
    for func in module_functions:
        for hunk_start, hunk_end in hunks:
            if func["start"] <= hunk_end and func["end"] >= hunk_start:
                touched.add(func["name"])
                break

    # 检查类方法
    for cls in classes:
        for method in cls["methods"]:
            for hunk_start, hunk_end in hunks:
                if method["start"] <= hunk_end and method["end"] >= hunk_start:
                    # 同时添加短名和全名
                    touched.add(method["name"])
                    touched.add(f"{cls['name']}.{method['name']}")
                    break

    return touched


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Python 源码分片工具 — 为单元测试生成提供结构化源码分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --file message/handler/email.py
  %(prog)s --file message/handler/email.py --functions "post_email,send_email"
  %(prog)s --dir message/handler/
  %(prog)s --diff "master..HEAD"
        """
    )
    parser.add_argument("--file", help="单文件模式：指定源文件路径")
    parser.add_argument("--functions", help="函数模式：逗号分隔的函数名（需配合 --file）")
    parser.add_argument("--dir", help="目录模式：递归扫描目录")
    parser.add_argument("--diff", help="Diff 模式：git diff spec（如 master..HEAD）")
    parser.add_argument("--pretty", action="store_true", help="格式化 JSON 输出")

    args = parser.parse_args()

    # 验证参数
    mode_count = sum(1 for x in [args.file, args.dir, args.diff] if x)
    if mode_count == 0:
        parser.error("必须指定 --file、--dir 或 --diff 之一")
    if mode_count > 1 and not (args.file and args.functions):
        parser.error("--file、--dir、--diff 不能同时使用")

    if args.functions and not args.file:
        parser.error("--functions 必须配合 --file 使用")

    # 执行
    if args.file:
        if not os.path.exists(args.file):
            print(json.dumps({"error": f"文件不存在: {args.file}"}))
            sys.exit(1)
        output = mode_file(args.file, args.functions)
    elif args.dir:
        if not os.path.isdir(args.dir):
            print(json.dumps({"error": f"目录不存在: {args.dir}"}))
            sys.exit(1)
        output = mode_dir(args.dir)
    else:
        output = mode_diff(args.diff)

    # 输出
    indent = 2 if args.pretty else None
    print(json.dumps(output, ensure_ascii=False, indent=indent))


if __name__ == "__main__":
    main()
