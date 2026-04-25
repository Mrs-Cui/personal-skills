#!/usr/bin/env python3
"""
shard.py — Go 源文件分片处理工具

支持四种输入模式，将 Go 源文件按函数和 receiver 自动分组，输出 JSON 格式的分片结果，
供主控 Agent 根据行号范围读取源码并组装分组上下文传给 Writer Agent。

用法:
    # 文件模式：对整个文件的所有函数做分片
    python3 shard.py --file path/to/file.go

    # 函数模式：只对指定函数做分片（逗号分隔函数名）
    python3 shard.py --file path/to/file.go --functions "GetConfig,Search"

    # 目录模式：递归扫描目录下所有 .go 文件（排除 _test.go、wire_gen.go）
    python3 shard.py --dir path/to/directory/

    # Git diff 模式：提取 diff 涉及的变更函数，自动映射并分组
    python3 shard.py --diff "main..HEAD"
    python3 shard.py --diff "HEAD~1"

    # 自定义分组行数上限（同时影响 needs_sharding 判断阈值）
    python3 shard.py --file path/to/file.go --max-lines 600

输出:
    JSON 格式写入 stdout，统一结构：
    {
      "mode": "file" | "func" | "dir" | "diff",
      "files": [ { "file": "...", "needs_sharding": bool, "header": {...}, "groups": [...] } ]
    }
    行号均为 1-indexed，与编辑器和 Read 工具行号一致。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# 正则表达式定义
# ---------------------------------------------------------------------------

# 匹配顶层函数定义起始行: func Foo(...) 或 func (r *T) Foo(...)
RE_FUNC = re.compile(r"^func\s")

# 从函数定义行提取 receiver 和函数名
# 支持: func Name(, func (v Type) Name(, func (v *Type) Name(, func (*Type) Name(
# 支持泛型: func Name[T any](, func (v *Type[T]) Name(
RE_FUNC_DETAIL = re.compile(
    r"^func\s+"
    r"(?:\(([^)]*)\)\s*)?"       # 可选的 receiver 部分，捕获组 1
    r"(\w+)"                      # 函数名，捕获组 2
)

# 匹配顶层 type 定义起始行
RE_TYPE = re.compile(r"^type\s")

# 从 type 定义行提取类型名和类别 (struct/interface/其他)
RE_TYPE_DETAIL = re.compile(
    r"^type\s+"
    r"(\w+)"                      # 类型名，捕获组 1
    r"(?:\[.*?\])?\s*"            # 可选的泛型参数
    r"(\w+)?"                     # 可选的类别关键字 (struct/interface)，捕获组 2
)

# 匹配 type 分组块: type (
RE_TYPE_BLOCK = re.compile(r"^type\s*\(")

# 匹配 import 块: import (
RE_IMPORT_BLOCK = re.compile(r"^import\s*\(")

# 匹配单行 import: import "fmt"
RE_IMPORT_LINE = re.compile(r'^import\s+"')

# 匹配 package 声明
RE_PACKAGE = re.compile(r"^package\s+\w+")

# 匹配顶层声明起始（用于判断定义边界）
RE_TOP_LEVEL = re.compile(r"^(func|type|var|const)\s")

# Go 内置类型和常见标准库类型，不需要作为关联类型
GO_BUILTIN_TYPES = frozenset({
    "bool", "byte", "complex64", "complex128",
    "error", "float32", "float64",
    "int", "int8", "int16", "int32", "int64",
    "rune", "string",
    "uint", "uint8", "uint16", "uint32", "uint64", "uintptr",
    "any", "comparable",
})


# ---------------------------------------------------------------------------
# 文件解析
# ---------------------------------------------------------------------------

def parse_file(filepath: str) -> list[str]:
    """读取文件，返回行列表（每行不含换行符）。"""
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f.readlines()]


def find_block_end(lines: list[str], start: int, open_char: str = "{", close_char: str = "}") -> int:
    """
    从 start 行（0-indexed）开始，用字符计数法找到配对的结束行。

    处理以下情况：
    - // 行注释：忽略该行剩余内容
    - /* */ 块注释：忽略其中内容（支持跨行）
    - "..." 双引号字符串：忽略其中内容
    - `...` 反引号字符串：忽略其中内容（支持跨行）
    - '...' 字符字面量：忽略其中内容

    返回结束行号（0-indexed）。如果没找到配对，返回 start。
    """
    depth = 0
    found_open = False
    in_block_comment = False    # 是否在 /* */ 块注释中
    in_raw_string = False       # 是否在 `` 反引号字符串中

    for i in range(start, len(lines)):
        line = lines[i]
        j = 0
        while j < len(line):
            c = line[j]

            # --- 处理跨行状态 ---

            # 在块注释中：寻找 */
            if in_block_comment:
                if c == "*" and j + 1 < len(line) and line[j + 1] == "/":
                    in_block_comment = False
                    j += 2
                else:
                    j += 1
                continue

            # 在反引号字符串中：寻找 `
            if in_raw_string:
                if c == "`":
                    in_raw_string = False
                j += 1
                continue

            # --- 常规状态 ---

            # 行注释 //：跳过本行剩余内容
            if c == "/" and j + 1 < len(line) and line[j + 1] == "/":
                break

            # 块注释开始 /*
            if c == "/" and j + 1 < len(line) and line[j + 1] == "*":
                in_block_comment = True
                j += 2
                continue

            # 双引号字符串 "..."
            if c == '"':
                j += 1
                while j < len(line):
                    if line[j] == "\\":
                        j += 2  # 跳过转义字符
                        continue
                    if line[j] == '"':
                        j += 1
                        break
                    j += 1
                continue

            # 反引号字符串 `...`（可跨行）
            if c == "`":
                in_raw_string = True
                j += 1
                continue

            # 字符字面量 '...'
            if c == "'":
                j += 1
                while j < len(line):
                    if line[j] == "\\":
                        j += 2
                        continue
                    if line[j] == "'":
                        j += 1
                        break
                    j += 1
                continue

            # 计数目标字符
            if c == open_char:
                depth += 1
                found_open = True
            elif c == close_char:
                depth -= 1

            j += 1

        # 找到配对：depth 回到 0
        if found_open and depth == 0:
            return i

    return start


def find_header_end(lines: list[str]) -> int:
    """
    找到文件头部（package 声明 + import 块）的结束行。

    扫描策略：
    1. 跳过 package 行
    2. 找到 import 块或单行 import，确定其结束位置
    3. 返回最后一个 import 相关行的行号（0-indexed）

    如果没有 import，返回 package 行号。
    """
    last_header_line = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 跳过空行和注释
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue

        if RE_PACKAGE.match(line):
            last_header_line = i
            continue

        # import 块: import (...)
        if RE_IMPORT_BLOCK.match(line):
            end = find_block_end(lines, i, "(", ")")
            last_header_line = end
            continue

        # 单行 import: import "fmt"
        if RE_IMPORT_LINE.match(line):
            last_header_line = i
            continue

        # 遇到非 import/package 的顶层声明，头部结束
        if RE_TOP_LEVEL.match(line):
            break

    return last_header_line


def extract_functions(lines: list[str]) -> list[dict]:
    """
    提取文件中所有顶层函数定义。

    返回列表，每个元素:
    {
        "name":     "FuncName",
        "receiver": "*TypeName" 或 "" (包级别函数),
        "start":    起始行号 (1-indexed),
        "end":      结束行号 (1-indexed),
        "signature": 函数签名行原文（用于关联类型匹配）
    }
    """
    functions = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if not RE_FUNC.match(line):
            i += 1
            continue

        m = RE_FUNC_DETAIL.match(line)
        if not m:
            i += 1
            continue

        raw_receiver = (m.group(1) or "").strip()
        func_name = m.group(2)

        # 规范化 receiver：去掉变量名，只保留类型
        receiver = _normalize_receiver(raw_receiver)

        # 收集完整的函数签名（可能跨多行直到 { 或下一个顶层声明）
        sig_lines = [line]
        has_body = "{" in _strip_strings_and_comments(line)

        if not has_body:
            # 签名可能跨行，向下搜索 { 或下一个顶层声明
            for k in range(i + 1, min(i + 30, len(lines))):
                stripped_k = _strip_strings_and_comments(lines[k])
                sig_lines.append(lines[k])
                if "{" in stripped_k:
                    has_body = True
                    break
                # 遇到下一个顶层声明 → 无函数体
                if RE_TOP_LEVEL.match(lines[k]):
                    sig_lines.pop()  # 不属于当前函数
                    break

        # 确定函数结束行
        if has_body:
            end = find_block_end(lines, i, "{", "}")
        else:
            # 无函数体（CGo/汇编），结束行 = 最后一行签名
            end = i + len(sig_lines) - 1

        signature = " ".join(l.strip() for l in sig_lines)

        functions.append({
            "name": func_name,
            "receiver": receiver,
            "start": i + 1,       # 转为 1-indexed
            "end": end + 1,       # 转为 1-indexed
            "signature": signature,
        })

        # 跳到函数结束行之后继续扫描
        i = end + 1

    return functions


def extract_types(lines: list[str]) -> list[dict]:
    """
    提取文件中所有顶层类型定义。

    返回列表，每个元素:
    {
        "name": "TypeName",
        "kind": "struct" | "interface" | "alias" | "other",
        "start": 起始行号 (1-indexed),
        "end":   结束行号 (1-indexed)
    }

    type block（type ( ... )）会被展开为多个独立的类型定义。
    """
    types = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if not RE_TYPE.match(line):
            i += 1
            continue

        # type block: type (
        if RE_TYPE_BLOCK.match(line):
            block_end = find_block_end(lines, i, "(", ")")
            # 解析 block 内部的每个类型定义
            types.extend(_parse_type_block(lines, i + 1, block_end))
            i = block_end + 1
            continue

        # 单个 type 定义
        m = RE_TYPE_DETAIL.match(line)
        if not m:
            i += 1
            continue

        type_name = m.group(1)
        kind_keyword = m.group(2) or ""

        if kind_keyword in ("struct", "interface"):
            kind = kind_keyword
            # 有 {} body，找结束行（find_block_end 会从 start 行开始扫描 { 的位置，
            # 无论 { 在当前行还是下一行都能正确处理）
            end = find_block_end(lines, i, "{", "}")
        elif "=" in line[len("type ") + len(type_name):]:
            kind = "alias"
            end = i
        else:
            kind = "other"
            end = i

        types.append({
            "name": type_name,
            "kind": kind,
            "start": i + 1,     # 1-indexed
            "end": end + 1,     # 1-indexed
        })

        i = end + 1

    return types


# ---------------------------------------------------------------------------
# 分组和拆分
# ---------------------------------------------------------------------------

def group_by_receiver(
    functions: list[dict],
    filter_names: Optional[set[str]] = None,
) -> dict[str, list[dict]]:
    """
    按 receiver 对函数进行分组。

    Args:
        functions:    extract_functions() 的输出
        filter_names: 可选，只保留名字在此集合中的函数（diff 模式用）

    Returns:
        dict, key 为 receiver 类型（包级别函数 key 为 "_pkg_"），
        value 为该 receiver 下的函数列表（保持文件中的出现顺序）。
    """
    groups: dict[str, list[dict]] = {}

    for func in functions:
        if filter_names and func["name"] not in filter_names:
            continue

        key = func["receiver"] if func["receiver"] else "_pkg_"

        if key not in groups:
            groups[key] = []
        groups[key].append(func)

    return groups


def split_large_groups(
    groups: dict[str, list[dict]],
    max_lines: int,
) -> list[dict]:
    """
    将超过 max_lines 的分组拆分为多个子组。

    拆分规则：
    1. 按函数在文件中的出现顺序，依次累加每个函数的行数
    2. 当累计行数超过 max_lines 时，开启新的子组
    3. 单个函数超过 max_lines 的，独立成一个子组

    Args:
        groups:    group_by_receiver() 的输出
        max_lines: 单组行数上限

    Returns:
        列表，每个元素:
        {
            "name":      分组名称（如 "_pkg_"、"*OrderSrv_group1"）,
            "receiver":  receiver 类型,
            "functions": 该组函数列表
        }
    """
    result = []

    for receiver_key, funcs in groups.items():
        total = sum(_func_lines(f) for f in funcs)

        # 不需要拆分
        if total <= max_lines:
            result.append({
                "name": receiver_key,
                "receiver": receiver_key if receiver_key != "_pkg_" else "",
                "functions": funcs,
            })
            continue

        # 需要拆分为多个子组
        sub_groups: list[list[dict]] = []
        current: list[dict] = []
        current_lines = 0

        for func in funcs:
            fl = _func_lines(func)

            # 单个函数就超过上限，独立成一组
            if fl > max_lines:
                if current:
                    sub_groups.append(current)
                    current = []
                    current_lines = 0
                sub_groups.append([func])
                continue

            # 加入当前组会超限，先保存当前组
            if current_lines + fl > max_lines and current:
                sub_groups.append(current)
                current = []
                current_lines = 0

            current.append(func)
            current_lines += fl

        if current:
            sub_groups.append(current)

        # 命名子组：{receiver}_group{N}
        for idx, sg in enumerate(sub_groups, 1):
            name = f"{receiver_key}_group{idx}" if len(sub_groups) > 1 else receiver_key
            result.append({
                "name": name,
                "receiver": receiver_key if receiver_key != "_pkg_" else "",
                "functions": sg,
            })

    return result


# ---------------------------------------------------------------------------
# 关联类型匹配
# ---------------------------------------------------------------------------

def find_receiver_type(
    receiver: str,
    all_types: list[dict],
) -> Optional[dict]:
    """
    根据 receiver 类型名，在类型列表中找到对应的 struct 定义。

    Args:
        receiver: 规范化后的 receiver（如 "*OrderSrv"），包级别函数传 ""
        all_types: extract_types() 的输出

    Returns:
        匹配的类型 dict，或 None。
    """
    if not receiver:
        return None

    # 去掉 * 前缀得到纯类型名
    type_name = receiver.lstrip("*")

    for t in all_types:
        if t["name"] == type_name and t["kind"] == "struct":
            return t

    return None


def find_interface_type(
    receiver: str,
    all_types: list[dict],
) -> Optional[dict]:
    """
    根据 receiver 类型名，查找关联的 interface 定义。

    命名约定：以 "I" 为前缀的同名 interface，如 OrderSrv → IOrderSrv。

    Args:
        receiver: 规范化后的 receiver
        all_types: extract_types() 的输出

    Returns:
        匹配的 interface 类型 dict，或 None。
    """
    if not receiver:
        return None

    type_name = receiver.lstrip("*")
    iface_name = "I" + type_name

    for t in all_types:
        if t["name"] == iface_name and t["kind"] == "interface":
            return t

    return None


def find_related_types(
    group_funcs: list[dict],
    all_types: list[dict],
    exclude_names: set[str],
) -> list[dict]:
    """
    扫描分组中所有函数的签名，找出引用的自定义类型定义。

    策略：
    1. 从函数签名中提取所有大写字母开头的标识符（Go 导出类型）
    2. 和小写字母开头但在 type 列表中存在的标识符（非导出类型）
    3. 排除 Go 内置类型和标准库带点号的类型（如 context.Context）
    4. 排除已作为 receiver_type / interface_type 包含的类型
    5. 在 all_types 中查找匹配项

    Args:
        group_funcs:   该组的函数列表
        all_types:     extract_types() 的输出
        exclude_names: 已包含的类型名集合，需排除

    Returns:
        匹配到的关联类型列表（去重）。
    """
    # 收集所有函数签名中出现的标识符
    all_identifiers: set[str] = set()
    # 匹配 Go 标识符（字母或下划线开头）
    re_ident = re.compile(r"\b([A-Za-z_]\w*)\b")

    type_name_set = {t["name"] for t in all_types}

    for func in group_funcs:
        sig = func.get("signature", "")
        for ident in re_ident.findall(sig):
            # 排除 Go 内置类型
            if ident in GO_BUILTIN_TYPES:
                continue
            # 排除 Go 关键字
            if ident in ("func", "type", "struct", "interface", "map",
                         "chan", "return", "if", "else", "for", "range",
                         "switch", "case", "default", "select", "go",
                         "defer", "var", "const", "package", "import",
                         "break", "continue", "fallthrough", "goto"):
                continue
            # 排除已包含的类型
            if ident in exclude_names:
                continue
            # 只保留在 type 列表中存在的标识符
            if ident in type_name_set:
                all_identifiers.add(ident)

    # 在 all_types 中查找匹配项
    related = []
    seen = set()
    for t in all_types:
        if t["name"] in all_identifiers and t["name"] not in seen:
            related.append(t)
            seen.add(t["name"])

    return related


# ---------------------------------------------------------------------------
# 输出组装
# ---------------------------------------------------------------------------

def build_output(
    filepath: str,
    lines: list[str],
    header_end: int,
    split_groups: list[dict],
    all_types: list[dict],
) -> dict:
    """
    组装最终 JSON 输出。

    对每个分组，确定其需要的：
    - header 行号范围
    - receiver 对应的 struct 定义行号范围
    - 关联的 interface 定义行号范围
    - 函数签名中引用的其他自定义类型行号范围
    - 函数源码行号范围

    行号均为 1-indexed。

    Args:
        filepath:     源文件路径
        lines:        文件行列表
        header_end:   header 结束行（0-indexed）
        split_groups: split_large_groups() 的输出
        all_types:    extract_types() 的输出

    Returns:
        完整的 JSON 输出 dict。
    """
    output_groups = []

    for group in split_groups:
        receiver = group["receiver"]
        funcs = group["functions"]

        # 查找 receiver 对应的 struct 和 interface
        recv_type = find_receiver_type(receiver, all_types)
        iface_type = find_interface_type(receiver, all_types)

        # 已包含的类型名（排除用）
        exclude_names: set[str] = set()
        if recv_type:
            exclude_names.add(recv_type["name"])
        if iface_type:
            exclude_names.add(iface_type["name"])

        # 查找关联类型
        related = find_related_types(funcs, all_types, exclude_names)

        # 计算该组函数总行数
        total_func_lines = sum(_func_lines(f) for f in funcs)

        # 构建函数列表（输出时去掉 signature 字段，保持输出简洁）
        output_funcs = [
            {
                "name": f["name"],
                "receiver": f["receiver"],
                "start": f["start"],
                "end": f["end"],
            }
            for f in funcs
        ]

        # 构建类型引用（只输出行号范围，不含源码内容）
        def _type_ref(t: Optional[dict]) -> Optional[dict]:
            if t is None:
                return None
            return {
                "name": t["name"],
                "kind": t["kind"],
                "start": t["start"],
                "end": t["end"],
            }

        output_groups.append({
            "name": group["name"],
            "functions": output_funcs,
            "receiver_type": _type_ref(recv_type),
            "interface_type": _type_ref(iface_type),
            "related_types": [_type_ref(t) for t in related],
            "total_func_lines": total_func_lines,
        })

    return {
        "file": filepath,
        "total_lines": len(lines),
        "header": {
            "start": 1,
            "end": header_end + 1,  # 转为 1-indexed
        },
        "groups": output_groups,
    }


# ---------------------------------------------------------------------------
# 高层处理函数（四种模式的入口）
# ---------------------------------------------------------------------------

# needs_sharding 默认阈值
_THRESHOLD_FILE = 1000   # 文件/目录模式：文件总行数超过此值需要分片
_THRESHOLD_FUNC = 800    # 函数/diff 模式：涉及函数总行数超过此值需要分片

# 排除的文件名模式
_EXCLUDE_SUFFIXES = ("_test.go",)
_EXCLUDE_NAMES = ("wire_gen.go",)

# 排除的目录前缀（不需要生成单元测试的目录）
_EXCLUDE_DIR_PREFIXES = (
    "cmd/",
    "config/",
    "configs/",
    "testmocks/",
    "mock/",
    "mocks/",
    "scripts/",
    "docs/",
    "vendor/",
    "third_party/",
    "tools/",
    ".git/",
)


def process_single_file(
    filepath: str,
    max_lines: int,
    filter_names: Optional[set[str]] = None,
    threshold: Optional[int] = None,
) -> dict:
    """
    处理单个 Go 源文件，返回包含分组信息的 dict。

    这是所有模式共用的核心管线：
    parse → extract → group → split → build → 判断 needs_sharding

    Args:
        filepath:     Go 源文件路径
        max_lines:    分组拆分行数上限
        filter_names: 可选，只保留指定函数名（函数/diff 模式用）
        threshold:    needs_sharding 判断阈值，None 时根据 filter_names 自动选择默认值

    Returns:
        单文件结果 dict，包含 file, total_lines, needs_sharding, header, groups 字段。
    """
    lines = parse_file(filepath)
    header_end = find_header_end(lines)
    all_functions = extract_functions(lines)
    all_types = extract_types(lines)

    groups = group_by_receiver(all_functions, filter_names)
    split_groups = split_large_groups(groups, max_lines)
    result = build_output(filepath, lines, header_end, split_groups, all_types)

    # 判断 needs_sharding
    if threshold is None:
        if filter_names:
            threshold = _THRESHOLD_FUNC
        else:
            threshold = _THRESHOLD_FILE

    if filter_names:
        # 函数/diff 模式：按涉及函数总行数判断
        total_func_lines = sum(
            g.get("total_func_lines", 0) for g in result["groups"]
        )
        result["needs_sharding"] = total_func_lines > threshold
    else:
        # 文件/目录模式：按文件总行数判断
        result["needs_sharding"] = result["total_lines"] > threshold

    return result


def process_directory(dirpath: str, max_lines: int, threshold: Optional[int] = None) -> list[dict]:
    """
    递归扫描目录下所有 Go 源文件，逐文件调用 process_single_file()。

    排除规则：
    - *_test.go 文件
    - wire_gen.go 文件
    - cmd/、config/、testmocks/、vendor/ 等非测试目录

    Args:
        dirpath:   目标目录路径
        max_lines: 分组拆分行数上限
        threshold: needs_sharding 阈值，None 时使用文件模式默认值

    Returns:
        文件结果列表，按文件路径排序。
    """
    go_files = []

    for root, _dirs, files in os.walk(dirpath):
        # 计算相对路径前缀，检查是否在排除目录中
        relroot = os.path.relpath(root, ".") + "/"
        if any(relroot.startswith(p) or ("/" + p) in relroot for p in _EXCLUDE_DIR_PREFIXES):
            continue
        for fname in files:
            if not fname.endswith(".go"):
                continue
            if any(fname.endswith(s) for s in _EXCLUDE_SUFFIXES):
                continue
            if fname in _EXCLUDE_NAMES:
                continue
            go_files.append(os.path.join(root, fname))

    # 按路径排序，确保输出确定性
    go_files.sort()

    results = []
    for fpath in go_files:
        try:
            result = process_single_file(fpath, max_lines, threshold=threshold)
            results.append(result)
        except Exception as e:
            # 单文件解析失败不中断整个目录，记录错误继续
            results.append({
                "file": fpath,
                "error": str(e),
            })

    return results


def process_diff(spec: str, max_lines: int, threshold: Optional[int] = None) -> list[dict]:
    """
    解析 Git diff，提取变更文件和变更函数，逐文件调用 process_single_file()。

    支持两种 spec 格式：
    - range 格式：如 "main..HEAD"、"HEAD~3..HEAD"
    - 单 commit 格式：如 "HEAD~1"、"abc1234"，自动转为 "{commit}^..{commit}"

    Args:
        spec:      Git diff 规范（range 或单 commit）
        max_lines: 分组拆分行数上限
        threshold: needs_sharding 阈值，None 时使用函数模式默认值

    Returns:
        文件结果列表，每个文件额外包含 changed_functions 字段。
    """
    # 规范化 spec：单 commit 转为 range
    if ".." not in spec:
        # 检查该 commit 是否有父 commit
        try:
            subprocess.run(
                ["git", "rev-parse", "--verify", f"{spec}^"],
                capture_output=True, check=True,
            )
            spec = f"{spec}^..{spec}"
        except subprocess.CalledProcessError:
            # 没有父 commit（初始 commit），使用 diff-tree --root 获取文件列表
            # 后续 _git_changed_files 和 _git_file_hunks 仍用 spec
            # 这里用特殊的 4b825dc 空树 hash 作为基准
            empty_tree = subprocess.run(
                ["git", "hash-object", "-t", "tree", "/dev/null"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            spec = f"{empty_tree}..{spec}"

    # 1. 获取变更文件列表
    changed_files = _git_changed_files(spec)
    if not changed_files:
        return []

    results = []
    for fpath in changed_files:
        # 2. 获取该文件的 diff hunk 行号范围
        hunks = _git_file_hunks(spec, fpath)
        if not hunks:
            continue

        # 3. 解析文件获取所有函数，映射 hunk 到函数
        try:
            lines = parse_file(fpath)
        except FileNotFoundError:
            # 文件可能在 diff 中被删除
            continue
        except Exception as e:
            results.append({"file": fpath, "error": str(e)})
            continue

        all_functions = extract_functions(lines)
        touched_names = _map_hunks_to_functions(hunks, all_functions)

        if not touched_names:
            continue

        # 4. 用 filter_names 调用 process_single_file
        try:
            result = process_single_file(
                fpath, max_lines,
                filter_names=touched_names,
                threshold=threshold,
            )
            result["changed_functions"] = sorted(touched_names)
            results.append(result)
        except Exception as e:
            results.append({"file": fpath, "error": str(e)})

    return results


# ---------------------------------------------------------------------------
# Git 辅助函数
# ---------------------------------------------------------------------------

def _git_changed_files(spec: str) -> list[str]:
    """
    调用 git diff --name-only 获取变更文件列表。

    过滤规则：
    - 只保留 .go 文件
    - 排除 _test.go、wire_gen.go

    Returns:
        排序后的变更文件路径列表。
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", spec],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(json.dumps({"error": f"git diff 失败: {e.stderr.strip()}"}), file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(json.dumps({"error": "git 命令未找到，请确保在 git 仓库中运行"}), file=sys.stderr)
        sys.exit(1)

    files = []
    for line in result.stdout.strip().splitlines():
        fname = line.strip()
        if not fname.endswith(".go"):
            continue
        # 排除不需要测试的目录
        if any(fname.startswith(p) for p in _EXCLUDE_DIR_PREFIXES):
            continue
        basename = os.path.basename(fname)
        if any(basename.endswith(s) for s in _EXCLUDE_SUFFIXES):
            continue
        if basename in _EXCLUDE_NAMES:
            continue
        files.append(fname)

    files.sort()
    return files


# 匹配 unified diff 的 hunk header: @@ -a,b +c,d @@
_RE_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _git_file_hunks(spec: str, filepath: str) -> list[tuple[int, int]]:
    """
    获取指定文件在 diff 中的 hunk 行号范围（新文件侧）。

    Args:
        spec:     Git diff 规范
        filepath: 文件路径

    Returns:
        列表，每个元素为 (start_line, end_line)，1-indexed，闭区间。
    """
    try:
        result = subprocess.run(
            ["git", "diff", "-U0", spec, "--", filepath],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return []

    hunks = []
    for line in result.stdout.splitlines():
        m = _RE_HUNK.match(line)
        if not m:
            continue
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) else 1
        if count == 0:
            continue
        # 转为 1-indexed 闭区间 [start, start + count - 1]
        end = start + count - 1
        hunks.append((start, end))

    return hunks


def _map_hunks_to_functions(
    hunks: list[tuple[int, int]],
    functions: list[dict],
) -> set[str]:
    """
    将 diff hunk 行号范围映射到函数名。

    判断标准：函数范围与 hunk 范围有交集（函数 start ≤ hunk end 且 函数 end ≥ hunk start）。

    Args:
        hunks:     hunk 行号范围列表 [(start, end), ...]，1-indexed
        functions: extract_functions() 的输出

    Returns:
        被 diff 触及的函数名集合。
    """
    touched = set()

    for func in functions:
        func_start = func["start"]
        func_end = func["end"]
        for hunk_start, hunk_end in hunks:
            if func_start <= hunk_end and func_end >= hunk_start:
                touched.add(func["name"])
                break  # 该函数已匹配，无需继续检查其他 hunk

    return touched


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _normalize_receiver(raw: str) -> str:
    """
    规范化 receiver：去掉变量名，只保留类型。

    示例:
        "s *OrderSrv"  → "*OrderSrv"
        "s OrderSrv"   → "OrderSrv"
        "*OrderSrv"    → "*OrderSrv"
        ""                 → ""
        "s *Stack[T]"      → "*Stack[T]"
    """
    if not raw:
        return ""

    raw = raw.strip()

    # 尝试匹配 "变量名 [*]类型" 模式
    m = re.match(r"\w+\s+(.*)", raw)
    if m:
        return m.group(1).strip()

    # 没有变量名，直接返回（如 "*Server"）
    return raw


def _strip_strings_and_comments(line: str) -> str:
    """
    去除行中的字符串字面量和注释内容，返回"有效代码"部分。

    用于安全地检测行内是否包含 { 或 } 等语法字符。
    仅处理单行，不处理跨行的块注释或反引号字符串。
    """
    result = []
    j = 0
    while j < len(line):
        c = line[j]

        # 行注释
        if c == "/" and j + 1 < len(line) and line[j + 1] == "/":
            break

        # 块注释
        if c == "/" and j + 1 < len(line) and line[j + 1] == "*":
            end = line.find("*/", j + 2)
            if end != -1:
                j = end + 2
            else:
                break  # 跨行块注释，本行剩余忽略
            continue

        # 双引号字符串
        if c == '"':
            j += 1
            while j < len(line):
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == '"':
                    j += 1
                    break
                j += 1
            continue

        # 反引号字符串
        if c == "`":
            j += 1
            while j < len(line) and line[j] != "`":
                j += 1
            if j < len(line):
                j += 1
            continue

        # 字符字面量
        if c == "'":
            j += 1
            while j < len(line):
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == "'":
                    j += 1
                    break
                j += 1
            continue

        result.append(c)
        j += 1

    return "".join(result)


def _func_lines(func: dict) -> int:
    """计算函数占用的行数。"""
    return func["end"] - func["start"] + 1


def _parse_type_block(lines: list[str], start: int, end: int) -> list[dict]:
    """
    解析 type ( ... ) 块内部的各个类型定义。

    Args:
        lines: 文件行列表
        start: 块内容起始行（type ( 的下一行，0-indexed）
        end:   块结束行（ ) 所在行，0-indexed）

    Returns:
        类型定义列表。
    """
    types = []
    i = start

    while i < end:
        line = lines[i].strip()

        # 跳过空行和注释
        if not line or line.startswith("//") or line.startswith("/*"):
            i += 1
            continue

        # 尝试匹配 type 定义（block 内部没有 "type" 关键字前缀）
        m = re.match(r"(\w+)\s+(?:=\s+)?(\w+)?", line)
        if not m:
            i += 1
            continue

        type_name = m.group(1)
        kind_keyword = m.group(2) or ""

        if kind_keyword in ("struct", "interface"):
            kind = kind_keyword
            block_end = find_block_end(lines, i, "{", "}")
            types.append({
                "name": type_name,
                "kind": kind,
                "start": i + 1,     # 1-indexed
                "end": block_end + 1,
            })
            i = block_end + 1
        else:
            # 单行定义或别名
            kind = "alias" if "=" in line else "other"
            types.append({
                "name": type_name,
                "kind": kind,
                "start": i + 1,
                "end": i + 1,
            })
            i += 1

    return types


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Go 源文件分片处理工具：支持文件/函数/目录/Git diff 四种模式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 文件模式 — 对整个文件分片
  python3 shard.py --file internal/services/custom.go

  # 函数模式 — 只对指定函数分片
  python3 shard.py --file internal/services/custom.go --functions "GetConfig,Search"

  # 目录模式 — 递归扫描目录下所有 .go 文件
  python3 shard.py --dir internal/services/custom/

  # Git diff 模式 — 提取 diff 涉及的变更函数
  python3 shard.py --diff "main..HEAD"
  python3 shard.py --diff "HEAD~1"

  # 自定义分组行数上限
  python3 shard.py --file internal/services/custom.go --max-lines 600
        """,
    )
    parser.add_argument(
        "--file",
        default=None,
        help="目标 Go 源文件路径（文件/函数模式）",
    )
    parser.add_argument(
        "--functions",
        default=None,
        help="逗号分隔的函数名列表（函数模式），只能与 --file 搭配使用",
    )
    parser.add_argument(
        "--dir",
        default=None,
        help="目标目录路径（目录模式），递归扫描所有 .go 文件",
    )
    parser.add_argument(
        "--diff",
        default=None,
        help="Git diff 规范（diff 模式），如 'main..HEAD' 或 'HEAD~1'",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=800,
        help="单个分组的最大行数，超过则拆分为子组（默认: 800）",
    )

    args = parser.parse_args()

    # --- 参数互斥校验 ---
    mode_count = sum(1 for x in [args.file, args.dir, args.diff] if x is not None)
    if mode_count == 0:
        parser.error("必须指定 --file、--dir 或 --diff 之一")
    if mode_count > 1:
        parser.error("--file、--dir、--diff 三者互斥，只能指定一个")
    if args.functions and not args.file:
        parser.error("--functions 只能与 --file 搭配使用")

    max_lines = args.max_lines

    # --- 文件/函数模式 ---
    if args.file:
        filter_names = None
        if args.functions:
            filter_names = set(
                name.strip() for name in args.functions.split(",") if name.strip()
            )
            mode = "func"
        else:
            mode = "file"

        try:
            file_result = process_single_file(
                args.file, max_lines, filter_names=filter_names,
            )
        except FileNotFoundError:
            print(json.dumps({"error": f"文件不存在: {args.file}"}), file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(json.dumps({"error": f"处理文件失败: {e}"}), file=sys.stderr)
            sys.exit(1)

        output = {
            "mode": mode,
            "files": [file_result],
        }

    # --- 目录模式 ---
    elif args.dir:
        if not os.path.isdir(args.dir):
            print(json.dumps({"error": f"目录不存在: {args.dir}"}), file=sys.stderr)
            sys.exit(1)

        file_results = process_directory(args.dir, max_lines)
        output = {
            "mode": "dir",
            "dir": args.dir,
            "files": file_results,
        }

    # --- Git diff 模式 ---
    elif args.diff:
        file_results = process_diff(args.diff, max_lines)
        output = {
            "mode": "diff",
            "diff_spec": args.diff,
            "files": file_results,
        }

    else:
        parser.error("必须指定 --file、--dir 或 --diff 之一")
        return  # unreachable, 但让类型检查器满意

    # 输出 JSON
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
