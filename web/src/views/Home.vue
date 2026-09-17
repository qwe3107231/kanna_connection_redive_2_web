<template>
  <div class="home-page">
    <!-- 欢迎卡片 -->
    <div class="welcome-card kanna-card">
      <div class="welcome-left">
        <div class="avatar-big">🌸</div>
        <div>
          <h2>欢迎回来，{{ userStore.userName || '指挥官' }}！</h2>
          <p class="qq-info">QQ 号：{{ userStore.userId }} · 身份：{{ priorityText }}</p>
          <p class="saying">"{{ userStore.saying }}"</p>
        </div>
      </div>
      <div class="welcome-right">
        <div class="stat-item">
          <div class="stat-label">我的公会</div>
          <div class="stat-value">{{ userStore.clanList.length }}</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">权限等级</div>
          <div class="stat-value">{{ userStore.priority }}</div>
        </div>
      </div>
    </div>

    <!-- 我的公会 -->
    <div class="section-title">
      <el-icon :size="18"><OfficeBuilding /></el-icon>
      <span>我的公会</span>
    </div>

    <el-row v-if="userStore.clanList.length" :gutter="16">
      <el-col
        v-for="clan in userStore.clanList"
        :key="clan.group_id"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
      >
        <div
          class="clan-card kanna-card"
          @click="enterClan(clan.group_id)"
        >
          <div class="clan-header">
            <div class="clan-logo">
              {{ (clan.group_name || '公会')[0] }}
            </div>
            <el-tag size="small" effect="light" type="success" v-if="clan.priority && clan.priority > 0">
              管理员
            </el-tag>
            <el-tag size="small" effect="light" v-else>成员</el-tag>
          </div>
          <div class="clan-name">{{ clan.group_name || `公会 ${clan.group_id}` }}</div>
          <div class="clan-id">群号：{{ clan.group_id }}</div>
          <div class="clan-actions">
            <el-button type="primary" link size="small">
              进入控制台 <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-empty v-else description="您还没有绑定任何公会，请在QQ群中发送【绑定本群公会】">
      <el-button type="primary" @click="reloadUser">刷新信息</el-button>
    </el-empty>

    <!-- 快捷入口 -->
    <div class="section-title">
      <el-icon size="18"><Grid /></el-icon>
      <span>快捷入口</span>
    </div>

    <el-row :gutter="16">
      <el-col :xs="12" :sm="8" :md="6" :lg="4">
        <div class="quick-card kanna-card" @click="go('/dashboard')">
          <el-icon size="32" color="#ec4899"><DataAnalysis /></el-icon>
          <div class="quick-text">会战仪表盘</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="8" :md="6" :lg="4">
        <div class="quick-card kanna-card" @click="go('/report')">
          <el-icon size="32" color="#f59e0b"><Document /></el-icon>
          <div class="quick-text">出刀报告</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="8" :md="6" :lg="4">
        <div class="quick-card kanna-card" @click="go('/notice')">
          <el-icon size="32" color="#10b981"><Bell /></el-icon>
          <div class="quick-text">通知管理</div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

const priorityText = computed(() => {
  const p = userStore.priority
  if (p >= 2) return '超级管理员'
  if (p >= 1) return '管理员'
  return '普通成员'
})

onMounted(async () => {
  if (!userStore.userId) {
    try {
      await userStore.fetchUserInfo()
    } catch (e) {
      /* router 拦截会处理 401 */
    }
  }
})

function enterClan(groupId: number) {
  userStore.setCurrentClan(groupId)
  router.push(`/dashboard/${groupId}`)
}

function go(path: string) {
  if (userStore.currentClanId) {
    router.push(`${path}/${userStore.currentClanId}`)
  } else {
    ElMessage.warning('请先选择一个公会')
    router.push(path)
  }
}

async function reloadUser() {
  await userStore.fetchUserInfo()
  ElMessage.success('已刷新')
}
</script>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.welcome-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.welcome-left {
  display: flex;
  gap: 18px;
  align-items: center;
}
.avatar-big {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, #fce7f3, #fef3c7);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  box-shadow: 0 4px 14px rgba(236, 72, 153, 0.2);
}
.welcome-left h2 {
  margin: 0 0 4px;
  color: #831843;
}
.qq-info {
  margin: 0 0 6px;
  color: #6b7280;
  font-size: 13px;
}
.saying {
  margin: 0;
  color: #9ca3af;
  font-size: 12px;
  max-width: 520px;
  font-style: italic;
}
.welcome-right {
  display: flex;
  gap: 24px;
}
.stat-item {
  text-align: center;
  min-width: 80px;
}
.stat-label {
  color: #9ca3af;
  font-size: 12px;
}
.stat-value {
  margin-top: 4px;
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(90deg, #ec4899, #f59e0b);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #831843;
  margin-top: 8px;
}
.clan-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  margin-bottom: 16px;
}
.clan-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(236, 72, 153, 0.15);
}
.clan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.clan-logo {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: linear-gradient(135deg, #fbcfe8, #fde68a);
  color: #9d174d;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 20px;
}
.clan-name {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}
.clan-id {
  color: #9ca3af;
  font-size: 12px;
  margin-top: 4px;
}
.clan-actions {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
.quick-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 12px;
  gap: 10px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 16px;
}
.quick-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(236, 72, 153, 0.15);
}
.quick-text {
  font-size: 14px;
  color: #374151;
  font-weight: 500;
}
</style>
