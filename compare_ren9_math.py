import sys

# Force utf-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

# open ticket:
# 5 singles: 14(主), 9(客), 10(主), 3(客), 8(客)
# 4 doubles: 4(主+客), 12(客+平), 2(客+平), 5(客+主)
p_open_singles = [0.803, 0.776, 0.702, 0.660, 0.650]
p_open_doubles = [0.778, 0.773, 0.758, 0.766]

prob_open = 1.0
for p in p_open_singles + p_open_doubles:
    prob_open *= p

print(f"open 票面自估全中率: {prob_open:.4%}")

# Antigravity ticket:
# 5 singles: 14(主 81.0%), 9(客 74.0%), 10(主 68.0%), 6(主 66.5%), 3(客 62.0%)
# 4 doubles: 4(主+平 81.2%), 8(客+平 81.0%), 7(主+平 75.4%), 12(客+平 77.3%)
p_ag_singles = [0.810, 0.740, 0.680, 0.665, 0.620]
p_ag_doubles = [0.812, 0.810, 0.754, 0.773]

prob_ag = 1.0
for p in p_ag_singles + p_ag_doubles:
    prob_ag *= p

print(f"Antigravity 票面自估全中率: {prob_ag:.4%}")
print(f"全中概率对比: Antigravity ({prob_ag:.2%}) vs open ({prob_open:.2%})")
