import sys
sys.path.append(r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model")
sys.path.append(r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model\web_dashboard")
from bivariate_nb_model import BivariateNBModel

nb = BivariateNBModel(dispersion_r=6.0)

matches = [
    {"num": "周五001", "league": "澳超", "home": "悉尼FC", "away": "中央海岸", "had": [1.34, 4.35, 6.15], "hhad": ["-1", 2.10, 3.55, 2.62]},
    {"num": "周五002", "league": "德乙", "home": "不伦瑞克", "away": "科特布斯", "had": [1.74, 3.82, 3.30], "hhad": ["-1", 3.10, 3.75, 1.82]},
    {"num": "周五003", "league": "瑞超", "home": "哈马比", "away": "埃夫斯堡", "had": [1.22, 5.15, 8.00], "hhad": ["-1", 1.82, 3.60, 3.20]},
    {"num": "周五004", "league": "法乙", "home": "蒙彼利埃", "away": "梅斯", "had": [1.69, 3.55, 3.77], "hhad": ["-1", 3.10, 3.55, 1.87]},
    {"num": "周五005", "league": "荷甲", "home": "威廉二世", "away": "兹沃勒", "had": [2.82, 3.48, 2.01], "hhad": ["+1", 1.60, 3.90, 3.87]},
    {"num": "周五006", "league": "荷乙", "home": "奥斯", "away": "瓦尔韦克", "had": [3.70, 3.75, 1.66], "hhad": ["+1", 1.93, 3.65, 2.88]},
    {"num": "周五007", "league": "德甲", "home": "汉堡", "away": "门兴", "had": [2.20, 3.35, 2.59], "hhad": ["-1", 4.60, 4.00, 1.49]},
    {"num": "周五008", "league": "意甲", "home": "威尼斯", "away": "乌迪内斯", "had": [2.16, 3.30, 2.68], "hhad": ["-1", 4.62, 3.90, 1.50]},
    {"num": "周五009", "league": "法甲", "home": "图卢兹", "away": "斯特拉斯", "had": [1.84, 3.60, 3.15], "hhad": ["-1", 3.40, 3.80, 1.72]},
    {"num": "周五010", "league": "英超", "home": "埃弗顿", "away": "考文垂", "had": [1.43, 3.98, 5.30], "hhad": ["-1", 2.48, 3.32, 2.30]},
    {"num": "周五011", "league": "英冠", "home": "德比郡", "away": "博尔顿", "had": [2.33, 3.32, 2.45], "hhad": ["-1", 4.90, 4.15, 1.44]},
    {"num": "周五012", "league": "西甲", "home": "塞维利亚", "away": "阿拉维斯", "had": [1.70, 3.17, 4.25], "hhad": ["-1", 3.55, 3.10, 1.87]},
    {"num": "周五013", "league": "葡超", "home": "法马利康", "away": "阿罗卡", "had": [2.00, 3.15, 3.12], "hhad": ["-1", 4.25, 3.65, 1.59]},
    {"num": "周五014", "league": "巴甲", "home": "维多利亚", "away": "弗鲁米嫩", "had": [2.69, 3.10, 2.25], "hhad": ["+1", 1.48, 3.88, 4.85]}
]

print("=== Friday Quant Breakdown ===")
for m in matches:
    h_sp, d_sp, a_sp = m['had']
    inv = (1/h_sp) + (1/d_sp) + (1/a_sp)
    p_h = round((1/h_sp)/inv, 3)
    p_d = round((1/d_sp)/inv, 3)
    p_a = round((1/a_sp)/inv, 3)
    
    h_xg = round(max(0.7, min(3.2, 1.35 * (p_h / (p_a + 0.001))**0.5)), 2)
    a_xg = round(max(0.6, min(3.0, 1.15 * (p_a / (p_h + 0.001))**0.5)), 2)
    
    line = m['hhad'][0]
    hh_sp, hd_sp, ha_sp = m['hhad'][1], m['hhad'][2], m['hhad'][3]
    
    # Check if HHAD has high cover
    # if line is +1, P(Home not lose) = p_h + p_d
    cover_plus1 = p_h + p_d if line == "+1" else 0
    
    print(f"[{m['num']}] {m['league']} {m['home']} vs {m['away']} | 胜率: 主{p_h*100:.1f}% 平{p_d*100:.1f}% 客{p_a*100:.1f}% | xG {h_xg}:{a_xg} | HAD[0]={h_sp} | 让球: {line} ({hh_sp}/{hd_sp}/{ha_sp})")
