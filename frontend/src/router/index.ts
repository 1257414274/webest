import { createRouter, createWebHistory } from 'vue-router'
import Layout from '../layout/index.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      component: () => import('../views/login/index.vue')
    },
    {
      path: '/',
      component: Layout,
      redirect: '/target',
      children: [
        {
          path: 'target',
          name: 'Target',
          component: () => import('../views/target/index.vue')
        },
        {
          path: 'claude',
          name: 'Claude',
          component: () => import('../views/claude/index.vue')
        },
        {
          path: 'opencode',
          name: 'OpenCode',
          component: () => import('../views/opencode/index.vue')
        }
      ]
    }
  ]
})

router.beforeEach((to, from, next) => {
  // 校验登录页参数
  if (to.path === '/login') {
    const queryCcid = to.query.ccid || new URLSearchParams(window.location.search).get('ccid')
    if (queryCcid !== 'wmszbd') {
      // 拒绝访问，直接停留在空页面或跳404
      next(false)
      return
    }
  }

  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login?ccid=wmszbd')
  } else {
    next()
  }
})

export default router
