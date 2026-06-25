<template>
  <div style="padding: 20px;">
    <h3>🎯 英语四级智能组卷</h3>

    <!-- 组卷配置表单 -->
    <el-card style="margin-top: 20px; max-width: 700px;">
      <el-form :model="config" label-width="140px">
        <el-form-item label="难度等级（1-5）">
          <el-input-number v-model="config.difficulty" :min="1" :max="5" />
          <span style="margin-left:10px;color:#909399;font-size:13px;">
            {{ difficultyHint }}
          </span>
        </el-form-item>
        <el-form-item label="试卷标题（可选）">
          <el-input v-model="config.title" placeholder="留空则自动生成" style="max-width:300px;" />
        </el-form-item>
        <el-form-item>
          <div style="color:#909399;font-size:13px;margin-bottom:8px;">
            📋 CET-4 固定格式：写作 1 题 · 听力 25 题 · 选词填空 10 题 · 段落匹配 10 题 · 仔细阅读 10 题 · 翻译 1 题（满分 710 分）
          </div>
          <el-button type="primary" @click="createPaper" :loading="loading">一键生成试卷</el-button>
          <el-button type="success" style="margin-left:10px;" @click="exportPaper" :disabled="!paperData">
            导出Word试卷
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 试卷生成成功信息 -->
    <div v-if="paperId" style="margin-top: 20px;">
      <el-alert type="success" :closable="false" show-icon>
        <template #title>
          <span>试卷生成成功！试卷ID：<b>{{ paperId }}</b></span>
          <el-tag type="warning" style="margin-left:10px;">考试编号：{{ examId }}</el-tag>
        </template>
        <span style="font-size:13px;color:#666;">
          学生可通过此编号参加在线考试；题目映射已持久化，服务重启不丢失。
        </span>
      </el-alert>
    </div>

    <!-- 生成的试卷预览 — CET-4 标准分层 -->
    <div v-if="paperData" style="margin-top: 30px;">
      <h3>📄 试卷预览（CET-4 标准格式）</h3>
      <el-divider />

      <el-collapse v-model="activeTypes">
        <el-collapse-item
          v-for="section in sections"
          :key="section.part"
          :name="section.part"
        >
          <template #title>
            <div style="display:flex;align-items:center;gap:10px;width:100%;">
              <span style="font-weight:bold;font-size:16px;">{{ section.part }}</span>
              <el-tag :type="section.tagType" size="small">{{ section.questionCount }} 题</el-tag>
            </div>
          </template>

          <!-- Directions -->
          <div v-if="section.instruction" style="color:#666;font-size:13px;margin-bottom:16px;line-height:1.7;">
            {{ section.instruction }}
          </div>

          <!-- ===== 听力 / 翻译 / 写作：扁平题目 ===== -->
          <template v-if="!section.subsections && section.questions">
            <el-card v-for="q in section.questions" :key="q.id"
              style="margin-bottom:10px;" shadow="hover">
              <div style="display:flex;align-items:flex-start;gap:12px;">
                <div style="min-width:50px;text-align:center;">
                  <el-tag type="info" size="small">{{ q.qid }}</el-tag>
                </div>
                <div style="flex:1;min-width:0;">
                  <div style="font-size:14px;line-height:1.8;white-space:pre-wrap;margin-bottom:6px;">
                    {{ q.content }}
                  </div>
                  <div v-if="q.options && q.options.length > 0" style="margin:6px 0;">
                    <div v-for="opt in q.options" :key="opt.label"
                      style="display:block;margin:4px 0;font-size:13px;padding-left:12px;">
                      {{ opt.label }}) {{ opt.text }}
                    </div>
                  </div>
                </div>
              </div>
            </el-card>
          </template>

          <!-- ===== 阅读理解：subsections + passage groups ===== -->
          <template v-if="section.subsections">
            <div v-for="sub in section.subsections" :key="sub.title" style="margin-bottom:24px;">
              <h4 style="color:#303133;margin-bottom:12px;border-left:4px solid #409EFF;padding-left:10px;">
                {{ sub.title }}
                <el-tag size="small" type="info" style="margin-left:8px;">
                  {{ sub.totalQuestions }} 题
                </el-tag>
              </h4>

              <!-- 选词填空：原文只显示一次，题目只显示题号和句子 -->
              <template v-if="sub.type === '选词填空'">
                <div v-for="(pg, pgIdx) in sub.groups" :key="'pg-'+pgIdx"
                  style="margin-bottom:20px;border:2px solid #dcdfe6;border-radius:8px;overflow:hidden;">
                  
                  <!-- Word Bank（可供选择的词汇） -->
                  <div v-if="pg.word_bank && pg.word_bank.length > 0" style="background:#e8f5e9;padding:14px 20px;border-bottom:1px solid #dcdfe6;">
                    <span style="font-weight:bold;font-size:14px;color:#27ae60;">Word Bank</span>
                  </div>
                  <div v-if="pg.word_bank && pg.word_bank.length > 0" style="padding:12px 20px;background:#f1f8e9;border-bottom:1px solid #dcdfe6;">
                    <div v-for="(word, idx) in pg.word_bank" :key="idx" 
                      style="display:inline-block;margin:4px 8px;padding:4px 12px;background:#fff;border:1px solid #c8e6c9;border-radius:4px;font-size:13px;">
                      <b>{{ word.label }}.</b> {{ word.text }}
                    </div>
                  </div>

                  <!-- Passage 原文（只显示一次） -->
                  <div v-if="pg.passage" style="background:#f0f2f5;padding:14px 20px;border-bottom:1px solid #dcdfe6;">
                    <span style="font-weight:bold;font-size:14px;color:#303133;">原文</span>
                  </div>
                  <div v-if="pg.passage" style="padding:16px 20px;font-size:14px;line-height:2;white-space:pre-wrap;color:#303133;">
                    {{ pg.passage }}
                  </div>
                  
                  <!-- 子题目：只显示题号和填空句，去除选项 -->
                  <div style="padding:8px 12px 12px;">
                    <div v-for="q in pg.questions" :key="q.id"
                      style="padding:10px 0;border-bottom:1px dashed #ebeef5;">
                      <div style="font-size:14px;line-height:1.8;">
                        <b>{{ q.qid }}.</b> {{ q.content }}
                      </div>
                      <!-- 答案（教师视角） -->
                      <div v-if="q.answer" style="margin-left:24px;margin-top:4px;">
                        <el-tag size="small" type="success" effect="plain">答案：{{ q.answer }}</el-tag>
                        <el-tag v-if="q.difficulty_label" size="small"
                          :type="getDifficultyType(q.difficulty)" effect="plain" style="margin-left:6px;">
                          {{ q.difficulty_label }}
                        </el-tag>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- 段落匹配：原文只显示一次，题目只显示句子 -->
              <template v-else-if="sub.type === '段落匹配'">
                <div v-for="(pg, pgIdx) in sub.groups" :key="'pg-'+pgIdx"
                  style="margin-bottom:20px;border:2px solid #dcdfe6;border-radius:8px;overflow:hidden;">
                  
                  <!-- Passage 原文（只显示一次） -->
                  <div v-if="pg.passage" style="background:#f0f2f5;padding:14px 20px;border-bottom:1px solid #dcdfe6;">
                    <span style="font-weight:bold;font-size:14px;color:#303133;">原文</span>
                  </div>
                  <div v-if="pg.passage" style="padding:16px 20px;font-size:14px;line-height:2;white-space:pre-wrap;color:#303133;">
                    {{ pg.passage }}
                  </div>
                  
                  <!-- 子题目：只显示题号和句子，去除选项 -->
                  <div style="padding:8px 12px 12px;">
                    <div v-for="q in pg.questions" :key="q.id"
                      style="padding:10px 0;border-bottom:1px dashed #ebeef5;">
                      <div style="font-size:14px;line-height:1.8;">
                        <b>{{ q.qid }}.</b> {{ q.content }}
                      </div>
                      <!-- 答案（教师视角） -->
                      <div v-if="q.answer" style="margin-left:24px;margin-top:4px;">
                        <el-tag size="small" type="success" effect="plain">答案：{{ q.answer }}</el-tag>
                        <el-tag v-if="q.difficulty_label" size="small"
                          :type="getDifficultyType(q.difficulty)" effect="plain" style="margin-left:6px;">
                          {{ q.difficulty_label }}
                        </el-tag>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- 仔细阅读：每个 Passage 只显示一次，题目显示选项 -->
              <template v-else>
                <div v-for="(pg, pgIdx) in sub.groups" :key="'pg-'+pgIdx"
                  style="margin-bottom:20px;border:2px solid #dcdfe6;border-radius:8px;overflow:hidden;">

                  <!-- Passage 原文 -->
                  <div style="background:#f0f2f5;padding:14px 20px;border-bottom:1px solid #dcdfe6;">
                    <span style="font-weight:bold;font-size:14px;color:#303133;">
                      Passage {{ pgIdx + 1 }}
                    </span>
                    <span v-if="pg.questions" style="color:#909399;font-size:12px;margin-left:8px;">
                      （{{ pg.questions.length }} 题）
                    </span>
                  </div>
                  <div style="padding:16px 20px;font-size:14px;line-height:2;white-space:pre-wrap;color:#303133;">
                    {{ pg.passage || '（原文未存储，请参考下方题目）' }}
                  </div>

                  <!-- 子题目 -->
                  <div style="padding:8px 12px 12px;">
                    <div v-for="q in pg.questions" :key="q.id"
                      style="padding:10px 0;border-bottom:1px dashed #ebeef5;">
                      <div style="font-size:14px;line-height:1.8;margin-bottom:6px;">
                        <b>{{ q.qid }}.</b> {{ q.content }}
                      </div>
                      <div v-if="q.options && q.options.length > 0"
                        style="margin-left:24px;">
                        <div v-for="opt in q.options" :key="opt.label"
                          style="font-size:13px;line-height:1.8;padding:2px 0;">
                          {{ opt.label }}) {{ opt.text }}
                        </div>
                      </div>
                      <!-- 答案（教师视角） -->
                      <div v-if="q.answer" style="margin-left:24px;margin-top:4px;">
                        <el-tag size="small" type="success" effect="plain">答案：{{ q.answer }}</el-tag>
                        <el-tag v-if="q.difficulty_label" size="small"
                          :type="getDifficultyType(q.difficulty)" effect="plain" style="margin-left:6px;">
                          {{ q.difficulty_label }}
                        </el-tag>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </template>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

// 获取认证状态
const authStore = useAuthStore()

// 组卷配置 — CET-4 固定格式，只需选择难度
const config = ref({
  difficulty: 3,
  title: '',
})

const loading = ref(false)
const paperData = ref(null)
const paperId = ref(null)
const examId = ref(null)
const activeTypes = ref(['一、听力理解', '二、阅读理解', '三、翻译', '四、写作'])

// 难度提示
const difficultyHint = computed(() => {
  const hints = { 1: '基础 — 大部分简单题', 2: '进阶 — 中等偏易', 3: '中等 — 均衡分布', 4: '较难 — 中等偏难', 5: '困难 — 大部分难题' }
  return hints[config.value.difficulty] || ''
})

// 难度 → el-tag type 映射
const getDifficultyType = (d) => {
  const map = { 1: 'success', 2: 'info', 3: 'warning', 4: 'danger', 5: 'danger' }
  return map[d] || 'info'
}

// CET-4 section tag colors
const SECTION_TAGS = {
  '一、听力理解': 'warning',
  '二、阅读理解': 'info',
  '三、翻译': 'success',
  '四、写作': 'danger',
}

// 从 paperData.sections 构建展示结构
const sections = computed(() => {
  if (!paperData.value || !paperData.value.sections) return []
  return paperData.value.sections.map(sec => {
    let questionCount = 0
    if (sec.subsections) {
      for (const sub of sec.subsections) {
        let subTotal = 0
        for (const pg of (sub.groups || [])) {
          subTotal += (pg.questions || []).length
        }
        sub.totalQuestions = subTotal
        questionCount += subTotal
      }
    } else if (sec.questions) {
      questionCount = sec.questions.length
    }
    return {
      ...sec,
      questionCount,
      tagType: SECTION_TAGS[sec.part] || 'info',
    }
  })
})

// 生成试卷
const createPaper = async () => {
  loading.value = true
  try {
    const res = await fetch('/api/paper/generate', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authStore.token}`
      },
      body: JSON.stringify(config.value)
    })
    const result = await res.json()

    if (result.code === 200) {
      ElMessage.success('✅ 试卷生成成功！')
      paperData.value = result.data
      paperId.value = result.paper_id
      examId.value = result.exam_id
      // 默认展开所有 section
      if (result.data && result.data.sections) {
        activeTypes.value = result.data.sections.map(s => s.part)
      }
    } else {
      ElMessage.error(result.msg || '生成失败')
    }
  } catch (err) {
    console.error(err)
    ElMessage.error('请求失败')
  } finally {
    loading.value = false
  }
}

// 导出试卷为Word
const exportPaper = async () => {
  ElMessage.info("正在生成试卷，请稍候...")
  try {
    const res = await fetch('/api/paper/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config.value)
    })

    if (!res.ok) {
      ElMessage.error("导出失败")
      return
    }

    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const contentDisposition = res.headers.get('content-disposition')
    const filename = contentDisposition
      ? contentDisposition.split('filename=')[1].replace(/"/g, '')
      : '四级模拟试卷.docx'
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)

    ElMessage.success("✅ 试卷导出成功！")
  } catch (err) {
    console.error(err)
    ElMessage.error("导出请求失败")
  }
}

</script>