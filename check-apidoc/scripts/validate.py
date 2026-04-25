#!/usr/bin/env python3
"""
check-apidoc 结构校验脚本（脚本层）
用法: python3 validate.py <json_file_path>
退出码: 0=通过(含警告), 1=有错误
"""

import json
import re
import sys
from pathlib import Path


def validate(path: str):
    errors = []
    warnings = []

    # 1. JSON 格式合法性
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"JSON 格式错误: {e}"], []
    except FileNotFoundError:
        return [f"文件不存在: {path}"], []

    # 2. 必要顶级字段
    for field in ["openapi", "info", "paths", "components", "tags"]:
        if field not in doc:
            errors.append(f"缺少顶级字段: '{field}'")

    # 3. x-stoplight.id
    if "x-stoplight" not in doc or "id" not in doc.get("x-stoplight", {}):
        warnings.append("缺少 x-stoplight.id")

    # 4. info 可选元数据字段（项目自定义，缺失只警告）
    info = doc.get("info", {})
    for field in ["x-last-updated", "x-source-handler"]:
        if field not in info:
            warnings.append(f"info 缺少可选字段 '{field}'（非必须）")

    # 5. $ref 悬空引用检查
    doc_str = json.dumps(doc)
    refs = re.findall(r'"\$ref":\s*"#/components/schemas/([^"]+)"', doc_str)
    defined_schemas = set(doc.get("components", {}).get("schemas", {}).keys())
    for ref in sorted(set(refs)):
        if ref not in defined_schemas:
            errors.append(f"$ref 引用了未定义的 schema: '{ref}'")

    # 6. 遍历所有接口
    paths = doc.get("paths", {})
    for path_str, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            loc = f"{method.upper()} {path_str}"

            # 必要字段
            for field in ["operationId", "summary", "tags", "responses"]:
                if field not in operation:
                    errors.append(f"[{loc}] 缺少 '{field}'")

            # responses 禁止直接写 allOf（必须用 $ref 引用 schema）
            for status_code, resp in operation.get("responses", {}).items():
                if not isinstance(resp, dict):
                    continue
                for media_type, media in resp.get("content", {}).items():
                    schema = media.get("schema", {}) if isinstance(media, dict) else {}
                    if "allOf" in schema:
                        errors.append(
                            f"[{loc}] responses.{status_code} 直接写了 allOf，"
                            f"应在 components/schemas 定义后用 $ref 引用"
                        )

            # deprecated 拼写检查
            op_str = json.dumps(operation)
            for typo in ["depcrecated", "deprcated", "depercated"]:
                if typo in op_str:
                    errors.append(f"[{loc}] 'deprecated' 拼写错误: '{typo}'")

    # 7. CommonResponse 结构检查（若存在则检查是否有 properties，字段内容由项目自定义）
    common = doc.get("components", {}).get("schemas", {}).get("CommonResponse", {})
    if common:
        if "properties" not in common and "allOf" not in common:
            warnings.append("CommonResponse 缺少 'properties' 或 'allOf' 字段")

    # 8. 时间戳字段格式检查
    schemas_obj = doc.get("components", {}).get("schemas", {})
    for schema_name, schema in schemas_obj.items():
        if not isinstance(schema, dict):
            continue
        for prop_name, prop in schema.get("properties", {}).items():
            if not isinstance(prop, dict):
                continue
            if (("time" in prop_name or "timestamp" in prop_name)
                    and prop.get("type") == "integer"
                    and prop.get("format") != "int64"):
                warnings.append(
                    f"{schema_name}.{prop_name}: 时间戳字段建议加 \"format\": \"int64\""
                )

    # 9. tags 非空检查
    tags = doc.get("tags", [])
    if not tags:
        warnings.append("tags 数组为空")

    return errors, warnings


def main():
    if len(sys.argv) < 2:
        print("用法: python3 validate.py <json_file_path>")
        sys.exit(1)

    path = sys.argv[1]
    errors, warnings = validate(path)

    print(f"\n{'='*60}")
    print(f"  脚本层校验：{Path(path).name}")
    print(f"{'='*60}")

    if warnings:
        print(f"\n⚠️  警告 ({len(warnings)})：")
        for w in warnings:
            print(f"   · {w}")

    if errors:
        print(f"\n❌ 错误 ({len(errors)})：")
        for e in errors:
            print(f"   · {e}")
        print()
        sys.exit(1)
    else:
        if warnings:
            print(f"\n✅ 无结构性错误（{len(warnings)} 条警告，请确认）\n")
        else:
            print(f"\n✅ 校验通过，无任何问题\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
