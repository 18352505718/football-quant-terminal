"""
bqc_engine.py - 半全场胜平负 (Half-Time / Full-Time, HT-FT) 量化预测引擎
采用双变量时间分片泊松模型 (Bivariate Time-Sliced Poisson) + 迪克森-考尔斯半场低比分偏置 (Dixon-Coles Low-Score HT Adjustment)
精准测算中国竞彩半全场 9 大盘口（胜胜、胜平、胜负、平胜、平平、平负、负胜、负平、负负）的真实概率与期望值 EV。
"""

import math

BQC_KEYS = [
    "胜胜", "胜平", "胜负",
    "平胜", "平平", "平负",
    "负胜", "负平", "负负"
]

def poisson_pmf(k, lmbda):
    if lmbda <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.pow(lmbda, k) * math.exp(-lmbda)) / math.factorial(k)

def compute_match_bqc(home, away, h_xg, a_xg, league="", num="", had_sp=None, official_bqc_sp=None):
    """
    计算单场赛事的 9 大半全场概率矩阵、公允赔率、市场赔率与期望值 EV
    """
    h_xg = max(0.4, float(h_xg))
    a_xg = max(0.4, float(a_xg))
    total_xg = h_xg + a_xg

    # 1. 战术攻防节奏与半场时间分片系数 (Half-Time Time-Slice Splitting)
    # 足球统计大数据：上半场进球占全场约 43%~46%，下半场因体能下降与战术搏命占 54%~57%
    h_first_ratio = 0.44
    a_first_ratio = 0.44

    # 战术特征识别
    is_home_heavy = (h_xg >= a_xg + 0.8)
    is_away_heavy = (a_xg >= h_xg + 0.8)
    is_tight = (abs(h_xg - a_xg) <= 0.35 and total_xg <= 2.5)

    if is_home_heavy:
        # 主队大优攻坚：客队往往深度收缩上半场死守，主队下半场发力
        h_first_ratio = 0.40
        rhythm_tag = "主队攻坚·下半场发力"
    elif is_away_heavy:
        a_first_ratio = 0.42
        rhythm_tag = "客队反客为主·后程施压"
    elif is_tight:
        # 强强对话或保级死拼：上半场谨慎试探，0-0 概率极高
        h_first_ratio = 0.38
        a_first_ratio = 0.38
        rhythm_tag = "强强谨慎·半场胶着"
    else:
        rhythm_tag = "均衡对攻·拉锯推进"

    l1 = h_xg * h_first_ratio
    m1 = a_xg * a_first_ratio
    l2 = h_xg * (1.0 - h_first_ratio)
    m2 = a_xg * (1.0 - a_first_ratio)

    # 2. 联合概率计算 (对半场与下半场分别积分)
    max_g = 5
    raw_probs = {k: 0.0 for k in BQC_KEYS}

    # 半场 0:0 纠偏因子 (Dixon-Coles HT correction, 实际足球中半场 0:0 出现率显著高于纯泊松独立性)
    ht_00_boost = 1.15 if is_tight else 1.08

    for x1 in range(max_g + 1):
        px1 = poisson_pmf(x1, l1)
        for y1 in range(max_g + 1):
            py1 = poisson_pmf(y1, m1)
            p_ht = px1 * py1
            if x1 == 0 and y1 == 0:
                p_ht *= ht_00_boost

            if x1 > y1:
                ht_res = "胜"
            elif x1 == y1:
                ht_res = "平"
            else:
                ht_res = "负"

            for x2 in range(max_g + 1):
                px2 = poisson_pmf(x2, l2)
                for y2 in range(max_g + 1):
                    py2 = poisson_pmf(y2, m2)
                    p_joint = p_ht * px2 * py2

                    tot_h = x1 + x2
                    tot_a = y1 + y2
                    if tot_h > tot_a:
                        ft_res = "胜"
                    elif tot_h == tot_a:
                        ft_res = "平"
                    else:
                        ft_res = "负"

                    key = ht_res + ft_res
                    raw_probs[key] += p_joint

    # 归一化
    norm_factor = sum(raw_probs.values())
    probs = {k: raw_probs[k] / norm_factor for k in BQC_KEYS}

    # 3. 赔率与 EV 映射 (中国竞彩抽水约 13%~15%)
    takeout_margin = 1.13
    bqc_matrix = []
    for k in BQC_KEYS:
        p = probs[k]
        fair_sp = round(1.0 / p, 2) if p > 0.001 else 99.0
        
        # 如果有官方抓取的半全场赔率则使用官方，否则采用标准定价体系反推
        if official_bqc_sp and k in official_bqc_sp and official_bqc_sp[k] > 1.0:
            mkt_sp = float(official_bqc_sp[k])
        else:
            # 基础竞彩估算赔率，加入低概率长尾保护
            mkt_sp = round(1.0 / (p * takeout_margin), 2) if p > 0.005 else (28.0 if "负胜" in k or "胜负" in k else 15.0)
            mkt_sp = max(1.18, min(mkt_sp, 45.0))

        ev = round((p * mkt_sp) - 1.0, 4)
        bqc_matrix.append({
            "key": k,
            "name": k,
            "prob": round(p, 4),
            "prob_pct": round(p * 100, 1),
            "fair_sp": fair_sp,
            "market_sp": mkt_sp,
            "ev": ev,
            "ev_pct": round(ev * 100, 1)
        })

    # 4. 遴选：首选正路 (Primary) 与 高赔价值潜伏 (Value Hedge)
    sorted_by_prob = sorted(bqc_matrix, key=lambda x: x["prob"], reverse=True)
    primary_pick = sorted_by_prob[0]

    # 寻找赔率 >= 3.40 且 EV 表现最佳的潜伏价值项
    high_odds_candidates = [item for item in bqc_matrix if item["market_sp"] >= 3.40 and item["key"] != primary_pick["key"]]
    if high_odds_candidates:
        value_hedge_pick = max(high_odds_candidates, key=lambda x: (x["ev"], x["prob"]))
    else:
        value_hedge_pick = sorted_by_prob[1]

    # 逆转冷门监控 (负胜 / 胜负)
    reversal_candidates = [item for item in bqc_matrix if item["key"] in ["负胜", "胜负"]]
    max_reversal = max(reversal_candidates, key=lambda x: x["prob"]) if reversal_candidates else None
    has_reversal_alert = max_reversal and max_reversal["prob"] >= 0.045

    # 5. 生成专业量化战术评述
    if primary_pick["key"] == "胜胜":
        rationale = f"主队整体战力呈碾压态势(xG {h_xg:.2f}:{a_xg:.2f})，抢开局意图强烈，上半场奠定领先概率达 {round((probs['胜胜']+probs['胜平']+probs['胜负'])*100, 1)}%，正路首选【胜胜 @{primary_pick['market_sp']}】。"
        if value_hedge_pick["key"] == "平胜":
            rationale += f" 若客队深度收缩死守，半场打平概率亦有储备，潜伏高性价比【平胜 @{value_hedge_pick['market_sp']}】实现双重防线覆盖。"
    elif primary_pick["key"] == "平平":
        rationale = f"双方战力均势且攻防谨慎(总xG {total_xg:.2f})，半场破门阻力极大，正路紧盯【平平 @{primary_pick['market_sp']}】；下半场变局重点关注【{value_hedge_pick['key']} @{value_hedge_pick['market_sp']}】。"
    elif primary_pick["key"] == "平胜":
        rationale = f"经典慢热攻坚盘，主队实力占优但进攻启动偏后半程，上半场胶着、下半场换人提速打破僵局，首推高赔黄金项【平胜 @{primary_pick['market_sp']}】。"
    elif primary_pick["key"] == "负负":
        rationale = f"客队反客为主战意极强(xG {a_xg:.2f})，主队防线漏洞显著，首选正路锁定【负负 @{primary_pick['market_sp']}】。"
    else:
        rationale = f"半全场矩阵呈多极化离散，核心主选【{primary_pick['key']} @{primary_pick['market_sp']}】，高赔补充【{value_hedge_pick['key']} @{value_hedge_pick['market_sp']}】构建对冲组合。"

    return {
        "num": num,
        "home": home,
        "away": away,
        "league": league,
        "h_xg": h_xg,
        "a_xg": a_xg,
        "rhythm_tag": rhythm_tag,
        "primary_pick": primary_pick,
        "value_hedge_pick": value_hedge_pick,
        "matrix": bqc_matrix,
        "has_reversal_alert": has_reversal_alert,
        "reversal_info": max_reversal if has_reversal_alert else None,
        "rationale": rationale
    }

def batch_compute_bqc(matches):
    """
    批量计算赛事列表的半全场预测
    """
    results = []
    for m in matches:
        num = m.get("num", "")
        home = m.get("home", "")
        away = m.get("away", "")
        league = m.get("league", "")
        h_xg = m.get("h_xg", 1.25)
        a_xg = m.get("a_xg", 1.10)
        had_sp = m.get("had_sp", [2.0, 3.2, 3.5])
        
        bqc_obj = compute_match_bqc(home, away, h_xg, a_xg, league, num, had_sp)
        results.append(bqc_obj)
    return results

if __name__ == "__main__":
    demo = compute_match_bqc("AC米兰", "莱切", 1.95, 0.65, league="意甲", num="周日015")
    print("Match:", demo["home"], "vs", demo["away"])
    print("Rhythm:", demo["rhythm_tag"])
    print("Primary:", demo["primary_pick"])
    print("Value Hedge:", demo["value_hedge_pick"])
    print("Rationale:", demo["rationale"])
