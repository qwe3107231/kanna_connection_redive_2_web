<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
      <div class="aside-inner">
        <div class="brand-mini">
          <span class="logo-mini">🌸</span>
          <transition name="fade">
            <span v-show="!isCollapse" class="brand-title">环奈连结 R</span>
          </transition>
        </div>

        <el-menu
          :default-active="activeMenu"
          router
          :collapse="isCollapse"
          class="side-menu"
          background-color="transparent"
          text-color="#4b5563"
          active-text-color="#ec4899"
        >
          <el-menu-item index="/home">
            <el-icon><HomeFilled /></el-icon>
            <template #title>首页</template>
          </el-menu-item>
          <el-menu-item index="/dashboard">
            <el-icon><DataAnalysis /></el-icon>
            <template #title>会战仪表盘</template>
          </el-menu-item>
          <el-menu-item index="/report">
            <el-icon><Document /></el-icon>
            <template #title>出刀报告</template>
          </el-menu-item>
          <el-menu-item index="/notice">
            <el-icon><Bell /></el-icon>
            <template #title>通知管理</template>
          </el-menu-item>
        </el-menu>
      </div>
    </el-aside>

    <!-- 主内容 -->
    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-button text @click="isCollapse = !isCollapse">
            <el-icon size="20">
              <Fold v-if="!isCollapse" />
              <Expand v-else />
            </el-icon>
          </el-button>

          <!-- 公会选择器 -->
          <el-select
            v-if="userStore.clanList.length > 0"
            v-model="currentGroupId"
            class="clan-select"
            size="default"
            placeholder="选择公会"
            @change="onClanChange"
          >
            <el-option
              v-for="c in userStore.clanList"
              :key="c.group_id"
              :label="c.group_name || `公会 ${c.group_id}`"
              :value="c.group_id"
            />
          </el-select>
          <el-tag
            v-else
            type="warning"
            effect="light"
            size="default"
            class="no-clan-tag"
          >
            暂无绑定公会，请在 QQ 群内使用【绑定本群公会】
          </el-tag>
        </div>

        <div class="header-right">
          <el-tooltip content="回到首页" placement="bottom">
            <el-button text @click="$router.push('/home')">
              <el-icon><House /></el-icon>
            </el-button>
          </el-tooltip>

          <el-dropdown trigger="click" @command="onUserCommand">
            <div class="user-chip">
              <el-avatar :size="32" style="background: #ec4899">
                {{ userStore.userName?.[0] || userStore.userId }}
              </el-avatar>
              <div class="user-info">
                <div class="user-name">{{ userStore.userName || '玩家' }}</div>
                <div class="user-id">QQ: {{ userStore.userId }}</div>
              </div>
              <el-icon><CaretBottom /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="password">
                  <el-icon><Key /></el-icon>修改密码
                </el-dropdown-item>
                <el-dropdown-item command="logout" divided>
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" :groupId="currentGroupId" />
          </transition>
        </router-view>
      </el-main>
    </el-container>

    <!-- 修改密码弹窗 -->
    <el-dialog
      v-model="pwdDialog.visible"
      title="修改登录密码"
      width="420px"
      :close-on-click-modal="false"
      @closed="resetPwdForm"
    >
      <el-alert
        title="修改成功后其他设备上的登录会失效，当前设备不受影响。"
        type="info"
        show-icon
        :closable="false"
        class="pwd-alert"
      />
      <el-form
        ref="pwdFormRef"
        :model="pwdDialog.form"
        :rules="pwdRules"
        label-position="top"
      >
        <el-form-item label="当前密码" prop="old_password">
          <el-input
            v-model="pwdDialog.form.old_password"
            type="password"
            show-password
            placeholder="临时密码，或你上次改过的密码"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="pwdDialog.form.new_password"
            type="password"
            show-password
            placeholder="6~32 位"
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input
            v-model="pwdDialog.form.confirm_password"
            type="password"
            show-password
            placeholder="再输一遍新密码"
            @keyup.enter="submitPwd"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="pwdDialog.loading" @click="submitPwd">
          确定修改
        </el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { changePassword } from '@/api'
import { useUserStore } from '@/store/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isCollapse = ref(false)
const currentGroupId = ref<number>(0)

// —— 修改密码 ——
// 后端 /change_password 需要旧密码；改成功后该账号其他设备上的 token 会失效。
const pwdFormRef = ref<FormInstance>()
const pwdDialog = reactive({
  visible: false,
  loading: false,
  form: { old_password: '', new_password: '', confirm_password: '' }
})

const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 32, message: '长度需在 6~32 位之间', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value && value === pwdDialog.form.old_password) {
          callback(new Error('新密码不能和当前密码相同'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  confirm_password: [
    { required: true, message: '请再输一遍新密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value !== pwdDialog.form.new_password) {
          callback(new Error('两次输入的新密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

function resetPwdForm() {
  pwdDialog.form.old_password = ''
  pwdDialog.form.new_password = ''
  pwdDialog.form.confirm_password = ''
  pwdFormRef.value?.clearValidate()
}

async function submitPwd() {
  if (!pwdFormRef.value) return
  try {
    await pwdFormRef.value.validate()
  } catch (e) {
    return
  }
  pwdDialog.loading = true
  try {
    await changePassword({
      old_password: pwdDialog.form.old_password,
      new_password: pwdDialog.form.new_password
    })
    ElMessage.success('密码修改成功，其他设备需要重新登录')
    pwdDialog.visible = false
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    pwdDialog.loading = false
  }
}

const activeMenu = computed(() => route.path.split('/').slice(0, 2).join('/') || '/home')

onMounted(async () => {
  await loadUserInfo()
})

async function loadUserInfo() {
  try {
    await userStore.fetchUserInfo()
    currentGroupId.value = userStore.currentClanId
  } catch (e: any) {
    if (e?.response?.status === 401) {
      router.replace('/login')
    }
  }
}

watch(
  () => userStore.currentClanId,
  (id) => {
    if (id && !currentGroupId.value) {
      currentGroupId.value = id
    }
  },
  { immediate: true }
)

function onClanChange(id: number) {
  userStore.setCurrentClan(id)
  // 广播给子视图使用
}

function onUserCommand(cmd: string) {
  if (cmd === 'password') {
    pwdDialog.visible = true
    return
  }
  if (cmd === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })
      .then(() => {
        userStore.logout()
        ElMessage.success('已退出登录')
        router.replace('/login')
      })
      .catch(() => {})
  }
}

defineExpose({ currentGroupId })
</script>

<style scoped>
.layout-container {
  height: 100vh;
  overflow: hidden;
}
.aside {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border-right: 1px solid rgba(236, 72, 153, 0.1);
  transition: width 0.25s ease;
}
.aside-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px 0;
}
.brand-mini {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 20px 20px;
  font-weight: 700;
  color: #be185d;
  font-size: 17px;
  white-space: nowrap;
  overflow: hidden;
}
.logo-mini {
  font-size: 24px;
  flex-shrink: 0;
}
.brand-title {
  background: linear-gradient(90deg, #ec4899, #f59e0b);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.side-menu {
  flex: 1;
  padding: 0 8px;
}
.side-menu .el-menu-item {
  border-radius: 8px;
  margin: 2px 0;
}
.header {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(236, 72, 153, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 60px;
}
.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.clan-select {
  width: 240px;
}
.no-clan-tag {
  max-width: 420px;
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 10px 4px 4px;
  border-radius: 100px;
  background: rgba(236, 72, 153, 0.08);
  cursor: pointer;
  transition: background 0.2s;
}
.user-chip:hover {
  background: rgba(236, 72, 153, 0.15);
}
.user-info {
  line-height: 1.2;
}
.user-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}
.user-id {
  font-size: 11px;
  color: #9ca3af;
}
.main-content {
  overflow: auto;
  padding: 20px 24px;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.pwd-alert {
  margin-bottom: 16px;
}
</style>
