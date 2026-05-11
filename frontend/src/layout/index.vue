<template>
  <el-container class="layout-container">
    <el-aside width="200px" class="aside">
      <div class="logo">WeBest 协同平台</div>
      <el-menu
        :default-active="route.path"
        class="el-menu-vertical"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
      >
        <el-menu-item index="/target">
          <el-icon><Location /></el-icon>
          <span>目标</span>
        </el-menu-item>
        <el-menu-item index="/claude">
          <el-icon><ChatDotRound /></el-icon>
          <span>Claude</span>
        </el-menu-item>
        <el-menu-item index="/opencode">
          <el-icon><Cpu /></el-icon>
          <span>OpenCode</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header class="header">
        <div class="header-right">
          <span class="user-name">Admin</span>
          <el-button type="danger" link @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>
      
      <el-main class="main">
        <router-view></router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ChatDotRound, Cpu, Location } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const route = useRoute()

const handleLogout = async () => {
  const token = localStorage.getItem('token')
  if (token) {
    try {
      await axios.post('/api/logoutCurrentSession', {}, { headers: { 'x-token': token } })
    } catch (_e) {
      // ignore
    }
  }
  localStorage.removeItem('token')
  localStorage.removeItem('session_id')
  router.push('/login')
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}
.aside {
  background-color: #304156;
}
.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  color: #fff;
  font-size: 20px;
  font-weight: bold;
  background: #2b3643;
}
.el-menu-vertical {
  border-right: none;
}
.header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0,21,41,.08);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 20px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 15px;
}
.main {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>
