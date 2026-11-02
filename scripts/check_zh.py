#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
motion-zh · 中文适配检查器
=========================

两个用途，一个目的：让中文在 AI 视频模板里不出错。

1) 校验一份参数是否放得进画面
     python3 check_zh.py --params my.json [--schema params.schema.json]

2) 审计任意 .motion 模板的 params.schema.json 是否做了中文适配
     python3 check_zh.py --schema path/to/params.schema.json --audit

3) 单条文案体检（不依赖任何模板）
     python3 check_zh.py --text "降准落地，钱会流向哪三个方向" --chars 12 --lines 2

退出码：0 = 通过（可能有 WARN），1 = 有 ERROR。
"""
import argparse
import json
import os
import sys

# 中文行首禁则：这些字符不能出现在行首
NO_LINE_START = "，。、；：？！）】》」』’”%‰℃"
# 这些字符不能出现在行尾
NO_LINE_END = "（【《「『‘“"

DEFAULTS = {
    "cps": 6.5,            # 中文每秒可读字数（信息卡建议 5~7）
    "min_cps": 3.0,        # 低于这个说明字太少、停留太久
    "max_line_zh": 18,     # 竖屏单行中文上限（1080 宽、44px 字）
    "min_line_zh": 4,      # 单行少于 4 字通常是碎句
}


def load_rules(path=None):
    r = dict(DEFAULTS)
    p = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json")
    if os.path.exists(p):
        try:
            r.update(json.load(open(p, encoding="utf-8")).get("rules", {}))
        except Exception:
            pass
    return r


def is_cjk(ch):
    return "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf"


def count_chars(s):
    """按中文字符计：一个汉字=1，一个 ASCII 字符=0.55，换行不计。"""
    if not isinstance(s, str):
        return 0
    n = 0.0
    for ch in s:
        if ch == "\n":
            continue
        n += 1.0 if is_cjk(ch) else 0.55
    return round(n, 2)


def wrap_zh(text, max_per_line, rules=None):
    """按标点禁则断行，返回行列表。这是模板 wrapZh() 的 Python 对照实现。"""
    rules = rules or DEFAULTS
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if count_chars(cur + ch) > max_per_line and cur:
            if ch in NO_LINE_START and count_chars(cur) > 1:
                cur += ch
                lines.append(cur)
                cur = ""
                continue
            # 行尾不能是开括号/开引号，退一个字符
            if cur[-1] in NO_LINE_END and len(cur) > 1:
                lines.append(cur[:-1])
                cur = cur[-1] + ch
                continue
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    # 孤字回退：末行太短就从上一行末尾挪字过去（中文排版基本要求）
    if len(lines) > 1 and count_chars(lines[-1]) < rules.get("min_line_zh", 4):
        prev, last = lines[-2], lines[-1]
        while prev and count_chars(last) < rules["min_line_zh"] and count_chars(prev) > rules["min_line_zh"]:
            last = prev[-1] + last
            prev = prev[:-1]
        lines[-2], lines[-1] = prev, last
    return lines


class Report:
    def __init__(self):
        self.items = []

    def err(self, where, msg):
        self.items.append(("ERROR", where, msg))

    def warn(self, where, msg):
        self.items.append(("WARN", where, msg))

    def info(self, where, msg):
        self.items.append(("INFO", where, msg))

    def ok(self):
        return not any(sev == "ERROR" for sev, _, _ in self.items)

    def dump(self):
        icon = {"ERROR": "✗", "WARN": "!", "INFO": "·"}
        for sev, where, msg in self.items:
            print(f"{icon[sev]} [{sev}] {where}: {msg}")
        e = sum(1 for s, _, _ in self.items if s == "ERROR")
        w = sum(1 for s, _, _ in self.items if s == "WARN")
        print(f"\n{'PASS' if e == 0 else 'FAIL'} — {e} error / {w} warn")


def check_one_text(rep, where, text, limit_chars, limit_lines, rules, note=""):
    if not isinstance(text, str):
        rep.err(where, "不是字符串")
        return
    n = count_chars(text)
    if limit_chars and n > limit_chars + 1e-6:
        rep.err(where, f"{n} 字 > 上限 {limit_chars} 字{(' ('+note+')') if note else ''}")
    raw_lines = text.split("\n")
    if limit_lines and len(raw_lines) > limit_lines:
        rep.err(where, f"硬换行 {len(raw_lines)} 行 > 上限 {limit_lines} 行")
    # 按实际渲染宽度再折一次，判断会不会超出
    per_line = (limit_chars / limit_lines) if (limit_chars and limit_lines) else rules["max_line_zh"]
    wrapped = wrap_zh(text, max(4, per_line), rules)
    if limit_lines and len(wrapped) > limit_lines:
        rep.warn(where, f"按每行 {per_line:.0f} 字折行后需要 {len(wrapped)} 行，可能溢出：{wrapped}")
    for i, ln in enumerate(wrapped):
        if ln and ln[0] in NO_LINE_START:
            rep.err(where, f"第 {i+1} 行以标点「{ln[0]}」开头：{ln}")
        if ln and ln[-1] in NO_LINE_END:
            rep.warn(where, f"第 {i+1} 行以「{ln[-1]}」结尾：{ln}")
        if count_chars(ln) < rules["min_line_zh"] and len(wrapped) > 1:
            rep.warn(where, f"第 {i+1} 行只有 {count_chars(ln)} 字，像碎句：{ln}")


def check_params(params, schema, rules, rep):
    props = (schema or {}).get("properties", {})
    for key, spec in props.items():
        x = spec.get("x-zh", {})
        max_chars = x.get("maxChars") or spec.get("maxLength")
        max_lines = x.get("maxLines", 1)
        if spec.get("type") == "string":
            val = params.get(key)
            if val is None:
                continue
            check_one_text(rep, key, val, max_chars, max_lines, rules, x.get("role", ""))
        elif spec.get("type") == "array":
            val = params.get(key)
            if val is None:
                continue
            if not isinstance(val, list):
                rep.err(key, "应为数组")
                continue
            lo, hi = spec.get("minItems"), spec.get("maxItems")
            if lo is not None and len(val) < lo:
                rep.err(key, f"{len(val)} 条 < 最少 {lo} 条")
            if hi is not None and len(val) > hi:
                rep.err(key, f"{len(val)} 条 > 最多 {hi} 条（多出来的会被画面挤掉）")
            item = spec.get("items", {})
            if item.get("type") == "object":
                for i, obj in enumerate(val):
                    for k2, s2 in (item.get("properties") or {}).items():
                        if s2.get("type") != "string" or k2 not in obj:
                            continue
                        x2 = s2.get("x-zh", {})
                        check_one_text(rep, f"{key}[{i}].{k2}", obj[k2],
                                       x2.get("maxChars") or s2.get("maxLength"),
                                       x2.get("maxLines", 1), rules, x2.get("role", ""))
            elif item.get("type") == "string":
                for i, s in enumerate(val):
                    x2 = item.get("x-zh", {})
                    check_one_text(rep, f"{key}[{i}]", s,
                                   x2.get("maxChars") or item.get("maxLength"),
                                   x2.get("maxLines", 1), rules, x2.get("role", ""))
    # 必填检查
    for req in (schema or {}).get("required", []):
        if params.get(req) in (None, "", []):
            rep.err(req, "必填项为空")


def audit_schema(schema, rules, rep):
    props = (schema or {}).get("properties", {})
    if not props:
        rep.err("schema", "没有 properties，可能不是 params.schema.json")
        return
    n_str = n_zh = 0
    for key, spec in props.items():
        types = [spec.get("type")] + [s.get("type") for s in spec.get("anyOf", [])]
        if "string" not in types:
            continue
        n_str += 1
        x = spec.get("x-zh")
        ml = spec.get("maxLength")
        if x:
            n_zh += 1
            rep.info(key, f"已声明中文容量：{x.get('maxChars')} 字 / {x.get('maxLines', 1)} 行")
            if ml and x.get("maxChars") and x["maxChars"] < ml:
                rep.warn(key, f"maxLength={ml} 与 x-zh.maxChars={x['maxChars']} 不一致，以更小者为准")
        elif ml:
            est = int(ml * 0.62)  # 英文 maxLength 折算中文可读字数
            rep.warn(key, f"只有 maxLength={ml}（按英文估），中文实际约只能放 {est} 字；建议补 x-zh")
        else:
            rep.err(key, "字符串字段没有 maxLength，也没有中文容量声明，中文一定会溢出")
    rep.info("summary", f"{n_str} 个字符串字段，其中 {n_zh} 个声明了中文容量")
    if n_zh < n_str:
        rep.err("summary", f"还有 {n_str - n_zh} 个字段未做中文适配")


def main():
    ap = argparse.ArgumentParser(description="motion-zh 中文适配检查器")
    ap.add_argument("--params", help="要校验的参数 JSON")
    ap.add_argument("--schema", help="对应的 params.schema.json")
    ap.add_argument("--audit", action="store_true", help="审计 schema 的中文适配度")
    ap.add_argument("--text", help="单条文案体检")
    ap.add_argument("--chars", type=int, default=0, help="单条文案的字符上限")
    ap.add_argument("--lines", type=int, default=1, help="单条文案的行数上限")
    ap.add_argument("--rules", help="自定义规则文件")
    a = ap.parse_args()

    rules = load_rules(a.rules)
    rep = Report()

    if a.text is not None:
        check_one_text(rep, "text", a.text, a.chars, a.lines, rules)
        rep.dump()
        return 0 if rep.ok() else 1

    schema = json.load(open(a.schema, encoding="utf-8")) if a.schema else None

    if a.audit:
        if not schema:
            print("--audit 需要 --schema", file=sys.stderr)
            return 2
        audit_schema(schema, rules, rep)
        rep.dump()
        return 0 if rep.ok() else 1

    if a.params:
        params = json.load(open(a.params, encoding="utf-8"))
        if schema is None:
            guess = os.path.join(os.path.dirname(os.path.abspath(a.params)), "params.schema.json")
            if os.path.exists(guess):
                schema = json.load(open(guess, encoding="utf-8"))
        if schema is None:
            rep.warn("schema", "没有提供 schema，只做通用长度检查（18 字/行）")
        check_params(params, schema, rules, rep)
        rep.dump()
        return 0 if rep.ok() else 1

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
