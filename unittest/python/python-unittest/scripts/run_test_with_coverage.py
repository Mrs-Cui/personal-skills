#!/usr/bin/env python3
"""
测试运行和覆盖率检查工具

运行指定的测试文件并生成覆盖率报告。

用法:
    python run_test_with_coverage.py <测试文件> [源文件]
    python run_test_with_coverage.py test_auto_generate/unit/handler/test_email.py message/handler/email.py
    python run_test_with_coverage.py --json test_auto_generate/unit/handler/test_email.py message/handler/email.py
    python run_test_with_coverage.py --json --uncovered-functions test_auto_generate/unit/handler/test_email.py message/handler/email.py

输出:
    - 测试执行结果
    - 覆盖率报告
    - 未覆盖的代码行
    - (--json) 结构化 JSON 输出
    - (--uncovered-functions) 未覆盖的函数列表
"""
import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


def run_test(test_file: str, source_file: str = None, quiet: bool = False) -> dict:
    """
    运行测试并收集覆盖率

    返回:
        {
            'success': bool,
            'test_output': str,
            'coverage': float,
            'uncovered_lines': list,
            'tests_passed': int,
            'tests_failed': int,
            'coverage_data': dict,  # 原始 coverage json 数据
        }
    """
    result = {
        'success': False,
        'test_output': '',
        'coverage': 0.0,
        'uncovered_lines': [],
        'tests_passed': 0,
        'tests_failed': 0,
        'coverage_data': None,
    }

    # 构建 coverage 命令
    if source_file:
        coverage_cmd = [
            'coverage', 'run',
            f'--source={source_file.replace(".py", "").replace("/", ".")}',
            '-m', 'pytest', test_file, '-v'
        ]
    else:
        coverage_cmd = [
            'coverage', 'run',
            '-m', 'pytest', test_file, '-v'
        ]

    if not quiet:
        print(f"🧪 运行测试: {' '.join(coverage_cmd)}")
        print("-" * 60)

    # 运行测试
    try:
        test_result = subprocess.run(
            coverage_cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        result['test_output'] = test_result.stdout + test_result.stderr
        result['success'] = test_result.returncode == 0

        # 解析 passed/failed 数量
        _parse_test_counts(result)

        if not quiet:
            print(result['test_output'])

    except subprocess.TimeoutExpired:
        result['test_output'] = "测试超时 (>300秒)"
        if not quiet:
            print(f"❌ {result['test_output']}")
        return result
    except Exception as e:
        result['test_output'] = f"测试执行错误: {e}"
        if not quiet:
            print(f"❌ {result['test_output']}")
        return result

    # 生成覆盖率报告
    if not quiet:
        print("\n📊 覆盖率报告:")
        print("-" * 60)

    try:
        # 打印人类可读的覆盖率报告
        coverage_report = subprocess.run(
            ['coverage', 'report', '-m'],
            capture_output=True,
            text=True
        )
        if not quiet:
            print(coverage_report.stdout)

        # 使用 JSON 格式解析覆盖率数据（更可靠）
        coverage_json = subprocess.run(
            ['coverage', 'json', '-o', '-'],
            capture_output=True,
            text=True
        )

        if coverage_json.returncode == 0:
            data = json.loads(coverage_json.stdout)
            result['coverage'] = data['totals']['percent_covered']
            result['coverage_data'] = data

            # 提取未覆盖的行信息
            for file_path, file_data in data.get('files', {}).items():
                missing = file_data.get('missing_lines', [])
                if missing:
                    result['uncovered_lines'].extend(
                        [f"{file_path}:{line}" for line in missing]
                    )
        else:
            # JSON 解析失败时回退到文本解析
            if not quiet:
                print("⚠️ JSON 覆盖率解析失败，使用文本解析")
            for line in coverage_report.stdout.split('\n'):
                if 'TOTAL' in line:
                    parts = line.split()
                    for part in parts:
                        if '%' in part:
                            result['coverage'] = float(part.replace('%', ''))
                            break

    except Exception as e:
        if not quiet:
            print(f"覆盖率报告生成失败: {e}")

    return result


def _parse_test_counts(result: dict):
    """从 pytest 输出解析通过/失败数量"""
    output = result['test_output']
    # pytest 输出格式: "X passed, Y failed" 或 "X passed"
    passed_match = re.search(r'(\d+) passed', output)
    failed_match = re.search(r'(\d+) failed', output)
    if passed_match:
        result['tests_passed'] = int(passed_match.group(1))
    if failed_match:
        result['tests_failed'] = int(failed_match.group(1))


def extract_uncovered_functions(coverage_data: dict, source_file: str) -> List[Dict]:
    """
    交叉 coverage JSON 数据与 AST 分析，提取未覆盖的函数列表

    返回:
        [{"file": str, "function": str, "class": str|None, "uncovered_lines": [int]}]
    """
    if not coverage_data or not source_file:
        return []

    # 从 coverage 数据获取未覆盖行
    uncovered_by_file = {}
    for fpath, fdata in coverage_data.get('files', {}).items():
        missing = set(fdata.get('missing_lines', []))
        if missing:
            uncovered_by_file[fpath] = missing

    # 找到匹配的源文件
    source_key = None
    source_abs = str(Path(source_file).resolve())
    for fpath in uncovered_by_file:
        if fpath == source_file or str(Path(fpath).resolve()) == source_abs:
            source_key = fpath
            break

    if not source_key:
        return []

    missing_lines = uncovered_by_file[source_key]

    # AST 解析获取函数定义
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except (SyntaxError, FileNotFoundError):
        return []

    uncovered_functions = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 模块级函数
            func_lines = set(range(node.lineno, (node.end_lineno or node.lineno) + 1))
            overlap = func_lines & missing_lines
            if overlap:
                uncovered_functions.append({
                    "file": source_file,
                    "function": node.name,
                    "class": None,
                    "uncovered_lines": sorted(overlap),
                })
        elif isinstance(node, ast.ClassDef):
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_lines = set(range(item.lineno, (item.end_lineno or item.lineno) + 1))
                    overlap = func_lines & missing_lines
                    if overlap:
                        uncovered_functions.append({
                            "file": source_file,
                            "function": item.name,
                            "class": node.name,
                            "uncovered_lines": sorted(overlap),
                        })

    return uncovered_functions


def print_summary(result: dict, test_file: str, source_file: str = None):
    """打印测试总结"""
    print("\n" + "=" * 60)
    print("📋 测试总结")
    print("=" * 60)

    status = "✅ 通过" if result['success'] else "❌ 失败"
    print(f"测试文件: {test_file}")
    if source_file:
        print(f"源文件: {source_file}")
    print(f"测试状态: {status}")
    print(f"覆盖率: {result['coverage']:.1f}%")

    # 覆盖率评估
    if result['coverage'] >= 80:
        print(f"覆盖率状态: ✅ 达标 (>80%)")
    else:
        print(f"覆盖率状态: ⚠️ 未达标 (目标 >80%)")
        print("\n建议:")
        print("  - 检查未覆盖的分支和异常处理")
        print("  - 添加边界条件测试用例")
        print("  - 考虑参数化测试覆盖更多场景")


def json_summary(result: dict, test_file: str, source_file: str = None,
                 include_uncovered_functions: bool = False) -> dict:
    """生成结构化 JSON 输出"""
    output = {
        "success": result['success'],
        "test_file": test_file,
        "source_file": source_file,
        "tests_passed": result['tests_passed'],
        "tests_failed": result['tests_failed'],
        "test_output_summary": f"{result['tests_passed']} passed, {result['tests_failed']} failed",
        "coverage_percent": round(result['coverage'], 2),
        "coverage_met": result['coverage'] >= 80,
        "uncovered_lines": {},
    }

    # 按文件分组未覆盖行
    for entry in result.get('uncovered_lines', []):
        if ':' in entry:
            fpath, line = entry.rsplit(':', 1)
            output["uncovered_lines"].setdefault(fpath, []).append(int(line))

    if include_uncovered_functions and source_file and result.get('coverage_data'):
        output["uncovered_functions"] = extract_uncovered_functions(
            result['coverage_data'], source_file
        )

    return output


def main():
    parser = argparse.ArgumentParser(
        description="测试运行和覆盖率检查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("test_file", help="测试文件路径")
    parser.add_argument("source_file", nargs="?", default=None, help="源文件路径（用于覆盖率过滤）")
    parser.add_argument("--json", action="store_true", dest="json_output", help="输出结构化 JSON")
    parser.add_argument("--uncovered-functions", action="store_true",
                        help="在 JSON 输出中包含未覆盖函数列表（需配合 --json）")

    args = parser.parse_args()

    test_file = args.test_file
    source_file = args.source_file
    use_json = args.json_output

    if not Path(test_file).exists():
        if use_json:
            print(json.dumps({"error": f"测试文件不存在: {test_file}"}))
        else:
            print(f"错误: 测试文件不存在 - {test_file}")
        sys.exit(1)

    if source_file and not Path(source_file).exists():
        if not use_json:
            print(f"警告: 源文件不存在 - {source_file}")
        source_file = None

    result = run_test(test_file, source_file, quiet=use_json)

    if use_json:
        output = json_summary(result, test_file, source_file, args.uncovered_functions)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_summary(result, test_file, source_file)

    # 返回适当的退出码
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
