# -*- coding: utf-8 -*-
"""
把 research/national_stats.json 合并进 sources.json。

national_stats.json 是新检索到的、按 GB/T 2260 编码的 34 省姓氏分布汇总，
带 18 条来源、7 条口径警告、以及公安部与报刊名单在 6 个省份的冲突记录。
旧的 sources.json 里 provinceTopSurname2019 用的是省名列表，此处改为 adcode 键。
"""
import json
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NS = ROOT / "research" / "national_stats.json"
SRC = ROOT / "sources.json"


def main():
    ns = json.loads(NS.read_text(encoding="utf-8"))
    src = json.loads(SRC.read_text(encoding="utf-8"))

    # 1) 追加来源（去重：按 url）
    have = {s.get("url") for s in src.get("sources", [])}
    added = 0
    for s in ns.get("sources", []):
        if s.get("url") and s.get("url") in have:
            continue
        src.setdefault("sources", []).append({
            "id": "NS%d" % s.get("id"),
            "title": s.get("title"),
            "publisher": s.get("publisher"),
            "date": s.get("date"),
            "url": s.get("url"),
            "tier": s.get("tier"),
            "quote": s.get("quote"),
        })
        added += 1

    # 2) 省级第一大姓：改成 adcode 键，并保留旧字段
    pst = src.setdefault("provinceTopSurname2019", {})
    by_name = pst.get("bySurname", {})
    new_by = {}
    for code, v in (ns.get("provinceTopSurname") or {}).items():
        top = v.get("top")
        if not top:
            continue
        new_by.setdefault(top, []).append(v.get("province") or code)
    # 与旧数据合并（旧的含 8 个姓）
    for ch, provs in by_name.items():
        merged = set(new_by.get(ch, [])) | set(provs)
        new_by[ch] = sorted(merged, key=lambda x: list((ns.get("provinceTopSurname") or {}).keys()).index(
            next((c for c, vv in (ns.get("provinceTopSurname") or {}).items() if vv.get("province") == x), "")) if any(
            vv.get("province") == x for vv in (ns.get("provinceTopSurname") or {}).values()) else 999)
    pst["bySurname"] = new_by
    pst["byAdcode"] = ns.get("provinceTopSurname", {})
    pst["note"] = ("合并后覆盖 34 个省级行政区（内地 30 + 台湾 + 澳门），西藏与香港无官方姓氏排名结论。"
                   "数据来自公安部《全国姓名报告》系列与各省统计局发布。")

    # 3) 人口最多省份
    mp = src.setdefault("maxProvince2021", {})
    for ch, v in (ns.get("maxPopulationProvince") or {}).items():
        if ch not in mp.setdefault("bySurname", {}):
            mp["bySurname"][ch] = v.get("province")
    mp["note"] = (ns.get("meta", {}).get("criticalConflict", "") +
                  " 口径：指该姓绝对人数最多的省份，不等于该姓在本省占比最高的省份，两者不可互换。")

    # 4) 分省具体人数
    src.setdefault("provinceSurnameCounts", []).extend(ns.get("provinceSurnameCounts", []))

    # 5) 台湾与澳门
    src["taiwan"] = ns.get("taiwan", {})

    # 6) 口径警告合并
    lim = src.setdefault("limits", [])
    for n in ns.get("notes", []):
        if n not in lim:
            lim.append(n)

    SRC.write_text(json.dumps(src, ensure_ascii=False, indent=1), encoding="utf-8")
    print("sources.json 已合并")
    print("  新增来源 %d 条 / 总来源 %d 条" % (added, len(src.get("sources", []))))
    print("  省级第一大姓覆盖姓数: %d / 省份条目 %d" % (
        len(pst["bySurname"]), len(pst.get("byAdcode", {}))))
    print("  分省人数条目: %d / 口径警告 %d" % (
        len(src.get("provinceSurnameCounts", [])), len(lim)))


if __name__ == "__main__":
    main()
