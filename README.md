# 竞彩足球量化预测与错价猎杀系统 (Football Quantitative Edge Model)

一套完全**独立于博彩市场隐含概率**的物理真实概率建模与市场错价发现量化系统。

---

## 核心设计哲学

### 1. 为什么要和市场隐含概率完全无关？
绝大多数彩民与初级软件习惯看“赔率变动、必发指数、初指终指”。这本质上是在观测**市场共识（Market Sentiment）**与**资金投注流向**。然而：
* 庄家赔率是平衡资金、规避自身赔付风险、赚取抽水佣金的商业报价，并非客观物理概率。
* 一旦用赔率作为特征训练模型，你预测的只是“市场会开出什么”，而非“球赛真实会怎么踢”，永远不可能发现市场错误。
* 本系统采用纯粹的**赛场物理数据（进球数、攻防评级、主客场效应、时间衰减半衰期）**建立**独立客观概率模型**，作为真正的物理基准（Ground Truth）。

### 2. 怎么对比赔率找错价、造 Edge？
1. **真实物理概率**: 通过改进型 **Dixon-Coles (1997)** 双变量泊松模型，估算任意两队对抗的比分联合概率矩阵 $P(x, y)$，进而衍生出常规胜平负、让球胜平负、大小球等物理概率 $P_{\text{model}}$。
2. **市场去水基准 (De-vigging)**: 利用 **Shin 算法** 剥离竞彩或海外权威机构的抽水与“热门-冷门偏差”，得到市场视角的无偏预期 $P_{\text{fair}}$。
3. **期望收益 (Expected Value, EV) 与 Edge 发现**:
   $$\text{EV} = P_{\text{model}} \times \text{Odds} - 1$$
   * 当 $\text{EV} > 0$ 时，代表该下注项具备数学正期望，属于被市场低估的**错价（Mispriced Odds）**。
   * 竞彩返还率一般在 87%~89% 左右（抽水达 11%~13%），只有当两队实际战力差距或冷门概率被公众严重扭曲时，才会涌现超高正期望。
4. **竞彩 2串1 复合正期望放大机制**:
   对于两场独立的错价赛事，组合 2串1 的复合期望收益为：
   $$\text{EV}_{\text{parlay}} = (1 + \text{EV}_1)(1 + \text{EV}_2) - 1$$
   当且仅当每一腿都是真实正期望时，2串1 会成倍放大 Edge！
5. **仓位管理 (Kelly Criterion)**:
   采用 **15% 分数凯利公式 (Fractional Kelly)** 结合单一注单最大风险敞口约束，彻底避免破产风险与模型估计误差。

---

## 系统目录结构

* [`internal_football_api.py`](file:///C:/Users/dzh18352505718/.gemini/antigravity/scratch/football_quant_model/internal_football_api.py): **最新足球 API SDK** (Base URL: `http://47.99.155.27:8321`)，完整封装 27 条接口，包含日期防坑转换 (`dd/mm/yyyy`)、Pinnacle/Bet365 原生逐家盘口解析、xG 与 CLV 走势拉取。
* [`scanner_with_internal_api.py`](file:///C:/Users/dzh18352505718/.gemini/antigravity/scratch/football_quant_model/scanner_with_internal_api.py): **实战全景错价扫描流水线**，联动赛程、赛前 xG 预期、Pinnacle 去水公允概率与聪明资金 CLV 走势，自动输出正期望注单。
* [`footystats_client.py`](file:///C:/Users/dzh18352505718/.gemini/antigravity/scratch/football_quant_model/footystats_client.py): **FootyStats 官方 API 客户端**，支持拉取海外真实 xG 与比赛攻防指标。
* [`dixon_coles.py`](file:///C:/Users/dzh18352505718/.gemini/antigravity/scratch/football_quant_model/dixon_coles.py): **Dixon-Coles 泊松极大似然估计模型核心**，支持连续 xG 拟似然与低比分修正。
* [`market_engine.py`](file:///C:/Users/dzh18352505718/.gemini/antigravity/scratch/football_quant_model/market_engine.py): 赔率抽水解析、Shin 去水模型、全盘口 Edge 与 EV 自动扫描器。
* [`portfolio_kelly.py`](file:///C:/Users/dzh18352505718/.gemini/antigravity/scratch/football_quant_model/portfolio_kelly.py): 凯利资金管理与 2串1 优化引擎。
* [`run_footystats_pipeline.py`](file:///C:/Users/dzh18352505718/.gemini/antigravity/scratch/football_quant_model/run_footystats_pipeline.py): 基于 FootyStats 数据的生产流水线。
* [`run_demo.py`](file:///C:/Users/dzh18352505718/.gemini/antigravity/scratch/football_quant_model/run_demo.py): 端到端离线模拟演示脚本。

---

## 快速运行

### 运行国内专业足球 API 实时错价扫描流水线：
```powershell
cd "C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
# 传入你的有效 X-API-Token 运行：
python scanner_with_internal_api.py --token "你的真实Token"

# 若未传 token，系统将启动内置高仿真沙盒模式演示：
python scanner_with_internal_api.py
```


