#!/usr/bin/env python3
"""
detect_interface_deps.py — 检测 Go 源文件中的外部接口依赖

分析被测文件的 struct 字段和嵌入类型，识别来自外部包的接口依赖，
输出需要调用 ensure_mock_generate.sh 生成 mock 的接口文件列表。

用法:
    python3 detect_interface_deps.py --file path/to/file.go --struct CoreService
    python3 detect_interface_deps.py --file path/to/file.go  # 自动检测所有 struct

输出 JSON:
    {
      "struct": "CoreService",
      "interface_deps": [
        {
          "field_name": "UserService",
          "import_alias": "userv2",
          "import_path": "github.com/yourorg/yourproject/.../userv2",
          "type_name": "UserService",
          "is_embedded": true,
          "source_file": "internal/services/userv2/user_service.go"
        }
      ],
      "mock_generate_files": [
        "internal/services/userv2/user_service.go"
      ]
    }
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# 正则表达式
# ---------------------------------------------------------------------------

# 匹配 import 块
RE_IMPORT_BLOCK = re.compile(r"^import\s*\(")
# 匹配单行 import
RE_IMPORT_LINE = re.compile(r'^import\s+"([^"]+)"')
# 匹配 import 块内的行: 可选别名 + "path"
RE_IMPORT_ENTRY = re.compile(r'^\s*(\w+)?\s*"([^"]+)"')
# 匹配 struct 定义
RE_STRUCT_DEF = re.compile(r"^type\s+(\w+)\s+struct\s*\{")
# 匹配 package 声明
RE_PACKAGE = re.compile(r"^package\s+(\w+)")


def parse_file(filepath: str) -> list[str]:
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f.readlines()]


def find_block_end(lines: list[str], start: int) -> int:
    """
    从 start 行找到 {} 配对的结束行 (0-indexed)。

    正确处理以下情况，避免误匹配字符串/注释中的花括号：
    - // 行注释
    - /* */ 块注释（支持跨行）
    - "..." 双引号字符串（含转义）
    - `...` 反引号字符串（支持跨行，常见于 Go struct tag）
    - '...' 字符字面量
    """
    depth = 0
    found_open = False
    in_block_comment = False
    in_raw_string = False

    for i in range(start, len(lines)):
        line = lines[i]
        j = 0
        while j < len(line):
            c = line[j]

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

            # 行注释 //：跳过本行剩余
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
                        j += 2
                        continue
                    if line[j] == '"':
                        j += 1
                        break
                    j += 1
                continue

            # 反引号字符串 `...`（可跨行，Go struct tag 常用）
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

            # 计数花括号
            if c == "{":
                depth += 1
                found_open = True
            elif c == "}":
                depth -= 1

            j += 1

        if found_open and depth == 0:
            return i

    return start


def extract_imports(lines: list[str]) -> dict[str, str]:
    """
    提取 import，返回 {别名或包名最后一段: 完整导入路径}。
    """
    imports = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 单行 import
        m = RE_IMPORT_LINE.match(line)
        if m:
            path = m.group(1)
            alias = path.rsplit("/", 1)[-1]
            imports[alias] = path
            i += 1
            continue

        # import 块
        if RE_IMPORT_BLOCK.match(line):
            i += 1
            while i < len(lines):
                entry_line = lines[i].strip()
                if entry_line == ")":
                    break
                m2 = RE_IMPORT_ENTRY.match(lines[i])
                if m2:
                    alias = m2.group(1)
                    path = m2.group(2)
                    if not alias:
                        alias = path.rsplit("/", 1)[-1]
                    imports[alias] = path
                i += 1

        i += 1

    return imports


def extract_struct_fields(
    lines: list[str], struct_name: str
) -> Optional[list[dict]]:
    """
    提取指定 struct 的所有字段，返回字段列表。
    每个字段: {"name": str, "type_expr": str, "is_embedded": bool}
    """
    for i, line in enumerate(lines):
        m = RE_STRUCT_DEF.match(line.strip())
        if m and m.group(1) == struct_name:
            end = find_block_end(lines, i)
            return _parse_struct_body(lines, i + 1, end)
    return None


def _parse_struct_body(
    lines: list[str], start: int, end: int
) -> list[dict]:
    """解析 struct body 中的字段。"""
    fields = []
    i = start
    while i < end:
        line = lines[i].strip()
        # 跳过空行、注释
        if not line or line.startswith("//") or line.startswith("/*"):
            i += 1
            continue

        # 嵌入字段: 只有类型，没有字段名
        # 模式1: pkg.Type 或 *pkg.Type
        # 模式2: Type 或 *Type (同包)
        embed_m = re.match(
            r"^(\*?(?:\w+\.)?[A-Z]\w*(?:\[.*?\])?)(?:\s*//.*)?$", line
        )
        if embed_m:
            type_expr = embed_m.group(1)
            # 嵌入字段的"名字"是类型名的最后部分
            name = type_expr.lstrip("*").rsplit(".", 1)[-1]
            # 去掉泛型参数
            name = re.sub(r"\[.*?\]", "", name)
            fields.append({
                "name": name,
                "type_expr": type_expr,
                "is_embedded": True,
            })
            i += 1
            continue

        # 普通字段: FieldName Type `tag`
        field_m = re.match(
            r"^(\w+)\s+((?:\*?(?:\w+\.)?)?[A-Z]\w*(?:\[.*?\])?)\s*(?:`.*`)?",
            line,
        )
        if field_m:
            fields.append({
                "name": field_m.group(1),
                "type_expr": field_m.group(2),
                "is_embedded": False,
            })
            i += 1
            continue

        i += 1

    return fields


def find_all_structs(lines: list[str]) -> list[str]:
    """找到文件中所有 struct 名称。"""
    structs = []
    for line in lines:
        m = RE_STRUCT_DEF.match(line.strip())
        if m:
            structs.append(m.group(1))
    return structs


def resolve_interface_file(
    project_root: str,
    import_path: str,
    type_name: str,
    go_mod_module: str,
) -> Optional[str]:
    """
    在项目中定位接口定义所在的 .go 文件。
    返回相对于 project_root 的路径，或 None。
    """
    # 只处理项目内部的包
    if not import_path.startswith(go_mod_module):
        return None

    # 计算相对目录
    rel_dir = import_path[len(go_mod_module):]
    rel_dir = rel_dir.lstrip("/")
    abs_dir = os.path.join(project_root, rel_dir)

    if not os.path.isdir(abs_dir):
        return None

    # 在目录下的 .go 文件中搜索 type TypeName interface {
    pattern = re.compile(
        rf"^\s*type\s+{re.escape(type_name)}\s+interface\s*\{{"
    )
    # 也匹配 type 块内的定义
    pattern_in_block = re.compile(
        rf"^\s*{re.escape(type_name)}\s+interface\s*\{{"
    )

    for fname in sorted(os.listdir(abs_dir)):
        if not fname.endswith(".go") or fname.endswith("_test.go"):
            continue
        fpath = os.path.join(abs_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    if pattern.match(line) or pattern_in_block.match(line):
                        return os.path.join(rel_dir, fname)
        except (OSError, UnicodeDecodeError):
            continue

    return None


def get_go_mod_module(project_root: str) -> str:
    """从 go.mod 读取 module 路径。"""
    go_mod = os.path.join(project_root, "go.mod")
    with open(go_mod, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("module "):
                return line.split(None, 1)[1].strip()
    raise RuntimeError(f"go.mod 中未找到 module 声明: {go_mod}")


def detect_interface_deps(
    filepath: str,
    project_root: str,
    struct_name: Optional[str] = None,
) -> dict:
    """
    主检测函数。

    分析 struct 的字段，识别外部接口依赖。
    判断逻辑：字段类型引用了外部包的类型 → 在项目中查找该类型 →
    如果是 interface 定义 → 加入依赖列表。
    """
    lines = parse_file(filepath)
    imports = extract_imports(lines)
    go_mod_module = get_go_mod_module(project_root)

    # 确定要分析的 struct
    if struct_name:
        struct_names = [struct_name]
    else:
        struct_names = find_all_structs(lines)

    results = []

    for sname in struct_names:
        fields = extract_struct_fields(lines, sname)
        if fields is None:
            continue

        interface_deps = []
        mock_files = []

        for field in fields:
            type_expr = field["type_expr"].lstrip("*")

            # 只关注带包前缀的类型: pkg.TypeName
            if "." not in type_expr:
                continue

            parts = type_expr.split(".", 1)
            pkg_alias = parts[0]
            type_name = re.sub(r"\[.*?\]", "", parts[1])  # 去泛型

            if pkg_alias not in imports:
                continue

            import_path = imports[pkg_alias]

            # 在项目中查找接口定义文件
            source_file = resolve_interface_file(
                project_root, import_path, type_name, go_mod_module
            )

            if source_file:
                dep = {
                    "field_name": field["name"],
                    "import_alias": pkg_alias,
                    "import_path": import_path,
                    "type_name": type_name,
                    "is_embedded": field["is_embedded"],
                    "source_file": source_file,
                }
                interface_deps.append(dep)
                if source_file not in mock_files:
                    mock_files.append(source_file)

        results.append({
            "struct": sname,
            "interface_deps": interface_deps,
            "mock_generate_files": mock_files,
        })

    # 单 struct 返回单个对象，多 struct 返回数组
    if len(results) == 1:
        return results[0]
    return {"structs": results}


def main():
    parser = argparse.ArgumentParser(
        description="检测 Go 源文件中的外部接口依赖",
    )
    parser.add_argument(
        "--file", required=True,
        help="目标 Go 源文件路径",
    )
    parser.add_argument(
        "--struct", default=None,
        help="指定要分析的 struct 名称（可选，默认分析所有 struct）",
    )
    parser.add_argument(
        "--project-root", default=None,
        help="项目根目录（go.mod 所在目录），默认自动向上查找",
    )

    args = parser.parse_args()

    # 自动查找项目根目录
    project_root = args.project_root
    if not project_root:
        d = os.path.abspath(os.path.dirname(args.file))
        while d != "/":
            if os.path.exists(os.path.join(d, "go.mod")):
                project_root = d
                break
            d = os.path.dirname(d)
        if not project_root:
            print(json.dumps({"error": "未找到 go.mod，请指定 --project-root"}))
            sys.exit(1)

    try:
        result = detect_interface_deps(
            args.file, project_root, args.struct
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
