<template>
  <el-container class="layout-container">
    <!-- 侧边栏（手机端整块隐藏，改用底部 tab bar） -->
    <el-aside v-if="!isMobile" :width="isCollapse ? '64px' : '220px'" class="aside">
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
          <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
            <el-icon><component :is="m.icon" /></el-icon>
            <template #title>{{ m.title }}</template>
          </el-menu-item>
        </el-menu>
      </div>
    </el-aside>

    <!-- 主内容 -->
    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-button v-if="!isMobile" text @click="isCollapse = !isCollapse">
            <el-icon size="20">
              <Fold v-if="!isCollapse" />
              <Expand v-else />
            </el-icon>
          </el-button>
          <!-- 手机端没有侧边栏，用一行小字保留品牌标识 -->
          <span v-else class="brand-inline">🌸 环奈连结 R</span>

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
          <el-tooltip v-if="!isMobile" content="回到首页" placement="bottom">
            <el-button text @click="$router.push('/home')">
              <el-icon><House /></el-icon>
            </el-button>
          </el-tooltip>

          <el-dropdown trigger="click" @command="onUserCommand">
            <div class="user-chip">
              <el-avatar :size="32" style="background: #ec4899">
                {{ userStore.userName?.[0] || userStore.userId }}
              </el-avatar>
              <div v-if="!isMobile" class="user-info">
                <div class="user-name">{{ userStore.userName || '玩家' }}</div>
                <div class="user-id">QQ: {{ userStore.userId }}</div>
              </div>
              <el-icon v-if="!isMobile"><CaretBottom /></el-icon>
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

    <!-- 手机端底部导航：4 个主菜单放在拇指可达的位置，比汉堡抽屉少一次点击 -->
    <nav v-if="isMobile" class="mobile-tabbar">
      <router-link
        v-for="m in menus"
        :key="m.path"
        :to="m.path"
        class="tab-item"
        :class="{ active: activeMenu === m.path }"
      >
        <el-icon size="20"><component :is="m.icon" /></el-icon>
        <span>{{ m.tab }}</span>
      </router-link>
    </nav>

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
import { useIsMobile } from '@/composables/useResponsive'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isMobile = useIsMobile()

const isCollapse = ref(false)
const currentGroupId = ref<number>(0)

/**
 * 菜单定义：桌面端左侧 el-menu 和手机端底部 tab 共用一份，避免两处漏改。
 * `title` 是侧边栏文字，`tab` 是底部 tab 的短标签（窄屏放不下长名字）。
 *
 * 出刀报告 / 通知管理**不再占菜单位** —— 它们已作为 Tab 整合进「会战仪表盘」，
 * 菜单只留 4 个一级入口（手机底栏最多也就放得下 4 个）。
 */
const menus = [
  { path: '/home', title: '首页', tab: '首页', icon: 'HomeFilled' },
  { path: '/dashboard', title: '会战仪表盘', tab: '仪表盘', icon: 'DataAnalysis' },
  { path: '/box', title: 'BOX/助战', tab: 'BOX', icon: 'Box' },
  { path: '/arena', title: '竞技场中心', tab: '竞技场', icon: 'Trophy' }
]

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
  // 子页面（Dashboard / Report / Notice）统一按「URL 参数 > props > store」解析 groupId，
  // 而 URL 参数优先级最高。切换公会只改 store 的话，URL 还停在旧群号，子页面的 groupId
  // 就被 URL 锁死了 —— computed 值不变、watch 不触发，表现就是「换了公会但页面毫无反应」。
  // 所以这里把新群号写回路径（/dashboard/123 → /dashboard/456），让子页面重新加载。
  // query 要一起带上：仪表盘的页内 Tab 存在 ?tab=report / ?tab=notice 里，
  // 只 replace 路径会把当前 Tab 丢掉、切完公会弹回「会战数据」。
  const seg = route.path.split('/')
  if (seg.length === 3 && /^\d+$/.test(seg[2])) {
    seg[2] = String(id)
    router.replace({ path: seg.join('/'), query: route.query })
  }
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
        // ⚠️ 这里**不需要** await，但顺序不能变：
        // store 的 logout() 会**同步**把本地登录态清掉（isLoggedIn / userId / 持久化），
        // 后端 token 作废 + cookie 清理在后台继续跑。所以紧接着的 router.replace('/login')
        // 里，路由守卫看到的已经是「未登录」，能正常进登录页。
        // 之前这个 BUG 就是：logout() 先 await 接口、之后才清本地态，而这里没等 ——
        // 守卫看到「还登录着」，把 /login 当成已登录用户访问登录页又弹回 /home，
        // 表现就是「点了退出登录没反应，人还留在原页面」。
        void userStore.logout()
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
  /* 手机上 100vh 会把地址栏算进去、导致底部被裁，dvh 才是真实可视高度 */
  height: 100dvh;
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

/* ================= 手机端（< 768px） ================= */
.brand-inline {
  display: none;
}
.mobile-tabbar {
  display: none;
}

@media (max-width: 767px) {
  .header {
    padding: 0 12px;
    height: 56px;
    gap: 8px;
  }
  .brand-inline {
    display: block;
    flex-shrink: 0;
    font-size: 14px;
    font-weight: 700;
    color: #be185d;
    white-space: nowrap;
  }
  /* 公会选择器吃掉剩余宽度，不再固定 240px */
  .header-left {
    flex: 1;
    min-width: 0;
    gap: 8px;
  }
  .header-right {
    flex-shrink: 0;
    gap: 6px;
  }
  .clan-select {
    width: 100%;
    min-width: 0;
  }
  .no-clan-tag {
    max-width: 100%;
    font-size: 12px;
    height: auto;
    padding: 4px 8px;
    white-space: normal;
    line-height: 1.4;
  }
  .user-chip {
    padding: 4px;
    gap: 0;
  }
  .main-content {
    padding: 12px;
    /* 给底部 tab bar 留位（含 iPhone home indicator 的安全区） */
    padding-bottom: calc(68px + env(safe-area-inset-bottom));
    /* 手机上内容略宽一点就整页左右晃动，比裁掉更难受。
       宽表格（el-table）自己有横向滚动条，不受这里影响。 */
    overflow-x: hidden;
  }

  .mobile-tabbar {
    display: flex;
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 100;
    background: rgba(255, 255, 255, 0.94);
    backdrop-filter: blur(12px);
    border-top: 1px solid rgba(236, 72, 153, 0.12);
    padding-bottom: env(safe-area-inset-bottom);
  }
  .tab-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    height: 56px;
    font-size: 11px;
    color: #9ca3af;
    transition: color 0.2s;
  }
  .tab-item.active {
    color: var(--kanna-primary);
  }
}
</style>
