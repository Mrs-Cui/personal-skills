#!/usr/bin/env python3
"""
Mock 路径分析工具

分析 Python 源文件的导入语句，生成正确的 Mock 路径建议。
支持按函数名裁剪，只输出指定函数实际引用的依赖。

用法:
    python analyze_mock_path.py <源文件路径>
    python analyze_mock_path.py message/handler/email.py --json
    python analyze_mock_path.py message/handler/email.py --json --functions "post_email,EmailHandler.send"

输出:
    - 文件中的所有导入（或按函数裁剪后的子集）
    - 每个导入对应的正确 Mock 路径
    - 常见依赖的 Mock 示例代码
"""
import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def analyze_imports(file_path: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    分析文件的导入语句

    返回:
        {
            'direct': [(导入名, 来源模块), ...],  # from x import y
            'module': [(别名, 模块路径), ...],    # import x as y
        }
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    tree = ast.parse(content)

    imports = {
        'direct': [],  # from x import y
        'module': [],  # import x
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                name = alias.asname or alias.name
                imports['direct'].append((name, module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                imports['module'].append((name, alias.name))

    return imports


def collect_names_in_node(node: ast.AST) -> set:
    """收集 AST 节点内所有引用的名称（Name.id 和 Attribute.attr 的首段）"""
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            # 收集链式属性的根名称，如 config.get → 收集 config
            val = child
            while isinstance(val, ast.Attribute):
                val = val.value
            if isinstance(val, ast.Name):
                names.add(val.id)
    return names


def get_used_imports_by_functions(file_path: str, function_names: set,
                                  imports: Dict) -> set:
    """
    分析指定函数体内实际引用了哪些导入名称。

    参数:
        file_path: 源文件路径
        function_names: 目标函数名集合（支持 "func" 或 "Class.method" 格式）
        imports: analyze_imports() 的返回值

    返回:
        实际被引用的导入名称集合
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    tree = ast.parse(content)

    # 拆分：纯函数名 vs Class.method
    plain_names = set()
    class_methods = {}  # class_name -> {method_names}
    for fn in function_names:
        if '.' in fn:
            cls, method = fn.split('.', 1)
            class_methods.setdefault(cls, set()).add(method)
        else:
            plain_names.add(fn)

    all_import_names = set()
    for name, _ in imports['direct']:
        all_import_names.add(name)
    for alias, _ in imports['module']:
        all_import_names.add(alias)

    used_names = set()

    for node in ast.iter_child_nodes(tree):
        # 模块级函数
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in plain_names:
                body_names = collect_names_in_node(node)
                used_names |= (body_names & all_import_names)
        # 类方法
        elif isinstance(node, ast.ClassDef):
            target_methods = set()
            if node.name in class_methods:
                target_methods = class_methods[node.name]
            # 也检查纯名称匹配类内方法
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name in plain_names or item.name in target_methods:
                        body_names = collect_names_in_node(item)
                        used_names |= (body_names & all_import_names)

    return used_names


def get_module_path(file_path: str) -> str:
    """将文件路径转换为模块路径"""
    path = Path(file_path)
    # 移除 .py 后缀
    if path.suffix == '.py':
        path = path.with_suffix('')
    # 转换为模块路径
    return str(path).replace('/', '.')


def is_async_function(module_path: str, func_name: str) -> bool:
    """
    通过 AST 分析检查目标模块中的函数是否是异步函数
    
    参数:
        module_path: 模块路径 (如 'utils.helper')
        func_name: 函数名
    
    返回:
        True 如果是 async def，否则 False
    """
    # 将模块路径转换为文件路径
    possible_paths = [
        module_path.replace('.', '/') + '.py',
        module_path.replace('.', '/') + '/__init__.py',
    ]
    
    for file_path in possible_paths:
        if not Path(file_path).exists():
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # 检查是否是异步函数定义
                if isinstance(node, ast.AsyncFunctionDef) and node.name == func_name:
                    return True
                # 检查类中的异步方法
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.AsyncFunctionDef) and item.name == func_name:
                            return True
        except (SyntaxError, IOError):
            continue
    
    return False


def generate_mock_paths(file_path: str, imports: Dict) -> List[Dict]:
    """
    生成 Mock 路径建议
    
    返回:
        [
            {
                'name': '导入名',
                'source': '来源模块',
                'mock_path': '正确的 Mock 路径',
                'example': 'Mock 代码示例'
            },
            ...
        ]
    """
    module_path = get_module_path(file_path)
    results = []
    
    # 已知的异步依赖白名单（作为 AST 分析的补充）
    known_async_deps = {
        'ConnectionManager',
        'RedisHelper',
        'aiohttp',
        'ClientSession',
    }
    
    # 特殊 Mock 配置
    special_mocks = {
        'redis_cache': 'side_effect=mock_redis_cache',
    }
    
    # 处理 from x import y 形式
    for name, source in imports['direct']:
        mock_path = f"{module_path}.{name}"
        
        # 判断是否需要 AsyncMock：
        # 1. 优先通过 AST 分析源模块中的函数定义
        # 2. 如果源文件不可访问，回退到白名单判断
        if is_async_function(source, name):
            mock_type = 'AsyncMock'
        elif name in known_async_deps:
            mock_type = 'AsyncMock'
        elif name in special_mocks:
            mock_type = special_mocks[name]
        else:
            mock_type = 'MagicMock'
        
        if 'AsyncMock' in mock_type:
            example = f"@patch('{mock_path}', new_callable=AsyncMock)"
        elif 'side_effect' in mock_type:
            example = f"@patch('{mock_path}', {mock_type})"
        else:
            example = f"@patch('{mock_path}')"
        
        results.append({
            'name': name,
            'source': source,
            'mock_path': mock_path,
            'mock_type': mock_type,
            'example': example,
        })
    
    # 处理 import x 形式
    for alias, module in imports['module']:
        mock_path = f"{module_path}.{alias}"
        results.append({
            'name': alias,
            'source': module,
            'mock_path': mock_path,
            'mock_type': 'MagicMock',
            'example': f"@patch('{mock_path}')",
        })
    
    return results


def print_analysis(file_path: str, mock_paths: List[Dict]):
    """打印分析结果"""
    print(f"\n{'='*60}")
    print(f"Mock 路径分析: {file_path}")
    print(f"{'='*60}\n")
    
    # 按类型分组
    async_mocks = [m for m in mock_paths if 'Async' in m.get('mock_type', '')]
    sync_mocks = [m for m in mock_paths if 'Async' not in m.get('mock_type', '')]
    
    if async_mocks:
        print("📌 异步依赖 (需要 AsyncMock):")
        print("-" * 40)
        for m in async_mocks:
            print(f"  {m['name']}")
            print(f"    来源: {m['source']}")
            print(f"    Mock: {m['example']}")
            print()
    
    if sync_mocks:
        print("📌 同步依赖 (使用 MagicMock):")
        print("-" * 40)
        for m in sync_mocks:
            print(f"  {m['name']}")
            print(f"    来源: {m['source']}")
            print(f"    Mock: {m['example']}")
            print()
    
    # 生成完整示例
    print("📝 完整 Mock 示例:")
    print("-" * 40)
    print("```python")
    print("import pytest")
    print("from unittest.mock import AsyncMock, MagicMock, patch")
    print()
    
    # 打印装饰器
    for m in mock_paths[:5]:  # 只显示前5个
        print(m['example'])
    
    print("@pytest.mark.asyncio")
    print("async def test_example(self, ...):")
    print("    # 测试代码")
    print("    pass")
    print("```")


def json_output(file_path: str, mock_paths: List[Dict], filtered: bool = False):
    """输出结构化 JSON"""
    module_path = get_module_path(file_path)
    result = {
        "file": file_path,
        "module_path": module_path,
        "filtered": filtered,
        "imports": [
            {
                "name": m["name"],
                "source": m["source"],
                "mock_path": m["mock_path"],
                "mock_type": "AsyncMock" if "Async" in m.get("mock_type", "") else "MagicMock",
                "is_async": "Async" in m.get("mock_type", ""),
            }
            for m in mock_paths
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Mock 路径分析工具",
        epilog="""
示例:
  %(prog)s message/handler/email.py --json
  %(prog)s message/handler/email.py --json --functions "post_email,EmailHandler.send_email"
        """
    )
    parser.add_argument("file", help="源文件路径")
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    parser.add_argument("--functions", help="逗号分隔的函数名，只输出这些函数实际引用的 Mock 路径（支持 Class.method 格式）")
    args = parser.parse_args()

    file_path = args.file

    if not Path(file_path).exists():
        print(f"错误: 文件不存在 - {file_path}")
        sys.exit(1)

    try:
        imports = analyze_imports(file_path)
        mock_paths = generate_mock_paths(file_path, imports)

        # 按函数裁剪 Mock 表
        filtered = False
        if args.functions:
            func_names = set(f.strip() for f in args.functions.split(",") if f.strip())
            used_names = get_used_imports_by_functions(file_path, func_names, imports)
            mock_paths = [m for m in mock_paths if m["name"] in used_names]
            filtered = True

        if args.json:
            json_output(file_path, mock_paths, filtered=filtered)
        else:
            print_analysis(file_path, mock_paths)
    except SyntaxError as e:
        print(f"语法错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"分析错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
