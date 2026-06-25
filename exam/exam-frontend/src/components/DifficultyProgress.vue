<template>
  <Transition name="slide">
    <div v-if="store.visible" class="difficulty-progress-card">
      <div class="card-header">
        <span class="card-title">
          <el-icon style="margin-right:4px;"><Loading v-if="store.status === 'running'" /></el-icon>
          难度分析进度
        </span>
        <el-button
          v-if="store.status !== 'running'"
          text
          size="small"
          @click="store.dismiss()"
          style="color:#999;"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>

      <div class="card-body">
        <!-- 进度条 -->
        <el-progress
          :percentage="store.percent()"
          :status="progressStatus"
          :stroke-width="16"
          :text-inside="true"
          style="margin-bottom:12px;"
        />

        <!-- 文字 -->
        <p class="progress-text">{{ store.message }}</p>
        <p v-if="store.total > 0" class="progress-detail">
          {{ store.progress }} / {{ store.total }} 题
        </p>

        <!-- 状态标签 -->
        <el-tag v-if="store.status === 'running'" type="warning" size="small" effect="dark">
          运行中...
        </el-tag>
        <el-tag v-else-if="store.status === 'completed'" type="success" size="small" effect="dark">
          已完成
        </el-tag>
        <el-tag v-else-if="store.status === 'failed'" type="danger" size="small" effect="dark">
          失败
        </el-tag>
        <el-tag v-else size="small" effect="dark">
          {{ store.status }}
        </el-tag>

        <!-- 完成结果摘要 -->
        <div v-if="store.result" style="margin-top:10px;font-size:12px;color:#666;">
          共 {{ store.result.total }} 题，更新 {{ store.result.updated }} 题
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'
import { Loading, Close } from '@element-plus/icons-vue'
import { useDifficultyTaskStore } from '../stores/difficultyTask'

const store = useDifficultyTaskStore()

const progressStatus = computed(() => {
  if (store.status === 'completed') return 'success'
  if (store.status === 'failed') return 'exception'
  return ''
})
</script>

<style scoped>
.difficulty-progress-card {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 320px;
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

.progress-text {
  font-size: 13px;
  color: #333;
  margin: 0 0 4px;
}

.progress-detail {
  font-size: 12px;
  color: #999;
  margin: 0 0 8px;
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
