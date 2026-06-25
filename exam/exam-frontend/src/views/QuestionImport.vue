<template>
  <div style="padding:20px;">
    <h3>PDF 导入管理</h3>

    <!-- 题目PDF导入 -->
    <el-card style="max-width:700px;margin-top:20px;" shadow="hover">
      <template #header>
        <span><b>📄 题目PDF上传</b></span>
      </template>
      <el-upload
        :auto-upload="false"
        :on-change="handleFileChange"
        accept=".pdf"
        :show-file-list="true"
        :limit="1"
      >
        <el-button type="primary">选择题目PDF文件</el-button>
        <div style="margin-top:8px;font-size:12px;color:#999;">
          支持文字版 CET-4 真题 PDF，上传后自动解析拆分每道题（文件名含「真题」字样）
        </div>
      </el-upload>

      <el-button
        type="success"
        style="margin-top:16px;"
        @click="submitUpload"
        :loading="loading"
        :disabled="!file"
      >
        开始导入题目
      </el-button>

      <div v-if="uploadResult" style="margin-top:20px;">
        <el-alert
          :title="uploadResult.msg"
          :type="uploadResult.code === 200 ? 'success' : 'error'"
          :closable="false"
          show-icon
        />
        <div v-if="uploadResult.sections" style="margin-top:12px;">
          <el-tag v-for="(count, sec) in uploadResult.sections" :key="sec" style="margin:4px;">
            {{ sec }}: {{ count }}题
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- 解析PDF上传 -->
    <el-card style="max-width:700px;margin-top:20px;" shadow="hover">
      <template #header>
        <span><b>📝 解析PDF上传（含答案）</b></span>
      </template>
      <el-upload
        :auto-upload="false"
        :on-change="handleAnsFileChange"
        accept=".pdf"
        :show-file-list="true"
        :limit="1"
      >
        <el-button type="primary">选择解析PDF文件</el-button>
        <div style="margin-top:8px;font-size:12px;color:#999;">
          上传 CET-4 解析/答案 PDF（文件名含「解析」字样），自动匹配对应题目并填充答案
        </div>
      </el-upload>

      <el-button
        type="success"
        style="margin-top:16px;"
        @click="submitAnsUpload"
        :loading="ansLoading"
        :disabled="!ansFile"
      >
        开始导入解析
      </el-button>

      <div v-if="ansResult" style="margin-top:20px;">
        <el-alert
          :title="ansResult.msg"
          :type="ansResult.code === 200 ? 'success' : 'error'"
          :closable="false"
          show-icon
        />
        <div v-if="ansResult.data" style="margin-top:12px;">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="年份月份">{{ ansResult.data.year_month || '—' }}</el-descriptions-item>
            <el-descriptions-item label="第几套">{{ ansResult.data.suite_number || '—' }}</el-descriptions-item>
            <el-descriptions-item label="可提取文字">{{ ansResult.data.has_text ? '是' : '否（扫描版）' }}</el-descriptions-item>
            <el-descriptions-item label="匹配题目源">{{ ansResult.data.matched_source || '未匹配' }}</el-descriptions-item>
            <el-descriptions-item label="提取答案数">{{ ansResult.data.answers_count || 0 }}条</el-descriptions-item>
            <el-descriptions-item label="成功匹配">{{ ansResult.data.match_count || 0 }}题</el-descriptions-item>
          </el-descriptions>
        </div>
        <!-- 提取答案预览 -->
        <div v-if="ansResult.data && ansResult.data.answers && ansResult.data.answers.length > 0" style="margin-top:16px;">
          <h4 style="margin-bottom:8px;">答案预览（前10条）</h4>
          <el-table :data="ansResult.data.answers" size="small" border>
            <el-table-column label="题号" prop="question_number" width="70" />
            <el-table-column label="题型" prop="type" width="70" />
            <el-table-column label="答案" prop="answer" width="80" />
            <el-table-column label="解析摘要" prop="analysis" min-width="200">
              <template #default="scope">
                <span>{{ (scope.row.analysis || '').slice(0, 60) }}{{ (scope.row.analysis || '').length > 60 ? '...' : '' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-card>

    <!-- 已导入的解析PDF列表 -->
    <el-card style="max-width:900px;margin-top:20px;" shadow="hover">
      <template #header>
        <span><b>📋 已导入解析PDF记录</b></span>
        <el-button size="small" style="float:right;" @click="getAnswerSheets">刷新</el-button>
      </template>
      <el-table :data="answerSheets" size="small" border>
        <el-table-column label="ID" prop="id" width="60" />
        <el-table-column label="文件名" prop="filename" min-width="250" />
        <el-table-column label="年份月份" prop="year_month" width="100" />
        <el-table-column label="套数" prop="suite_number" width="60" />
        <el-table-column label="文字版" width="70">
          <template #default="scope">
            <el-tag :type="scope.row.has_extracted_text ? 'success' : 'warning'" size="small">
              {{ scope.row.has_extracted_text ? '是' : '扫描版' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="答案数" prop="answers_count" width="70" />
        <el-table-column label="匹配题目" width="100">
          <template #default="scope">
            <span v-if="scope.row.matched_exam_source" style="color:#67C23A;">已匹配</span>
            <span v-else style="color:#F56C6C;">未匹配</span>
          </template>
        </el-table-column>
        <el-table-column label="已填充" prop="match_count" width="70" />
        <el-table-column label="操作" width="150">
          <template #default="scope">
            <el-button v-if="scope.row.matched_exam_source && scope.row.match_count === 0" type="success" size="small" @click="applyAnswers(scope.row.id)">
              应用到题目
            </el-button>
            <el-button type="danger" size="small" @click="deleteAnsSheet(scope.row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="sheetPage"
        :total="sheetTotal"
        style="margin-top:12px;text-align:right;"
        background layout="prev, pager, next"
        @current-change="getAnswerSheets"
      />
    </el-card>

    <!-- 听力音频导入 -->
    <el-card style="max-width:700px;margin-top:20px;" shadow="hover">
      <template #header>
        <span><b>🎵 批量导入听力音频</b></span>
      </template>
      <p style="color:#666;font-size:14px;">自动扫描测试题目文件夹中的MP3音频文件，匹配到对应试卷的听力题目</p>
      <el-button
        type="success"
        @click="batchImportAudio"
        :loading="audioLoading"
      >
        导入听力音频
      </el-button>

      <div v-if="audioResult" style="margin-top:20px;">
        <el-alert
          :title="audioResult.msg"
          :type="audioResult.code === 200 ? 'success' : 'error'"
          :closable="false"
          show-icon
        />
        <div v-if="audioResult.data" style="margin-top:12px;">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="MP3总数">{{ audioResult.data.total_mp3 }}</el-descriptions-item>
            <el-descriptions-item label="已匹配">{{ audioResult.data.matched }}</el-descriptions-item>
            <el-descriptions-item label="更新题目">{{ audioResult.data.updated_questions }}</el-descriptions-item>
          </el-descriptions>
          <div v-if="audioResult.data.unmatched && audioResult.data.unmatched.length > 0" style="margin-top:8px;">
            <el-tag type="warning" v-for="f in audioResult.data.unmatched" :key="f" style="margin:4px;">{{ f }}</el-tag>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 批量导入题目PDF -->
    <el-card style="max-width:700px;margin-top:20px;" shadow="hover">
      <template #header>
        <span><b>📚 批量导入全部题目PDF</b></span>
      </template>
      <p style="color:#666;font-size:14px;">导入服务器 pdf_upload 文件夹中的所有 PDF 文件（自动跳过解析PDF）</p>
      <el-button
        type="warning"
        @click="batchImport"
        :loading="batchLoading"
      >
        批量导入全部题目
      </el-button>

      <div v-if="batchResult" style="margin-top:20px;">
        <el-alert
          :title="batchResult.msg"
          type="success"
          :closable="false"
          show-icon
        />
        <el-table v-if="batchResult.files" :data="batchResult.files" size="small" style="margin-top:12px;">
          <el-table-column label="文件名" prop="file" min-width="280" />
          <el-table-column label="导入数量" width="100">
            <template #default="scope">
              <el-tag v-if="scope.row.count > 0" type="success">{{ scope.row.count }}题</el-tag>
              <el-tag v-else type="danger">{{ scope.row.error || '0题' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useImportTaskStore } from '../stores/importTask'

const importTask = useImportTaskStore()

// ── 题目PDF ──────────────────────────────────────
const loading = ref(false)
const file = ref(null)
const uploadResult = ref(null)

const audioLoading = ref(false)
const audioResult = ref(null)

const batchLoading = ref(false)
const batchResult = ref(null)

const handleFileChange = (uploadFile) => {
  file.value = uploadFile.raw
}

const submitUpload = async () => {
  if (!file.value) {
    ElMessage.warning('请先选择PDF文件')
    return
  }
  importTask.start('导入题目PDF')
  loading.value = true
  const formData = new FormData()
  formData.append('file', file.value)
  try {
    importTask.setPhase('parsing', '正在解析PDF...')
    const res = await fetch('/api/pdf/upload', { method: 'POST', body: formData })
    const result = await res.json()
    uploadResult.value = result
    if (result.code === 200) {
      importTask.complete(result.msg, result)
      ElMessage.success(result.msg)
    } else {
      importTask.fail(result.msg || '导入失败')
      ElMessage.error(result.msg || '导入失败')
    }
  } catch (err) {
    console.error(err)
    importTask.fail('上传失败，请确认后端服务已启动')
    ElMessage.error('上传失败，请确认后端服务已启动')
  } finally {
    loading.value = false
  }
}

const batchImportAudio = async () => {
  audioLoading.value = true
  try {
    const res = await fetch('/api/audio/batch-import', { method: 'POST' })
    const result = await res.json()
    audioResult.value = result
    if (result.code === 200) {
      ElMessage.success(result.msg)
    } else {
      ElMessage.error(result.msg || '导入失败')
    }
  } catch (err) {
    console.error(err)
    ElMessage.error('音频导入失败，请确认后端服务已启动')
  } finally {
    audioLoading.value = false
  }
}

const batchImport = async () => {
  importTask.start('批量导入全部题目PDF')
  batchLoading.value = true
  try {
    importTask.setPhase('parsing', '正在解析全部PDF...')
    const res = await fetch('/api/pdf/batch-import', { method: 'POST' })
    const result = await res.json()
    batchResult.value = result
    if (result.code === 200) {
      importTask.complete(result.msg, result)
      ElMessage.success(result.msg)
    } else {
      importTask.fail(result.msg || '导入失败')
      ElMessage.error(result.msg || '导入失败')
    }
  } catch (err) {
    console.error(err)
    importTask.fail('批量导入失败，请确认后端服务已启动')
    ElMessage.error('批量导入失败，请确认后端服务已启动')
  } finally {
    batchLoading.value = false
  }
}

// ── 解析PDF ──────────────────────────────────────
const ansLoading = ref(false)
const ansFile = ref(null)
const ansResult = ref(null)

const answerSheets = ref([])
const sheetPage = ref(1)
const sheetTotal = ref(0)

const handleAnsFileChange = (uploadFile) => {
  ansFile.value = uploadFile.raw
}

const submitAnsUpload = async () => {
  if (!ansFile.value) {
    ElMessage.warning('请先选择解析PDF文件')
    return
  }
  importTask.start('导入解析PDF')
  ansLoading.value = true
  const formData = new FormData()
  formData.append('file', ansFile.value)
  try {
    importTask.setPhase('parsing', '正在解析答案...')
    const res = await fetch('/api/answer-sheet/upload', { method: 'POST', body: formData })
    const result = await res.json()
    ansResult.value = result
    if (result.code === 200) {
      importTask.complete(result.msg, result.data)
      ElMessage.success(result.msg)
      getAnswerSheets()
    } else {
      importTask.fail(result.msg || '导入失败')
      ElMessage.error(result.msg || '导入失败')
    }
  } catch (err) {
    console.error(err)
    importTask.fail('上传失败，请确认后端服务已启动')
    ElMessage.error('上传失败，请确认后端服务已启动')
  } finally {
    ansLoading.value = false
  }
}

const getAnswerSheets = async () => {
  try {
    const res = await fetch(`/api/answer-sheet/list?page=${sheetPage.value}&size=10`)
    const result = await res.json()
    if (result.code === 200) {
      answerSheets.value = result.data || []
      sheetTotal.value = result.total || 0
    }
  } catch (err) {
    console.error(err)
  }
}

const applyAnswers = async (id) => {
  try {
    const res = await fetch(`/api/answer-sheet/${id}/apply`, { method: 'POST' })
    const result = await res.json()
    if (result.code === 200) {
      ElMessage.success(result.msg)
      getAnswerSheets()
    } else {
      ElMessage.error(result.msg || '操作失败')
    }
  } catch (err) {
    ElMessage.error('请求失败')
  }
}

const deleteAnsSheet = async (id) => {
  try {
    const res = await fetch(`/api/answer-sheet/${id}`, { method: 'DELETE' })
    const result = await res.json()
    if (result.code === 200) {
      ElMessage.success('删除成功')
      getAnswerSheets()
    } else {
      ElMessage.error(result.msg || '删除失败')
    }
  } catch (err) {
    ElMessage.error('请求失败')
  }
}

onMounted(() => {
  getAnswerSheets()
})
</script>
