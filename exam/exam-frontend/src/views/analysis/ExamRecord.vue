<template>
  <div style="padding:16px;">
    <h3 style="margin-bottom:16px;">答题记录管理</h3>

    <!-- 视图切换 + 操作栏 -->
    <el-card shadow="hover" style="margin-bottom:16px;">
      <el-row :gutter="16" align="middle">
        <el-col :xs="24" :sm="12" :md="8">
          <el-radio-group v-model="viewMode" size="default" @change="onViewModeChange">
            <el-radio-button value="detail">详细记录</el-radio-button>
            <el-radio-button value="summary">学生总成绩</el-radio-button>
          </el-radio-group>
        </el-col>
        <el-col :xs="24" :sm="12" :md="16" style="text-align:right;margin-top:8px;">
          <el-button type="success" @click="showImportDialog = true">
            <el-icon style="margin-right:4px;"><Upload /></el-icon>导入Excel
          </el-button>
          <el-button @click="downloadTemplate">
            <el-icon style="margin-right:4px;"><Download /></el-icon>下载模板
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 筛选栏 -->
    <el-card shadow="hover" style="margin-bottom:16px;">
      <el-form :inline="true" style="margin-bottom:0;">
        <el-form-item label="考试">
          <el-select v-model="filters.exam_id" placeholder="选择考试" clearable style="width:180px;" @change="onFilterChange">
            <el-option v-for="e in filterOptions.exam_ids" :key="e" :label="e" :value="e" />
          </el-select>
        </el-form-item>
        <el-form-item label="班级">
          <el-select v-model="filters.class_name" placeholder="选择班级" clearable style="width:150px;" @change="onFilterChange">
            <el-option v-for="c in filterOptions.class_names" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="学生姓名">
          <el-input v-model="filters.student_name" placeholder="搜索学生" clearable style="width:150px;" @change="onFilterChange" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- ============ 视图1: 详细记录 ============ -->
    <el-card v-show="viewMode === 'detail'" shadow="hover">
      <el-table :data="records" border stripe v-loading="loading" size="small" style="width:100%;">
        <el-table-column type="index" label="#" width="50" fixed="left" />
        <el-table-column prop="exam_id" label="考试" width="140" />
        <el-table-column prop="student_name" label="学生" width="90" />
        <el-table-column prop="class_name" label="班级" width="100" />
        <el-table-column prop="question_id" label="题号" width="65" />
        <el-table-column prop="question_type" label="题型" width="75">
          <template #default="{ row }">
            <el-tag :type="qtypeTag(row.question_type)" size="small">{{ row.question_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="得分" width="75" />
        <el-table-column prop="full_score" label="满分" width="75" />
        <el-table-column label="正确率" width="75">
          <template #default="{ row }">
            <span v-if="row.full_score > 0" :style="{color: row.score >= row.full_score ? '#67C23A' : '#F56C6C'}">
              {{ (row.score / row.full_score * 100).toFixed(0) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editRecord(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteRecord(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="totalPages > 1"
        :current-page="filters.page"
        :page-size="filters.size"
        :total="totalRecords"
        layout="total, prev, pager, next"
        background
        style="margin-top:16px;text-align:right;"
        @current-change="onPageChange"
      />
    </el-card>

    <!-- ============ 视图2: 学生总成绩 ============ -->
    <el-card v-show="viewMode === 'summary'" shadow="hover">
      <el-table :data="summaryData" border stripe v-loading="summaryLoading" size="small" style="width:100%;">
        <el-table-column type="index" label="#" width="50" fixed="left" />
        <el-table-column prop="student_name" label="学生姓名" width="100" />
        <el-table-column prop="class_name" label="班级" width="100" />
        <el-table-column prop="total_score" label="总分" width="80">
          <template #default="{ row }">
            <span style="font-weight:bold;color:#409EFF;">{{ row.total_score }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="total_full" label="满分" width="80" />
        <el-table-column label="得分率" width="90">
          <template #default="{ row }">
            <el-progress :percentage="row.score_rate" :color="rateColor(row.score_rate)" :stroke-width="16" />
          </template>
        </el-table-column>
        <el-table-column prop="question_count" label="答题数" width="75" />
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewStudentDetail(row)">
              详情
            </el-button>
            <el-button type="success" size="small" @click="viewStudentAnswers(row)">
              答卷
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!summaryLoading && summaryData.length === 0" description="暂无学生成绩数据" style="margin-top:20px;" />
    </el-card>

    <!-- ============ 学生详情抽屉 ============ -->
    <el-drawer
      v-model="detailDrawerVisible"
      :title="`${currentStudent?.student_name} 的得分详情`"
      size="600px"
      direction="rtl"
    >
      <template v-if="studentDetail">
        <el-descriptions :column="2" border size="small" style="margin-bottom:16px;">
          <el-descriptions-item label="班级">{{ studentDetail.class_name }}</el-descriptions-item>
          <el-descriptions-item label="考试">{{ studentDetail.exam_id }}</el-descriptions-item>
          <el-descriptions-item label="总分">
            <span style="font-weight:bold;color:#409EFF;font-size:18px;">{{ studentDetail.total_score }}</span>
            <span style="color:#999;"> / {{ studentDetail.total_full }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="得分率">
            <el-progress :percentage="studentDetail.score_rate" :color="rateColor(studentDetail.score_rate)" :stroke-width="16" style="width:120px;" />
          </el-descriptions-item>
        </el-descriptions>

        <!-- 题型得分统计 -->
        <h4 style="margin-bottom:8px;">题型得分统计</h4>
        <el-table :data="typeTable" border stripe size="small" style="width:100%;margin-bottom:16px;">
          <el-table-column prop="type" label="题型" width="70" />
          <el-table-column prop="score" label="得分" width="70" />
          <el-table-column prop="full_score" label="满分" width="70" />
          <el-table-column label="得分率" width="80">
            <template #default="{ row }">{{ (row.score_rate * 100).toFixed(0) }}%</template>
          </el-table-column>
          <el-table-column prop="count" label="题数" width="60" />
        </el-table>

        <!-- 每题得分明细 -->
        <h4 style="margin-bottom:8px;">每题得分明细</h4>
        <div style="display:flex;flex-wrap:wrap;gap:6px;max-height:360px;overflow-y:auto;padding:4px 0;">
          <div v-for="d in studentDetail.details" :key="d.question_id"
            :style="{
              width:'48px',height:'48px',display:'flex',flexDirection:'column',
              alignItems:'center',justifyContent:'center',
              borderRadius:'6px',fontSize:'11px',cursor:'default',
              background: d.score >= d.full_score ? '#e1f3d8' : '#fde2e2',
              color: d.score >= d.full_score ? '#67C23A' : '#F56C6C',
              border: d.score >= d.full_score ? '1px solid #b3e19d' : '1px solid #fab6b6',
              fontWeight:'bold'
            }"
            :title="`题${d.question_id}: ${d.score}/${d.full_score}`">
            <span>{{ d.question_id }}</span>
            <span style="font-size:10px;opacity:0.8;">{{ d.score }}</span>
          </div>
        </div>
      </template>
      <div v-else v-loading="detailLoading" style="height:200px;"></div>
    </el-drawer>

    <!-- ============ 学生答卷抽屉（左右分栏：左题目 + 右答案） ============ -->
    <el-drawer
      v-model="answerDrawerVisible"
      :title="`${answerStudent?.student_name} 的答题卡`"
      size="92%"
      direction="rtl"
    >
      <template v-if="answerData">
        <!-- 顶部统计 -->
        <el-row :gutter="16" style="margin-bottom:12px;">
          <el-col :span="8">
            <el-tag type="info">{{ answerData.exam_id }}</el-tag>
            <span style="margin-left:8px;font-weight:bold;">{{ answerData.student_name }}</span>
          </el-col>
          <el-col :span="4" style="text-align:center;">
            <span style="color:#409EFF;font-size:18px;font-weight:bold;">{{ answerData.total_score }}</span>
            <span style="color:#999;"> / {{ answerData.total_full }}</span>
          </el-col>
          <el-col :span="4" style="text-align:center;">
            <el-progress :percentage="answerData.score_rate" :color="rateColor(answerData.score_rate)" :stroke-width="18" style="width:120px;display:inline-block;" />
          </el-col>
          <el-col :span="8" style="text-align:right;">
            <el-tag type="success" size="default">共 {{ answerData.question_count }} 题</el-tag>
          </el-col>
        </el-row>

        <!-- 左右分栏：左侧题目 + 右侧答案 -->
        <div style="display:flex;gap:12px;height:calc(100vh - 160px);overflow:hidden;">
          <!-- 左侧：题号导航 + 题目内容 -->
          <div style="width:200px;min-width:200px;overflow-y:auto;border:1px solid #eee;border-radius:6px;padding:8px;">
            <div style="font-size:13px;font-weight:bold;color:#333;margin-bottom:8px;">题号导航</div>
            <div v-for="d in answerData.details" :key="d.question_id"
              @click="scrollToAnswer(d.question_id)"
              :style="{
                display:'flex',alignItems:'center',gap:'6px',padding:'6px 8px',marginBottom:'4px',
                borderRadius:'4px',cursor:'pointer',fontSize:'13px',
                background: currentAnswerId === d.question_id ? '#ecf5ff' : (d.score > 0 ? '#e1f3d8' : '#fef0f0'),
                border: currentAnswerId === d.question_id ? '1px solid #409EFF' : (d.score > 0 ? '1px solid #b3e19d' : '1px solid #fde2e2'),
              }">
              <span :style="{
                width:'22px',height:'22px',display:'flex',alignItems:'center',justifyContent:'center',
                borderRadius:'50%',fontSize:'11px',fontWeight:'bold',flexShrink:0,
                background: d.score > 0 ? '#67C23A' : '#F56C6C',
                color:'#fff'
              }">{{ d.question_id }}</span>
              <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;color:#666;">
                {{ d.type }}
              </span>
              <span :style="{fontSize:'12px',fontWeight:'bold',color:d.score>0?'#67C23A':'#F56C6C'}">{{ d.score }}</span>
            </div>
          </div>

          <!-- 右侧：题目与答案详情 -->
          <div style="flex:1;overflow-y:auto;padding-right:4px;">
            <div v-for="d in answerData.details" :key="d.question_id"
              :id="'ans-' + d.question_id"
              :style="{
                border: currentAnswerId === d.question_id ? '2px solid #409EFF' : '1px solid #e8e8e8',
                borderRadius:'8px',padding:'14px',marginBottom:'12px',
                background: currentAnswerId === d.question_id ? '#f8fbff' : '#fff'
              }"
              @click="currentAnswerId = d.question_id">

              <!-- 题头 -->
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                <span :style="{
                  width:'26px',height:'26px',display:'flex',alignItems:'center',justifyContent:'center',
                  borderRadius:'50%',fontSize:'13px',fontWeight:'bold',color:'#fff',
                  background: d.score > 0 ? '#67C23A' : '#F56C6C'
                }">{{ d.question_id }}</span>
                <el-tag :type="d.is_subjective ? 'success' : 'primary'" size="small" effect="plain">{{ d.type }}</el-tag>
                <span style="font-size:12px;color:#999;">{{ d.full_score }}分</span>
                <span style="margin-left:auto;font-weight:bold;font-size:14px;"
                  :style="{color: d.score > 0 ? '#67C23A' : '#F56C6C'}">
                  得分：{{ d.score }}
                </span>
              </div>

              <!-- 题目内容 -->
              <div style="font-size:13px;line-height:1.7;color:#333;margin-bottom:10px;padding:10px;background:#f8f9fa;border-radius:4px;white-space:pre-wrap;">
                <div style="font-size:11px;color:#999;margin-bottom:4px;">📄 题目：</div>
                {{ d.question_content || '（题目内容未加载）' }}
              </div>

              <!-- 答案对比 -->
              <div style="display:flex;gap:16px;font-size:13px;">
                <div style="flex:1;padding:8px 12px;border-radius:4px;background:#fef0f0;">
                  <div style="font-size:11px;color:#999;margin-bottom:2px;">你的答案</div>
                  <span :style="{color: d.student_answer ? '#333' : '#ccc'}">{{ d.student_answer || '未作答' }}</span>
                </div>
                <div v-if="!d.is_subjective" style="flex:1;padding:8px 12px;border-radius:4px;background:#f0f9eb;">
                  <div style="font-size:11px;color:#999;margin-bottom:2px;">正确答案</div>
                  <span :style="{color: d.correct_answer ? '#67C23A' : '#E6A23C', fontWeight:'bold'}">
                    {{ d.correct_answer || '无答案' }}
                  </span>
                </div>
                <div v-else style="flex:1;padding:8px 12px;border-radius:4px;background:#fdf6ec;">
                  <div style="font-size:11px;color:#999;margin-bottom:2px;">评分方式</div>
                  <span style="color:#E6A23C;">AI 智能评分</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
      <div v-else v-loading="answerLoading" style="height:300px;">
        <el-empty v-if="!answerLoading && !answerData" description="无原始答卷数据（可能为Excel导入的模拟数据）" />
      </div>
    </el-drawer>

    <!-- ============ Excel导入对话框 ============ -->
    <el-dialog v-model="showImportDialog" title="导入答题记录 (Excel)" width="520px">
      <div style="text-align:center;padding:16px 0;">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :on-change="handleFileChange"
          accept=".xlsx,.xls"
          :show-file-list="true"
          :limit="1"
          :on-exceed="() => ElMessage.warning('只能上传一个文件')"
        >
          <el-button type="primary">
            <el-icon style="margin-right:4px;"><FolderOpened /></el-icon>选择Excel文件
          </el-button>
          <div style="margin-top:8px;font-size:12px;color:#999;">
            支持 .xlsx / .xls 格式，可先<a href="javascript:void(0)" @click="downloadTemplate" style="color:#409EFF;">下载模板</a>填写数据
          </div>
        </el-upload>
      </div>

      <div v-if="importResult" style="margin-top:12px;">
        <el-alert
          :title="importResult.msg"
          :type="importResult.code === 200 ? 'success' : 'error'"
          :closable="false"
          show-icon
        />
        <div v-if="importResult.errors && importResult.errors.length" style="margin-top:8px;">
          <p style="color:#E6A23C;font-size:13px;">以下行导入异常：</p>
          <div style="max-height:120px;overflow-y:auto;background:#fdf6ec;padding:8px;border-radius:4px;">
            <p v-for="(err, i) in importResult.errors" :key="i" style="font-size:12px;color:#E6A23C;margin:2px 0;">{{ err }}</p>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="closeImportDialog">取消</el-button>
        <el-button type="success" @click="submitImport" :loading="importLoading" :disabled="!importFile">
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <!-- ============ 编辑对话框 ============ -->
    <el-dialog v-model="showEditDialog" title="编辑记录" width="420px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="考试ID">
          <el-input v-model="editForm.exam_id" />
        </el-form-item>
        <el-form-item label="学生姓名">
          <el-input v-model="editForm.student_name" />
        </el-form-item>
        <el-form-item label="班级">
          <el-input v-model="editForm.class_name" />
        </el-form-item>
        <el-form-item label="题号">
          <el-input-number v-model="editForm.question_id" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="得分">
          <el-input-number v-model="editForm.score" :min="0" :step="0.1" />
        </el-form-item>
        <el-form-item label="满分">
          <el-input-number v-model="editForm.full_score" :min="0" :step="0.1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Download, FolderOpened } from '@element-plus/icons-vue'
import axios from 'axios'

const API_BASE = ''

// ── 状态 ──
const viewMode = ref('detail')
const loading = ref(false)
const summaryLoading = ref(false)
const records = ref([])
const summaryData = ref([])
const totalRecords = ref(0)
const totalPages = ref(0)
const filterOptions = reactive({ exam_ids: [], class_names: [] })
const filters = reactive({ exam_id: '', class_name: '', student_name: '', page: 1, size: 20 })

// 编辑
const showEditDialog = ref(false)
const editingId = ref(null)
const editForm = reactive({ exam_id: '', student_name: '', class_name: '', question_id: 1, score: 0, full_score: 1 })

// 导入
const showImportDialog = ref(false)
const importFile = ref(null)
const importLoading = ref(false)
const importResult = ref(null)
const uploadRef = ref(null)

// 学生详情抽屉
const detailDrawerVisible = ref(false)
const currentStudent = ref(null)
const studentDetail = ref(null)
const detailLoading = ref(false)

// 学生答卷抽屉
const answerDrawerVisible = ref(false)
const answerStudent = ref(null)
const answerData = ref(null)
const answerLoading = ref(false)
const currentAnswerId = ref(0)

function scrollToAnswer(qid) {
  currentAnswerId.value = qid
  setTimeout(() => {
    const el = document.getElementById('ans-' + qid)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, 100)
}

const TYPE_TAGS = { '写作': 'success', '听力': 'warning', '阅读': 'primary', '翻译': 'info' }
function qtypeTag(type) { return TYPE_TAGS[type] || 'info' }
function rateColor(rate) { return rate >= 80 ? '#67C23A' : rate >= 50 ? '#E6A23C' : '#F56C6C' }

const typeTable = computed(() => {
  if (!studentDetail.value) return []
  return Object.entries(studentDetail.value.type_scores || {}).map(([type, info]) => ({ type, ...info }))
})

// ── 筛选选项 ──
async function loadFilters() {
  try {
    const res = await axios.get(`${API_BASE}/api/exam-record/filters`)
    if (res.data.code === 200) {
      filterOptions.exam_ids = res.data.exam_ids
      filterOptions.class_names = res.data.class_names
    }
  } catch (e) { console.error('加载筛选失败', e) }
}

// ── 详细记录 ──
async function loadRecords() {
  loading.value = true
  try {
    const params = { page: filters.page, size: filters.size }
    if (filters.exam_id) params.exam_id = filters.exam_id
    if (filters.class_name) params.class_name = filters.class_name
    if (filters.student_name) params.student_name = filters.student_name
    const res = await axios.get(`${API_BASE}/api/exam-record/list`, { params })
    if (res.data.code === 200) {
      records.value = res.data.data
      totalRecords.value = res.data.total
      totalPages.value = res.data.pages
    }
  } catch (e) { console.error('加载记录失败', e) }
  finally { loading.value = false }
}

// ── 学生总成绩 ──
async function loadSummary() {
  summaryLoading.value = true
  try {
    const params = {}
    if (filters.exam_id) params.exam_id = filters.exam_id
    if (filters.class_name) params.class_name = filters.class_name
    if (filters.student_name) params.student_name = filters.student_name
    const res = await axios.get(`${API_BASE}/api/exam-record/student-summary`, { params })
    if (res.data.code === 200) summaryData.value = res.data.data
  } catch (e) { console.error('加载总成绩失败', e) }
  finally { summaryLoading.value = false }
}

function onFilterChange() {
  filters.page = 1
  if (viewMode.value === 'detail') loadRecords()
  else loadSummary()
}

function onPageChange(page) {
  filters.page = page
  loadRecords()
}

// ── 编辑 ──
function editRecord(row) {
  editingId.value = row.id
  Object.assign(editForm, {
    exam_id: row.exam_id, student_name: row.student_name, class_name: row.class_name,
    question_id: row.question_id, score: row.score, full_score: row.full_score
  })
  showEditDialog.value = true
}

async function submitEdit() {
  try {
    await axios.put(`${API_BASE}/api/exam-record/${editingId.value}`, editForm)
    showEditDialog.value = false
    editingId.value = null
    ElMessage.success('修改成功')
    loadRecords()
  } catch (e) { console.error('修改失败', e); ElMessage.error('修改失败') }
}

// ── 删除 ──
async function deleteRecord(id) {
  ElMessageBox.confirm('确定要删除该记录吗？', '提示', {
    confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning'
  }).then(async () => {
    try {
      await axios.delete(`${API_BASE}/api/exam-record/${id}`)
      ElMessage.success('删除成功')
      loadRecords()
    } catch (e) { console.error('删除失败', e); ElMessage.error('删除失败') }
  }).catch(() => {})
}

// ── 学生详情抽屉 ──
async function viewStudentDetail(row) {
  currentStudent.value = row
  detailDrawerVisible.value = true
  detailLoading.value = true
  studentDetail.value = null
  try {
    const res = await axios.get(`${API_BASE}/api/analysis/student`, {
      params: { exam_id: row.exam_id, student_name: row.student_name }
    })
    if (res.data.code === 200) studentDetail.value = res.data.data
    else ElMessage.error(res.data.msg || '加载失败')
  } catch (e) { console.error('加载详情失败', e); ElMessage.error('加载详情失败') }
  finally { detailLoading.value = false }
}

// ── 查看学生答卷 ──
async function viewStudentAnswers(row) {
  answerStudent.value = row
  answerDrawerVisible.value = true
  answerLoading.value = true
  answerData.value = null
  try {
    const res = await axios.get(`${API_BASE}/api/exam/student-answers`, {
      params: { exam_id: row.exam_id, student_name: row.student_name }
    })
    if (res.data.code === 200) {
      answerData.value = res.data.data
    } else if (res.data.code === 404) {
      ElMessage.info('该学生为导入数据，无原始答卷记录')
      answerDrawerVisible.value = false
    } else {
      ElMessage.error(res.data.msg || '加载失败')
    }
  } catch (e) {
    console.error('加载答卷失败', e)
    ElMessage.error('加载答卷失败')
    answerDrawerVisible.value = false
  } finally { answerLoading.value = false }
}

// ── Excel导入 ──
function handleFileChange(uploadFile) {
  importFile.value = uploadFile.raw
  importResult.value = null
}

async function submitImport() {
  if (!importFile.value) { ElMessage.warning('请先选择文件'); return }
  importLoading.value = true
  importResult.value = null
  const formData = new FormData()
  formData.append('file', importFile.value)
  try {
    const res = await axios.post(`${API_BASE}/api/exam-record/import-excel`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    importResult.value = res.data
    if (res.data.code === 200) {
      ElMessage.success(res.data.msg)
      if (viewMode.value === 'detail') loadRecords()
      else loadSummary()
    } else {
      ElMessage.error(res.data.msg || '导入失败')
    }
  } catch (e) {
    console.error('导入失败', e)
    importResult.value = { code: 500, msg: '导入请求失败，请确认后端服务已启动' }
    ElMessage.error('导入请求失败')
  } finally {
    importLoading.value = false
  }
}

function closeImportDialog() {
  showImportDialog.value = false
  importFile.value = null
  importResult.value = null
}

function downloadTemplate() {
  window.open(`${API_BASE}/api/exam-record/download-template`, '_blank')
}

// ── 视图切换 ──
function onViewModeChange() {
  filters.page = 1
  if (viewMode.value === 'detail') loadRecords()
  else loadSummary()
}

// ── 初始化 ──
onMounted(() => {
  loadFilters()
  loadRecords()
})
</script>
