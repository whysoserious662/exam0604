import { createRouter, createWebHistory } from 'vue-router'
import QuestionList from '../views/QuestionList.vue'
import QuestionAdd from '../views/QuestionAdd.vue'
import QuestionImport from '../views/QuestionImport.vue'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import UserManage from '../views/UserManage.vue'

const routes = [
  { path: '/', redirect: '/question/list' },

  // 认证
  { path: '/login', name: 'Login', component: Login },
  { path: '/register', name: 'Register', component: Register },

  // 题目管理
  { path: '/question/list', name: 'QuestionList', component: QuestionList },
  { path: '/question/add', name: 'QuestionAdd', component: QuestionAdd },
  { path: '/question/import', name: 'QuestionImport', component: QuestionImport },

  // 智能组卷
  {
    path: '/paper/generate',
    name: 'PaperGenerate',
    component: () => import('../views/paper/generate.vue')
  },

  // 答题记录管理
  {
    path: '/analysis/records',
    name: 'ExamRecord',
    component: () => import('../views/analysis/ExamRecord.vue')
  },

  // 试卷分析
  {
    path: '/analysis/dashboard',
    name: 'Analysis',
    component: () => import('../views/analysis/Analysis.vue')
  },

  // 在线考试
  {
    path: '/exam/online',
    name: 'OnlineExam',
    component: () => import('../views/exam/OnlineExam.vue')
  },

  // 用户管理（教师）
  { path: '/users', name: 'UserManage', component: UserManage }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：未登录重定向到登录页
router.beforeEach((to, from, next) => {
  // 动态导入 store 避免循环依赖
  const token = localStorage.getItem('token')
  const isLoggedIn = !!token

  if (!isLoggedIn && to.path !== '/login' && to.path !== '/register') {
    return next('/login')
  }
  if (isLoggedIn && (to.path === '/login' || to.path === '/register')) {
    return next('/question/list')
  }
  next()
})

export default router
