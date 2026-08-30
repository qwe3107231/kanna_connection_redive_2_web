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
                <el-dropdown-item command="logout">
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
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/store/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isCollapse = ref(false)
const currentGroupId = ref<number>(0)

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
</style>
