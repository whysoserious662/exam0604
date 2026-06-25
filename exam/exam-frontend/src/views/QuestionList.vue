<template>
  <div>
    <h3>四级真题题库管理</h3>

    <!-- 题型筛选 -->
    <el-form inline style="margin-top:16px">
      <el-form-item label="题型筛选">
        <el-select v-model="filterType" placeholder="全部题型" clearable @change="getList">
          <el-option label="写作" value="写作" />
          <el-option label="听力" value="听力" />
          <el-option label="阅读" value="阅读" />
          <el-option label="翻译" value="翻译" />
        </el-select>
      </el-form-item>
      <el-form-item label="大题筛选">
        <el-input v-model="filterSection" placeholder="如: Section A" clearable @change="getList" style="width:200px" />
      </el-form-item>
      <el-form-item>
        <el-select v-model="answerFilter" placeholder="答案状态" clearable @change="getList" style="width:140px">
          <el-option label="全部题目" value="all" />
          <el-option label="有答案" value="yes" />
          <el-option label="无答案" value="no" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleDifficultyAnalysis" :loading="analyzing">
          <el-icon style="margin-right:4px;"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg></el-icon>
          一键难度分析
        </el-button>
        <el-button type="success" @click="handleTextOnlyAnalysis" :loading="textAnalyzing" style="margin-left:8px;">
          纯文本难度分析
        </el-button>
      </el-form-item>
    </el-form>

    <!-- 题目表格 -->
    <el-table :data="list" border style="width:100%;margin-top:12px;" size="small">
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="题号" prop="question_number" width="70" />
      <el-table-column label="题型" prop="type" width="80" />
      <el-table-column label="所属大题" prop="section" width="160" />
      <el-table-column label="题目内容" min-width="300">
        <template #default="scope">
          <span>{{ scope.row.content.slice(0, 80) }}{{ scope.row.content.length > 80 ? '...' : '' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="选项" width="80" align="center">
        <template #default="scope">
          <el-tag v-if="scope.row.options && scope.row.options.length > 0" type="info" size="small">
            {{ scope.row.options.length }}个
          </el-tag>
          <span v-else style="color:#ccc">—</span>
        </template>
      </el-table-column>
      <el-table-column label="答案" width="70" align="center">
        <template #default="scope">
          <el-tag v-if="scope.row.answer" type="success" size="small">有</el-tag>
          <el-tag v-else type="danger" size="small">无</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="难度" prop="difficulty" width="70" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="scope">
          <el-button type="primary" size="small" @click="openViewDialog(scope.row)">查看</el-button>
          <el-button type="warning" size="small" @click="openEditDialog(scope.row)">编辑</el-button>
          <el-button type="danger" size="small" @click="handleDelete(scope.row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      v-model:current-page="page"
      v-model:page-size="size"
      :total="total"
      style="margin-top:20px;text-align:right;"
      background
      layout="total, prev, pager, next, jumper"
      @current-change="getList"
    />

    <!-- 查看详情弹窗 -->
    <el-dialog v-model="viewDialogVisible" title="题目详情" width="850px" :close-on-click-modal="false">
      <div style="padding:10px 0;">
        <!-- 基本信息 -->
        <el-descriptions :column="3" border size="small" style="margin-bottom:20px;">
          <el-descriptions-item label="题号">{{ currentQuestion.question_number || '—' }}</el-descriptions-item>
          <el-descriptions-item label="题型">{{ currentQuestion.type }}</el-descriptions-item>
          <el-descriptions-item label="难度">{{ currentQuestion.difficulty }}</el-descriptions-item>
          <el-descriptions-item label="所属大题" :span="2">{{ currentQuestion.section || '—' }}</el-descriptions-item>
          <el-descriptions-item label="分值">{{ currentQuestion.score || '—' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 题干 -->
        <div style="margin-bottom:16px;">
          <h4 style="color:#2f4050;margin-bottom:8px;">题干内容</h4>
          <div style="background:#f8f9fa;padding:15px;border-radius:4px;line-height:1.8;white-space:pre-wrap;">{{ currentQuestion.content }}</div>
        </div>

        <!-- 听力音频播放器 -->
        <div v-if="currentQuestion.type === '听力' && currentQuestion.audio_url" style="margin-bottom:16px;">
          <h4 style="color:#2f4050;margin-bottom:8px;">听力音频</h4>
          <audio :src="'/api/audio/' + currentQuestion.id" controls controlsList="nodownload"
            style="width:100%;height:40px;border-radius:4px;" preload="metadata">
            您的浏览器不支持音频播放
          </audio>
        </div>

        <!-- 选项 -->
        <div v-if="currentQuestion.options && currentQuestion.options.length > 0" style="margin-bottom:16px;">
          <h4 style="color:#2f4050;margin-bottom:8px;">选项列表</h4>
          <div style="background:#f0f7ff;padding:15px;border-radius:4px;">
            <div v-for="opt in currentQuestion.options" :key="opt.label" style="line-height:1.8;">
              <b :style="{color: currentQuestion.answer && opt.label === currentQuestion.answer ? '#67C23A' : ''}">{{ opt.label }})</b> {{ opt.text }}
            </div>
          </div>
        </div>

        <!-- 原文段落（阅读题） -->
        <div v-if="currentQuestion.passage_text" style="margin-bottom:16px;">
          <h4 style="color:#2f4050;margin-bottom:8px;">原文段落</h4>
          <div style="background:#f5f5f5;padding:15px;border-radius:4px;line-height:1.8;white-space:pre-wrap;max-height:300px;overflow-y:auto;">{{ currentQuestion.passage_text }}</div>
        </div>

        <!-- 答案 -->
        <div style="margin-bottom:16px;">
          <h4 style="color:#2f4050;margin-bottom:8px;">
            参考答案
            <el-tag v-if="currentQuestion.answer" type="success" size="small" style="margin-left:8px;">{{ currentQuestion.answer }}</el-tag>
          </h4>
          <div style="background:#f0f9eb;padding:15px;border-radius:4px;line-height:1.8;">{{ currentQuestion.answer || '暂无答案（可导入解析PDF自动填充）' }}</div>
        </div>

        <!-- 解析 -->
        <div>
          <h4 style="color:#2f4050;margin-bottom:8px;">题目解析</h4>
          <div style="background:#fffbe6;padding:15px;border-radius:4px;line-height:1.8;">{{ currentQuestion.analysis || '暂无解析（可导入解析PDF自动填充）' }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 编辑题目弹窗 -->
    <el-dialog v-model="editDialogVisible" title="编辑题目" width="800px" :close-on-click-modal="false">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="题型">
          <el-input v-model="editForm.type" />
        </el-form-item>
        <el-form-item label="难度">
          <el-input-number v-model="editForm.difficulty" :min="1" :max="5" />
        </el-form-item>
        <el-form-item label="所属大题">
          <el-input v-model="editForm.section" />
        </el-form-item>
        <el-form-item label="题号">
          <el-input-number v-model="editForm.question_number" :min="1" />
        </el-form-item>
        <el-form-item label="分值">
          <el-input-number v-model="editForm.score" :min="0" :step="0.5" />
        </el-form-item>
        <el-form-item label="题干内容">
          <el-input v-model="editForm.content" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="参考答案">
          <el-input v-model="editForm.answer" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="题目解析">
          <el-input v-model="editForm.analysis" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleEditSubmit">保存修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useDifficultyTaskStore } from '../stores/difficultyTask'

const difficultyTask = useDifficultyTaskStore()

const page = ref(1)
const size = ref(10)
const total = ref(0)
const list = ref([])

const filterType = ref('')
const filterSection = ref('')
const answerFilter = ref('all')
const analyzing = ref(false)
const textAnalyzing = ref(false)

const viewDialogVisible = ref(false)
const currentQuestion = ref({})

const editDialogVisible = ref(false)
const editForm = ref({
  id: null,
  type: '',
  content: '',
  answer: '',
  analysis: '',
  difficulty: 1,
  section: '',
  question_number: null,
  score: 1
})

const getList = async () => {
  try {
    let url = `/api/question/list?page=${page.value}&size=${size.value}`
    if (filterType.value) url += `&type=${encodeURIComponent(filterType.value)}`
    const res = await fetch(url, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token') || ''}` }
    })
    const result = await res.json()
    let data = result.data || []
    if (answerFilter.value === 'yes') {
      data = data.filter(q => q.answer)
    } else if (answerFilter.value === 'no') {
      data = data.filter(q => !q.answer)
    }
    list.value = data
    total.value = result.total || 0
  } catch (err) {
    console.error('请求失败', err)
  }
}

const openViewDialog = (row) => {
  currentQuestion.value = row
  viewDialogVisible.value = true
}

const openEditDialog = (row) => {
  editForm.value = {
    id: row.id,
    type: row.type,
    content: row.content,
    answer: row.answer || '',
    analysis: row.analysis || '',
    difficulty: row.difficulty || 1,
    section: row.section || '',
    question_number: row.question_number,
    score: row.score || 1
  }
  editDialogVisible.value = true
}

const handleEditSubmit = async () => {
  try {
    const res = await fetch(`/api/question/${editForm.value.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token') || ''}` },
      body: JSON.stringify({
        type: editForm.value.type,
        content: editForm.value.content,
        answer: editForm.value.answer,
        analysis: editForm.value.analysis,
        difficulty: editForm.value.difficulty
      })
    })
    const result = await res.json()
    if (result.code === 200) {
      ElMessage.success('修改成功')
      editDialogVisible.value = false
      getList()
    } else {
      ElMessage.error(result.msg || '修改失败')
    }
  } catch (err) {
    console.error('修改失败', err)
    ElMessage.error('请求出错')
  }
}

const handleDelete = async (id) => {
  ElMessageBox.confirm('确定要删除这道题目吗？删除后无法恢复', '提示', {
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      const res = await fetch(`/api/question/${id}`, { method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token') || ''}` }
      })
      const result = await res.json()
      if (result.code === 200) {
        ElMessage.success('删除成功')
        getList()
      } else {
        ElMessage.error(result.msg || '删除失败')
      }
    } catch (err) {
      console.error('删除失败', err)
      ElMessage.error('请求出错')
    }
  }).catch(() => {
    ElMessage.info('已取消删除')
  })
}

// 一键难度分析：调用 AI+textstat 混合分析，后台运行
const handleDifficultyAnalysis = async () => {
  ElMessageBox.confirm(
    '将对题库中所有题目进行 AI+textstat 混合难度分析并更新难度分，是否继续？',
    '一键难度分析',
    { confirmButtonText: '开始分析', cancelButtonText: '取消', type: 'info' }
  ).then(async () => {
    analyzing.value = true
    try {
      const res = await fetch('/api/difficulty/analyze-all', { method: 'POST',
    headers: { 'Authorization': `Bearer ${localStorage.getItem('token') || ''}` }
  })
      const result = await res.json()
      if (result.code === 200 && result.task_id) {
        difficultyTask.startTask(result.task_id, true)
        ElMessage.success('难度分析已在后台启动，可自由切换页面')
      } else {
        ElMessage.error(result.msg || '启动失败')
      }
    } catch (err) {
      console.error('分析请求失败', err)
      ElMessage.error('网络请求失败')
    } finally {
      analyzing.value = false
    }
  }).catch(() => {})
}

// 纯文本难度分析：仅使用 textstat 静态分析，不调用 AI
const handleTextOnlyAnalysis = async () => {
  ElMessageBox.confirm(
    '将对题库中所有题目进行纯文本难度分析（不调用AI，速度更快），是否继续？',
    '纯文本难度分析',
    { confirmButtonText: '开始分析', cancelButtonText: '取消', type: 'info' }
  ).then(async () => {
    textAnalyzing.value = true
    try {
      const res = await fetch('/api/difficulty/analyze-all?use_ai=false', { method: 'POST' })
      const result = await res.json()
      if (result.code === 200 && result.task_id) {
        difficultyTask.startTask(result.task_id, false)
        ElMessage.success('纯文本难度分析已在后台启动，可自由切换页面')
      } else {
        ElMessage.error(result.msg || '启动失败')
      }
    } catch (err) {
      console.error('分析请求失败', err)
      ElMessage.error('网络请求失败')
    } finally {
      textAnalyzing.value = false
    }
  }).catch(() => {})
}

onMounted(() => {
  getList()
})
</script>
