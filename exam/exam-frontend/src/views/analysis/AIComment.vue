<template>
  <div>
    <el-button type="primary" :loading="loading" :disabled="!!comment" @click="generate">
      {{ comment ? '已生成' : '生成 AI 评语' }}
    </el-button>

    <div v-if="comment" style="margin-top:16px;">
      <el-card>
        <template #header><span>AI 试卷评语</span></template>
        <p style="white-space:pre-wrap;line-height:2;font-size:15px;">{{ comment }}</p>
      </el-card>
    </div>

    <el-alert v-else-if="error" :title="error" type="warning" show-icon style="margin-top:16px;" />

    <el-empty v-else description="点击按钮生成 AI 评语" style="margin-top:60px;" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const props = defineProps({ examId: String })
const API_BASE = ''

const comment = ref('')
const error = ref('')
const loading = ref(false)

async function generate() {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.post(`${API_BASE}/api/analysis/ai-comment`, { exam_id: props.examId })
    if (res.data.code === 200) {
      comment.value = res.data.data.comment
        .replace(/\*\*(.+?)\*\*/g, '$1')  // 去除加粗标记 **text**
        .replace(/\*\*/g, '')              // 去除孤立的 **
        .replace(/^#+\s*/gm, '')           // 去除标题标记 ###/##
        .replace(/__([^_]+)__/g, '$1')     // 去除下划线标记
    } else {
      error.value = res.data.msg || '生成失败'
    }
  } catch (e) {
    error.value = 'AI 评语生成失败，请检查后端 API 配置'
  } finally {
    loading.value = false
  }
}
</script>
