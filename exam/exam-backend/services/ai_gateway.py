"""
AI 大模型网关 — DeepSeek 集成
4套分题型 Prompt 模板 + JSON 结构化解析 + 降级策略 + 并发调用
"""
import os
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
import httpx
from dotenv import load_dotenv

load_dotenv()

_shared_http = httpx.Client(
    limits=httpx.Limits(max_keepalive_connections=50, max_connections=200),
    timeout=httpx.Timeout(90.0, connect=15.0),
)

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    http_client=_shared_http,
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


# ═══════════════════════════════════════════════════════════
#  Prompt 模板
# ═══════════════════════════════════════════════════════════

SYSTEM_PROMPT_BASE = """你是一位资深大学英语四六级命题专家和心理测量学专家。
你的任务是分析一道英语题目，从多个维度评估其难度，输出严格的JSON格式结果。
每个维度打分范围为1-5，1=最简单，5=最困难。
评分必须严格参照以下Few-shot校准示例的尺度，确保1-5全量程覆盖。
注意：评分应结合CET-4/CET-6考试的实际水平进行区分。
只返回JSON，不要添加任何额外解释。"""

# ── 写作 Prompt ──
WRITING_PROMPT = """分析以下四级写作题目，从5个维度评估难度。
评分必须严格对照下列5级校准示例，每级都有明确标杆。

【5级校准示例（必读）】

<example difficulty=1>
题目: Describe your favorite season and explain what activities you enjoy doing during that season.
评分: {"abstractness":1,"vocabulary_level":1,"syntax_complexity":1,"constraint_count":1,"knowledge_burden":1,"overall":1}
理由: 纯个人日常话题（季节/活动），全A1-A2基础词汇，简单句/并列句即可应对，仅1个约束（describe+explain合并为开放式提示），依赖纯个人生活经验，幼儿级别。
</example>

<example difficulty=2>
题目: Write a short letter to your friend, inviting him or her to attend your birthday party this weekend. Tell them when and where the party will be held.
评分: {"abstractness":1,"vocabulary_level":1,"syntax_complexity":2,"constraint_count":3,"knowledge_burden":1,"overall":2}
理由: 日常社交话题（邀请信），A2词汇为主，需简单时间状语从句和地点说明，3个约束（letter形式/invite/tell when+where），无需背景知识。
</example>

<example difficulty=3>
题目: Suppose your university is conducting a survey on students' satisfaction with campus canteen services. You are asked to write an essay to describe the current situation and give your suggestions for improvement. You should write at least 120 words but no more than 180 words.
评分: {"abstractness":2,"vocabulary_level":2,"syntax_complexity":3,"constraint_count":4,"knowledge_burden":2,"overall":3}
理由: 社会功能评论（食堂服务评价），B1-B2词汇（satisfaction/canteen/suggestions/improvement），需描述+建议双重结构，4个约束（suppose/survey/describe+suggest/字数上下限），需校园生活认知。此为典型CET-4写作难度。
</example>

<example difficulty=4>
题目: Some people believe that the widespread use of social media has negatively affected young people's ability to form meaningful relationships. Others argue that social media helps people stay connected in ways never before possible. Discuss both views and give your own opinion. You should write at least 150 words but no more than 200 words.
评分: {"abstractness":3,"vocabulary_level":3,"syntax_complexity":4,"constraint_count":5,"knowledge_burden":3,"overall":4}
理由: 社会争议话题（社交媒体利弊），B2-C1词汇（widespread/negatively/meaningful relationships/connected），需平衡论述+个人观点三重结构，含对比/因果从句，5个约束（both views/discuss/opinion/150/200），需社会观察和辩证思维能力。
</example>

<example difficulty=5>
题目: The concept of "lifelong learning" has become increasingly important in today's rapidly changing job market. Some argue that formal education should focus on teaching students how to learn independently rather than transmitting specific knowledge. To what extent do you agree or disagree with this view? Support your argument with reasons and examples. You should write at least 200 words.
评分: {"abstractness":4,"vocabulary_level":4,"syntax_complexity":5,"constraint_count":5,"knowledge_burden":4,"overall":5}
理由: 抽象教育哲学话题（终身学习vs知识传授），大量B2-C1抽象词汇（concept/lifelong/increasingly/transmitting/independently），需多层级论证（现象→观点→立场→理由→例证），含虚拟语气/倒装/多重复句，5个约束，需教育理论和社会发展趋势认知。
</example>

【维度说明】
1. abstractness (主题抽象度):
   1=个人日常/具象事物  2=校园生活/人际交往  3=社会现象/公共议题  4=抽象概念/制度思辨  5=哲学/理论高度

2. vocabulary_level (题干词汇难度):
   1=全A1/A2基础词  2=少量B1词  3=B1-B2为主（典型CET-4）  4=多B2-C1词  5=大量C1+学术词汇

3. syntax_complexity (句式复杂度):
   1=简单句/并列句  2=含状语从句  3=含1-2类从句（典型CET-4）  4=多类从句嵌套  5=倒装/虚拟/多层级嵌套

4. constraint_count (限定约束数量):
   统计题目中独立要求（情景设定/写作目的/内容要点/字数下限/字数上限/格式要求等）
   1=1个  2=2个  3=3个  4=4个  5=5个及以上

5. knowledge_burden (知识背景依赖):
   1=纯个人经验  2=校园常识  3=社会热点认知  4=专业领域入门知识  5=深厚专业/理论背景

【题目内容】
{content}

返回JSON:
{"abstractness":1-5,"vocabulary_level":1-5,"syntax_complexity":1-5,"constraint_count":1-5,"knowledge_burden":1-5,"overall":1-5,"reasoning":"一句话总结"}"""

# ── 阅读 Prompt ──
READING_PROMPT = """分析以下四级阅读题，从8个维度评估难度。
评分必须严格对照下列5级校准示例，每级都有明确标杆。

【5级校准示例（必读）】

<example difficulty=1>
原文: Tom is a 10-year-old boy. He likes sports very much. After school, he always goes to the playground to play basketball with his classmates. He also enjoys swimming in summer. His mother says sports are good for his health.
题目: 1. What does Tom like to do after school? A) Do homework B) Play basketball C) Watch TV D) Cook dinner
评分: {"vocabulary_level":1,"syntax_complexity":1,"cohesion_difficulty":1,"information_density":1,"question_complexity":1,"option_vocabulary":1,"distractor_strength":1,"location_difficulty":1,"overall":1}
理由: 全A1/A2基础词汇（boy/like/sports/playground），超短简单句，线性叙述无指代无转折，无任何数据/专名/术语，直接细节题原文原句可答，选项全A1词且明显无关（homework不出现/cook不出现），答案在首句直接定位。
</example>

<example difficulty=2>
原文: Many college students today face increasing pressure to find jobs after graduation. A recent report shows that over 60 percent of graduating seniors worry about their career prospects. Some universities have started offering career counseling services to help students prepare for the job market. These services include resume writing workshops, mock interviews, and job search strategies. Students who participate in these programs report feeling more confident about their future.
题目: 2. According to the passage, what percentage of seniors worry about finding jobs? A) Less than 30 percent B) About 50 percent C) Over 60 percent D) Nearly 90 percent
评分: {"vocabulary_level":2,"syntax_complexity":2,"cohesion_difficulty":1,"information_density":2,"question_complexity":1,"option_vocabulary":1,"distractor_strength":2,"location_difficulty":1,"overall":2}
理由: A2-B1词汇（pressure/graduation/prospects/counseling），含简单定语从句，线性叙述有列举，含百分比数字(60%)，直接细节题数字定位，选项全基础词，干扰项为相近数字需区分(30/50/60/90)，直接定位含数字句。
</example>

<example difficulty=3>
原文: A growing body of research suggests that the traditional 9-to-5 work schedule may not be optimal for everyone. Scientists have discovered that individuals have different "chronotypes" — natural preferences for being active at certain times of the day. Some people, known as "early birds," perform best in the morning hours, while "night owls" reach their peak productivity later in the day. Companies that allow flexible working hours report higher employee satisfaction and a 15 percent increase in overall productivity, according to a study published in the Journal of Occupational Health.
题目: 3. What does the study published in the Journal of Occupational Health indicate? A) Traditional schedules work best for most employees B) Flexible hours lead to higher satisfaction and productivity C) Early birds are more productive than night owls D) Night owls should change their sleep habits
评分: {"vocabulary_level":3,"syntax_complexity":3,"cohesion_difficulty":2,"information_density":3,"question_complexity":2,"option_vocabulary":2,"distractor_strength":3,"location_difficulty":3,"overall":3}
理由: B1-B2词汇为主（optimal/chronotypes/preferences/productivity/satisfaction），含宾语从句/定语从句/对比结构，有专业术语(chronotypes)和期刊名，需根据研究结论推断，选项有B1词（flexible/satisfaction/habits），干扰项A与原文立场相反、C偷换概念（early birds更productive未提及）、B正确、D过度推断未提及，定位需在末尾句找到期刊名对应信息。此为典型CET-4仔细阅读难度。
</example>

<example difficulty=4>
原文: The rapid advancement of artificial intelligence has sparked intense debate among economists regarding its potential impact on employment patterns. While previous technological revolutions primarily displaced manual labor, AI systems are increasingly capable of performing cognitive tasks that were once considered the exclusive domain of human intelligence. A comprehensive analysis by the McKinsey Global Institute estimates that by 2030, approximately 400 million workers worldwide could be displaced by automation. However, the report also emphasizes that this same technological shift is projected to create roughly 250 million new jobs in fields that do not yet exist, suggesting that the net effect depends largely on the capacity of educational systems and government policies to facilitate workforce transition.
题目: 4. What does the McKinsey report suggest about the future impact of AI on employment? A) The number of jobs lost will definitely exceed those created B) Manual labor is more threatened than cognitive work C) The overall outcome depends on education and policy responses D) Most new jobs will require advanced degrees in technology
评分: {"vocabulary_level":4,"syntax_complexity":4,"cohesion_difficulty":3,"information_density":4,"question_complexity":3,"option_vocabulary":3,"distractor_strength":4,"location_difficulty":4,"overall":4}
理由: 大量B2-C1词汇（advancement/sparked/revolution/displaced/cognitive/comprehensive/approximately/facilitate/transition），多层嵌套从句（while让步+that宾语+that定语+where定语），有具体机构(McKinsey)和数据(400M/250M/2030)，需综合两处数据对比推断结论而非直接找答案，选项含C1词汇（exceed/threatened/outcome），干扰项A用"definitely"绝对化扭曲原文化"largely depends"、B与原文"manual→cognitive"相反、C正确需理解末句、D"most"过度概括未提及。
</example>

<example difficulty=5>
原文: The precautionary principle, which originated in environmental ethics during the 1970s, has evolved into a contentious yet influential framework in regulatory policy. At its core, the principle posits that in the absence of scientific consensus, the burden of proof falls on proponents of an activity—rather than its critics—to demonstrate that it does not cause disproportionate harm to public welfare or ecological systems. Proponents argue this framework is indispensable for addressing complex risks characterized by irreversibility and scientific uncertainty, such as genetic modification and climate engineering. Detractors counter that the principle is inherently conservative, stifling technological innovation by imposing an insurmountable evidentiary burden that effectively paralyzes progress in fields ranging from pharmaceutical development to nanotechnology.
题目: 5. Which of the following best describes the critics' main objection to the precautionary principle? A) It lacks a clear definition in regulatory contexts B) It places too much emphasis on environmental concerns over human welfare C) It imposes impossible proof requirements that hinder innovation D) It has been rendered obsolete by advances in risk assessment methodology
评分: {"vocabulary_level":5,"syntax_complexity":5,"cohesion_difficulty":5,"information_density":5,"question_complexity":4,"option_vocabulary":5,"distractor_strength":5,"location_difficulty":5,"overall":5}
理由: 密集C1+学术词汇（precautionary/ethics/contentious/regulatory/consensus/proponents/disproportionate/irreversibility/insurmountable/paralyzes/nanotechnology），多层嵌套从句+同位语+破折号插入+分词结构，复杂因果链（环境伦理→监管原则→正方→反方）和多专业领域指代（环保/基因/气候/制药/纳米），需精准区分批评者观点（detractors counter that）区别于支持者观点，选项全C1词汇（regulatory/obsolete/methodology/imposes/hinder），干扰项A利用"definition"原文未讨论、B方向正确但"human welfare"原文为"public welfare"微妙不同、C正确需理解"insurmountable evidentiary burden→paralyzes→stifling innovation"、D用"obsolete"与原文"still influential"矛盾。
</example>

【维度说明】
1. vocabulary_level: 1=全A1/A2  2=含B1词  3=B1-B2为主(典型CET-4)  4=多B2-C1词  5=密集C1+学术词汇
2. syntax_complexity: 1=短简单句  2=含简单从句  3=含2类从句(典型CET-4)  4=多层从句嵌套  5=复杂嵌套+插入+特殊结构
3. cohesion_difficulty: 1=线性叙述  2=列举/递进  3=转折/对比(典型CET-4)  4=多观点交织  5=复杂跨领域指代链
4. information_density: 1=稀疏无数据  2=有1-2个数字/专名  3=有数据+机构(典型CET-4)  4=多数据+多术语  5=密集数据+跨领域术语
5. question_complexity: 1=原文原句细节  2=简单同义转换  3=单步推断(典型CET-4)  4=综合推断  5=深层抽象+跨段综合
6. option_vocabulary: 1=全A1/A2词  2=含B1词  3=含B2词(典型CET-4)  4=多B2-C1词  5=大量C1+词
7. distractor_strength: 1=明显无关  2=数字/方向混淆  3=部分迷惑需区分(典型CET-4)  4=高度相似需精细分析  5=极近微妙差别
8. location_difficulty: 1=直接定位原句  2=定位同义表达  3=需识别同义转述(典型CET-4)  4=需跨句综合  5=跨段推断+多源信息融合

【题目内容】
{content}

{content_structured}

返回JSON:
{"vocabulary_level":1-5,"syntax_complexity":1-5,"cohesion_difficulty":1-5,"information_density":1-5,"question_complexity":1-5,"option_vocabulary":1-5,"distractor_strength":1-5,"location_difficulty":1-5,"overall":1-5,"reasoning":"一句话总结"}"""

# ── 听力 Prompt ──
LISTENING_PROMPT = """分析以下四级听力题文本，从8个维度评估难度。听力难度通常比阅读低1级。
评分必须严格对照下列5级校准示例，每级都有明确标杆。

【5级校准示例（必读）】

<example difficulty=1>
听力原文: Woman: Excuse me, where can I find the English books? Man: They are on the second floor, next to the reading room. Woman: Thank you very much. Man: You're welcome.
题目: 1. Where does the woman want to go? A) The reading room B) The second floor English section C) The library entrance D) The study area
评分: {"vocabulary_level":1,"syntax_complexity":1,"speech_rate_factor":1,"information_density":1,"question_complexity":1,"option_vocabulary":1,"distractor_strength":1,"memory_load":1,"overall":1}
理由: 全A1日常词汇（find/floor/reading room），超短句无从句，对话极短(4轮)语速缓慢信息稀疏，无数字/专名，直接细节题，选项全A1词，干扰项A为对话中出现的非答案信息/C和D完全未提及/答案B直接对应原文，信息集中在2句内。
</example>

<example difficulty=2>
听力原文: A new bike-sharing program has been launched on campus this semester. Students can rent a bicycle for just one yuan per hour by scanning a QR code with their smartphones. The bikes are available at ten different locations around the university, including the main gate, the library, and all dormitory areas. The program aims to reduce traffic on campus and provide a convenient transportation option for students who live far from their classrooms.
题目: 2. How much does it cost to rent a bike for one hour? A) Nothing, it's free B) One yuan C) Five yuan D) Ten yuan
评分: {"vocabulary_level":2,"syntax_complexity":2,"speech_rate_factor":1,"information_density":2,"question_complexity":1,"option_vocabulary":1,"distractor_strength":2,"memory_load":2,"overall":2}
理由: A2-B1词汇（bike-sharing/launched/semester/scanning/locations/convenient/transportation），含简单不定式和定语从句，校园广播语速适中，有数量(1元/10处)但结构清晰，直接数字细节题，选项全基础词，干扰项为零和其他数字需精准记忆，信息分散在3句中需记住数字对应关系。
</example>

<example difficulty=3>
听力原文: A recent study conducted by researchers at the University of Cambridge has revealed that students who engage in regular physical exercise three times a week score on average 12 percent higher on memory tests compared to those who lead a largely sedentary lifestyle. The study, which tracked over 800 participants across a two-year period, found that exercise increases blood flow to the hippocampus, the region of the brain responsible for memory formation. Dr. Sarah Mitchell, the lead researcher, noted that even moderate activities such as brisk walking for 30 minutes produced measurable improvements in cognitive function.
题目: 3. What did the Cambridge study find about the relationship between exercise and memory? A) Exercise only benefits older adults B) Regular exercise is linked to better memory performance C) Walking is more effective than running D) Memory improvement requires intense workouts
评分: {"vocabulary_level":3,"syntax_complexity":3,"speech_rate_factor":2,"information_density":3,"question_complexity":3,"option_vocabulary":2,"distractor_strength":3,"memory_load":3,"overall":3}
理由: B1-B2词汇（conducted/engage/participants/sedentary/hippocampus/cognitive/moderate/measurable），含定语从句和宾语从句，标准新闻语速，有数字(12%/800/2年/30分钟)和机构(Cambridge)及人名，需推断因果而非直接细节，选项有B1词（benefits/effective/intense），干扰项A增加"older adults"原文未提、B正确需概括study发现、C比较walking vs running原文未做此比较、D与原文"moderate activities"矛盾。此为典型CET-4听力Section C难度。
</example>

<example difficulty=4>
听力原文: The International Labor Organization has released its annual Global Employment Trends report, painting a complex picture of the world's job market. According to the report, global unemployment is projected to rise from 5.1 percent to 5.7 percent over the next biennium, with developing economies expected to bear a disproportionate share of the impact. The report identifies automation, trade tensions, and the lingering effects of the pandemic as the primary drivers of this trend. However, it also highlights emerging opportunities in sectors such as renewable energy, digital services, and healthcare, which are expected to generate approximately 180 million new positions globally by 2028. ILO Director-General Gilbert Houngbo emphasized the urgent need for governments to invest in reskilling programs, warning that failure to do so could exacerbate existing inequalities and potentially undermine social cohesion in vulnerable regions.
题目: 4. What is the ILO's main recommendation for addressing the employment challenge? A) Reducing trade tensions between major economies B) Increasing automation in developing countries C) Investing in programs to teach workers new skills D) Creating more jobs in the renewable energy sector
评分: {"vocabulary_level":4,"syntax_complexity":4,"speech_rate_factor":4,"information_density":5,"question_complexity":3,"option_vocabulary":3,"distractor_strength":4,"memory_load":4,"overall":4}
理由: 密集B2-C1词汇（biennium/disproportionate/lingering/emerging/approximately/exacerbate/inequalities/cohesion/vulnerable），含多重定语从句/分词结构/that引导的警告，较快正式报告语速，密集信息（机构ILO/人名Gilbert Houngbo/多百分比/180M/2028/多行业/多原因），需区分文末"urgent need"建议与其他罗列因素，选项有B2词汇（economies/renewable/reskilling），干扰项A为文中因素非建议、B与原文"automation是威胁"相反、C正确需识别"reskilling=teach new skills"、D为机会非建议。
</example>

<example difficulty=5>
听力原文: The unprecedented convergence of demographic shifts, technological disruption, and climate imperatives is fundamentally reconfiguring the architecture of global labor markets at a pace that has surpassed the capacity of most institutional frameworks to adapt. According to a comprehensive meta-analysis published in the Journal of Economic Perspectives, the phenomenon of "skills obsolescence"—whereby the half-life of professional competencies has contracted from approximately 15 years in the 1980s to merely 4 years today—is particularly pronounced in knowledge-intensive sectors such as information technology, biotechnology, and financial engineering. The study's authors postulate that this trajectory necessitates a paradigm shift from front-loaded education models toward a continuum of lifelong micro-credentials, though they acknowledge that such a transformation would require unprecedented levels of coordination between sovereign regulatory bodies, multinational corporations, and supranational accreditation agencies.
题目: 5. What fundamental change do the study's authors argue is necessary? A) Increasing investment in biotechnology and financial engineering B) Moving from one-time education to ongoing skill certification C) Strengthening coordination between sovereign governments D) Extending the half-life of professional competencies
评分: {"vocabulary_level":5,"syntax_complexity":5,"speech_rate_factor":5,"information_density":5,"question_complexity":5,"option_vocabulary":5,"distractor_strength":5,"memory_load":5,"overall":5}
理由: 大量C1+学术词汇（unprecedented/convergence/demographic/disruption/imperatives/reconfiguring/surpassed/institutional/meta-analysis/obsolescence/competencies/contracted/paradigm/trajectory/continuum/supranational/accreditation），超多层嵌套从句+破折号插入解释+让步acknowledge，极快学术报告语速长句连读，超高密度（多概念嵌套/数据对比15→4年/多领域/多主体），需从复杂论证中提炼"paradigm shift from X toward Y"的核心论点，选项全C1词汇（biotechnology/sovereign/competencies/certification），干扰项A偷换举例为论点、B正确概括"front-loaded→continuum of micro-credentials"、C偷换手段为目标、D与原文趋势相反。
</example>

【维度说明】
1. vocabulary_level: 1=全A1/A2口语  2=含B1词  3=B1-B2为主(典型CET-4)  4=多B2-C1词  5=密集C1+
2. syntax_complexity: 1=短口语句  2=含简单从句  3=含2类从句(典型CET-4)  4=多类从句嵌套  5=超长嵌套+插入结构
3. speech_rate_factor: 1=缓慢有停顿  2=正常语速  3=标准新闻语速(典型CET-4)  4=较快正式语速  5=极快信息密集
4. information_density: 1=稀疏无数据  2=简单数据  3=有数字/专名/机构(典型CET-4)  4=多数据点+多主体  5=超高密度跨领域
5. question_complexity: 1=直接细节  2=简单数字匹配  3=单步推断(典型CET-4)  4=综合推断  5=深层概括+论点提炼
6. option_vocabulary: 1=全A1/A2词  2=含B1词  3=含B2词(典型CET-4)  4=多B2-C1词  5=大量C1+词
7. distractor_strength: 1=明显无关  2=简单混淆  3=部分迷惑需区分(典型CET-4)  4=高度相似  5=极近微妙差别
8. memory_load: 1=2句内  2=短段落  3=跨3-4句(典型CET-4)  4=跨全段  5=跨全段+多信息点精确记忆

【题目内容】
{content}

{content_structured}

返回JSON:
{"vocabulary_level":1-5,"syntax_complexity":1-5,"speech_rate_factor":1-5,"information_density":1-5,"question_complexity":1-5,"option_vocabulary":1-5,"distractor_strength":1-5,"memory_load":1-5,"overall":1-5,"reasoning":"一句话总结"}"""

# ── 选词填空 Prompt ──
CLOZE_PROMPT = """分析以下四级选词填空题（Reading Section A），从8个维度评估难度。
选词填空特征：一篇短文留10个空（26-35），提供A-O共15词词库，每词最多用一次。考察词汇辨析、语法搭配和上下文理解。
评分必须严格对照下列5级校准示例，每级都有明确标杆。

【5级校准示例（必读）】

<example difficulty=1>
原文: Tom is a student. He ___ to school every day. A) go B) goes C) going D) gone. [词库: go, goes, going, gone, walk, runs, play, reads, write, speaks, sing, dance, eat, sleep, study]
题目: 26. 选择正确答案填入空格
评分: {"vocabulary_level":1,"wordbank_difficulty":1,"syntax_complexity":1,"context_dependency":1,"grammatical_complexity":1,"distractor_strength":1,"information_density":1,"passage_familiarity":1,"overall":1}
理由: 全A1词汇，词库全高频基础词，简单句，单句第三人称单数即可判断，语法仅考察主谓一致，干扰项为同一动词不同形式（仅语法区别无词义混淆），日常话题。
</example>

<example difficulty=2>
原文: College students today face increasing ___ to find jobs after graduation. Many of them feel anxious about their future careers. [词库: pressure, pleasure, measure, treasure, stress, anxiety, future, career, market, education, success, failure, hope, dream, plan]
题目: 27. 选择正确答案填入空格
评分: {"vocabulary_level":2,"wordbank_difficulty":2,"syntax_complexity":2,"context_dependency":1,"grammatical_complexity":1,"distractor_strength":2,"information_density":2,"passage_familiarity":2,"overall":2}
理由: A2-B1词汇，词库含B1词和形近词（pressure/pleasure/measure/treasure），含简单从句，单句+语义判断（"face increasing ___" + "feel anxious"），名词选择考察搭配，干扰项为同词性形近词（-sure结尾），校园话题。
</example>

<example difficulty=3>
原文: The traditional 9-to-5 work schedule may not be ___ for everyone, as scientists have discovered that individuals have different "chronotypes" — natural ___ for being active at certain times of the day. Some people, known as "early birds," ___ best in the morning, while "night owls" reach their ___ productivity later. [词库: A) optimal B) preferences C) perform D) peak E) flexible F) significant G) patterns H) decline I) maintain J) reduce K) tend L) relatively M) efficiency N) demonstrate O) generally]
题目: 28-31. 选择正确答案填入空格
评分: {"vocabulary_level":3,"wordbank_difficulty":3,"syntax_complexity":3,"context_dependency":2,"grammatical_complexity":3,"distractor_strength":3,"information_density":3,"passage_familiarity":3,"overall":3}
理由: B1-B2词汇为主（optimal/chronotypes/preferences/peak），词库15词含B1-B2级别+近义词（optimal/best/peak同义方向，preferences/patterns非选词），含宾语从句和对比结构，需跨2-3句推断（chronotypes→preferences关联），考察形容词选择+固定搭配+动词辨析，干扰项含同词性近义词和形近词，科普话题（生物钟研究）。
</example>

<example difficulty=4>
原文: The ___ of artificial intelligence in the workplace has ___ considerable debate regarding its ___ impact on employment. While previous technological revolutions ___ displaced manual labor, AI systems are increasingly ___ of performing cognitive tasks. A ___ analysis by McKinsey estimates that 400 million workers could be ___ by 2030, though 250 million new jobs may be ___ . [词库: A) advancement B) sparked C) potential D) primarily E) capable F) comprehensive G) displaced H) created I) fundamentally J) assessment K) technological L) transformation M) significantly N) emergence O) substantially]
题目: 32-39. 选择正确答案填入空格
评分: {"vocabulary_level":4,"wordbank_difficulty":4,"syntax_complexity":3,"context_dependency":3,"grammatical_complexity":4,"distractor_strength":4,"information_density":4,"passage_familiarity":3,"overall":4}
理由: B2-C1词汇（advancement/sparked/comprehensive/displaced/capable/substantially），词库多B2-C1词+词性多样（名词/动词/形容词/副词混合），含while对比+that定语从句，需跨段落理解AI对就业的复杂影响，考察被动语态+动词搭配+副词修饰，干扰项含同词性近义词（primarily/significantly/substantially同义方向）。
</example>

<example difficulty=5>
原文: The precautionary principle, which ___ in environmental ethics, has evolved into a ___ yet influential framework. The principle ___ that the ___ of proof falls on ___ of an activity to demonstrate it does not cause ___ harm. Proponents argue this is ___ for addressing risks characterized by ___ and scientific uncertainty. Detractors counter that it ___ innovation by imposing an ___ evidentiary burden. [词库: A) originated B) contentious C) posits D) burden E) proponents F) disproportionate G) indispensable H) irreversibility I) stifles J) insurmountable K) regulatory L) consensus M) ecological N) inherently O) paradigm]
题目: 40-49. 选择正确答案填入空格
评分: {"vocabulary_level":5,"wordbank_difficulty":5,"syntax_complexity":4,"context_dependency":4,"grammatical_complexity":5,"distractor_strength":5,"information_density":5,"passage_familiarity":5,"overall":5}
理由: 密集C1+学术词汇，词库全C1+词汇+多词性混淆（名词:burden/proponents/consensus/paradigm，形容词:contentious/indispensable/insurmountable/regulatory/ecological，动词:originated/posits/stifles），含定语从句+同位语+分词结构，需跨领域理解（环境伦理→监管政策→创新影响），考察虚拟语气+固定搭配+专业术语辨析，干扰项高度精密，专业政策话题。
</example>

【维度说明】
1. vocabulary_level: 1=全A1/A2  2=含B1词  3=B1-B2为主(典型CET-4)  4=多B2-C1词  5=密集C1+学术词汇
2. wordbank_difficulty: 1=全高频基础词  2=含B1词  3=B1-B2+近义词(典型CET-4)  4=多B2-C1+词性多样  5=大量C1+低频词+多词性混淆
3. syntax_complexity: 1=短简单句  2=含简单从句  3=含2类从句(典型CET-4)  4=多层从句嵌套  5=复杂嵌套+特殊结构
4. context_dependency: 1=单句即可判断  2=前后1句  3=跨2-3句(典型CET-4)  4=跨段落理解  5=全文综合理解
5. grammatical_complexity: 1=单一词性选择  2=形容词/副词  3=词性转换+固定搭配(典型CET-4)  4=虚拟/倒装/分词  5=复合语法+语义双重判断
6. distractor_strength: 1=词性明显不同  2=同词性语义远  3=同词性+近义(典型CET-4)  4=近义+形近混淆  5=多词性+近义+形近综合
7. information_density: 1=稀疏  2=适中  3=正常学术密度(典型CET-4)  4=较密集  5=高度密集
8. passage_familiarity: 1=日常话题  2=校园生活  3=科普/社会(典型CET-4)  4=专业学科  5=高度专业/冷门

【题目内容】
{content}

{content_structured}

返回JSON:
{"vocabulary_level":1-5,"wordbank_difficulty":1-5,"syntax_complexity":1-5,"context_dependency":1-5,"grammatical_complexity":1-5,"distractor_strength":1-5,"information_density":1-5,"passage_familiarity":1-5,"overall":1-5,"reasoning":"一句话总结"}"""

# ── 段落匹配 Prompt ──
MATCHING_PROMPT = """分析以下四级段落匹配题（Reading Section B），从8个维度评估难度。
段落匹配特征：一篇长文分A-L共10-12段，10条匹配语句（36-45），需将每句匹配到对应段落。考察信息定位、同义转述和快速阅读能力。
评分必须严格对照下列5级校准示例，每级都有明确标杆。

【5级校准示例（必读）】

<example difficulty=1>
原文(3段): A. Tom is a student. He likes sports very much. B. Tom plays basketball with his friends every day after school. C. Tom also enjoys swimming in summer when the weather is hot.
题目: 36. Tom likes to do sports activities regularly. → (B)
评分: {"vocabulary_level":1,"syntax_complexity":1,"passage_length":1,"paragraph_count":1,"paraphrase_difficulty":1,"information_scatter":1,"distractor_similarity":1,"topic_familiarity":1,"overall":1}
理由: 全A1词汇，短简单句，篇幅极短仅3段，匹配语句与原文几乎原词对应（"plays basketball every day"→"sports activities regularly"为简单同义），信息集中，无干扰段落，日常话题。
</example>

<example difficulty=2>
原文(6段): A. Many students feel stressed about exams. B. Regular exercise can reduce stress levels significantly. C. The university gym offers free fitness classes. D. Yoga is especially popular among female students. E. Running is the most accessible form of exercise. F. A healthy diet also contributes to academic performance.
题目: 37. Physical activity helps lower anxiety related to academic tests. → (B)
评分: {"vocabulary_level":2,"syntax_complexity":2,"passage_length":2,"paragraph_count":1,"paraphrase_difficulty":2,"information_scatter":1,"distractor_similarity":2,"topic_familiarity":2,"overall":2}
理由: A2-B1词汇，含简单从句，6段短篇，匹配语句需词组级同义转述（"Physical activity"→"exercise"，"lower anxiety"→"reduce stress"，"academic tests"→"exams"），信息集中，仅D/E段略有相似但可区分，校园话题。
</example>

<example difficulty=3>
原文(9段，约600词): A. The sharing economy has transformed multiple industries over the past decade... B. Ride-sharing platforms like Uber and Lyft have disrupted traditional taxi services... C. In the accommodation sector, Airbnb has challenged the hotel industry... D. Critics argue that these platforms often bypass regulations... E. Workers in the gig economy lack traditional employment benefits... F. Some cities have imposed restrictions on short-term rentals... G. Proponents highlight the flexibility and entrepreneurial opportunities... H. The environmental impact remains debated... I. Future regulations will likely shape the trajectory of these platforms...
题目: 40. Some urban areas have limited the operation of home-sharing services. → (F)
评分: {"vocabulary_level":3,"syntax_complexity":3,"passage_length":3,"paragraph_count":3,"paraphrase_difficulty":3,"information_scatter":2,"distractor_similarity":3,"topic_familiarity":3,"overall":3}
理由: B1-B2词汇为主（transformed/disrupted/bypass/gig economy/entrepreneurial/trajectory），含定语从句和宾语从句，9段约600词（典型CET-4），匹配需句式级转述（"urban areas have limited"→"cities have imposed restrictions"，"home-sharing"→"short-term rentals"），C/F/I段共享经济主题相近需区分，社会热点话题。
</example>

<example difficulty=4>
原文(12段，约900词): A. The relationship between biodiversity and ecosystem stability has fascinated ecologists for decades... B. Early research by MacArthur proposed that species richness enhances resilience... C. Recent meta-analyses have largely corroborated this hypothesis... D. However the mechanisms remain contentious... E. Some emphasize functional diversity over species count... F. Keystone species exert disproportionate influence... G. Climate change introduces unprecedented stressors... H. Habitat fragmentation compounds species loss... I. Marine ecosystems exhibit different patterns... J. Restoration ecology applies these principles... K. Economic valuation adds policy urgency... L. Interdisciplinary approaches are needed...
题目: 43. The importance of certain species goes far beyond their numerical proportion in the community. → (F)
评分: {"vocabulary_level":4,"syntax_complexity":4,"passage_length":4,"paragraph_count":4,"paraphrase_difficulty":4,"information_scatter":3,"distractor_similarity":4,"topic_familiarity":4,"overall":4}
理由: 密集B2-C1学术词汇（biodiversity/ecosystem/resilience/corroborated/contentious/keystone/disproportionate/fragmentation/restoration/interdisciplinary），含多重定语从句，12段约900词（超出典型CET-4），需抽象概括（"importance beyond numerical proportion"→"disproportionate influence"→"keystone species"），D/E/F段生态机制主题高度相似需精细区分，专业学科话题。
</example>

<example difficulty=5>
原文(14段，约1100词): A. The etiology and pathophysiology of Alzheimer disease represent one of the most formidable challenges in contemporary neurology... B. Amyloid-beta plaques have historically dominated the etiological narrative, with the amyloid cascade hypothesis positing that the accumulation of these protein aggregates triggers a pathogenic cascade leading to synaptic dysfunction and neuronal loss... C. However, the repeated failure of anti-amyloid therapeutics in phase III clinical trials has prompted a fundamental reconsideration of this paradigm... D. Tau pathology, specifically the hyperphosphorylation and aggregation of tau protein into neurofibrillary tangles, has emerged as an alternative etiological framework... E. The spatial and temporal progression of tau pathology, as mapped by Braak staging, correlates more closely with clinical symptom severity than amyloid burden... F. Recent advances in neuroimaging, particularly the development of tau-PET ligands, have enabled in vivo tracking of tau deposition, revealing that tau propagation along neural networks precedes measurable cognitive decline by a decade or more... G. Microglial activation and neuroinflammatory responses have been identified as critical mediators bridging protein pathology to neurodegeneration... H. Genome-wide association studies have identified over 70 risk loci, implicating microglial function, complement cascade, and lipid metabolism in disease pathogenesis... I. The emerging consensus posits a multi-factorial model wherein genetic susceptibility, protein misfolding, neuroinflammation, and vascular dysfunction converge to produce the clinical syndrome... J. Sleep disruption has been identified not merely as a symptom but as a potential upstream driver of amyloid accumulation, with glymphatic system dysfunction impairing the clearance of metabolic waste products during sleep... K. ApoE4 genotype remains the strongest genetic risk factor for sporadic Alzheimer disease, with its impact on lipid transport, synaptic plasticity, and neuroimmune modulation under intensive investigation... L. The failure of single-target therapeutic approaches has motivated interest in combinatorial strategies targeting multiple nodes in the pathogenic network simultaneously... M. Lifestyle interventions including cognitive reserve building, aerobic exercise, and Mediterranean diet continue to show modest but consistent epidemiological benefit, though their mechanistic basis remains incompletely understood... N. The convergence of molecular pathology, systems biology, and computational neuroscience promises to yield a more integrated understanding that may ultimately translate into effective disease-modifying therapies.
题目: 41. The spatial distribution pattern of tau protein pathology has been shown to align more accurately with patients' cognitive decline compared to amyloid plaque deposition. → (E)
评分: {"vocabulary_level":5,"syntax_complexity":5,"passage_length":5,"paragraph_count":5,"paraphrase_difficulty":5,"information_scatter":5,"distractor_similarity":5,"topic_familiarity":5,"overall":5}
理由: 大量C1+医学/神经科学学术词汇（etiology/pathophysiology/formidable/amyloid/hyperphosphorylation/neurofibrillary/ligands/propagation/etiological/pathogenic/glymphatic/genome-wide/combinatorial），超多层嵌套从句+专业术语密集+被动语态+分词结构，14段超长文超1100词跨多个子话题(蛋白假说/基因/影像/炎症/睡眠/治疗)，需跨多段综合理解（F段tau-PET进展+E段Braak分期+C段amyloid失效+？段comparison），D/E/F/G/H 五段主题高度相似（tau/amyloid/炎症/基因/多因素）极难区分，高度专业医学研究话题。
</example>

【维度说明】
1. vocabulary_level: 1=全A1/A2  2=含B1词  3=B1-B2为主(典型CET-4)  4=多B2-C1词  5=密集C1+学术词汇
2. syntax_complexity: 1=短简单句  2=含简单从句  3=含2类从句(典型CET-4)  4=多层从句嵌套  5=复杂嵌套+插入结构
3. passage_length: 1=<300词  2=300-500  3=500-800(典型CET-4)  4=800-1000  5=>1000词
4. paragraph_count: 1=<5段  2=5-7段  3=8-10段(典型CET-4)  4=11-13段  5=>13段
5. paraphrase_difficulty: 1=原词匹配  2=简单同义词  3=词组级转述(典型CET-4)  4=句式级改写  5=抽象概括+跨段综合
6. information_scatter: 1=集中一处  2=2处关键信息  3=多段含线索(典型CET-4)  4=全篇分散需筛选  5=多段交叉+干扰信息
7. distractor_similarity: 1=主题明显不同  2=有相似但不混淆  3=2-3段相近(典型CET-4)  4=多段高度相似  5=几乎每段都有迷惑性
8. topic_familiarity: 1=日常  2=校园  3=科普/社会(典型CET-4)  4=专业学科  5=高度专业/冷门

【题目内容】
{content}

{content_structured}

返回JSON:
{"vocabulary_level":1-5,"syntax_complexity":1-5,"passage_length":1-5,"paragraph_count":1-5,"paraphrase_difficulty":1-5,"information_scatter":1-5,"distractor_similarity":1-5,"topic_familiarity":1-5,"overall":1-5,"reasoning":"一句话总结"}"""

# ── 翻译 Prompt ──
TRANSLATION_PROMPT = """分析以下四级翻译题，从5个维度评估中文源文本的翻译难度。
评分必须严格对照下列5级校准示例，每级都有明确标杆。

【5级校准示例（必读）】

<example difficulty=1>
中文源文: 我喜欢运动。我每天跑步半小时。运动让我身体健康。
评分: {"vocabulary_level":1,"syntax_complexity":1,"semantic_abstraction":1,"cultural_load":1,"logic_chain":1,"overall":1}
理由: 全A1基础词（我/喜欢/运动/跑步/身体/健康），三个独立简单句无连接词无从句，纯具象行为描述无任何抽象概念，零文化负载可直接对应英文词，单线罗列无因果连接。
</example>

<example difficulty=2>
中文源文: 中国的茶文化有着悠久的历史。很多人喜欢在空闲时间喝茶，因为茶不仅味道好，而且对健康有益。在一些地方，人们还会用茶来招待客人。
评分: {"vocabulary_level":2,"syntax_complexity":2,"semantic_abstraction":1,"cultural_load":2,"logic_chain":2,"overall":2}
理由: A2-B1词汇（悠久/历史/空闲/味道/健康/招待/客人），含简单因果复句（因为/而且），具象描述饮茶习惯无隐喻，有中国文化元素但为常识级别（茶/待客传统），简单因果链（茶好喝+有益→人们喜欢→待客）。
</example>

<example difficulty=3>
中文源文: 随着互联网技术的快速发展，移动支付已经成为中国人日常生活中不可或缺的一部分。无论是在大型商场购物，还是在街边小摊买早餐，人们都可以用手机轻松完成支付。这种便捷的支付方式不仅改变了人们的消费习惯，也推动了传统商业模式的转型升级。
评分: {"vocabulary_level":3,"syntax_complexity":3,"semantic_abstraction":2,"cultural_load":3,"logic_chain":3,"overall":3}
理由: B1-B2书面语词汇（互联网/移动支付/不可或缺/便捷/消费/转型/升级），含偏正复句+递进+无条件复句（随着/无论...都/不仅...也），有社会现象抽象（商业模式转型），中国当代社会文化元素（移动支付/街边小摊）需解释性翻译，多层因果链（互联网发展→移动支付普及→消费习惯改变→商业模式转型）。此为典型CET-4翻译难度。
</example>

<example difficulty=4>
中文源文: 中医药学凝聚着中华民族数千年的健康养生理念及其实践经验，是中国古代科学的瑰宝。它以整体观念和辨证论治为核心，强调"治未病"的预防理念，主张通过调整人体的阴阳平衡来达到治疗目的。近年来，随着"一带一路"倡议的推进，中医药已传播到全球180多个国家和地区，成为中外人文交流的重要纽带。
评分: {"vocabulary_level":4,"syntax_complexity":4,"semantic_abstraction":4,"cultural_load":4,"logic_chain":4,"overall":4}
理由: B2-C1词汇（凝聚/瑰宝/辨证论治/阴阳/纽带），含多重复句+引用术语+并列分述（中医→核心→理念→主张→传播），抽象概念密集（整体观念/阴阳平衡/预防理念/人文交流），深度文化依赖（中医理论术语需解释性翻译+专名"治未病"/"一带一路"需标准化译法），复杂逻辑链（中医本质→核心方法论→预防思想→阴阳理论→现代传播→人文价值）。
</example>

<example difficulty=5>
中文源文: "大道之行也，天下为公"是中华文明自古以来的政治理想，体现了先贤对公平正义社会的不懈追求。这一思想源远流长，从孔子"不患寡而患不均"的分配伦理，到孟子"民为贵，社稷次之"的民本主张，再到顾炎武"天下兴亡，匹夫有责"的责任意识，构成了中国知识分子一脉相承的精神图谱。在当代语境下，这一传统智慧与社会主义核心价值观交相辉映，彰显了中华优秀传统文化创造性转化的时代意义。
评分: {"vocabulary_level":5,"syntax_complexity":5,"semantic_abstraction":5,"cultural_load":5,"logic_chain":5,"overall":5}
理由: 大量成语/文言引语（天下为公/不患寡而患不均/民为贵社稷次之/天下兴亡匹夫有责/源远流长/一脉相承/交相辉映），多重复句+三重引用嵌套+排比递进（从孔子→到孟子→再到顾炎武），高度抽象政治哲学概念（分配伦理/民本思想/精神图谱/创造性转化），极度文化依赖需深厚国学知识才能理解原意并找到恰当的英文对应，超多层逻辑链（总纲→孔子→孟子→顾炎武→传统脉络→当代价值→时代意义）。
</example>

【维度说明】
1. vocabulary_level: 所需英文CEFR等级  1=A1基础词  2=A2-B1日常词汇  3=B1-B2一般书面语(典型CET-4)  4=B2-C1书面语+专业术语  5=成语/文言/哲学专名
2. syntax_complexity: 中文句式  1=独立简单句  2=简单因果/并列复句  3=偏正复句+递进(典型CET-4)  4=多重关系复句++引用  5=多重复句+文言+排比递进
3. semantic_abstraction: 1=纯具象行为描述  2=具象+简单说明  3=社会现象/趋势概括(典型CET-4)  4=抽象理念/专业概念  5=高度哲学/政治抽象
4. cultural_load: 中国文化元素密度  1=零文化元素  2=常识级文化（茶/待客）  3=社会文化现象(移动支付/互联网)(典型CET-4)  4=传统文化+专业概念  5=深层国学/政治哲学
5. logic_chain: 1=单线罗列  2=简单因果  3=因果递进链(典型CET-4)  4=多线因果+理论论证  5=多层嵌套因果+历史脉络+理论升华

【题目内容】
{content}

返回JSON:
{"vocabulary_level":1-5,"syntax_complexity":1-5,"semantic_abstraction":1-5,"cultural_load":1-5,"logic_chain":1-5,"overall":1-5,"reasoning":"一句话总结"}"""

# ── 题型 → Prompt 映射 ──
TYPE_PROMPTS = {
    "写作": WRITING_PROMPT,
    "听力": LISTENING_PROMPT,
    "选词填空": CLOZE_PROMPT,
    "段落匹配": MATCHING_PROMPT,
    "仔细阅读": READING_PROMPT,
    "阅读": READING_PROMPT,
    "翻译": TRANSLATION_PROMPT,
}

# ── 题型 → 权重配置 ──
TYPE_WEIGHTS = {
    "写作": {
        "abstractness": 0.25, "vocabulary_level": 0.20, "syntax_complexity": 0.20,
        "constraint_count": 0.20, "knowledge_burden": 0.15,
    },
    "听力": {
        "vocabulary_level": 0.15, "syntax_complexity": 0.10, "speech_rate_factor": 0.10,
        "information_density": 0.10, "question_complexity": 0.10, "option_vocabulary": 0.08,
        "distractor_strength": 0.17, "memory_load": 0.20,
    },
    "选词填空": {
        "vocabulary_level": 0.15, "wordbank_difficulty": 0.20, "syntax_complexity": 0.10,
        "context_dependency": 0.15, "grammatical_complexity": 0.15, "distractor_strength": 0.10,
        "information_density": 0.05, "passage_familiarity": 0.10,
    },
    "段落匹配": {
        "vocabulary_level": 0.15, "syntax_complexity": 0.10, "passage_length": 0.10,
        "paragraph_count": 0.05, "paraphrase_difficulty": 0.25, "information_scatter": 0.15,
        "distractor_similarity": 0.10, "topic_familiarity": 0.10,
    },
    "仔细阅读": {
        "vocabulary_level": 0.20, "syntax_complexity": 0.15, "cohesion_difficulty": 0.10,
        "information_density": 0.10, "question_complexity": 0.10, "option_vocabulary": 0.08,
        "distractor_strength": 0.17, "location_difficulty": 0.10,
    },
    "翻译": {
        "vocabulary_level": 0.30, "syntax_complexity": 0.25, "semantic_abstraction": 0.20,
        "cultural_load": 0.15, "logic_chain": 0.10,
    },
}


# ═══════════════════════════════════════════════════════════
#  AI 调用 + 解析
# ═══════════════════════════════════════════════════════════

def _call_deepseek(system_prompt, user_prompt, max_retries=3):
    """调用 DeepSeek API，带重试机制"""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1000,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            return json.loads(raw)
        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                time.sleep(1 * (attempt + 1))
            continue
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise e
    return None


def _validate_and_weight(dimensions, weights, overall_from_ai):
    """校验各维度，用权重重新计算 overall"""
    weighted_sum = 0
    for dim, weight in weights.items():
        raw = dimensions.get(dim, 3)
        # 钳制到 1-5，容错AI输出异常值
        score = max(1, min(5, int(raw)))
        dimensions[dim] = score
        weighted_sum += score * weight

    computed_overall = round(weighted_sum)
    computed_overall = max(1, min(5, computed_overall))

    return {
        "dimensions": dimensions,
        "weights": weights,
        "overall": computed_overall,
        "ai_raw_overall": overall_from_ai,
    }


def analyze_by_ai(content, question_type):
    """
    使用 AI 大模型分析单道题的难度。自动预处理听力/阅读内容结构。

    Returns:
        dict: {
            "overall": int (1-5),
            "dimensions": {name: score, ...},
            "weights": {name: weight, ...},
            "confidence": float,
            "model": str,
            "reasoning": str
        }
        失败时返回 None
    """
    if question_type not in TYPE_PROMPTS:
        return None

    if len(content) > 2500:
        content = content[:2500]

    structured_text = ""
    if question_type in ("听力", "选词填空", "段落匹配", "仔细阅读", "阅读"):
        try:
            from .content_preprocessor import extract_passage_and_questions, format_structured_for_prompt
            structured = extract_passage_and_questions(content, question_type)
            if structured["total_questions"] > 0:
                structured_text = format_structured_for_prompt(structured)
        except Exception:
            structured_text = ""

    prompt_template = TYPE_PROMPTS[question_type]
    user_prompt = prompt_template.replace("{content}", content)
    user_prompt = user_prompt.replace("{content_structured}", structured_text)

    try:
        result = _call_deepseek(SYSTEM_PROMPT_BASE, user_prompt)

        if result is None:
            return None

        overall_ai = result.pop("overall", 3)
        reasoning = result.pop("reasoning", "")
        # 剩余字段即维度分
        dimensions = result

        validated = _validate_and_weight(dimensions, TYPE_WEIGHTS[question_type], overall_ai)

        return {
            "overall": validated["overall"],
            "dimensions": validated["dimensions"],
            "weights": validated["weights"],
            "ai_raw_overall": validated["ai_raw_overall"],
            "confidence": 0.85,
            "model": MODEL,
            "reasoning": reasoning,
        }
    except Exception:
        return None


# ── 并发批量分析 ──────────────────────────────────────────

CONCURRENCY = int(os.getenv("AI_CONCURRENCY", "30"))
_thread_local = threading.local()


def _get_client():
    """线程安全的 OpenAI client（连接池复用）"""
    if not hasattr(_thread_local, "client"):
        _thread_local.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            http_client=httpx.Client(
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=20),
                timeout=httpx.Timeout(90.0, connect=10.0),
            ),
        )
    return _thread_local.client


def _call_deepseek_threadsafe(system_prompt, user_prompt):
    """线程安全版 DeepSeek 调用"""
    for attempt in range(3):
        try:
            response = _get_client().chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1000,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            if attempt < 2:
                time.sleep(1 * (attempt + 1))
        except Exception:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    return None


def _analyze_single(qid, content, question_type):
    """分析单道题（供并发使用），返回 (qid, result_or_none)"""
    if question_type not in TYPE_PROMPTS:
        return (qid, None)

    # Truncate: 2500 chars sufficient for analysis, reduces API latency
    if len(content) > 2500:
        content = content[:2500]

    structured_text = ""
    if question_type in ("听力", "选词填空", "段落匹配", "仔细阅读", "阅读"):
        try:
            from .content_preprocessor import extract_passage_and_questions, format_structured_for_prompt
            structured = extract_passage_and_questions(content, question_type)
            if structured["total_questions"] > 0:
                structured_text = format_structured_for_prompt(structured)
        except Exception:
            structured_text = ""

    prompt_template = TYPE_PROMPTS[question_type]
    user_prompt = prompt_template.replace("{content}", content)
    user_prompt = user_prompt.replace("{content_structured}", structured_text)

    try:
        result = _call_deepseek_threadsafe(SYSTEM_PROMPT_BASE, user_prompt)
        if result is None:
            return (qid, None)

        overall_ai = result.pop("overall", 3)
        reasoning = result.pop("reasoning", "")
        dimensions = result
        validated = _validate_and_weight(dimensions, TYPE_WEIGHTS[question_type], overall_ai)

        return (qid, {
            "overall": validated["overall"],
            "dimensions": validated["dimensions"],
            "weights": validated["weights"],
            "ai_raw_overall": validated["ai_raw_overall"],
            "confidence": 0.85,
            "model": MODEL,
            "reasoning": reasoning,
        })
    except Exception:
        return (qid, None)


def analyze_batch_ai(questions, concurrency=None):
    """并发批量 AI 分析，速度提升 6-8x。

    Args:
        questions: [(id, content, type), ...]
        concurrency: 并发数（默认 CONCURRENCY=8）

    Returns:
        list of (id, result_dict or None)
    """
    workers = concurrency or CONCURRENCY
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_analyze_single, qid, content, qtype): qid
            for qid, content, qtype in questions
        }
        for future in as_completed(futures):
            qid, result = future.result()
            results[qid] = result
    return [(qid, results.get(qid)) for qid, _, _ in questions]


def analyze_and_update_db(question_ids):
    """并发分析题目并直接写入数据库（供 PDF 导入后自动调用）。

    Args:
        question_ids: list of question IDs to analyze
    """
    from datetime import datetime as dt
    import sys

    # 延迟导入避免循环
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from db.database import SessionLocal
    from models.question import Question
    from .difficulty_analyzer import extract_english_text, compute_text_features, features_to_difficulty

    db = SessionLocal()
    try:
        questions = db.query(Question).filter(Question.id.in_(question_ids)).all()
    except Exception:
        db.close()
        return

    if not questions:
        db.close()
        return

    # 构建请求列表
    tasks = [(q.id, q.content, q.type) for q in questions]
    db.close()

    print(f"[AI] 开始并发分析 {len(tasks)} 道题（并发={CONCURRENCY}）...")

    results = analyze_batch_ai(tasks, concurrency=CONCURRENCY)

    db2 = SessionLocal()
    ai_success = 0
    fallback = 0

    # 懒加载 textstat：仅 AI 失败时才计算，节省 90%+ 的 CPU 时间
    for i, (qid, ai_result) in enumerate(results):
        q = db2.query(Question).filter(Question.id == qid).first()
        if not q:
            continue

        if ai_result is not None:
            q.difficulty = str(ai_result["overall"])
            existing = q.difficulty_detail or {}
            existing.update({
                "version": "2.0",
                "source": "ai",
                "analyzed_at": dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ai_detail": {
                    "model": ai_result["model"],
                    "dimensions": ai_result["dimensions"],
                    "weights": ai_result["weights"],
                    "reasoning": ai_result["reasoning"],
                },
                "metrics": {},
            })
            q.difficulty_detail = existing
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(q, "difficulty_detail")
            ai_success += 1
        else:
            # 仅失败时才计算 textstat
            extracted = extract_english_text(q.content, q.type)
            features = compute_text_features(extracted)
            ts = features_to_difficulty(features, q.type)
            q.difficulty = ts.get("difficulty", "2")
            existing = q.difficulty_detail or {}
            existing.update({
                "version": "2.0",
                "source": "textstat_fallback",
                "analyzed_at": dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ai_detail": None,
                "metrics": ts.get("metrics", {}),
            })
            q.difficulty_detail = existing
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(q, "difficulty_detail")
            fallback += 1

        # 分批提交，避免内存堆积
        if (i + 1) % 100 == 0:
            db2.commit()

    try:
        db2.commit()
        print(f"[AI] 分析完成: AI成功={ai_success}, textstat降级={fallback}")
    except Exception as e:
        print(f"[AI] 保存失败: {e}")
        db2.rollback()
    finally:
        db2.close()
