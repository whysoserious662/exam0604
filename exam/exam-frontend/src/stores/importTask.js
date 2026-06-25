import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useImportTaskStore = defineStore('importTask', () => {
  const taskId = ref('')
  const status = ref('')       // '' | 'uploading' | 'parsing' | 'importing' | 'completed' | 'failed'
  const label = ref('')        // 描述文字，如 "批量导入全部题目"
  const message = ref('')
  const visible = ref(false)
  const result = ref(null)

  function start(labelText) {
    label.value = labelText
    status.value = 'uploading'
    message.value = '正在上传...'
    visible.value = true
    result.value = null
  }

  function setPhase(phase, msg) {
    status.value = phase
    if (msg) message.value = msg
  }

  function complete(msg, resultData = null) {
    status.value = 'completed'
    message.value = msg || '完成'
    result.value = resultData
  }

  function fail(msg) {
    status.value = 'failed'
    message.value = msg || '失败'
  }

  function dismiss() {
    if (status.value !== 'uploading' && status.value !== 'parsing' && status.value !== 'importing') {
      visible.value = false
    }
  }

  function reset() {
    taskId.value = ''
    status.value = ''
    label.value = ''
    message.value = ''
    visible.value = false
    result.value = null
  }

  return {
    taskId, status, label, message, visible, result,
    start, setPhase, complete, fail, dismiss, reset,
  }
})
