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
  const urlToken = new URLSearchParams(window.location.search).get('token')
  if (urlToken) {
    localStorage.setItem('access_token', urlToken)
    window.history.replaceState({}, '', to.path)
  }
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
