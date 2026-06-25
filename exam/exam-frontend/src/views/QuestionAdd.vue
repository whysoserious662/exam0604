<template>
  <div style="padding: 20px;">
    <h3>手动录入题目</h3>

    <!-- 题目录入表单 -->
    <el-form
      :model="form"
      label-width="80px"
      style="max-width: 900px; margin-top: 20px;"
    >
      <el-form-item label="题目类型" required>
        <el-select v-model="form.type" placeholder="请选择题型" style="width: 100%;">
          <el-option label="写作" value="写作" />
          <el-option label="听力" value="听力" />
          <el-option label="阅读" value="阅读" />
          <el-option label="翻译" value="翻译" />
        </el-select>
      </el-form-item>

      <el-form-item label="难度" required>
        <el-input-number
          v-model="form.difficulty"
          :min="1"
          :max="5"
          placeholder="1-5级难度"
        />
      </el-form-item>

      <el-form-item label="题干内容" required>
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="5"
          placeholder="请输入完整题目内容"
        />
      </el-form-item>

      <el-form-item label="参考答案">
        <el-input
          v-model="form.answer"
          type="textarea"
          :rows="2"
          placeholder="请输入答案（可选）"
        />
      </el-form-item>

      <el-form-item label="题目解析">
        <el-input
          v-model="form.analysis"
          type="textarea"
          :rows="3"
          placeholder="请输入解析（可选）"
        />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="submitForm">提交保存</el-button>
        <el-button @click="resetForm">重置清空</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

// 表单数据
const form = ref({
  type: '',
  difficulty: 1,
  content: '',
  answer: '',
  analysis: ''
})

// 提交表单
const submitForm = async () => {
  if (!form.value.type || !form.value.content) {
    ElMessage.warning('题型和题干为必填项')
    return
  }

  try {
    const res = await fetch('/api/question', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(form.value)
    })

    const result = await res.json()
    if (result.code === 200) {
      ElMessage.success('题目录入成功！')
      resetForm() // 清空表单
    } else {
      ElMessage.error(result.msg || '录入失败')
    }
  } catch (err) {
    console.error(err)
    ElMessage.error('网络请求失败')
  }
}

// 重置表单
const resetForm = () => {
  form.value = {
    type: '',
    difficulty: 1,
    content: '',
    answer: '',
    analysis: ''
  }
}
</script>