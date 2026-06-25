# CET-4 难度分析 Prompt 模板

> **代码文件**: `services/ai_gateway.py`（主用，含6套模板） / `ai_gateway.py`（备用，含4套旧版）
> **调用链**: `difficulty/__init__.py` → `services/difficulty_analyzer.py` → `services/ai_gateway.py`
> **所有 Prompt 集中管理，便于修改和版本控制。每个题型含 5 级 Few-shot 校准（L1-L5），L3 = 典型 CET-4。**

---

## 基础 Prompt（SYSTEM_PROMPT_BASE）

所有题型共享，定义 AI 角色和行为约束。

```
你是一位资深大学英语四六级命题专家和心理测量学专家。
你的任务是分析一道英语题目，从多个维度评估其难度，输出严格的JSON格式结果。
每个维度打分范围为1-5，1=最简单，5=最困难。
评分必须严格参照以下Few-shot校准示例的尺度，确保1-5全量程覆盖。
注意：评分应结合CET-4/CET-6考试的实际水平进行区分。
只返回JSON，不要添加任何额外解释。
```

**参数说明：**
- `temperature = 0.2` — 控制输出随机性，越低越稳定
- `max_tokens = 1000` — 单次 API 调用的最大输出长度
- `response_format = {"type": "json_object"}` — 强制 JSON 输出

---

## 1. 写作 (Writing) — 5 维度

### 维度说明

| 维度 | 1 | 2 | 3 (典型CET-4) | 4 | 5 |
|------|---|---|---------------|----|----|
| abstractness（主题抽象度） | 个人日常/具象事物 | 校园生活/人际交往 | 社会现象/公共议题 | 抽象概念/制度思辨 | 哲学/理论高度 |
| vocabulary_level（题干词汇难度） | 全A1/A2基础词 | 少量B1词 | B1-B2为主 | 多B2-C1词 | 大量C1+学术词汇 |
| syntax_complexity（句式复杂度） | 简单句/并列句 | 含状语从句 | 含1-2类从句 | 多类从句嵌套 | 倒装/虚拟/多层级嵌套 |
| constraint_count（限定约束数量） | 1个 | 2个 | 3个 | 4个 | 5个及以上 |
| knowledge_burden（知识背景依赖） | 纯个人经验 | 校园常识 | 社会热点认知 | 专业领域入门知识 | 深厚专业/理论背景 |

### 权重配置

```json
{"abstractness": 0.25, "vocabulary_level": 0.20, "syntax_complexity": 0.20, "constraint_count": 0.20, "knowledge_burden": 0.15}
```

### 返回 JSON

```json
{"abstractness":1-5,"vocabulary_level":1-5,"syntax_complexity":1-5,"constraint_count":1-5,"knowledge_burden":1-5,"overall":1-5,"reasoning":"一句话总结"}
```

### 5 级校准示例

**L1 — 基础**
> 题目: Describe your favorite season and explain what activities you enjoy doing during that season.
> 评分: {"abstractness":1,"vocabulary_level":1,"syntax_complexity":1,"constraint_count":1,"knowledge_burden":1,"overall":1}
> 理由: 纯个人日常话题（季节/活动），全A1-A2基础词汇，简单句/并列句即可应对，仅1个约束（describe+explain合并为开放式提示），依赖纯个人生活经验。

**L2 — 进阶**
> 题目: Write a short letter to your friend, inviting him or her to attend your birthday party this weekend. Tell them when and where the party will be held.
> 评分: {"abstractness":1,"vocabulary_level":1,"syntax_complexity":2,"constraint_count":3,"knowledge_burden":1,"overall":2}
> 理由: 日常社交话题（邀请信），A2词汇为主，需简单时间状语从句和地点说明，3个约束（letter形式/invite/tell when+where），无需背景知识。

**L3 — 中等（典型CET-4）**
> 题目: Suppose your university is conducting a survey on students' satisfaction with campus canteen services. You are asked to write an essay to describe the current situation and give your suggestions for improvement. You should write at least 120 words but no more than 180 words.
> 评分: {"abstractness":2,"vocabulary_level":2,"syntax_complexity":3,"constraint_count":4,"knowledge_burden":2,"overall":3}
> 理由: 社会功能评论（食堂服务评价），B1-B2词汇（satisfaction/canteen/suggestions/improvement），需描述+建议双重结构，4个约束（suppose/survey/describe+suggest/字数上下限），需校园生活认知。

**L4 — 较难**
> 题目: Some people believe that the widespread use of social media has negatively affected young people's ability to form meaningful relationships. Others argue that social media helps people stay connected in ways never before possible. Discuss both views and give your own opinion. You should write at least 150 words but no more than 200 words.
> 评分: {"abstractness":3,"vocabulary_level":3,"syntax_complexity":4,"constraint_count":5,"knowledge_burden":3,"overall":4}
> 理由: 社会争议话题（社交媒体利弊），B2-C1词汇（widespread/negatively/meaningful relationships/connected），需平衡论述+个人观点三重结构，含对比/因果从句，5个约束（both views/discuss/opinion/150/200），需社会观察和辩证思维能力。

**L5 — 困难**
> 题目: The concept of "lifelong learning" has become increasingly important in today's rapidly changing job market. Some argue that formal education should focus on teaching students how to learn independently rather than transmitting specific knowledge. To what extent do you agree or disagree with this view? Support your argument with reasons and examples. You should write at least 200 words.
> 评分: {"abstractness":4,"vocabulary_level":4,"syntax_complexity":5,"constraint_count":5,"knowledge_burden":4,"overall":5}
> 理由: 抽象教育哲学话题（终身学习vs知识传授），大量B2-C1抽象词汇（concept/lifelong/increasingly/transmitting/independently），需多层级论证（现象→观点→立场→理由→例证），含虚拟语气/倒装/多重复句，5个约束，需教育理论和社会发展趋势认知。

---

## 2. 听力 (Listening) — 8 维度

> 听力难度通常比阅读低1级。

### 维度说明

| 维度 | 1 | 2 | 3 (典型CET-4) | 4 | 5 |
|------|---|---|---------------|----|----|
| vocabulary_level | 全A1/A2口语 | 含B1词 | B1-B2为主 | 多B2-C1词 | 密集C1+ |
| syntax_complexity | 短口语句 | 含简单从句 | 含2类从句 | 多类从句嵌套 | 超长嵌套+插入结构 |
| speech_rate_factor | 缓慢有停顿 | 正常语速 | 标准新闻语速 | 较快正式语速 | 极快信息密集 |
| information_density | 稀疏无数据 | 简单数据 | 有数字/专名/机构 | 多数据点+多主体 | 超高密度跨领域 |
| question_complexity | 直接细节 | 简单数字匹配 | 单步推断 | 综合推断 | 深层概括+论点提炼 |
| option_vocabulary | 全A1/A2词 | 含B1词 | 含B2词 | 多B2-C1词 | 大量C1+词 |
| distractor_strength | 明显无关 | 简单混淆 | 部分迷惑需区分 | 高度相似 | 极近微妙差别 |
| memory_load | 2句内 | 短段落 | 跨3-4句 | 跨全段 | 跨全段+多信息点精确记忆 |

### 权重配置

```json
{"vocabulary_level": 0.15, "syntax_complexity": 0.10, "speech_rate_factor": 0.10, "information_density": 0.10, "question_complexity": 0.10, "option_vocabulary": 0.08, "distractor_strength": 0.17, "memory_load": 0.20}
```

### 返回 JSON

```json
{"vocabulary_level":1-5,"syntax_complexity":1-5,"speech_rate_factor":1-5,"information_density":1-5,"question_complexity":1-5,"option_vocabulary":1-5,"distractor_strength":1-5,"memory_load":1-5,"overall":1-5,"reasoning":"一句话总结"}
```

### 5 级校准示例

**L1 — 基础**
> 听力原文: Woman: Excuse me, where can I find the English books? Man: They are on the second floor, next to the reading room. Woman: Thank you very much. Man: You're welcome.
> 题目: 1. Where does the woman want to go? A) The reading room B) The second floor English section C) The library entrance D) The study area
> 评分: {"vocabulary_level":1,"syntax_complexity":1,"speech_rate_factor":1,"information_density":1,"question_complexity":1,"option_vocabulary":1,"distractor_strength":1,"memory_load":1,"overall":1}
> 理由: 全A1日常词汇，超短句无从句，对话极短(4轮)语速缓慢，无数字/专名，直接细节题，选项全A1词，干扰项明显，信息集中在2句内。

**L2 — 进阶**
> 听力原文: A new bike-sharing program has been launched on campus this semester. Students can rent a bicycle for just one yuan per hour by scanning a QR code with their smartphones. The bikes are available at ten different locations around the university, including the main gate, the library, and all dormitory areas.
> 题目: 2. How much does it cost to rent a bike for one hour? A) Nothing, it's free B) One yuan C) Five yuan D) Ten yuan
> 评分: {"vocabulary_level":2,"syntax_complexity":2,"speech_rate_factor":1,"information_density":2,"question_complexity":1,"option_vocabulary":1,"distractor_strength":2,"memory_load":2,"overall":2}
> 理由: A2-B1词汇（bike-sharing/launched/semester/scanning），含简单不定式和定语从句，校园广播语速适中，有数量(1元/10处)，直接数字细节题，选项全基础词，干扰项为零和其他数字需精准记忆，信息分散在3句中。

**L3 — 中等（典型CET-4）**
> 听力原文: A recent study conducted by researchers at the University of Cambridge has revealed that students who engage in regular physical exercise three times a week score on average 12 percent higher on memory tests compared to those who lead a largely sedentary lifestyle. The study, which tracked over 800 participants across a two-year period, found that exercise increases blood flow to the hippocampus. Dr. Sarah Mitchell noted that even moderate activities such as brisk walking for 30 minutes produced measurable improvements in cognitive function.
> 题目: 3. What did the Cambridge study find about the relationship between exercise and memory? A) Exercise only benefits older adults B) Regular exercise is linked to better memory performance C) Walking is more effective than running D) Memory improvement requires intense workouts
> 评分: {"vocabulary_level":3,"syntax_complexity":3,"speech_rate_factor":2,"information_density":3,"question_complexity":3,"option_vocabulary":2,"distractor_strength":3,"memory_load":3,"overall":3}
> 理由: B1-B2词汇（conducted/engage/participants/sedentary/hippocampus/cognitive），含定语从句和宾语从句，标准新闻语速，有数字(12%/800/2年/30分钟)和机构(Cambridge)及人名，需推断因果非直接细节，选项有B1词，干扰项需区分原文未提及信息。

**L4 — 较难**
> 听力原文: The International Labor Organization has released its annual Global Employment Trends report, painting a complex picture of the world's job market. According to the report, global unemployment is projected to rise from 5.1 percent to 5.7 percent over the next biennium, with developing economies expected to bear a disproportionate share of the impact. The report identifies automation, trade tensions, and the lingering effects of the pandemic as the primary drivers. However, it also highlights emerging opportunities in renewable energy, digital services, and healthcare, expected to generate approximately 180 million new positions globally by 2028. ILO Director-General Gilbert Houngbo emphasized the urgent need for governments to invest in reskilling programs.
> 题目: 4. What is the ILO's main recommendation for addressing the employment challenge? A) Reducing trade tensions B) Increasing automation C) Investing in reskilling programs D) Creating more renewable energy jobs
> 评分: {"vocabulary_level":4,"syntax_complexity":4,"speech_rate_factor":4,"information_density":5,"question_complexity":3,"option_vocabulary":3,"distractor_strength":4,"memory_load":4,"overall":4}
> 理由: 密集B2-C1词汇（biennium/disproportionate/lingering/emerging/exacerbate/cohesion），含多重定语从句/分词结构，较快正式报告语速，密集信息（机构/人名/多百分比/180M/2028），需区分文末"urgent need"建议与其他罗列因素。

**L5 — 困难**
> 听力原文: The unprecedented convergence of demographic shifts, technological disruption, and climate imperatives is fundamentally reconfiguring the architecture of global labor markets at a pace that has surpassed the capacity of most institutional frameworks to adapt. According to a comprehensive meta-analysis in the Journal of Economic Perspectives, the phenomenon of "skills obsolescence"—whereby the half-life of professional competencies has contracted from approximately 15 years in the 1980s to merely 4 years today—is particularly pronounced in knowledge-intensive sectors such as information technology, biotechnology, and financial engineering. The study's authors postulate that this trajectory necessitates a paradigm shift from front-loaded education models toward a continuum of lifelong micro-credentials.
> 题目: 5. What fundamental change do the study's authors argue is necessary? A) Increasing investment in biotechnology B) Moving from one-time education to ongoing skill certification C) Strengthening coordination between governments D) Extending the half-life of professional competencies
> 评分: {"vocabulary_level":5,"syntax_complexity":5,"speech_rate_factor":5,"information_density":5,"question_complexity":5,"option_vocabulary":5,"distractor_strength":5,"memory_load":5,"overall":5}
> 理由: 大量C1+学术词汇（unprecedented/convergence/demographic/imperatives/reconfiguring/obsolescence/paradigm/trajectory/continuum/supranational），超多层嵌套从句+破折号插入解释，极快学术语速，超高密度（多概念/数据对比15→4年/多领域），需从复杂论证中提炼"paradigm shift from X toward Y"的核心论点。

---

## 3. 选词填空 (Banked Cloze / Reading Section A) — 8 维度

> CET-4 特征：一篇短文 200-250 词，留 10 个空（题号 26-35），提供 15 个词（A-O）作为词库，每词最多用一次。考察词汇辨析、语法搭配和上下文理解。

### 维度说明

| 维度 | 1 | 2 | 3 (典型CET-4) | 4 | 5 |
|------|---|---|---------------|----|----|
| vocabulary_level（原文词汇难度） | 全A1/A2 | 含B1词 | B1-B2为主 | 多B2-C1词 | 密集C1+学术词汇 |
| wordbank_difficulty（词库词汇难度） | 全高频基础词 | 含B1词 | B1-B2为主，含近义词 | 多B2-C1，词性多样 | 大量C1+低频词，多词性混淆 |
| syntax_complexity（句式复杂度） | 短简单句 | 含简单从句 | 含2类从句 | 多层从句嵌套 | 复杂嵌套+特殊结构 |
| context_dependency（上下文依赖度） | 单句即可判断 | 前后1句 | 跨2-3句推断 | 跨段落理解 | 全文综合理解 |
| grammatical_complexity（语法考点难度） | 单一名词/动词 | 形容词/副词 | 词性转换+固定搭配 | 虚拟/倒装/分词 | 复合语法+语义双重判断 |
| distractor_strength（干扰项强度） | 词性明显不同 | 词性相同语义远 | 同词性+近义需区分 | 近义词+形近词混淆 | 多词性+近义+形近综合 |
| information_density（信息密度） | 稀疏 | 适中 | 正常学术密度 | 较密集 | 高度密集 |
| passage_familiarity（话题熟悉度） | 日常话题 | 校园生活 | 科普/社会话题 | 专业学科话题 | 高度专业/冷门话题 |

### 权重配置

```json
{"vocabulary_level": 0.15, "wordbank_difficulty": 0.20, "syntax_complexity": 0.10, "context_dependency": 0.15, "grammatical_complexity": 0.15, "distractor_strength": 0.10, "information_density": 0.05, "passage_familiarity": 0.10}
```

### 返回 JSON

```json
{"vocabulary_level":1-5,"wordbank_difficulty":1-5,"syntax_complexity":1-5,"context_dependency":1-5,"grammatical_complexity":1-5,"distractor_strength":1-5,"information_density":1-5,"passage_familiarity":1-5,"overall":1-5,"reasoning":"一句话总结"}
```

### 5 级校准示例

**L1 — 基础**
> 原文: Tom is a student. He ___ to school every day. A) go B) goes C) going D) gone. 词库: [go, goes, going, gone, walk, runs, ...]
> 评分: {"vocabulary_level":1,"wordbank_difficulty":1,"syntax_complexity":1,"context_dependency":1,"grammatical_complexity":1,"distractor_strength":1,"information_density":1,"passage_familiarity":1,"overall":1}
> 理由: 全A1词汇，词库全高频基础词，简单句，单句第三人称单数即可判断，语法仅考察主谓一致，干扰项为同一动词不同形式（仅语法区别），日常话题。

**L2 — 进阶**
> 原文: College students today face increasing ___ to find jobs after graduation. Many of them feel anxious about their future careers. A) pressure B) pleasure C) measure D) treasure. 词库: [pressure, pleasure, measure, treasure, stress, anxiety, ...]
> 评分: {"vocabulary_level":2,"wordbank_difficulty":2,"syntax_complexity":2,"context_dependency":1,"grammatical_complexity":1,"distractor_strength":2,"information_density":2,"passage_familiarity":2,"overall":2}
> 理由: A2-B1词汇，词库含B1词和形近词（pressure/pleasure/measure/treasure），含简单从句，单句+语义判断（"face increasing ___" + "feel anxious"），名词选择考察搭配，干扰项为同词性形近词，校园话题。

**L3 — 中等（典型CET-4）**
> 原文: The traditional 9-to-5 work schedule may not be ___ for everyone, as scientists have discovered that individuals have different "chronotypes" — natural ___ for being active at certain times of the day. Some people, known as "early birds," ___ best in the morning, while "night owls" reach their ___ productivity later. 词库: A) optimal B) preferences C) perform D) peak E) flexible F) significant G) patterns H) decline I) maintain J) reduce K) tend L) relatively M) efficiency N) demonstrate O) generally
> 评分: {"vocabulary_level":3,"wordbank_difficulty":3,"syntax_complexity":3,"context_dependency":2,"grammatical_complexity":3,"distractor_strength":3,"information_density":3,"passage_familiarity":3,"overall":3}
> 理由: B1-B2词汇为主（optimal/chronotypes/preferences/peak），词库15词含B1-B2级别+近义词，含宾语从句和对比结构，需跨2-3句推断（chronotypes→preferences关联），考察形容词选择+固定搭配+动词辨析，干扰项含同词性近义词和形近词，科普话题（生物钟研究）。

**L4 — 较难**
> 原文: The ___ of artificial intelligence in the workplace has ___ considerable debate regarding its ___ impact on employment. While previous technological revolutions ___ displaced manual labor, AI systems are increasingly ___ of performing cognitive tasks. A ___ analysis by McKinsey estimates that 400 million workers could be ___ by 2030, though 250 million new jobs may be ___ . 词库: A) advancement B) sparked C) potential D) primarily E) capable F) comprehensive G) displaced H) created I) fundamentally J) assessment K) technological L) transformation M) significantly N) emergence O) substantially
> 评分: {"vocabulary_level":4,"wordbank_difficulty":4,"syntax_complexity":3,"context_dependency":3,"grammatical_complexity":4,"distractor_strength":4,"information_density":4,"passage_familiarity":3,"overall":4}
> 理由: B2-C1词汇（advancement/sparked/comprehensive/displaced/capable/substantially），词库多B2-C1词+词性多样（名词/动词/形容词/副词混合），含while对比+that定语从句，需跨段落理解AI对就业的复杂影响，考察被动语态+动词搭配+副词修饰，干扰项含同词性近义词。

**L5 — 困难**
> 原文: The precautionary principle, which ___ in environmental ethics, has evolved into a ___ yet influential framework. The principle ___ that the ___ of proof falls on ___ of an activity to demonstrate it does not cause ___ harm. Proponents argue this is ___ for addressing risks characterized by ___ and scientific uncertainty. Detractors counter that it ___ innovation by imposing an ___ evidentiary burden. 词库: A) originated B) contentious C) posits D) burden E) proponents F) disproportionate G) indispensable H) irreversibility I) stifles J) insurmountable K) regulatory L) consensus M) ecological N) inherently O) paradigm
> 评分: {"vocabulary_level":5,"wordbank_difficulty":5,"syntax_complexity":4,"context_dependency":4,"grammatical_complexity":5,"distractor_strength":5,"information_density":5,"passage_familiarity":5,"overall":5}
> 理由: 密集C1+学术词汇（precautionary/ethics/contentious/posits/proponents/disproportionate/irreversibility/insurmountable），词库全C1+词汇+多词性混淆（名词/形容词/动词混合），含定语从句+同位语+分词结构，需跨领域理解（环境伦理→监管政策→创新影响），考察虚拟语气+固定搭配+专业术语辨析，干扰项高度精密，专业政策话题。

---

## 4. 段落匹配 (Paragraph Matching / Reading Section B) — 8 维度

> CET-4 特征：一篇长文 800-1000 词，分 A-L 共 10-12 段，10 条匹配语句（题号 36-45）。考察信息定位、同义转述和快速阅读能力。

### 维度说明

| 维度 | 1 | 2 | 3 (典型CET-4) | 4 | 5 |
|------|---|---|---------------|----|----|
| vocabulary_level（原文词汇） | 全A1/A2 | 含B1词 | B1-B2为主 | 多B2-C1词 | 密集C1+学术词汇 |
| syntax_complexity（句式复杂度） | 短简单句 | 含简单从句 | 含2类从句 | 多层从句嵌套 | 复杂嵌套+插入结构 |
| passage_length（文章长度） | <300词 | 300-500词 | 500-800词 | 800-1000词 | >1000词 |
| paragraph_count（段落数量） | <5段 | 5-7段 | 8-10段 | 11-13段 | >13段 |
| paraphrase_difficulty（同义转述难度） | 原文原词匹配 | 简单同义词替换 | 词组级转述 | 句式级改写 | 抽象概括+跨段综合 |
| information_scatter（信息分散度） | 集中在一处 | 2处关键信息 | 多段含相关线索 | 全篇分散需筛选 | 多段交叉+干扰信息 |
| distractor_similarity（干扰段落相似度） | 主题明显不同 | 有相似但不混淆 | 2-3段主题相近 | 多段内容高度相似 | 几乎每段都有迷惑性 |
| topic_familiarity（话题熟悉度） | 日常话题 | 校园生活 | 科普/社会话题 | 专业学科话题 | 高度专业/冷门话题 |

### 权重配置

```json
{"vocabulary_level": 0.15, "syntax_complexity": 0.10, "passage_length": 0.10, "paragraph_count": 0.05, "paraphrase_difficulty": 0.25, "information_scatter": 0.15, "distractor_similarity": 0.10, "topic_familiarity": 0.10}
```

### 返回 JSON

```json
{"vocabulary_level":1-5,"syntax_complexity":1-5,"passage_length":1-5,"paragraph_count":1-5,"paraphrase_difficulty":1-5,"information_scatter":1-5,"distractor_similarity":1-5,"topic_familiarity":1-5,"overall":1-5,"reasoning":"一句话总结"}
```

### 5 级校准示例

**L1 — 基础**
> 原文(3段): A. Tom is a student. He likes sports. B. Tom plays basketball every day. C. Tom also enjoys swimming in summer.
> 题目: 36. Tom likes to do sports activities regularly. → (B)
> 评分: {"vocabulary_level":1,"syntax_complexity":1,"passage_length":1,"paragraph_count":1,"paraphrase_difficulty":1,"information_scatter":1,"distractor_similarity":1,"topic_familiarity":1,"overall":1}
> 理由: 全A1词汇，短简单句，篇幅极短仅3段，匹配语句与原文几乎原词对应，信息集中，无干扰段落，日常话题。

**L2 — 进阶**
> 原文(6段): A. Many students feel stressed about exams. B. Regular exercise can reduce stress levels. C. The university gym offers free classes. D. Yoga is especially popular among female students. E. Running is the most accessible form of exercise. F. A healthy diet also contributes to academic performance.
> 题目: 37. Physical activity helps lower anxiety related to academic tests. → (B)
> 评分: {"vocabulary_level":2,"syntax_complexity":2,"passage_length":2,"paragraph_count":1,"paraphrase_difficulty":2,"information_scatter":1,"distractor_similarity":2,"topic_familiarity":2,"overall":2}
> 理由: A2-B1词汇，含简单从句，6段短篇，匹配语句需同义转述（"Physical activity"→"exercise"），信息集中，仅D/E段略有相似，校园话题。

**L3 — 中等（典型CET-4）**
> 原文(9段，约600词): A. The sharing economy has transformed multiple industries... B. Ride-sharing platforms like Uber and Lyft have disrupted traditional taxi services... C. In the accommodation sector, Airbnb has challenged the hotel industry... D. Critics argue that these platforms often bypass regulations... E. Workers in the gig economy lack traditional employment benefits... F. Some cities have imposed restrictions on short-term rentals... G. Proponents highlight the flexibility and entrepreneurial opportunities... H. The environmental impact of the sharing economy remains debated... I. Future regulations will likely shape the trajectory of these platforms...
> 题目: 40. Some urban areas have limited the operation of home-sharing services. → (F)
> 评分: {"vocabulary_level":3,"syntax_complexity":3,"passage_length":3,"paragraph_count":3,"paraphrase_difficulty":3,"information_scatter":2,"distractor_similarity":3,"topic_familiarity":3,"overall":3}
> 理由: B1-B2词汇为主（transformed/disrupted/bypass/gig economy/entrepreneurial），含定语从句和宾语从句，9段约600词，匹配需句式级转述（"urban areas have limited"→"cities have imposed restrictions"），C/F/I段主题相近需区分，社会热点话题。

**L4 — 较难**
> 原文(12段，约900词，生态学): A. The relationship between biodiversity and ecosystem stability... B. Early research by MacArthur proposed that species richness enhances resilience... C. Recent meta-analyses have largely corroborated this hypothesis... D. However, the mechanisms remain contentious... E. Some emphasize functional diversity over species count... F. Keystone species exert disproportionate influence... G. Climate change introduces unprecedented stressors... H. Habitat fragmentation compounds species loss... I. Marine ecosystems exhibit different patterns... J. Restoration ecology applies these principles... K. Economic valuation adds policy urgency... L. Interdisciplinary approaches are needed...
> 题目: 43. The importance of certain species goes far beyond their numerical proportion in the community. → (F)
> 评分: {"vocabulary_level":4,"syntax_complexity":4,"passage_length":4,"paragraph_count":4,"paraphrase_difficulty":4,"information_scatter":3,"distractor_similarity":4,"topic_familiarity":4,"overall":4}
> 理由: 密集B2-C1学术词汇（biodiversity/ecosystem/resilience/corroborated/keystone/disproportionate/fragmentation/restoration/interdisciplinary），12段约900词，匹配需抽象概括（"importance beyond numerical proportion"→"disproportionate influence"→"keystone species"），D/E/F段生态机制高度相似需精细区分，专业学科话题。

**L5 — 困难**
> 原文(14段，约1100词，阿尔茨海默病分子机制): A. The etiology and pathophysiology of Alzheimer disease represent a formidable challenge in contemporary neurology... B. Amyloid-beta plaques have historically dominated the etiological narrative, with the amyloid cascade hypothesis positing that accumulation of these protein aggregates triggers a pathogenic cascade... C. However, the repeated failure of anti-amyloid therapeutics in phase III trials has prompted a fundamental reconsideration... D. Tau pathology, specifically hyperphosphorylation and aggregation into neurofibrillary tangles, has emerged as an alternative framework... E. The spatial and temporal progression of tau pathology, as mapped by Braak staging, correlates more closely with clinical symptom severity than amyloid burden... F. Recent advances in neuroimaging, particularly tau-PET ligands, have enabled in vivo tracking of tau deposition... G. Microglial activation and neuroinflammatory responses have been identified as critical mediators... H. Genome-wide association studies have identified over 70 risk loci... I. The emerging consensus posits a multi-factorial model... J. Sleep disruption has been identified as a potential upstream driver of amyloid accumulation... K. ApoE4 genotype remains the strongest genetic risk factor... L. The failure of single-target approaches has motivated combinatorial strategies... M. Lifestyle interventions show modest but consistent epidemiological benefit... N. The convergence of molecular pathology, systems biology, and computational neuroscience promises more integrated understanding...
> 题目: 41. The spatial distribution pattern of tau protein pathology has been shown to align more accurately with patients' cognitive decline compared to amyloid plaque deposition. → (E)
> 评分: {"vocabulary_level":5,"syntax_complexity":5,"passage_length":5,"paragraph_count":5,"paraphrase_difficulty":5,"information_scatter":5,"distractor_similarity":5,"topic_familiarity":5,"overall":5}
> 理由: 大量C1+医学/神经科学学术词汇（etiology/pathophysiology/amyloid/hyperphosphorylation/neurofibrillary/ligands/propagation/glymphatic/genome-wide/combinatorial），超多层嵌套从句+专业术语密集+被动语态+分词结构，14段超长文超1100词跨多个子话题（蛋白假说/基因/影像/炎症/睡眠/治疗），需跨多段综合理解，D/E/F/G/H五段主题高度相似（tau/amyloid/炎症/基因/多因素）极难区分，高度专业医学研究话题。

---

## 5. 仔细阅读 (Careful Reading / Reading Section C) — 8 维度

> CET-4 特征：2 篇短文（各 300-400 词），每篇 5 道选择题（题号 46-55）。考察深度理解、推理判断和细节定位。

### 维度说明

| 维度 | 1 | 2 | 3 (典型CET-4) | 4 | 5 |
|------|---|---|---------------|----|----|
| vocabulary_level | 全A1/A2 | 含B1词 | B1-B2为主 | 多B2-C1词 | 密集C1+学术词汇 |
| syntax_complexity | 短简单句 | 含简单从句 | 含2类从句 | 多层从句嵌套 | 复杂嵌套+插入+特殊结构 |
| cohesion_difficulty（篇章连贯难度） | 线性叙述 | 列举/递进 | 转折/对比 | 多观点交织 | 复杂跨领域指代链 |
| information_density | 稀疏无数据 | 有1-2个数字/专名 | 有数据+机构 | 多数据+多术语 | 密集数据+跨领域术语 |
| question_complexity | 原文原句细节 | 简单同义转换 | 单步推断 | 综合推断 | 深层抽象+跨段综合 |
| option_vocabulary | 全A1/A2词 | 含B1词 | 含B2词 | 多B2-C1词 | 大量C1+词 |
| distractor_strength | 明显无关 | 数字/方向混淆 | 部分迷惑需区分 | 高度相似需精细分析 | 极近微妙差别 |
| location_difficulty（定位难度） | 直接定位原句 | 定位同义表达 | 需识别同义转述 | 需跨句综合 | 跨段推断+多源信息融合 |

### 权重配置

```json
{"vocabulary_level": 0.20, "syntax_complexity": 0.15, "cohesion_difficulty": 0.10, "information_density": 0.10, "question_complexity": 0.10, "option_vocabulary": 0.08, "distractor_strength": 0.17, "location_difficulty": 0.10}
```

### 返回 JSON

```json
{"vocabulary_level":1-5,"syntax_complexity":1-5,"cohesion_difficulty":1-5,"information_density":1-5,"question_complexity":1-5,"option_vocabulary":1-5,"distractor_strength":1-5,"location_difficulty":1-5,"overall":1-5,"reasoning":"一句话总结"}
```

### 5 级校准示例

**L1 — 基础**
> 原文: Tom is a 10-year-old boy. He likes sports very much. After school, he always goes to the playground to play basketball with his classmates. He also enjoys swimming in summer. His mother says sports are good for his health.
> 题目: 1. What does Tom like to do after school? A) Do homework B) Play basketball C) Watch TV D) Cook dinner
> 评分: {"vocabulary_level":1,"syntax_complexity":1,"cohesion_difficulty":1,"information_density":1,"question_complexity":1,"option_vocabulary":1,"distractor_strength":1,"location_difficulty":1,"overall":1}
> 理由: 全A1/A2基础词汇，超短简单句，线性叙述无指代无转折，无任何数据/专名/术语，直接细节题原文原句可答，选项全A1词且明显无关，答案在首句直接定位。

**L2 — 进阶**
> 原文: Many college students today face increasing pressure to find jobs after graduation. A recent report shows that over 60 percent of graduating seniors worry about their career prospects. Some universities have started offering career counseling services to help students prepare for the job market.
> 题目: 2. According to the passage, what percentage of seniors worry about finding jobs? A) Less than 30 percent B) About 50 percent C) Over 60 percent D) Nearly 90 percent
> 评分: {"vocabulary_level":2,"syntax_complexity":2,"cohesion_difficulty":1,"information_density":2,"question_complexity":1,"option_vocabulary":1,"distractor_strength":2,"location_difficulty":1,"overall":2}
> 理由: A2-B1词汇（pressure/graduation/prospects/counseling），含简单定语从句，有百分比数字(60%)，直接细节题数字定位，选项全基础词，干扰项为相近数字需区分(30/50/60/90)。

**L3 — 中等（典型CET-4）**
> 原文: A growing body of research suggests that the traditional 9-to-5 work schedule may not be optimal for everyone. Scientists have discovered that individuals have different "chronotypes" — natural preferences for being active at certain times of the day. Some people, known as "early birds," perform best in the morning, while "night owls" reach their peak productivity later in the day. Companies that allow flexible working hours report higher employee satisfaction and a 15 percent increase in overall productivity, according to a study published in the Journal of Occupational Health.
> 题目: 3. What does the study published in the Journal of Occupational Health indicate? A) Traditional schedules work best for most employees B) Flexible hours lead to higher satisfaction and productivity C) Early birds are more productive than night owls D) Night owls should change their sleep habits
> 评分: {"vocabulary_level":3,"syntax_complexity":3,"cohesion_difficulty":2,"information_density":3,"question_complexity":2,"option_vocabulary":2,"distractor_strength":3,"location_difficulty":3,"overall":3}
> 理由: B1-B2词汇为主（optimal/chronotypes/preferences/productivity/satisfaction），含宾语从句/定语从句/对比结构，有专业术语(chronotypes)和期刊名，需根据研究结论推断，干扰项A与原文立场相反、C偷换概念、D过度推断，定位需在末尾句找到期刊名对应信息。

**L4 — 较难**
> 原文: The rapid advancement of artificial intelligence has sparked intense debate among economists regarding its potential impact on employment patterns. While previous technological revolutions primarily displaced manual labor, AI systems are increasingly capable of performing cognitive tasks. A comprehensive analysis by the McKinsey Global Institute estimates that by 2030, approximately 400 million workers could be displaced by automation. However, the report also emphasizes that this same shift is projected to create roughly 250 million new jobs in fields that do not yet exist, suggesting that the net effect depends largely on education and government policies to facilitate workforce transition.
> 题目: 4. What does the McKinsey report suggest about the future impact of AI on employment? A) Jobs lost will definitely exceed those created B) Manual labor is more threatened than cognitive work C) The overall outcome depends on education and policy responses D) Most new jobs will require advanced degrees in technology
> 评分: {"vocabulary_level":4,"syntax_complexity":4,"cohesion_difficulty":3,"information_density":4,"question_complexity":3,"option_vocabulary":3,"distractor_strength":4,"location_difficulty":4,"overall":4}
> 理由: 大量B2-C1词汇（advancement/sparked/revolution/displaced/cognitive/comprehensive/facilitate/transition），多层嵌套从句，有具体机构(McKinsey)和数据(400M/250M/2030)，需综合两处数据对比推断结论，干扰项A用"definitely"绝对化扭曲原文、B与原文相反、C正确、D"most"过度概括。

**L5 — 困难**
> 原文: The precautionary principle, which originated in environmental ethics during the 1970s, has evolved into a contentious yet influential framework in regulatory policy. At its core, the principle posits that in the absence of scientific consensus, the burden of proof falls on proponents of an activity—rather than its critics—to demonstrate that it does not cause disproportionate harm to public welfare or ecological systems. Proponents argue this framework is indispensable for addressing complex risks characterized by irreversibility and scientific uncertainty, such as genetic modification and climate engineering. Detractors counter that the principle is inherently conservative, stifling technological innovation by imposing an insurmountable evidentiary burden that effectively paralyzes progress in fields ranging from pharmaceutical development to nanotechnology.
> 题目: 5. Which of the following best describes the critics' main objection to the precautionary principle? A) It lacks a clear definition in regulatory contexts B) It places too much emphasis on environmental concerns over human welfare C) It imposes impossible proof requirements that hinder innovation D) It has been rendered obsolete by advances in risk assessment methodology
> 评分: {"vocabulary_level":5,"syntax_complexity":5,"cohesion_difficulty":5,"information_density":5,"question_complexity":4,"option_vocabulary":5,"distractor_strength":5,"location_difficulty":5,"overall":5}
> 理由: 密集C1+学术词汇（precautionary/ethics/contentious/regulatory/consensus/proponents/disproportionate/irreversibility/insurmountable/paralyzes/nanotechnology），多层嵌套从句+同位语+破折号插入+分词结构，复杂因果链（环境伦理→监管原则→正方→反方）和多专业领域指代，需精准区分批评者观点（detractors counter that）区别于支持者观点，干扰项A利用"definition"原文未讨论、C正确需理解"insurmountable evidentiary burden→paralyzes→stifling innovation"、D用"obsolete"与原文"still influential"矛盾。

---

## 6. 翻译 (Translation) — 5 维度

> 分析中文源文本翻译成英文的难度。使用 CEFR 等级评估所需英文词汇水平。

### 维度说明

| 维度 | 1 | 2 | 3 (典型CET-4) | 4 | 5 |
|------|---|---|---------------|----|----|
| vocabulary_level（所需英文CEFR等级） | A1基础词 | A2-B1日常词汇 | B1-B2一般书面语 | B2-C1书面语+专业术语 | 成语/文言/哲学专名 |
| syntax_complexity（中文句式复杂度） | 独立简单句 | 简单因果/并列复句 | 偏正复句+递进 | 多重关系复句+引用 | 多重复句+文言+排比递进 |
| semantic_abstraction（语义抽象度） | 纯具象行为描述 | 具象+简单说明 | 社会现象/趋势概括 | 抽象理念/专业概念 | 高度哲学/政治抽象 |
| cultural_load（文化负载度） | 零文化元素 | 常识级文化 | 社会文化现象 | 传统文化+专业概念 | 深层国学/政治哲学 |
| logic_chain（逻辑链复杂度） | 单线罗列 | 简单因果 | 因果递进链 | 多线因果+理论论证 | 多层嵌套因果+历史脉络+理论升华 |

### 权重配置

```json
{"vocabulary_level": 0.30, "syntax_complexity": 0.25, "semantic_abstraction": 0.20, "cultural_load": 0.15, "logic_chain": 0.10}
```

### 返回 JSON

```json
{"vocabulary_level":1-5,"syntax_complexity":1-5,"semantic_abstraction":1-5,"cultural_load":1-5,"logic_chain":1-5,"overall":1-5,"reasoning":"一句话总结"}
```

### 5 级校准示例

**L1 — 基础**
> 中文源文: 我喜欢运动。我每天跑步半小时。运动让我身体健康。
> 评分: {"vocabulary_level":1,"syntax_complexity":1,"semantic_abstraction":1,"cultural_load":1,"logic_chain":1,"overall":1}
> 理由: 全A1基础词，三个独立简单句无连接词无从句，纯具象行为描述，零文化负载，单线罗列无因果连接。

**L2 — 进阶**
> 中文源文: 中国的茶文化有着悠久的历史。很多人喜欢在空闲时间喝茶，因为茶不仅味道好，而且对健康有益。在一些地方，人们还会用茶来招待客人。
> 评分: {"vocabulary_level":2,"syntax_complexity":2,"semantic_abstraction":1,"cultural_load":2,"logic_chain":2,"overall":2}
> 理由: A2-B1词汇（悠久/历史/空闲/味道/健康/招待/客人），含简单因果复句（因为/而且），具象描述饮茶习惯，有中国文化元素但为常识级别，简单因果链。

**L3 — 中等（典型CET-4）**
> 中文源文: 随着互联网技术的快速发展，移动支付已经成为中国人日常生活中不可或缺的一部分。无论是在大型商场购物，还是在街边小摊买早餐，人们都可以用手机轻松完成支付。这种便捷的支付方式不仅改变了人们的消费习惯，也推动了传统商业模式的转型升级。
> 评分: {"vocabulary_level":3,"syntax_complexity":3,"semantic_abstraction":2,"cultural_load":3,"logic_chain":3,"overall":3}
> 理由: B1-B2书面语词汇（互联网/移动支付/不可或缺/便捷/消费/转型/升级），含偏正复句+递进（随着/无论...都/不仅...也），有社会现象抽象，中国当代社会文化元素需解释性翻译，多层因果链。

**L4 — 较难**
> 中文源文: 中医药学凝聚着中华民族数千年的健康养生理念及其实践经验，是中国古代科学的瑰宝。它以整体观念和辨证论治为核心，强调"治未病"的预防理念，主张通过调整人体的阴阳平衡来达到治疗目的。近年来，随着"一带一路"倡议的推进，中医药已传播到全球180多个国家和地区，成为中外人文交流的重要纽带。
> 评分: {"vocabulary_level":4,"syntax_complexity":4,"semantic_abstraction":4,"cultural_load":4,"logic_chain":4,"overall":4}
> 理由: B2-C1词汇（凝聚/瑰宝/辨证论治/阴阳/纽带），含多重复句+引用术语+并列分述，抽象概念密集（整体观念/阴阳平衡/预防理念/人文交流），深度文化依赖（中医术语+专名"治未病"/"一带一路"需标准化译法），复杂逻辑链。

**L5 — 困难**
> 中文源文: "大道之行也，天下为公"是中华文明自古以来的政治理想，体现了先贤对公平正义社会的不懈追求。这一思想源远流长，从孔子"不患寡而患不均"的分配伦理，到孟子"民为贵，社稷次之"的民本主张，再到顾炎武"天下兴亡，匹夫有责"的责任意识，构成了中国知识分子一脉相承的精神图谱。在当代语境下，这一传统智慧与社会主义核心价值观交相辉映，彰显了中华优秀传统文化创造性转化的时代意义。
> 评分: {"vocabulary_level":5,"syntax_complexity":5,"semantic_abstraction":5,"cultural_load":5,"logic_chain":5,"overall":5}
> 理由: 大量成语/文言引语（天下为公/不患寡而患不均/民为贵社稷次之/天下兴亡匹夫有责/源远流长/一脉相承/交相辉映），多重复句+三重引用嵌套+排比递进，高度抽象政治哲学概念（分配伦理/民本思想/精神图谱/创造性转化），极度文化依赖需深厚国学知识才能找到恰当的英文对应，超多层逻辑链（总纲→孔子→孟子→顾炎武→传统脉络→当代价值→时代意义）。

---

## 附录

### 题型映射表

| 题型 | TYPE_PROMPTS 键名 | DB type 字段值 | CET-4 Section | 题号范围 |
|------|------------------|---------------|---------------|---------|
| 写作 | 写作 | 写作, essay, writing | Part I Writing | 1 |
| 听力 | 听力 | 听力, listening | Part II Listening A/B/C | 2-26 |
| 选词填空 | 选词填空 | 选词填空, fill, cloze | Part III Reading A | 27-36 |
| 段落匹配 | 段落匹配 | 段落匹配, matching | Part III Reading B | 37-46 |
| 仔细阅读 | 仔细阅读, 阅读 | 仔细阅读, reading, 阅读 | Part III Reading C | 47-56 |
| 翻译 | 翻译 | 翻译, translation | Part IV Translation | 57 |

> **注意**: `仔细阅读` 和 `阅读` 共享相同的 READING_PROMPT 模板和权重配置。`"阅读"` 用于兼容数据库中的旧值。

### 调用参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `temperature` | 0.2 | 控制输出随机性，越低越稳定 |
| `max_tokens` | 1000 | 单次 API 调用的最大输出长度 |
| `content` 截断 | 2500 字符 | 超出部分截断以降低 API 延迟 |
| `AI_CONCURRENCY` | 30（环境变量） | 并发 AI 分析线程数 |
| `batch_commit` | 每 100 题 | 批量写入数据库的分批提交间隔 |
