<template>
  <div class="login-container">
    <div class="login-bg"></div>
    <div class="login-box kanna-card">
      <div class="brand">
        <div class="logo">🌸</div>
        <h1>环奈连结 R · 管理后台</h1>
        <p class="subtitle">Kanna Connection Redive Relink</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @keyup.enter="onLoginClick"
      >
        <el-form-item label="账号 (QQ 号)" prop="account">
          <el-input
            v-model="form.account"
            placeholder="请输入机器人分配给你的账号"
            clearable
            :prefix-icon="User"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入临时密码或修改后的密码"
            show-password
            clearable
            :prefix-icon="Lock"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            class="w-full login-btn"
            :loading="loading"
            @click="onLoginClick"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="tip-box">
        <el-icon><InfoFilled /></el-icon>
        <span>还没有账号？在 QQ 对机器人发送 <b>网页端登录</b> 获取临时登录链接</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElForm, ElMessage } from 'element-plus'
import { User, Lock, InfoFilled } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'
import type { FormInstance, FormRules } from 'element-plus'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
// 防止自动登录 + 用户点击重复触发
const submitting = ref(false)

const form = reactive({
  account: '',
  password: ''
})

const rules: FormRules = {
  account: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

/** 实际登录动作，保证只执行一次 */
async function doLogin() {
  if (submitting.value) return
  if (!formRef.value) return false

  // validate 同时支持 callback 和 Promise 风格，这里用 Promise 风格，避免回调被执行两次
  try {
    await formRef.value.validate()
  } catch (e) {
    return false
  }

  try {
    submitting.value = true
    loading.value = true

    await userStore.login(form.account.trim(), form.password)

    ElMessage.success('登录成功')

    // 计算跳转目标：redirect query（必须是站内路径，不能跳到外站）
    let redirect = (route.query.redirect as string) || '/home'
    if (!redirect.startsWith('/')) redirect = '/home'
    // 安全起见，防止 /http:/xxx 这种跳转
    if (/^\/+https?:/i.test(redirect)) redirect = '/home'

    // 用 replace，避免用户点"后退"回到登录页
    await router.replace(redirect)
    return true
  } catch (e) {
    // axios 拦截器已提示错误；这里不做额外提示，但返回失败
    return false
  } finally {
    loading.value = false
    // 短暂保留 submitting，避免 validate 回调重复导致的连续调用
    setTimeout(() => { submitting.value = false }, 600)
  }
}

function onLoginClick() {
  doLogin()
}

onMounted(() => {
  // 支持从 URL query 携带 account/password 自动登录（机器人私发的链接）
  const urlAccount = route.query.account as string
  const urlPassword = route.query.password as string
  if (urlAccount) {
    form.account = urlAccount
  }
  if (urlPassword) {
    form.password = urlPassword
  }
  // 有完整凭据则自动登录一次
  if (form.account && form.password) {
    // 下一帧再执行，确保表单 ref 已就绪
    setTimeout(() => doLogin(), 50)
  }
})
</script>

<style scoped>
.login-container {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  overflow: hidden;
}
.login-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 20% 30%, rgba(236, 72, 153, 0.25), transparent 40%),
    radial-gradient(circle at 80% 70%, rgba(251, 191, 36, 0.25), transparent 45%),
    radial-gradient(circle at 60% 10%, rgba(147, 197, 253, 0.3), transparent 40%);
  filter: blur(30px);
  z-index: 0;
}
.login-box {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: 36px 32px 24px;
}
.brand {
  text-align: center;
  margin-bottom: 28px;
}
.logo {
  font-size: 54px;
  line-height: 1;
  margin-bottom: 12px;
  filter: drop-shadow(0 4px 12px rgba(236, 72, 153, 0.3));
}
.brand h1 {
  font-size: 22px;
  margin: 0 0 6px;
  color: #be185d;
  font-weight: 700;
}
.brand .subtitle {
  font-size: 13px;
  color: #9ca3af;
  margin: 0;
  letter-spacing: 1px;
}
.w-full {
  width: 100%;
}
.login-btn {
  height: 44px;
  font-size: 16px;
  letter-spacing: 4px;
  font-weight: 600;
}
.tip-box {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 14px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  color: #9a3412;
  font-size: 13px;
  line-height: 1.6;
}
.tip-box .el-icon {
  flex-shrink: 0;
  margin-top: 2px;
}
.tip-box b {
  color: #c2410c;
}
</style>
