<template>
  <div>
    <el-form :inline="true">
      <el-form-item label="选择学生">
        <el-select v-model="studentName" placeholder="选择学生" filterable style="width:220px;" @change="loadStudent">
          <el-option v-for="s in studentList" :key="s.student_name" :label="`${s.student_name} (${s.class_name})`" :value="s.student_name" />
        </el-select>
      </el-form-item>
    </el-form>

    <div v-loading="loading" v-if="data">
      <!-- 统计卡片 -->
      <el-row :gutter="16" style="margin-bottom:16px;">
        <el-col :span="6">
          <el-card shadow="hover">
            <div style="text-align:center;">
              <div style="font-size:28px;font-weight:bold;color:#409EFF;">{{ data.total_score }}</div>
              <div style="font-size:13px;color:#909399;margin-top:4px;">总分 / {{ data.total_full }}</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover">
            <div style="text-align:center;">
              <div style="font-size:28px;font-weight:bold;color:#67C23A;">{{ (data.score_rate * 100).toFixed(1) }}%</div>
              <div style="font-size:13px;color:#909399;margin-top:4px;">得分率</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover">
            <div style="text-align:center;">
              <div style="font-size:28px;font-weight:bold;color:#E6A23C;">{{ data.class_rank }}/{{ data.class_total }}</div>
              <div style="font-size:13px;color:#909399;margin-top:4px;">班级排名</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover">
            <div style="text-align:center;">
              <div style="font-size:28px;font-weight:bold;color:#F56C6C;">{{ data.exam_rank }}/{{ data.exam_total }}</div>
              <div style="font-size:13px;color:#909399;margin-top:4px;">年级排名</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <!-- 能力雷达图 -->
        <el-col :span="12">
          <el-card style="margin-bottom:16px;">
            <template #header><span>各题型能力雷达图</span></template>
            <div ref="radarRef" style="height:300px;"></div>
          </el-card>
        </el-col>
        <!-- 题型统计 -->
        <el-col :span="12">
          <el-card style="margin-bottom:16px;">
            <template #header><span>各题型得分详情</span></template>
            <el-table :data="typeTable" border stripe>
              <el-table-column prop="type" label="题型" width="80" />
              <el-table-column prop="score" label="得分" width="80" />
              <el-table-column prop="full_score" label="满分" width="80" />
              <el-table-column prop="accuracy" label="正确率" width="80">
                <template #default="{ row }">
                  <span v-if="row.is_objective">{{ (row.accuracy * 100).toFixed(0) }}%</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="得分率" width="80">
                <template #default="{ row }">{{ (row.score_rate * 100).toFixed(0) }}%</template>
              </el-table-column>
              <el-table-column prop="correct" label="正确/总数" min-width="100">
                <template #default="{ row }">
                  <span v-if="row.is_objective">{{ row.correct }}/{{ row.count }}</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <!-- 每题得分明细 -->
      <el-card>
        <template #header><span>每题得分明细</span></template>
        <div style="display:flex;flex-wrap:wrap;gap:6px;max-height:400px;overflow-y:auto;padding:8px 0;">
          <div v-for="d in data.details" :key="d.question_id"
            :style="{
              width:'44px',height:'44px',display:'flex',alignItems:'center',justifyContent:'center',
              borderRadius:'4px',fontSize:'12px',cursor:'default',
              background: d.score >= d.full_score ? '#e1f3d8' : '#fde2e2',
              color: d.score >= d.full_score ? '#67C23A' : '#F56C6C',
              border: d.score >= d.full_score ? '1px solid #b3e19d' : '1px solid #fab6b6'
            }"
            :title="`题号${d.question_id}: ${d.score}/${d.full_score}`">
            {{ d.question_id }}
          </div>
        </div>
      </el-card>
    </div>

    <el-empty v-else-if="!loading" description="请选择学生查看详细分析" style="margin-top:60px;" />
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const props = defineProps({ examId: String })
const API_BASE = ''

const loading = ref(false)
const studentList = ref([])
const studentName = ref('')
const data = ref(null)
const radarRef = ref(null)

const TYPE_COLORS = { '写作': '#67C23A', '听力': '#E6A23C', '阅读': '#409EFF', '翻译': '#909399' }

const typeTable = computed(() => {
  if (!data.value) return []
  return Object.entries(data.value.type_scores).map(([type, info]) => ({ type, ...info }))
})

async function loadStudents() {
  try {
    const res = await axios.get(`${API_BASE}/api/analysis/students`, { params: { exam_id: props.examId } })
    if (res.data.code === 200) studentList.value = res.data.data
  } catch (e) {
    console.error('加载学生列表失败', e)
  }
}

async function loadStudent() {
  if (!studentName.value) return
  loading.value = true
  data.value = null
  try {
    const res = await axios.get(`${API_BASE}/api/analysis/student`, {
      params: { exam_id: props.examId, student_name: studentName.value }
    })
    if (res.data.code === 200) {
      data.value = res.data.data
      await nextTick()
      renderRadar()
    }
  } catch (e) {
    console.error('加载学生分析失败', e)
  } finally {
    loading.value = false
  }
}

function renderRadar() {
  if (!data.value) return
  const types = data.value.type_scores
  const entries = Object.entries(types)
  if (!entries.length) return

  echarts.init(radarRef.value).setOption({
    radar: {
      indicator: entries.map(([type]) => ({ name: type, max: 100 })),
      radius: '60%'
    },
    series: [{
      type: 'radar',
      data: [{
        value: entries.map(([, v]) => +(v.score_rate * 100).toFixed(1)),
        name: '得分率',
        areaStyle: { opacity: 0.2 },
        lineStyle: { width: 2 },
        itemStyle: { color: '#409EFF' }
      }]
    }],
    tooltip: { trigger: 'item' }
  })
}

watch(() => props.examId, () => { studentName.value = ''; data.value = null; loadStudents() }, { immediate: true })
</script>
