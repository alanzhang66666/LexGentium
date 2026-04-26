"""
从 ClaimGen-CN（207k 民事判决书）构建模拟法庭系统数据集。

来源：Josieeee/ClaimGen-CN (HuggingFace) - EMNLP 2025
       207,748 条真实中国民事判决书，来自中国裁判文书网

输出：1000 条数据 → 600 训练 / 200 验证 / 200 测试
格式：适配系统 CD/DD/CI 三场景的 JSONL ground truth
"""
import json
import os
import random
import re
import sys
from pathlib import Path
from collections import Counter

random.seed(42)

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "dataset_1000"

# 20 种常见民事案由，确保案由多样性
TARGET_CAUSES = [
    "民间借贷纠纷", "买卖合同纠纷", "金融借款合同纠纷",
    "机动车交通事故责任纠纷", "合同纠纷", "劳动争议",
    "物业服务合同纠纷", "租赁合同纠纷", "离婚纠纷",
    "房屋买卖合同纠纷", "建设工程施工合同纠纷", "追偿权纠纷",
    "生命权、身体权、健康权纠纷", "商品房预售合同纠纷",
    "提供劳务者受害责任纠纷", "保险合同纠纷",
    "借款合同纠纷", "承揽合同纠纷", "侵权责任纠纷",
    "民事其他",
]

# 民法典常用法条映射（按案由）
CAUSE_LAW_MAP = {
    "民间借贷纠纷": ["民法典第六百六十七条", "民法典第六百七十五条", "民法典第六百七十六条", "民法典第六百八十条"],
    "买卖合同纠纷": ["民法典第五百九十五条", "民法典第五百九十七条", "民法典第六百一十七条"],
    "金融借款合同纠纷": ["民法典第六百六十七条", "民法典第六百七十四条", "民法典第六百七十六条"],
    "机动车交通事故责任纠纷": ["民法典第一千一百七十九条", "民法典第一千二百零八条", "道路交通安全法第七十六条"],
    "合同纠纷": ["民法典第五百零九条", "民法典第五百七十七条", "民法典第五百八十四条"],
    "劳动争议": ["劳动合同法第四十六条", "劳动合同法第四十七条", "劳动合同法第八十七条"],
    "物业服务合同纠纷": ["民法典第九百三十七条", "民法典第九百四十四条"],
    "租赁合同纠纷": ["民法典第七百零三条", "民法典第七百二十二条", "民法典第七百三十三条"],
    "离婚纠纷": ["民法典第一千零七十九条", "民法典第一千零八十七条", "民法典第一千零八十八条"],
    "房屋买卖合同纠纷": ["民法典第五百零九条", "民法典第五百七十七条", "民法典第二百零九条"],
    "建设工程施工合同纠纷": ["民法典第七百八十八条", "民法典第七百九十三条"],
    "生命权、身体权、健康权纠纷": ["民法典第一千一百六十五条", "民法典第一千一百七十九条"],
    "保险合同纠纷": ["保险法第二十三条", "保险法第六十条"],
}
DEFAULT_LAWS = ["民法典第五百零九条", "民法典第五百七十七条", "民事诉讼法第六十七条"]


def _gen_name(seed: int, gender: str = "") -> str:
    """生成虚构姓名。"""
    surnames = "张王李赵刘陈杨黄周吴孙马朱胡林何高罗郑梁"
    given_m = "伟强军磊涛明辉刚杰峰浩波鹏亮建文斌"
    given_f = "芳娟敏静丽艳红梅玲桂萍珍秀兰霞"
    r = random.Random(seed)
    s = r.choice(surnames)
    if gender == "女":
        g = r.choice(given_f) + (r.choice(given_f) if r.random() > 0.5 else "")
    else:
        g = r.choice(given_m) + (r.choice(given_m) if r.random() > 0.5 else "")
    return s + g


def _gen_date(seed: int) -> str:
    r = random.Random(seed)
    y = r.randint(1960, 2000)
    m = r.randint(1, 12)
    d = r.randint(1, 28)
    return f"{y}年{m}月{d}日"


def _gen_address(seed: int) -> str:
    provinces = ["北京市", "上海市", "广东省广州市", "江苏省南京市", "浙江省杭州市",
                 "四川省成都市", "湖北省武汉市", "山东省济南市", "河南省郑州市",
                 "湖南省长沙市", "福建省福州市", "安徽省合肥市", "重庆市"]
    r = random.Random(seed)
    return f"{r.choice(provinces)}某区某街道{r.randint(1,200)}号"


def _extract_amount(text: str) -> str:
    """尝试从事实中提取金额。"""
    m = re.search(r'[\d,]+(?:\.\d+)?(?:元|万元)', text)
    return m.group() if m else ""


def build_cd_record(case: dict, idx: int) -> dict:
    """构建 CD（起诉状）场景 ground truth。"""
    fact = case.get("plaintiffFactSegment", "")
    claims = case.get("claims", [])
    cause = case.get("cause", "民事纠纷")

    p_name = _gen_name(idx * 3, "")
    p_gender = random.choice(["男", "女"])
    d_name = _gen_name(idx * 3 + 1, "")
    d_gender = random.choice(["男", "女"])

    evidence_items = [
        "原告身份证复印件：证明原告主体资格。",
        "被告身份信息：证明被告主体资格。",
    ]

    _CAUSE_EVIDENCE = {
        "民间借贷纠纷": ["借款合同/借条原件：证明借贷关系成立。", "银行转账凭证：证明借款已实际交付。"],
        "金融借款合同纠纷": ["金融借款合同原件：证明借款关系成立。", "还款记录/对账单：证明还款情况。"],
        "机动车交通事故责任纠纷": ["交通事故认定书：证明事故责任划分。", "医疗费票据及病历：证明损害事实和损失金额。", "车辆维修费发票：证明财产损失。"],
        "劳动争议": ["劳动合同：证明劳动关系成立。", "工资发放记录/银行流水：证明工资标准。", "解除劳动关系通知书：证明解除事实。"],
        "离婚纠纷": ["结婚证：证明婚姻关系。", "共同财产清单及证明材料：证明夫妻共同财产。"],
        "房屋买卖合同纠纷": ["房屋买卖合同原件：证明买卖关系成立。", "房产证/不动产权证书：证明房屋权属。", "付款凭证：证明已支付价款。"],
        "租赁合同纠纷": ["租赁合同原件：证明租赁关系成立。", "租金支付凭证：证明租金支付情况。"],
        "房屋租赁合同纠纷": ["房屋租赁合同原件：证明租赁关系成立。", "租金支付凭证：证明租金支付情况。"],
        "建设工程施工合同纠纷": ["建设工程施工合同原件：证明承发包关系。", "工程竣工验收报告：证明工程完工情况。", "工程结算资料：证明工程款金额。"],
        "买卖合同纠纷": ["买卖合同原件：证明买卖关系成立。", "送货单/签收单：证明货物已交付。"],
        "保险合同纠纷": ["保险合同/保险单：证明保险关系成立。", "理赔申请材料：证明保险事故及损失。"],
        "生命权、身体权、健康权纠纷": ["医疗费票据及病历：证明损害事实和损失金额。", "伤残鉴定报告：证明伤残等级。"],
        "生命权、健康权、身体权纠纷": ["医疗费票据及病历：证明损害事实和损失金额。", "伤残鉴定报告：证明伤残等级。"],
    }

    cause_evidence = _CAUSE_EVIDENCE.get(cause, [])
    if cause_evidence:
        evidence_items.extend(cause_evidence)
    else:
        if "借" in fact or "贷" in fact:
            evidence_items.append("借款合同/借条原件：证明借贷关系成立。")
            evidence_items.append("银行转账凭证：证明借款已实际交付。")
        elif "合同" in fact:
            evidence_items.append("合同原件：证明合同关系成立。")
        if "损害" in fact or "伤" in fact:
            evidence_items.append("医疗费票据及病历：证明损害事实和损失金额。")
    evidence_items.append("其他相关证据材料。")

    return {
        "id": f"CD-{idx + 1:04d}",
        "scenario": "CD",
        "cause": cause,
        "specific_characters": {
            "plaintiff": {
                "name": p_name, "gender": p_gender,
                "birth_date": _gen_date(idx * 7),
                "nation": "汉族",
                "address": _gen_address(idx * 11),
                "representative": "",
            },
            "defendant": {
                "name": d_name, "gender": d_gender,
                "birth_date": _gen_date(idx * 7 + 3),
                "nation": "汉族",
                "address": _gen_address(idx * 11 + 5),
                "representative": "",
            },
        },
        "claims": claims if isinstance(claims, list) else [claims],
        "case_details": fact,
        "evidence": evidence_items,
    }


def build_dd_record(case: dict, idx: int) -> dict:
    """构建 DD（答辩状）场景 ground truth。"""
    fact = case.get("plaintiffFactSegment", "")
    claims = case.get("claims", [])
    cause = case.get("cause", "民事纠纷")

    d_name = _gen_name(idx * 3 + 1, "")

    claims_list = claims if isinstance(claims, list) else [claims]
    claims_list = [c for c in claims_list if c]

    defense_points = []
    if claims_list:
        defense_points.append("答辩人对原告诉讼请求不予认可。")
        for ci, claim_text in enumerate(claims_list, 1):
            defense_points.append(f"针对原告第{ci}项诉讼请求"{str(claim_text)[:50]}"：该请求缺乏充分的事实和法律依据。")
    defense_points.append("原告所述事实与实际情况不符，答辩人将在举证质证阶段详细说明。")
    if "利息" in str(claims_list) or "违约" in str(claims_list):
        defense_points.append("原告主张的利息/违约金标准过高，应予调整。")

    evidence_dd = {
        "1": {"evidence": "本答辩状副本一份。", "source": ""},
        "2": {"evidence": "答辩人身份证明材料。", "source": "答辩人提供"},
    }

    return {
        "id": f"DD-{idx + 1:04d}",
        "scenario": "DD",
        "cause": cause,
        "specific_characters": {
            "defendant": {
                "name": d_name,
                "address": _gen_address(idx * 11 + 5),
                "representative": "",
            },
        },
        "plaintiff_claims": claims_list,
        "plaintiff_facts": fact,
        "statement_of_defence": "\n".join(defense_points),
        "evidence": evidence_dd,
    }


def build_ci_record(case: dict, idx: int) -> dict:
    """构建 CI（庭审判决）场景 ground truth。"""
    fact = case.get("plaintiffFactSegment", "")
    claims = case.get("claims", [])
    cause = case.get("cause", "民事纠纷")
    laws = CAUSE_LAW_MAP.get(cause, DEFAULT_LAWS)

    p_name = _gen_name(idx * 3, "")
    d_name = _gen_name(idx * 3 + 1, "")

    amount_str = _extract_amount(fact)
    if amount_str:
        judgment_result = (
            f"一、被告{d_name}于本判决生效之日起十日内向原告{p_name}支付{amount_str}；\n"
            f"二、驳回原告{p_name}的其他诉讼请求。\n"
            f"案件受理费由被告{d_name}负担。"
        )
    else:
        judgment_result = (
            f"一、被告{d_name}于本判决生效之日起十日内履行相应义务；\n"
            f"二、驳回原告{p_name}的其他诉讼请求。\n"
            f"案件受理费由被告{d_name}负担。"
        )

    fact_summary = fact[:300].rstrip("，。、；：")
    reasoning = (
        f"本院认为，本案系{cause}。"
        f"根据查明的事实，{fact_summary}。"
        f"原告的诉讼请求部分成立，本院依法予以支持。"
    )

    full_doc = (
        f"民事判决书\n\n"
        f"本院认为\n\n{reasoning}\n\n"
        f"判决如下\n\n{judgment_result}\n\n"
        f"附：本案适用法律条文\n\n"
        + "\n".join(laws)
    )

    return {
        "id": f"CI-{idx + 1:04d}",
        "scenario": "CI",
        "cause": cause,
        "plaintiff_name": p_name,
        "defendant_name": d_name,
        "plaintiff_claims": claims if isinstance(claims, list) else [claims],
        "case_facts": fact,
        "judgment_result": judgment_result,
        "full_document": full_doc,
        "law": laws,
        "ground_truth": {
            "judgment": judgment_result,
            "reasoning": reasoning,
            "law": laws,
        },
    }


def load_claimgen_data() -> list:
    """加载 ClaimGen-CN 数据集。"""
    try:
        from huggingface_hub import hf_hub_download
        cache_path = hf_hub_download(
            repo_id="Josieeee/ClaimGen-CN",
            filename="ClaimGen-CN.json",
            repo_type="dataset",
        )
        print(f"从 HuggingFace 加载: {cache_path}")
    except Exception as e:
        print(f"HuggingFace 下载失败: {e}")
        # 尝试本地路径
        local_path = PROJECT_ROOT / "data" / "cail_raw" / "ClaimGen-CN.json"
        if local_path.exists():
            cache_path = str(local_path)
            print(f"使用本地文件: {cache_path}")
        else:
            raise FileNotFoundError("无法获取 ClaimGen-CN 数据集")

    with open(cache_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"加载完成: {len(data)} 条民事判决书")
    return data


def select_diverse_cases(data: list, n: int = 1000) -> list:
    """选择案由多样化的 n 条数据。"""
    # 按案由分组
    by_cause: dict = {}
    for item in data:
        cause = item.get("cause", "其他")
        if cause not in by_cause:
            by_cause[cause] = []
        by_cause[cause].append(item)

    print(f"共 {len(by_cause)} 种案由")

    # 过滤掉事实描述太短的
    filtered_causes = {}
    for cause, items in by_cause.items():
        valid = [it for it in items
                 if len(it.get("plaintiffFactSegment", "")) >= 50
                 and len(it.get("claims", [])) >= 1]
        if valid:
            filtered_causes[cause] = valid

    print(f"有效案由: {len(filtered_causes)} 种")

    # 优先选择目标案由，然后补充
    selected = []
    target_per_cause = max(n // len(filtered_causes), 5)

    # 第一轮：从目标案由各取一定数量
    for cause in TARGET_CAUSES:
        if cause in filtered_causes:
            items = filtered_causes[cause]
            take = min(len(items), target_per_cause)
            sampled = random.sample(items, take)
            selected.extend(sampled)

    # 第二轮：从其他案由补充
    if len(selected) < n:
        remaining_causes = [c for c in filtered_causes if c not in TARGET_CAUSES]
        for cause in remaining_causes:
            if len(selected) >= n:
                break
            items = filtered_causes[cause]
            take = min(len(items), max(n // len(filtered_causes), 3))
            selected.extend(random.sample(items, take))

    # 第三轮：如果还不够，从所有数据补充
    if len(selected) < n:
        all_ids = {id(s) for s in selected}
        extras = [it for it in data
                  if id(it) not in all_ids
                  and len(it.get("plaintiffFactSegment", "")) >= 50]
        needed = n - len(selected)
        selected.extend(random.sample(extras, min(needed, len(extras))))

    # 截断到 n 条
    if len(selected) > n:
        selected = random.sample(selected, n)

    random.shuffle(selected)
    print(f"选取 {len(selected)} 条（目标 {n}）")

    # 统计案由分布
    cause_dist = Counter(s.get("cause", "?") for s in selected)
    print("案由分布 (前15):")
    for c, cnt in cause_dist.most_common(15):
        print(f"  {c}: {cnt}")

    return selected


def split_dataset(cases: list) -> dict:
    """按 3:1:1 划分数据集。"""
    n = len(cases)
    n_train = int(n * 0.6)
    n_val = int(n * 0.2)

    return {
        "train": cases[:n_train],
        "val": cases[n_train:n_train + n_val],
        "test": cases[n_train + n_val:],
    }


def write_jsonl(records: list, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  写入 {path.name}: {len(records)} 条")


def main():
    print("=" * 60)
    print("构建模拟法庭数据集（1000 条民事判决书 → CD/DD/CI）")
    print("=" * 60)

    data = load_claimgen_data()
    cases = select_diverse_cases(data, n=1000)
    splits = split_dataset(cases)

    for split_name, split_cases in splits.items():
        print(f"\n--- {split_name}: {len(split_cases)} 条 ---")

        cd_records = [build_cd_record(c, i) for i, c in enumerate(split_cases)]
        dd_records = [build_dd_record(c, i) for i, c in enumerate(split_cases)]
        ci_records = [build_ci_record(c, i) for i, c in enumerate(split_cases)]

        split_dir = OUTPUT_DIR / split_name
        write_jsonl(cd_records, split_dir / "CD_ground_truth.jsonl")
        write_jsonl(dd_records, split_dir / "DD_ground_truth.jsonl")
        write_jsonl(ci_records, split_dir / "CI_ground_truth.jsonl")

        # 写入统一的案件信息文件（供全流程模拟使用）
        case_infos = []
        for i, c in enumerate(split_cases):
            raw_claims = c.get("claims", [])
            case_infos.append({
                "case_id": f"CASE-{i + 1:04d}",
                "cause": c.get("cause", ""),
                "case_description": c.get("plaintiffFactSegment", ""),
                "plaintiff_claims": raw_claims if isinstance(raw_claims, list) else [raw_claims],
                "plaintiff_name": _gen_name(i * 3, ""),
                "defendant_name": _gen_name(i * 3 + 1, ""),
            })
        write_jsonl(case_infos, split_dir / "case_info.jsonl")

    # 写入数据集元信息
    meta = {
        "source": "ClaimGen-CN (Josieeee/ClaimGen-CN, HuggingFace)",
        "paper": "ClaimGen-CN: A Large-scale Chinese Dataset for Legal Claim Generation (EMNLP 2025)",
        "original_size": len(data),
        "selected_size": len(cases),
        "split_ratio": "3:1:1 (train:val:test)",
        "splits": {k: len(v) for k, v in splits.items()},
        "scenarios": ["CD", "DD", "CI"],
        "cause_distribution": dict(Counter(c.get("cause", "") for c in cases).most_common(30)),
    }
    with open(OUTPUT_DIR / "dataset_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"\n元信息 → {OUTPUT_DIR / 'dataset_meta.json'}")

    print("\n" + "=" * 60)
    print(f"数据集构建完成！输出目录: {OUTPUT_DIR}")
    print(f"  train: {len(splits['train'])} 条 × 3 场景")
    print(f"  val:   {len(splits['val'])} 条 × 3 场景")
    print(f"  test:  {len(splits['test'])} 条 × 3 场景")
    print("=" * 60)


if __name__ == "__main__":
    main()
