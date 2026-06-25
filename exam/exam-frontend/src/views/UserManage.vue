<template>
  <div>
    <h3>用户管理</h3>

    <el-table :data="list" border style="width:100%;margin-top:16px;" size="small">
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="用户名" prop="username" width="120" />
      <el-table-column label="角色" width="100">
        <template #default="scope">
          <el-tag :type="scope.row.role === 'teacher' ? 'warning' : 'success'" size="small">
            {{ scope.row.role === 'teacher' ? '教师' : '学生' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="邮箱" prop="email" min-width="180" />
      <el-table-column label="状态" width="80">
        <template #default="scope">
          <el-switch v-model="scope.row.is_active" @change="toggleActive(scope.row)" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="创建时间" prop="created_at" width="160" />
      <el-table-column label="操作" width="160">
        <template #default="scope">
          <el-button type="warning" size="small" @click="openEdit(scope.row)">编辑</el-button>
          <el-button type="danger" size="small" @click="handleDelete(scope.row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="size"
      :total="total"
      style="margin-top:16px;text-align:right;"
      background
      layout="total, prev, pager, next, jumper"
      @current-change="getList"
    />

    <!-- 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" title="编辑用户" width="500px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="editForm.username" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="editForm.role">
            <el-radio value="student">学生</el-radio>
            <el-radio value="teacher">教师</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="editForm.password" type="password" show-password placeholder="留空则不修改" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleEditSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const page = ref(1)
const size = ref(10)
const total = ref(0)
const list = ref([])

const dialogVisible = ref(false)
const editForm = ref({ id: null, username: '', email: '', role: 'student', password: '' })

const authHeaders = () => ({
  'Authorization': `Bearer ${auth.token}`,
  'Content-Type': 'application/json'
})

const getList = async () => {
  try {
    const res = await fetch(`/api/auth/users?page=${page.value}&size=${size.value}`, {
      headers: authHeaders()
    })
    const result = await res.json()
    if (result.code === 200) {
      list.value = result.data || []
      total.value = result.total || 0
    } else if (res.status === 403) {
      ElMessage.error('无权访问')
    }
  } catch (err) {
    console.error(err)
  }
}

const toggleActive = async (row) => {
  try {
    const res = await fetch(`/api/auth/users/${row.id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify({ is_active: row.is_active })
    })
    const result = await res.json()
    if (result.code !== 200) {
      ElMessage.error(result.msg)
      row.is_active = !row.is_active  // revert
    }
  } catch (err) {
    ElMessage.error('操作失败')
    row.is_active = !row.is_active
  }
}

const openEdit = (row) => {
  editForm.value = {
    id: row.id,
    username: row.username,
    email: row.email,
    role: row.role,
    password: ''
  }
  dialogVisible.value = true
}

const handleEditSubmit = async () => {
  const body = {
    username: editForm.value.username,
    email: editForm.value.email,
    role: editForm.value.role
  }
  if (editForm.value.password) {
    body.password = editForm.value.password
  }
  try {
    const res = await fetch(`/api/auth/users/${editForm.value.id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(body)
    })
    const result = await res.json()
    if (result.code === 200) {
      ElMessage.success('修改成功')
      dialogVisible.value = false
      getList()
    } else {
      ElMessage.error(result.msg || '修改失败')
    }
  } catch (err) {
    ElMessage.error('请求出错')
  }
}

const handleDelete = (id) => {
  ElMessageBox.confirm('确定要删除该用户吗？', '提示', {
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      const res = await fetch(`/api/auth/users/${id}`, {
        method: 'DELETE',
        headers: authHeaders()
      })
      const result = await res.json()
      if (result.code === 200) {
        ElMessage.success('删除成功')
        getList()
      } else {
        ElMessage.error(result.msg || '删除失败')
      }
    } catch (err) {
      ElMessage.error('请求出错')
    }
  }).catch(() => {})
}

onMounted(() => {
  getList()
})
</script>
