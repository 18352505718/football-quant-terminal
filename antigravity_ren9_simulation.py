import os
import sys
import json
import numpy as np

# Force utf-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
with open(os.path.join(base_dir, "antigravity_independent_quant_results.json"), "r", encoding="utf-8") as f:
    quant_data = json.load(f)

# The 14 matches of 任9 26158:
# 1. 浦项制铁 vs 大阪钢巴 (亚冠)
# 2. 布里兰 vs 鹿岛鹿角 (亚冠)
# 3. 费内巴切 vs 利物浦 (欧冠)
# 4. 多特蒙德 vs 贝蒂斯 (欧冠)
# 5. 朗斯 vs 科莫 (欧冠)
# 6. 波尔图 vs 那不勒斯 (欧冠)
# 7. 埃因霍温 vs 布鲁日 (欧冠)
# 8. 莱比锡红牛 vs 曼城 (欧冠)
# 9. 斯拉维亚 vs 阿森纳 (欧冠)
# 10. 维京 vs 萨巴赫 (欧冠)
# 11. 加的夫 vs 西汉姆联 (英冠)
# 12. 雷克斯 vs 米德尔斯堡 (英冠)
# 13. 布里斯托尔城 vs 伍尔弗汉普顿 (英冠)
# 14. 弗拉门戈 vs 格雷米奥 (巴甲)

# Market devigged probabilities from open:
market_probs = {
    14: {"h": 80.3, "d": 12.7, "a": 6.9, "match": "弗拉门戈 vs 格雷米奥"},
    9:  {"h": 8.0,  "d": 14.4, "a": 77.6, "match": "斯拉维亚 vs 阿森纳"},
    10: {"h": 70.2, "d": 16.7, "a": 13.1, "match": "维京 vs 萨巴赫"},
    3:  {"h": 15.3, "d": 18.7, "a": 66.0, "match": "费内巴切 vs 利物浦"},
    8:  {"h": 16.7, "d": 18.3, "a": 65.0, "match": "莱比锡红牛 vs 曼城"},
    4:  {"h": 54.8, "d": 22.2, "a": 23.0, "match": "多特蒙德 vs 贝蒂斯"},
    12: {"h": 22.7, "d": 24.1, "a": 53.2, "match": "雷克斯 vs 米德尔斯堡"},
    2:  {"h": 24.2, "d": 24.7, "a": 51.0, "match": "布里兰 vs 鹿岛鹿角"},
    5:  {"h": 27.9, "d": 23.4, "a": 48.7, "match": "朗斯 vs 科莫"},
    11: {"h": 29.0, "d": 23.8, "a": 47.2, "match": "加的夫 vs 西汉姆联"},
    6:  {"h": 46.7, "d": 25.4, "a": 27.9, "match": "波尔图 vs 那不勒斯"},
    7:  {"h": 45.7, "d": 22.8, "a": 31.5, "match": "埃因霍温 vs 布鲁日"},
    13: {"h": 28.5, "d": 27.2, "a": 44.3, "match": "布里斯托尔城 vs 伍尔弗汉普顿"},
    1:  {"h": 30.8, "d": 27.0, "a": 42.2, "match": "浦项制铁 vs 大阪钢巴"}
}

# Antigravity Model Probabilities (calibrated Dixon-Coles + physical metrics):
# For matches in quant_reports:
# #3 (周三004): 费内巴切 vs 利物浦 -> Calibrated: 利物浦客胜 ~ 62%, 平 21%, 主 17%
# #4 (周三008): 多特蒙德 vs 贝蒂斯 -> 主 60.4%, 平 20.8%, 客 18.8%
# #5 (周三010): 朗斯 vs 科莫 -> 主 42.9%, 平 23.8%, 客 33.3%
# #6 (周三006): 波尔图 vs 那不勒斯 -> 主 66.5%, 平 19.5%, 客 13.9%
# #7 (周三007): 埃因霍温 vs 布鲁日 -> 主 55.2%, 平 20.2%, 客 24.6%
# #8 (周三005): 莱比锡 vs 曼城 -> 曼城客胜 ~ 60%, 平 21%, 主 19%
# #9 (周三011): 斯拉维亚 vs 阿森纳 -> 阿森纳客胜 ~ 74%, 平 16%, 主 10%
# #10 (周三009): 维京 vs 萨巴赫 -> 维京主胜 68.0%, 平 18%, 客 14%
# #13 (周三012): 布城 vs 狼队 -> 主 43.5%, 平 28.1%, 客 28.4%
# #14: 弗拉门戈 vs 格雷米奥 -> 主 81.0%, 平 12.5%, 客 6.5%

antigravity_probs = {
    14: {"h": 81.0, "d": 12.5, "a": 6.5,  "top1": 81.0, "opt": "主", "source": "巴甲常模"},
    9:  {"h": 10.0, "d": 16.0, "a": 74.0, "top1": 74.0, "opt": "客", "source": "欧冠分级"},
    10: {"h": 68.0, "d": 18.0, "a": 14.0, "top1": 68.0, "opt": "主", "source": "欧冠常模"},
    6:  {"h": 66.5, "d": 19.5, "a": 13.9, "top1": 66.5, "opt": "主", "source": "Dixon-Coles物理模型"},
    3:  {"h": 17.0, "d": 21.0, "a": 62.0, "top1": 62.0, "opt": "客", "source": "欧冠分级"},
    4:  {"h": 60.4, "d": 20.8, "a": 18.8, "top1": 60.4, "opt": "主", "source": "Dixon-Coles物理模型"},
    8:  {"h": 19.0, "d": 21.0, "a": 60.0, "top1": 60.0, "opt": "客", "source": "欧冠分级"},
    7:  {"h": 55.2, "d": 20.2, "a": 24.6, "top1": 55.2, "opt": "主", "source": "Dixon-Coles物理模型"},
    12: {"h": 22.7, "d": 24.1, "a": 53.2, "top1": 53.2, "opt": "客", "source": "英冠市场"},
    2:  {"h": 24.2, "d": 24.7, "a": 51.0, "top1": 51.0, "opt": "客", "source": "亚冠市场"},
    13: {"h": 43.5, "d": 28.1, "a": 28.4, "top1": 43.5, "opt": "主", "source": "Dixon-Coles物理模型"},
    5:  {"h": 42.9, "d": 23.8, "a": 33.3, "top1": 42.9, "opt": "主", "source": "Dixon-Coles物理模型"},
    11: {"h": 29.0, "d": 23.8, "a": 47.2, "top1": 47.2, "opt": "客", "source": "英冠市场"},
    1:  {"h": 30.8, "d": 27.0, "a": 42.2, "top1": 42.2, "opt": "客", "source": "亚冠市场"}
}

print("=== 14 场比赛在 Antigravity 模型下的排序 ===")
sorted_ag = sorted(antigravity_probs.items(), key=lambda x: x[1]["top1"], reverse=True)
for idx, (num, data) in enumerate(sorted_ag, 1):
    m_name = market_probs[num]["match"]
    m_top = max(market_probs[num]["h"], market_probs[num]["d"], market_probs[num]["a"])
    diff = data["top1"] - m_top
    print(f"#{idx:02d} [第{num:02d}场] {m_name:24s} | 模型Top1: {data['opt']} {data['top1']:.1f}% (市场: {m_top:.1f}%, 差异: {diff:+.1f}pp) | 来源: {data['source']}")

# Compare Top 9 selection:
open_top9 = [14, 9, 10, 3, 8, 4, 12, 2, 5]
ag_top9 = [k for k, v in sorted_ag[:9]]

print(f"\nopen 的 Top 9: {open_top9}")
print(f"Antigravity 的 Top 9: {ag_top9}")
print(f"两方重合场次: {set(open_top9).intersection(set(ag_top9))}")
print(f"open 选了但 Antigravity 弃选: {set(open_top9) - set(ag_top9)}")
print(f"Antigravity 选了但 open 弃选: {set(ag_top9) - set(open_top9)}")
