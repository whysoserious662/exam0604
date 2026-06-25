<template>
  <div style="padding: 16px; max-width: 1200px; margin: 0 auto;">
    <!-- ============ 模式1：填写信息 + 选择试卷 ============ -->
    <template v-if="mode === 'info'">
      <el-card shadow="hover">
        <template #header>
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:18px;font-weight:bold;">📝 CET4 在线考试</span>
          </div>
        </template>

        <el-form :model="form" label-width="100px" style="max-width:500px;margin:20px auto;">
          <el-form-item label="学生姓名" required>
            <el-input v-model="form.student_name" placeholder="请输入你的姓名" clearable />
          </el-form-item>
          <el-form-item label="班级" required>
            <el-input v-model="form.class_name" placeholder="请输入班级" clearable />
          </el-form-item>
          <el-form-item label="选择试卷" required>
            <el-select v-model="form.exam_id" placeholder="请选择一张试卷" style="width:100%;"
              :loading="loadingPapers" @focus="loadPapers">
              <el-option v-for="p in paperList" :key="p.exam_id" :label="p.exam_id" :value="p.exam_id">
                <div style="display:flex;justify-content:space-between;font-size:13px;">
                  <span>{{ p.exam_id }}</span>
                  <span style="color:#909399;">{{ p.question_count }}题 · {{ p.total_score }}分</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="large" style="width:100%;"
              @click="startExam" :loading="starting" :disabled="!canStart">
              进入考试
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </template>

    <!-- ============ 模式2：答题中 ============ -->
    <template v-if="mode === 'exam'">
      <!-- 顶部信息栏 -->
      <el-card shadow="hover" style="margin-bottom:12px;">
        <el-row :gutter="16" align="middle">
          <el-col :xs="24" :sm="6">
            <span style="font-weight:bold;">{{ examInfo.exam_id }}</span>
          </el-col>
          <el-col :xs="12" :sm="6">
            <span style="color:#666;font-size:13px;">考生：</span>
            <span>{{ examInfo.student_name }}</span>
          </el-col>
          <el-col :xs="12" :sm="6">
            <span style="color:#666;font-size:13px;">班级：</span>
            <span>{{ examInfo.class_name }}</span>
          </el-col>
          <el-col :xs="12" :sm="6" style="text-align:right;">
            <span style="color:#909399;font-size:13px;">
              已答 <b style="color:#67C23A;font-size:16px;">{{ answeredCount }}</b> / {{ questions.length }} 题
            </span>
          </el-col>
        </el-row>
      </el-card>

      <el-row :gutter="12">
        <!-- 左侧：题号导航 -->
        <el-col :xs="24" :sm="5" :md="4">
          <el-card shadow="hover" :body-style="{padding:'12px'}" style="position:sticky;top:12px;">
            <div style="font-size:13px;font-weight:bold;color:#333;margin-bottom:8px;">题号导航</div>
            <div v-for="group in sectionGroups" :key="group.label" style="margin-bottom:8px;">
              <div style="font-size:11px;color:#999;margin-bottom:4px;">{{ group.label }}</div>
              <div style="display:flex;flex-wrap:wrap;gap:4px;">
                <div v-for="q in group.questions" :key="q.qid"
                  @click="scrollToQuestion(q.qid)"
                  :style="{
                    width:'30px',height:'30px',display:'flex',alignItems:'center',justifyContent:'center',
                    borderRadius:'6px',cursor:'pointer',fontSize:'13px',fontWeight:'bold',
                    background: currentQid === q.qid ? '#409EFF' : (answerMap[q.qid] ? '#e1f3d8' : '#f5f5f5'),
                    color: currentQid === q.qid ? '#fff' : (answerMap[q.qid] ? '#67C23A' : '#666'),
                    border: currentQid === q.qid ? '2px solid #409EFF' : (answerMap[q.qid] ? '1px solid #b3e19d' : '1px solid #eee')
                  }"
                  :title="`第${q.qid}题`">
                  {{ q.qid }}
                </div>
              </div>
            </div>
            <el-divider style="margin:8px 0;" />
            <el-button type="success" style="width:100%;margin-top:4px;"
              @click="confirmSubmit" :disabled="answeredCount === 0">
              提交答卷
            </el-button>
          </el-card>
        </el-col>

        <!-- 右侧：题目区域 -->
        <el-col :xs="24" :sm="19" :md="20">
          <div v-if="paperData && paperData.sections">
            <div v-for="section in paperData.sections" :key="section.part">
              <!-- 写作、听力、翻译：扁平化展示 -->
              <template v-if="!section.subsections">
                <el-card shadow="hover" style="margin-bottom:16px;">
                  <template #header>
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                      <span style="font-weight:bold;font-size:15px;">{{ section.part }}</span>
                      <span style="font-size:13px;color:#999;">
                        {{ section.questions ? section.questions.length : 0 }} 题
                      </span>
                    </div>
                  </template>

                  <div v-for="q in section.questions" :key="q.qid"
                    :id="'q-' + q.qid"
                    :style="{
                      padding: '16px 12px', marginBottom: '12px',
                      borderRadius: '8px', cursor: 'pointer',
                      border: currentQid === q.qid ? '2px solid #409EFF' : '1px solid #eee',
                      background: currentQid === q.qid ? '#f8fbff' : '#fff'
                    }"
                    @click="currentQid = q.qid">

                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
                      <el-tag :type="q.type === '写作' || q.type === '翻译' ? 'success' : 'primary'" size="small" effect="plain">
                        {{ q.type }}
                      </el-tag>
                      <span style="font-size:14px;font-weight:bold;">第 {{ q.qid }} 题</span>
                      <span style="font-size:12px;color:#999;">（{{ q.full_score }} 分）</span>
                    </div>

                    <div style="font-size:14px;line-height:1.8;white-space:pre-wrap;margin-bottom:12px;color:#333;">
                      {{ q.content }}
                    </div>

                    <div v-if="q.options && q.options.length > 0">
                      <div v-for="opt in q.options" :key="opt.label"
                        @click="answerMap[q.qid] = opt.label; scrollToQuestion(Math.min(q.qid + 1, 57))"
                        :style="{
                          margin: '6px 0', padding: '10px 14px',
                          borderRadius: '8px', cursor: 'pointer',
                          border: answerMap[q.qid] === opt.label ? '2px solid #409EFF' : '1px solid #e8e8e8',
                          background: answerMap[q.qid] === opt.label ? '#ecf5ff' : '#fff',
                          transition: 'all 0.15s'
                        }">
                        <span style="font-size:14px;display:flex;align-items:center;gap:8px;">
                          <span :style="{
                            display:'inline-flex',width:'24px',height:'24px',borderRadius:'50%',
                            alignItems:'center',justifyContent:'center',
                            background: answerMap[q.qid] === opt.label ? '#409EFF' : '#f0f0f0',
                            color: answerMap[q.qid] === opt.label ? '#fff' : '#666',
                            fontWeight:'bold',fontSize:'13px'
                          }">{{ opt.label }}</span>
                          <span>{{ opt.text }}</span>
                        </span>
                      </div>
                    </div>

                    <div v-if="!q.options || q.options.length === 0">
                      <el-input type="textarea"
                        :rows="q.qid === 1 ? 8 : 5"
                        :placeholder="q.qid === 1 ? '请在此输入作文...（建议120-180词）' : q.qid === 57 ? '请在此输入翻译...' : '请输入答案...'"
                        v-model="answerMap[q.qid]"
                        @focus="currentQid = q.qid"
                        style="font-size:14px;" />
                    </div>
                  </div>
                </el-card>
              </template>

              <!-- 阅读理解：分组展示 -->
              <template v-else>
                <el-card shadow="hover" style="margin-bottom:16px;">
                  <template #header>
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                      <span style="font-weight:bold;font-size:15px;">{{ section.part }}</span>
                    </div>
                  </template>

                  <div v-for="sub in section.subsections" :key="sub.title" style="margin-bottom:24px;">
                    <h4 style="color:#303133;margin-bottom:12px;border-left:4px solid #409EFF;padding-left:10px;">
                      {{ sub.title }}
                    </h4>

                    <div v-for="(pg, pgIdx) in sub.groups" :key="'pg-'+pgIdx"
                      style="margin-bottom:20px;border:2px solid #dcdfe6;border-radius:8px;overflow:hidden;">

                      <!-- Passage 原文（只显示一次） -->
                      <div v-if="pg.passage" style="background:#f0f2f5;padding:14px 20px;border-bottom:1px solid #dcdfe6;">
                        <span style="font-weight:bold;font-size:14px;color:#303133;">
                          {{ sub.type === '仔细阅读' ? `Passage ${pgIdx + 1}` : '原文' }}
                        </span>
                      </div>
                      <div v-if="pg.passage" style="padding:16px 20px;font-size:14px;line-height:2;white-space:pre-wrap;color:#303133;">
                        {{ pg.passage }}
                      </div>

                      <!-- 该 Passage 下的题目 -->
                      <div style="padding:8px 12px 12px;">
                        <div v-for="q in pg.questions" :key="q.qid"
                          :id="'q-' + q.qid"
                          :style="{
                            padding: '10px 0', borderBottom: '1px dashed #ebeef5',
                            borderRadius: '8px', cursor: 'pointer',
                            border: currentQid === q.qid ? '2px solid #409EFF' : '1px solid transparent',
                            background: currentQid === q.qid ? '#f8fbff' : 'transparent'
                          }"
                          @click="currentQid = q.qid">

                          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
                            <el-tag :type="sub.type === '仔细阅读' ? 'primary' : 'info'" size="small" effect="plain">
                              {{ sub.type }}
                            </el-tag>
                            <span style="font-size:14px;font-weight:bold;">第 {{ q.qid }} 题</span>
                            <span style="font-size:12px;color:#999;">（{{ q.full_score }} 分）</span>
                          </div>

                          <div style="font-size:14px;line-height:1.8;margin-bottom:6px;">
                            {{ q.content }}
                          </div>

                          <!-- 选词填空和段落匹配：不显示选项，直接输入答案 -->
                          <template v-if="sub.type === '选词填空' || sub.type === '段落匹配'">
                            <el-input v-model="answerMap[q.qid]"
                              placeholder="请输入答案"
                              @focus="currentQid = q.qid"
                              style="margin-top:8px;" />
                          </template>

                          <!-- 仔细阅读：显示选项 -->
                          <template v-else>
                            <div v-if="q.options && q.options.length > 0" style="margin-left:24px;">
                              <div v-for="opt in q.options" :key="opt.label"
                                @click="answerMap[q.qid] = opt.label; scrollToQuestion(Math.min(q.qid + 1, 57))"
                                :style="{
                                  margin: '6px 0', padding: '10px 14px',
                                  borderRadius: '8px', cursor: 'pointer',
                                  border: answerMap[q.qid] === opt.label ? '2px solid #409EFF' : '1px solid #e8e8e8',
                                  background: answerMap[q.qid] === opt.label ? '#ecf5ff' : '#fff',
                                  transition: 'all 0.15s'
                                }">
                                <span style="font-size:14px;display:flex;align-items:center;gap:8px;">
                                  <span :style="{
                                    display:'inline-flex',width:'24px',height:'24px',borderRadius:'50%',
                                    alignItems:'center',justifyContent:'center',
                                    background: answerMap[q.qid] === opt.label ? '#409EFF' : '#f0f0f0',
                                    color: answerMap[q.qid] === opt.label ? '#fff' : '#666',
                                    fontWeight:'bold',fontSize:'13px'
                                  }">{{ opt.label }}</span>
                                  <span>{{ opt.text }}</span>
                                </span>
                              </div>
                            </div>
                          </template>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-card>
              </template>
            </div>
          </div>

          <!-- 降级：如果没有完整 paperData，使用扁平化展示 -->
          <div v-else v-for="group in sectionGroups" :key="group.label">
            <el-card shadow="hover" style="margin-bottom:16px;">
              <template #header>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                  <span style="font-weight:bold;font-size:15px;">{{ group.label }}</span>
                  <span style="font-size:13px;color:#999;">
                    {{ group.questions.length }} 题 · {{ group.totalScore }} 分
                  </span>
                </div>
              </template>

              <div v-for="q in group.questions" :key="q.qid"
                :id="'q-' + q.qid"
                :style="{
                  padding: '16px 12px', marginBottom: '12px',
                  borderRadius: '8px', cursor: 'pointer',
                  border: currentQid === q.qid ? '2px solid #409EFF' : '1px solid #eee',
                  background: currentQid === q.qid ? '#f8fbff' : '#fff'
                }"
                @click="currentQid = q.qid">

                <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
                  <el-tag :type="q.is_subjective ? 'success' : 'primary'" size="small" effect="plain">
                    {{ q.type }}
                  </el-tag>
                  <span style="font-size:14px;font-weight:bold;">第 {{ q.qid }} 题</span>
                  <span style="font-size:12px;color:#999;">（{{ q.full_score }} 分）</span>
                </div>

                <div style="font-size:14px;line-height:1.8;white-space:pre-wrap;margin-bottom:12px;color:#333;">
                  {{ q.content }}
                </div>

                <div v-if="q.options && q.options.length > 0">
                  <div v-for="opt in q.options" :key="opt.label"
                    @click="answerMap[q.qid] = opt.label; scrollToQuestion(Math.min(q.qid + 1, 57))"
                    :style="{
                      margin: '6px 0', padding: '10px 14px',
                      borderRadius: '8px', cursor: 'pointer',
                      border: answerMap[q.qid] === opt.label ? '2px solid #409EFF' : '1px solid #e8e8e8',
                      background: answerMap[q.qid] === opt.label ? '#ecf5ff' : '#fff',
                      transition: 'all 0.15s'
                    }">
                    <span style="font-size:14px;display:flex;align-items:center;gap:8px;">
                      <span :style="{
                        display:'inline-flex',width:'24px',height:'24px',borderRadius:'50%',
                        alignItems:'center',justifyContent:'center',
                        background: answerMap[q.qid] === opt.label ? '#409EFF' : '#f0f0f0',
                        color: answerMap[q.qid] === opt.label ? '#fff' : '#666',
                        fontWeight:'bold',fontSize:'13px'
                      }">{{ opt.label }}</span>
                      <span>{{ opt.text }}</span>
                    </span>
                  </div>
                </div>

                <div v-if="!q.options || q.options.length === 0">
                  <el-input type="textarea"
                    :rows="q.qid === 1 ? 8 : 5"
                    :placeholder="q.qid === 1 ? '请在此输入作文...（建议120-180词）' : q.qid === 57 ? '请在此输入翻译...' : '请输入答案...'"
                    v-model="answerMap[q.qid]"
                    @focus="currentQid = q.qid"
                    style="font-size:14px;" />
                </div>
              </div>
            </el-card>
          </div>
        </el-col>
      </el-row>
    </template>

    <!-- ============ 模式3：评分结果 ============ -->
    <template v-if="mode === 'result'">
      <el-card shadow="hover">
        <template #header>
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:18px;font-weight:bold;">📊 成绩报告</span>
          </div>
        </template>

        <el-row :gutter="16" style="margin-bottom:20px;">
          <el-col :xs="12" :sm="6">
            <el-card shadow="hover" :body-style="{padding:'16px'}">
              <div style="text-align:center;">
                <div style="font-size:28px;font-weight:bold;color:#409EFF;">{{ gradeResult.total_score }}</div>
                <div style="font-size:13px;color:#909399;">总分 / {{ gradeResult.total_full }}</div>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-card shadow="hover" :body-style="{padding:'16px'}">
              <div style="text-align:center;">
                <div :style="{fontSize:'28px',fontWeight:'bold',color: rateColor(gradeResult.score_rate)}">
                  {{ gradeResult.score_rate }}%
                </div>
                <div style="font-size:13px;color:#909399;">得分率</div>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-card shadow="hover" :body-style="{padding:'16px'}">
              <div style="text-align:center;">
                <div style="font-size:28px;font-weight:bold;color:#67C23A;">{{ gradeResult.graded_count }}</div>
                <div style="font-size:13px;color:#909399;">批改题数</div>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-card shadow="hover" :body-style="{padding:'16px'}">
              <div style="text-align:center;">
                <div style="font-size:28px;font-weight:bold;color:#E6A23C;">{{ correctCount }}</div>
                <div style="font-size:13px;color:#909399;">客观题正确数</div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-table :data="gradeResult.details" border stripe size="small" style="width:100%;margin-bottom:16px;">
          <el-table-column label="题号" prop="question_id" width="60" />
          <el-table-column label="题型" prop="type" width="80">
            <template #default="{row}">
              <el-tag :type="row.is_subjective ? 'success' : 'primary'" size="small">{{ row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="得分" width="70">
            <template #default="{row}">
              <span :style="{color: row.score > 0 ? '#67C23A' : '#F56C6C', fontWeight:'bold'}">{{ row.score }}</span>
            </template>
          </el-table-column>
          <el-table-column label="满分" prop="full_score" width="70" />
          <el-table-column label="你选" prop="student_answer" min-width="80" />
          <el-table-column label="正确答案" min-width="80">
            <template #default="{row}">
              <span v-if="row.is_subjective" style="color:#999;">—</span>
              <span v-else-if="row.correct_answer" style="color:#67C23A;font-weight:bold;">{{ row.correct_answer }}</span>
              <span v-else style="color:#E6A23C;">无答案</span>
            </template>
          </el-table-column>
          <el-table-column label="评分方式" width="80">
            <template #default="{row}">
              <el-tag v-if="row.is_subjective" type="warning" size="small">AI评分</el-tag>
              <el-tag v-else size="small" effect="plain">客观匹配</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <div style="text-align:center;margin-top:16px;">
          <el-button @click="resetExam">返回首页</el-button>
          <el-button type="primary" @click="mode='result'; showDetail=!showDetail">刷新</el-button>
        </div>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const API_BASE = ''

const mode = ref('info')
const form = reactive({ student_name: '', class_name: '', exam_id: '' })
const paperList = ref([])
const loadingPapers = ref(false)
const starting = ref(false)

const questions = ref([])
const paperData = ref(null)
const examInfo = reactive({ exam_id: '', student_name: '', class_name: '' })
const currentQid = ref(1)
const answerMap = reactive({})

const gradeResult = ref(null)
const showDetail = ref(true)
const submitting = ref(false)

const canStart = computed(() => form.student_name.trim() && form.class_name.trim() && form.exam_id)

const answeredCount = computed(() => {
  return Object.values(answerMap).filter(v => v !== undefined && v !== null && String(v).trim() !== '').length
})

const correctCount = computed(() => {
  if (!gradeResult.value) return 0
  return gradeResult.value.details.filter(d => !d.is_subjective && d.score > 0).length
})

function rateColor(rate) {
  return rate >= 80 ? '#67C23A' : rate >= 50 ? '#E6A23C' : '#F56C6C'
}

const sectionGroups = computed(() => {
  const groups = []
  let current = null
  for (const q of questions.value) {
    if (!current || current.label !== q.section) {
      current = { label: q.section, questions: [], totalScore: 0 }
      groups.push(current)
    }
    current.questions.push(q)
    current.totalScore += q.full_score
  }
  return groups
})

async function loadPapers() {
  if (paperList.value.length > 0) return
  loadingPapers.value = true
  try {
    const res = await axios.get(`${API_BASE}/api/exam/paper-list`)
    if (res.data.code === 200) paperList.value = res.data.data
  } catch (e) {
    console.error('加载试卷列表失败', e)
  } finally {
    loadingPapers.value = false
  }
}

async function startExam() {
  starting.value = true
  try {
    const res = await axios.post(`${API_BASE}/api/exam/start`, {
      exam_id: form.exam_id,
      student_name: form.student_name.trim(),
      class_name: form.class_name.trim(),
    })
    if (res.data.code === 200) {
      questions.value = res.data.questions || []
      paperData.value = res.data.paper || null
      examInfo.exam_id = res.data.exam_id
      examInfo.student_name = res.data.student_name
      examInfo.class_name = res.data.class_name
      Object.keys(answerMap).forEach(k => delete answerMap[k])
      currentQid.value = 1
      mode.value = 'exam'
      setTimeout(() => scrollToQuestion(1), 200)
    } else {
      ElMessage.error(res.data.msg || '加载试卷失败')
    }
  } catch (e) {
    ElMessage.error('请求失败，请检查后端服务')
  } finally {
    starting.value = false
  }
}

function scrollToQuestion(qid) {
  currentQid.value = qid
  setTimeout(() => {
    const el = document.getElementById('q-' + qid)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, 100)
}

async function confirmSubmit() {
  const total = questions.value.length
  const answered = answeredCount.value
  if (answered === 0) return

  try {
    await ElMessageBox.confirm(
      `共 ${total} 题，已答 ${answered} 题，未答 ${total - answered} 题。\n提交后将自动进行AI评分，确定提交吗？`,
      '确认提交',
      { confirmButtonText: '确定提交', cancelButtonText: '再检查', type: 'warning' }
    )
  } catch { return }

  await submitExam()
}

async function submitExam() {
  submitting.value = true
  try {
    const answerList = Object.entries(answerMap)
      .filter(([, v]) => v !== undefined && v !== null && String(v).trim() !== '')
      .map(([qid, text]) => ({
        question_id: parseInt(qid),
        answer_text: String(text).trim(),
      }))

    const res = await axios.post(`${API_BASE}/api/exam/grade`, {
      exam_id: examInfo.exam_id,
      student_name: examInfo.student_name,
      class_name: examInfo.class_name,
      answers: answerList,
    })

    if (res.data.code === 200) {
      gradeResult.value = res.data.data
      mode.value = 'result'
      ElMessage.success(res.data.msg)
    } else {
      ElMessage.error(res.data.msg || '提交评分失败')
    }
  } catch (e) {
    console.error('提交失败', e)
    ElMessage.error('提交失败，请重试')
  } finally {
    submitting.value = false
  }
}

function resetExam() {
  mode.value = 'info'
  Object.keys(answerMap).forEach(k => delete answerMap[k])
  gradeResult.value = null
  questions.value = []
  paperData.value = null
}

onMounted(() => {
  loadPapers()
})
</script>
