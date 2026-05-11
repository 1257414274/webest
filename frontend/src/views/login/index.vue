<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="login-header">
          <h2>WeBest 系统登录</h2>
        </div>
      </template>
      <el-form :model="loginForm" :rules="rules" ref="loginFormRef" label-width="0">
        <el-form-item prop="username">
          <el-input v-model="loginForm.username" placeholder="请输入用户名" prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" prefix-icon="Lock" @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="login-btn" :loading="loading" @click="handleLogin">登录</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const loginFormRef = ref()
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const getDeviceId = () => {
  const key = 'device_id'
  let deviceId = localStorage.getItem(key)
  if (!deviceId) {
    deviceId = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    localStorage.setItem(key, deviceId)
  }
  return deviceId
}

const handleLogin = async () => {
  if (!loginFormRef.value) return
  await loginFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      loading.value = true
      try {
        const res = await axios.post('/api/login', loginForm, {
          headers: {
            'x-device-id': getDeviceId(),
            'x-device-name': navigator.platform || 'web'
          }
        })
        if (res.data.code === 0) {
          ElMessage.success('登录成功')
          localStorage.setItem('token', res.data.data.token)
          localStorage.setItem('session_id', res.data.data.session_id || '')
          router.push('/')
        } else {
          ElMessage.error(res.data.msg || '登录失败')
        }
      } catch (error) {
        ElMessage.error('网络错误，请稍后再试')
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #2d3a4b;
}
.login-card {
  width: 400px;
}
.login-header {
  text-align: center;
}
.login-header h2 {
  margin: 0;
  color: #303133;
}
.login-btn {
  width: 100%;
}
</style>
