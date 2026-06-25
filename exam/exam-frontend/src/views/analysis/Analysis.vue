<template>
  <div>
    <h2>试卷分析</h2>

    <!-- 考试选择 -->
    <el-select v-model="examId" placeholder="选择考试" style="margin-bottom:16px;width:300px;" @change="onExamChange">
      <el-option v-for="e in examIds" :key="e" :label="e" :value="e" />
    </el-select>

    <el-tabs v-model="activeTab" v-if="examId" :key="examId">
      <el-tab-pane label="总体概览" name="overview">
        <Overview :exam-id="examId" />
      </el-tab-pane>
      <el-tab-pane label="AI 评语" name="ai">
        <AIComment :exam-id="examId" />
      </el-tab-pane>
      <el-tab-pane label="学生分析" name="student">
        <StudentDetail :exam-id="examId" />
      </el-tab-pane>
    </el-tabs>

    <el-empty v-else description="请先选择考试" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import Overview from './Overview.vue'
import AIComment from './AIComment.vue'
import StudentDetail from './StudentDetail.vue'

const API_BASE = ''
const examId = ref('')
const examIds = ref([])
const activeTab = ref('overview')

async function loadExamIds() {
  try {
    const res = await axios.get(`${API_BASE}/api/exam-record/filters`)
    if (res.data.code === 200) examIds.value = res.data.exam_ids
  } catch (e) {
    console.error('获取考试列表失败', e)
  }
}

function onExamChange() {
  activeTab.value = 'overview'
}

onMounted(loadExamIds)
</script>
