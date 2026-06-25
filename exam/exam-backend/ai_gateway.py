"""
AI 大模型网关 — DeepSeek 集成
4套分题型 Prompt 模板 + JSON 结构化解析 + 降级策略
"""
import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
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
评分必须参照下列已标定的Few-shot示例，确保1-5全量程覆盖。

【Few-shot校准示例】

<example difficulty=1>
题目: Write about your favorite hobby and explain why you enjoy it.
评分: {"abstractness":1,"vocabulary_level":1,"syntax_complexity":1,"constraint_count":1,"knowledge_burden":1,"overall":1}
理由: 纯个人日常话题，A1词汇，简单句，无约束，无需背景知识。
</example>

<example difficulty=3>
题目: Suppose your university is conducting a survey on students' opinions about the use of AI technology in learning. You are asked to write an essay to express your view. You should write at least 120 words but no more than 180 words.
评分: {"abstractness":3,"vocabulary_level":2,"syntax_complexity":2,"constraint_count":4,"knowledge_burden":3,"overall":3}
理由: 社会现象评论（AI+教育），有B2词汇（conducting/survey），简单从句，4个约束（suppose/survey/write/字数上下限），需校园常识。
</example>

<example difficulty=5>
题目: Some philosophers argue that the pursuit of economic prosperity inevitably undermines the moral foundations of society, while others contend that material well-being is a prerequisite for ethical development. Critically evaluate both perspectives and defend your own position using philosophical reasoning. You should write at least 200 words.
评分: {"abstractness":5,"vocabulary_level":5,"syntax_complexity":5,"constraint_count":5,"knowledge_burden":5,"overall":5}
理由: 高度哲学抽象话题，大量C1+词汇（prosperity/undermines/prerequisite/ethical/philosophical），多层嵌套从句，5+约束，需哲学专业知识。
</example>

【维度说明】
1. abstractness (主题抽象度):
   1=日常具象话题  3=社会现象评论  5=哲学思辨/高度抽象

2. vocabulary_level (题干词汇难度):
   统计题干词汇CEFR等级，根据B2及以上词汇占比打分
   1=几乎全是A1/A2  3=有B1/B2词汇  5=大量C1+词汇

3. syntax_complexity (句式复杂度):
   1=简单句/并列句  3=含1-2个从句  5=多层嵌套/倒装/虚拟语气

4. constraint_count (限定约束数量):
   统计题目中具体要求数量(write/suppose/directions/at least/no more than等)
   1=1个  2=2个  3=3个  4=4个  5=5个及以上

5. knowledge_burden (知识背景依赖):
   1=纯个人经验即可  3=需校园/社会常识  5=需特定专业知识

【题目内容】
{content}

返回JSON:
{"abstractness":1-5,"vocabulary_level":1-5,"syntax_complexity":1-5,"constraint_count":1-5,"knowledge_burden":1-5,"overall":1-5,"reasoning":"一句话总结"}"""

# ── 阅读 Prompt ──
READING_PROMPT = """分析以下四级阅读题，从8个维度评估难度。
评分必须参照下列已标定的Few-shot示例，确保1-5全量程覆盖。

【Few-shot校准示例】

<example difficulty=1>
原文: My name is Tom. I am a student at a middle school. I like playing basketball with my friends after class. My favorite subject is science because it is interesting. Last weekend, I went to the park with my family. We had a picnic and played games.
题目: 1. What does Tom like to do after class? A) Read books B) Play basketball C) Watch TV D) Sleep
评分: {"vocabulary_level":1,"syntax_complexity":1,"cohesion_difficulty":1,"information_density":1,"question_complexity":1,"option_vocabulary":1,"distractor_strength":1,"location_difficulty":1,"overall":1}
理由: 全A1词汇，简单短句，线性叙述无指代，无数字/专名，直接细节题，选项均为A1词，干扰项明显无关，答案直接定位原文原句。
</example>

<example difficulty=3>
原文: Scientists have known that depriving adult mice of vision can increase the sensitivity of individual neurons in the part of the brain devoted to hearing. New research from biologists at the University of Maryland revealed that sight deprivation also changes the way brain cells interact with one another. It was once thought that the sensory regions of the brain were not adaptable after a critical period in childhood. This is why children learn languages much more readily than adults.
题目: What did the new research reveal? A) Adult mice can regain vision B) Sight deprivation changes brain cell interaction C) Children learn slower than adults D) Hearing is more important than vision
评分: {"vocabulary_level":3,"syntax_complexity":3,"cohesion_difficulty":2,"information_density":3,"question_complexity":2,"option_vocabulary":2,"distractor_strength":3,"location_difficulty":2,"overall":3}
理由: B1-B2词汇为主（depriving/sensitivity/interact/adaptable），含定语从句和宾语从句，线性叙述有转折，有大学名/术语等专名，直接推断题，选项有B1词汇，干扰项B部分关联原文词汇但偏离核心（需区分"regain vision"与原文"depriving vision"），定位需识别"revealed"与原文同义。
</example>

<example difficulty=5>
原文: The epistemological implications of quantum mechanics have fundamentally challenged the Newtonian paradigm that dominated scientific discourse for three centuries. Whereas classical physics posited a deterministic universe amenable to objective observation, Heisenberg's uncertainty principle and the Copenhagen interpretation suggest that the act of measurement inextricably alters the phenomenon under investigation. This ontological shift has reverberated beyond physics, prompting philosophers to reconsider the nature of consciousness, free will, and the objective reality that underpins empirical methodology.
题目: According to the passage, the Copenhagen interpretation implies that: A) Newtonian physics remains valid for macroscopic objects B) The observer cannot be separated from the observed phenomenon C) Quantum mechanics has no philosophical relevance D) Determinism is essential to scientific methodology
评分: {"vocabulary_level":5,"syntax_complexity":5,"cohesion_difficulty":5,"information_density":5,"question_complexity":5,"option_vocabulary":5,"distractor_strength":5,"location_difficulty":5,"overall":5}
理由: 大量C1+学术词汇（epistemological/paradigm/posit/deterministic/inextricably/ontological/reverberated/empirical），多层嵌套从句+whereas对比结构+被动语态，复杂跨领域指代（物理学→哲学），多专业术语/人名密集，需理解深层推断（从"act of measurement alters phenomenon"推断出observer不能分离），选项含C1+词汇（macroscopic/paradigm/determinism），干扰项高度精密（A利用"Newtonian"似是而非，B正确但需抽象提炼，C/D与原文立场微妙相反），需跨段综合+同义转述推断。
</example>

【维度说明】
1. vocabulary_level: 1=A1/A2词汇  3=B1/B2为主  5=大量C1+学术词汇
2. syntax_complexity: 1=短简单句  3=含定语/状语从句  5=多层嵌套+倒装+被动语态
3. cohesion_difficulty: 1=线性叙述  3=有指代和转折  5=复杂指代+多线并行
4. information_density: 1=稀疏  3=适中  5=密集（大量数据/专名/术语）
5. question_complexity: 1=直接细节题  3=推断题  5=深层推断+综合理解
6. option_vocabulary: 1=均为A1/A2词  3=有B2词汇  5=大量C1+词汇
7. distractor_strength: 1=干扰项明显无关  3=部分有迷惑性  5=高度相似需精细区分
8. location_difficulty: 1=直接原文定位  3=需同义转换  5=跨段推断+综合多信息点

【题目内容】
{content}

{content_structured}

返回JSON:
{"vocabulary_level":1-5,"syntax_complexity":1-5,"cohesion_difficulty":1-5,"information_density":1-5,"question_complexity":1-5,"option_vocabulary":1-5,"distractor_strength":1-5,"location_difficulty":1-5,"overall":1-5,"reasoning":"一句话总结"}"""

# ── 听力 Prompt ──
LISTENING_PROMPT = """分析以下四级听力题文本，从8个维度评估难度。听力材料难度通常低于同级别阅读。
评分必须参照下列已标定的Few-shot示例，确保1-5全量程覆盖。

【Few-shot校准示例】

<example difficulty=1>
听力原文: Hello, I'd like to order a coffee please. Sure, what size would you like? A medium, please. And would you like anything else? No, that's all. Thank you.
题目: 1. What does the customer order? A) Tea B) Coffee C) Juice D) Water
评分: {"vocabulary_level":1,"syntax_complexity":1,"speech_rate_factor":1,"information_density":1,"question_complexity":1,"option_vocabulary":1,"distractor_strength":1,"memory_load":1,"overall":1}
理由: 全日常口语词汇，简短口语句式，语速缓慢有停顿，无数字/专名，直接细节题，选项全A1高频词，干扰项明显不相关，信息集中在两句内。
</example>

<example difficulty=3>
听力原文: A recent study by researchers at Stanford University has found that students who take regular breaks during study sessions retain information up to 40% more effectively than those who study continuously. The study, which involved over 500 participants, suggests that the brain needs time to process and consolidate new information. However, the researchers noted that the length of breaks should not exceed 15 minutes to maintain focus.
题目: What did the Stanford study find about study breaks? A) They should last at least 30 minutes B) They improve information retention C) They work better for older students D) They reduce concentration levels
评分: {"vocabulary_level":3,"syntax_complexity":3,"speech_rate_factor":2,"information_density":4,"question_complexity":2,"option_vocabulary":2,"distractor_strength":3,"memory_load":3,"overall":3}
理由: B1-B2词汇（retain/consolidate/participants），含定语从句和宾语从句，语速正常，有数字(40%/500/15)和专名(Stanford)，推断题，选项有B1词汇，干扰项A利用数字反向(15→30)、B正确、C添加无关修饰(old)、D反向(improve→reduce)，信息跨3句需记忆细节。
</example>

<example difficulty=5>
听力原文: The unprecedented convergence of geopolitical tensions in Eastern Europe, coupled with the Federal Reserve's aggressive monetary tightening policy, has precipitated a paradigm shift in global capital allocation strategies. According to the International Monetary Fund's latest World Economic Outlook, emerging markets have experienced net capital outflows exceeding 83 billion dollars in the third quarter alone, marking the most severe liquidity contraction since the 2008 financial crisis. Analysts at Goldman Sachs caution that this trend could exacerbate existing structural vulnerabilities in economies with high external debt-to-GDP ratios.
题目: According to the IMF report, what happened to emerging markets in Q3? A) They received unprecedented capital inflows B) Their GDP growth exceeded expectations C) They experienced significant capital outflows D) Their debt-to-GDP ratios stabilized
评分: {"vocabulary_level":5,"syntax_complexity":5,"speech_rate_factor":5,"information_density":5,"question_complexity":4,"option_vocabulary":4,"distractor_strength":4,"memory_load":5,"overall":5}
理由: 大量C1+金融/经济术语（unprecedented/convergence/geopolitical/precipitated/paradigm/liquidity/exacerbate/structural vulnerabilities），多层嵌套从句+分词结构+被动语态，语速极快信息密集（长句连读），密集数字($83B)、机构名(IMF/Goldman Sachs)和专名，需从密集信息中筛选推断，选项含B2-C1词汇(unprecedented/exceeded/stabilized)，干扰项精密(A为反向inflows vs outflows、B偷换概念GDP growth vs capital flow、C正确、D偷换stabilized vs exacerbate)，信息跨全段+需记忆大量数字和术语。
</example>

【维度说明】(略，参照示例尺度打分)

【题目内容】
{content}

{content_structured}

返回JSON:
{"vocabulary_level":1-5,"syntax_complexity":1-5,"speech_rate_factor":1-5,"information_density":1-5,"question_complexity":1-5,"option_vocabulary":1-5,"distractor_strength":1-5,"memory_load":1-5,"overall":1-5,"reasoning":"一句话总结"}"""

# ── 翻译 Prompt ──
TRANSLATION_PROMPT = """分析以下四级翻译题，从5个维度评估中文源文本的翻译难度。
评分必须参照下列已标定的Few-shot示例，确保1-5全量程覆盖。

【Few-shot校准示例】

<example difficulty=1>
中文源文: 我喜欢读书。我每天花一个小时读书。读书让我感到快乐。
评分: {"vocabulary_level":1,"syntax_complexity":1,"semantic_abstraction":1,"cultural_load":1,"logic_chain":1,"overall":1}
理由: 全高频基础词（我/喜欢/读书/每天/快乐），简单陈述句式无从句，具象描述无隐喻，无文化负载词，单线描述无逻辑连接。
</example>

<example difficulty=3>
中文源文: 随着生活水平的提高，越来越多的人开始加入自驾游的行列之中。自驾游者既可驾驶自家车也可借车或租车出游。自驾游与传统的组团旅游不同，它能够更好地满足旅游者的个性化需求，使他们更好地享受旅游的过程。
评分: {"vocabulary_level":3,"syntax_complexity":3,"semantic_abstraction":2,"cultural_load":2,"logic_chain":3,"overall":3}
理由: 一般书面语词汇（水平/自驾游/个性化/需求/享受/过程），偏正复句+递进+对比结构（随着.../既可...也可.../与...不同），具象描述旅游方式无隐喻，有中国当代社会文化元素（自驾游/组团旅游），有因果递进逻辑链（水平提高→加入自驾游→满足需求→享受过程）。
</example>

<example difficulty=5>
中文源文: "天人合一"是中国古代哲学的核心思想，强调人与自然和谐共生。这一理念源远流长，早在先秦时期诸子百家便多有阐发。道家主张"道法自然"，认为人应顺应天道而无为；儒家则倡导"参赞天地之化育"，将人的道德修养与宇宙运行相贯通。千百年来，这一思想深刻影响了中国的园林艺术、中医理论和书画审美，成为中华文明区别于西方文明的重要标志之一。
评分: {"vocabulary_level":5,"syntax_complexity":5,"semantic_abstraction":5,"cultural_load":5,"logic_chain":5,"overall":5}
理由: 高频成语（天人合一/源远流长/诸子百家）和哲学专名（道法自然/参赞天地之化育/先秦/儒/道），多重复句嵌套+引用+文言句式（"者...也"/"而"转折/分号并列），高度抽象哲学概念（天人关系/道德与宇宙/无为/化育），极度文化依赖（中国传统哲学/儒道思想/园林/中医/书画/中西文明对比），多层复杂逻辑（总起→分述道家→对比儒家→时间延续→影响范围→文明对比）。
</example>

【维度说明】
1. vocabulary_level: 所需英文CEFR等级  1=高频基础词  3=一般书面语  5=成语/哲学术语/文化专名
2. syntax_complexity: 中文句式  1=简单句/并列句  3=偏正复句  5=多重复句+文言/特殊句式
3. semantic_abstraction: 1=具象描述  3=比喻/象征  5=高度抽象哲学概念
4. cultural_load: 中国文化元素密度  1=无  3=含1-2个  5=深度文化依赖
5. logic_chain: 1=单线  3=因果/转折  5=多层嵌套因果+多线并列

【题目内容】
{content}

返回JSON:
{"vocabulary_level":1-5,"syntax_complexity":1-5,"semantic_abstraction":1-5,"cultural_load":1-5,"logic_chain":1-5,"overall":1-5,"reasoning":"一句话总结"}"""

# ── 题型 → Prompt 映射 ──
TYPE_PROMPTS = {
    "写作": WRITING_PROMPT,
    "阅读": READING_PROMPT,
    "听力": LISTENING_PROMPT,
    "翻译": TRANSLATION_PROMPT,
}

# ── 题型 → 权重配置 ──
TYPE_WEIGHTS = {
    "写作": {
        "abstractness": 0.25, "vocabulary_level": 0.20, "syntax_complexity": 0.20,
        "constraint_count": 0.20, "knowledge_burden": 0.15,
    },
    "阅读": {
        "vocabulary_level": 0.20, "syntax_complexity": 0.15, "cohesion_difficulty": 0.10,
        "information_density": 0.10, "question_complexity": 0.10, "option_vocabulary": 0.08,
        "distractor_strength": 0.17, "location_difficulty": 0.10,
    },
    "听力": {
        "vocabulary_level": 0.15, "syntax_complexity": 0.10, "speech_rate_factor": 0.10,
        "information_density": 0.10, "question_complexity": 0.10, "option_vocabulary": 0.08,
        "distractor_strength": 0.17, "memory_load": 0.20,
    },
    "翻译": {
        "vocabulary_level": 0.30, "syntax_complexity": 0.25, "semantic_abstraction": 0.20,
        "cultural_load": 0.15, "logic_chain": 0.10,
    },
}


# ═══════════════════════════════════════════════════════════
#  AI 调用 + 解析
# ═══════════════════════════════════════════════════════════

def _call_deepseek(system_prompt, user_prompt, max_retries=2):
    """调用 DeepSeek API，短重试"""
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
                time.sleep(0.3)
            continue
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(0.3)
            continue
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

    # 结构化预处理（仅听力/阅读）
    structured_text = ""
    if question_type in ("听力", "阅读"):
        try:
            from content_preprocessor import extract_passage_and_questions, format_structured_for_prompt
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


def analyze_batch_ai(questions, delay=0.3):
    """
    批量 AI 分析。

    Args:
        questions: [(id, content, type), ...]
        delay: API调用间隔（秒），防止限流

    Returns:
        list of (id, result_dict or None)
    """
    results = []
    for i, (qid, content, qtype) in enumerate(questions):
        result = analyze_by_ai(content, qtype)
        results.append((qid, result))
        time.sleep(delay)
    return results
