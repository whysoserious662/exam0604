import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useDifficultyTaskStore = defineStore('difficultyTask', () => {
  const taskId = ref('')
  const status = ref('')     // '' | 'running' | 'completed' | 'failed'
  const progress = ref(0)
  const total = ref(0)
  const message = ref('')
  const useAi = ref(true)
  const result = ref(null)
  const visible = ref(false) // 悬浮窗是否可见
  let pollTimer = null

  function startTask(id, ai = true) {
    taskId.value = id
    status.value = 'running'
    progress.value = 0
    total.value = 0
    message.value = '正在启动...'
    useAi.value = ai
    result.value = null
    visible.value = true
    startPolling()
  }

  function startPolling() {
    stopPolling()
    pollTimer = setInterval(async () => {
      if (!taskId.value) return
      try {
        const res = await fetch(`/api/difficulty/task/${taskId.value}`)
        const data = await res.json()
        if (data.code === 200) {
          const t = data.data
          status.value = t.status
          progress.value = t.progress
          total.value = t.total
          message.value = t.message
          result.value = t.result
          if (t.status === 'completed' || t.status === 'failed') {
            stopPolling()
          }
        } else {
          // 任务不存在
          status.value = 'not_found'
          message.value = '任务已过期'
          stopPolling()
        }
      } catch {
        // 网络错误，继续重试
      }
    }, 1000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function dismiss() {
    if (status.value !== 'running') {
      stopPolling()
      visible.value = false
    }
  }

  // 百分比
  function percent() {
    if (total.value === 0) return 0
    return Math.round((progress.value / total.value) * 100)
  }

  return {
    taskId, status, progress, total, message, useAi, result, visible,
    startTask, dismiss,
    percent,
  }
})
