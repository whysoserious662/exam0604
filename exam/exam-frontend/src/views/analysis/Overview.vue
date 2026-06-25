<template>
  <div v-loading="loading">
    <div v-if="analysis">
      <el-row :gutter="16" style="margin-bottom:16px;">
        <el-col :span="6" v-for="card in statCards" :key="card.label">
          <el-card shadow="hover">
            <div style="text-align:center;">
              <div style="font-size:28px;font-weight:bold;color:#409EFF;">{{ card.value }}</div>
              <div style="font-size:13px;color:#909399;margin-top:4px;">{{ card.label }}</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-card style="margin-bottom:16px;">
            <template #header><span>题型掌握率雷达图</span></template>
            <div ref="radarRef" style="height:350px;"></div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card style="margin-bottom:16px;">
            <template #header><span>题目得分率</span></template>
            <div ref="barRef" style="height:350px;"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-card style="margin-bottom:16px;">
        <template #header><span>成绩分布直方图</span></template>
        <div ref="histogramRef" style="height:350px;"></div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const props = defineProps({ examId: String })
const API_BASE = ''

const loading = ref(false)
const analysis = ref(null)
const radarRef = ref(null)
const barRef = ref(null)
const histogramRef = ref(null)


const statCards = computed(() => {
  if (!analysis.value) return []
  const a = analysis.value
  return [
    { label: '考生人数', value: `${a.student_count} 人` },
    { label: '平均分', value: `${a.avg_score}` },
    { label: '得分率', value: `${(a.avg_score_rate * 100).toFixed(1)}%` },
    { label: '满分', value: `${a.total_possible}` },
  ]
})

async function loadAnalysis() {
  if (!props.examId) return
  loading.value = true
  analysis.value = null
  try {
    const res = await axios.get(`${API_BASE}/api/analysis`, { params: { exam_id: props.examId } })
    if (res.data.code === 200) {
      analysis.value = res.data.data
      await nextTick()
      renderCharts()
    }
  } catch (e) {
    console.error('加载分析失败', e)
  } finally {
    loading.value = false
  }
}

function renderCharts() {
  if (!analysis.value) return
  // Dispose previous instances to avoid stale render issues
  ;[radarRef.value, barRef.value, histogramRef.value].forEach(el => { if (el) echarts.dispose(el) })
  renderRadar(); renderBar(); renderHistogram()
}

// 四级题型对应的题号范围
const TYPE_QUESTIONS = { '写作': [1], '听力': [2, 26], '阅读': [27, 56], '翻译': [57] }

function renderRadar() {
  const qa = analysis.value.question_analysis || []
  if (!qa.length) return
  // 按题型分组计算平均得分率
  const typeRates = {}
  for (const [type, [start, end]] of Object.entries(TYPE_QUESTIONS)) {
    const items = qa.filter(q => q.question_number >= start && q.question_number <= (end || start))
    if (items.length) {
      typeRates[type] = +(items.reduce((s, q) => s + q.score_rate, 0) / items.length * 100).toFixed(1)
    }
  }
  const entries = Object.entries(typeRates)
  if (!entries.length) return
  echarts.init(radarRef.value).setOption({
    radar: {
      indicator: entries.map(([type]) => ({ name: type, max: 100 })),
      radius: '60%'
    },
    series: [{
      type: 'radar',
      data: [{
        value: entries.map(([, v]) => v),
        name: '掌握率',
        areaStyle: { opacity: 0.2 }
      }],
      symbol: 'none',
      lineStyle: { width: 2 }
    }],
    tooltip: { trigger: 'item' }
  })
}

function renderBar() {
  const qa = analysis.value.question_analysis || []
  echarts.init(barRef.value).setOption({
    xAxis: { type: 'category', data: qa.map(q => `第${q.question_number}题`), axisLabel: { rotate: 45, fontSize: 11 } },
    yAxis: { type: 'value', name: '得分率', min: 0, max: 1, axisLabel: { formatter: (v) => `${(v * 100).toFixed(0)}%` } },
    series: [{
      type: 'bar', data: qa.map(q => q.score_rate),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#409EFF' },
          { offset: 1, color: '#79bbff' }
        ])
      }
    }],
    tooltip: { trigger: 'axis', formatter: (p) => `题号 ${qa[p[0].dataIndex].question_number}<br/>得分率: ${(p[0].value * 100).toFixed(1)}%` },
    grid: { left: 60, right: 20, top: 40, bottom: 60 }
  })
}

function renderHistogram() {
  const dist = analysis.value.score_distribution || []
  echarts.init(histogramRef.value).setOption({
    xAxis: { type: 'category', data: dist.map(d => `${d.range_start}-${d.range_end}`), axisLabel: { rotate: 45 } },
    yAxis: { type: 'value', name: '人数' },
    series: [{ type: 'bar', data: dist.map(d => d.count), itemStyle: { color: '#409EFF' } }],
    tooltip: { trigger: 'axis' }
  })
}

onMounted(() => { if (props.examId) loadAnalysis() })
watch(() => props.examId, (val) => { if (val) loadAnalysis() })
onUnmounted(() => {
  ;[radarRef.value, barRef.value, histogramRef.value].forEach(el => { if (el) echarts.dispose(el) })
})
</script>
