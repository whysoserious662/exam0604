<template>
  <Transition name="slide">
    <div v-if="store.visible" class="import-progress-card">
      <div class="card-header">
        <span class="card-title">
          <el-icon style="margin-right:4px;"><Loading v-if="isRunning" /></el-icon>
          {{ store.label || '导入进度' }}
        </span>
        <el-button
          v-if="!isRunning"
          text
          size="small"
          @click="store.dismiss()"
          style="color:#999;"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>

      <div class="card-body">
        <!-- 阶段进度条 -->
        <div class="phase-steps">
          <div
            v-for="(step, i) in phases"
            :key="step.key"
            class="phase-step"
            :class="{ active: currentPhaseIndex === i, done: currentPhaseIndex > i }"
          >
            <div class="phase-dot">
              <el-icon v-if="currentPhaseIndex > i"><Check /></el-icon>
              <Loading v-else-if="currentPhaseIndex === i && isRunning" class="is-loading" />
              <span v-else>{{ i + 1 }}</span>
            </div>
            <span class="phase-label">{{ step.label }}</span>
          </div>
        </div>

        <el-progress
          :percentage="progressPercent"
          :status="progressStatus"
          :stroke-width="12"
          :text-inside="true"
          style="margin:12px 0;"
        />

        <p class="msg-text">{{ store.message }}</p>

        <el-tag v-if="store.status === 'completed'" type="success" size="small" effect="dark">
          完成
        </el-tag>
        <el-tag v-else-if="store.status === 'failed'" type="danger" size="small" effect="dark">
          失败
        </el-tag>

        <div v-if="store.result" style="margin-top:10px;font-size:12px;color:#666;">
          <div v-if="store.result.count">导入 {{ store.result.count }} 道题目</div>
          <div v-else-if="store.result.match_count">已匹配 {{ store.result.match_count }} 题</div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'
import { Loading, Close, Check } from '@element-plus/icons-vue'
import { useImportTaskStore } from '../stores/importTask'

const store = useImportTaskStore()

const phases = [
  { key: 'uploading', label: '上传' },
  { key: 'parsing', label: '解析' },
  { key: 'importing', label: '导入' },
]

const isRunning = computed(() =>
  ['uploading', 'parsing', 'importing'].includes(store.status)
)

const currentPhaseIndex = computed(() => {
  if (store.status === 'uploading') return 0
  if (store.status === 'parsing') return 1
  if (store.status === 'importing') return 2
  if (store.status === 'completed') return 3
  if (store.status === 'failed') return currentPhaseIndex.value || 1
  return 0
})

const progressPercent = computed(() => {
  if (store.status === 'completed') return 100
  if (store.status === 'failed') return 50
  if (store.status === 'uploading') return 15
  if (store.status === 'parsing') return 45
  if (store.status === 'importing') return 75
  return 0
})

const progressStatus = computed(() => {
  if (store.status === 'completed') return 'success'
  if (store.status === 'failed') return 'exception'
  return ''
})
</script>

<style scoped>
.import-progress-card {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 340px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.18);
  z-index: 9999;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #2f4050;
  color: #fff;
}

.card-title {
  font-size: 14px;
  font-weight: bold;
  display: flex;
  align-items: center;
}

.card-body {
  padding: 14px;
}

.msg-text {
  font-size: 13px;
  color: #333;
  margin: 0 0 8px;
}

.phase-steps {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.phase-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.phase-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: bold;
  background: #e8e8e8;
  color: #999;
  transition: all 0.3s;
}

.phase-step.active .phase-dot {
  background: #409EFF;
  color: #fff;
}

.phase-step.done .phase-dot {
  background: #67C23A;
  color: #fff;
}

.phase-label {
  font-size: 11px;
  color: #999;
}

.phase-step.active .phase-label {
  color: #409EFF;
  font-weight: bold;
}

.phase-step.done .phase-label {
  color: #67C23A;
}

/* 过渡动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.35s ease;
}
.slide-enter-from {
  transform: translateY(100px);
  opacity: 0;
}
.slide-leave-to {
  transform: translateY(100px);
  opacity: 0;
}
</style>
