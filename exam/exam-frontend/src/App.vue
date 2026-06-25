<template>
  <div id="app">
    <!-- 未登录：全屏显示登录/注册页 -->
    <template v-if="!auth.isLoggedIn">
      <router-view />
    </template>

    <!-- 已登录：侧边栏布局 -->
    <el-container v-else style="height: 100vh;">
      <el-aside width="200" style="background:#2f4050;display:flex;flex-direction:column;">
        <!-- 用户信息 -->
        <div style="padding:16px;color:#fff;text-align:center;border-bottom:1px solid #444;">
          <div style="font-size:14px;font-weight:bold;">{{ auth.user?.username }}</div>
          <div style="font-size:12px;color:#aaa;margin-top:4px;">
            {{ auth.isTeacher ? '教师' : '学生' }}
          </div>
        </div>

        <!-- 菜单 -->
        <el-menu
          router
          background-color="#2f4050"
          text-color="#ffffff"
          active-text-color="#ffd04b"
          style="flex:1;"
        >
          <el-menu-item index="/question/list">题目管理</el-menu-item>
          <el-menu-item index="/question/add">题目录入</el-menu-item>
          <el-menu-item index="/question/import">批量导入</el-menu-item>
          <el-menu-item index="/paper/generate">智能组卷</el-menu-item>
          <el-menu-item index="/exam/online">在线考试</el-menu-item>
          <el-menu-item index="/analysis/records">答题记录</el-menu-item>
          <el-menu-item index="/analysis/dashboard">试卷分析</el-menu-item>
          <el-menu-item v-if="auth.isTeacher" index="/users">用户管理</el-menu-item>
        </el-menu>

        <!-- 退出按钮 -->
        <div style="padding:12px;text-align:center;border-top:1px solid #444;">
          <el-button type="danger" size="small" plain @click="handleLogout" style="width:80%;">
            退出登录
          </el-button>
        </div>
      </el-aside>

      <el-container>
        <el-main>
          <router-view />
        </el-main>
      </el-container>

      <!-- 难度分析悬浮进度窗 -->
      <DifficultyProgress />
      <!-- 导入悬浮进度窗 -->
      <ImportProgress />
    </el-container>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from './stores/auth'
import DifficultyProgress from './components/DifficultyProgress.vue'
import ImportProgress from './components/ImportProgress.vue'

const auth = useAuthStore()
const router = useRouter()

const handleLogout = () => {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    auth.logout()
    router.push('/login')
  }).catch(() => {})
}

onMounted(() => {
  auth.fetchUser()
})
</script>

<style>
body { margin: 0; }
#app {
  font-family: "Microsoft YaHei";
}
</style>
