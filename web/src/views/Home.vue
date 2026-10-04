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
          <div class="stat-label">最高权限</div>
          <div class="stat-value">{{ maxClanPriority }}</div>
        </div>
      </div>
    </div>

    <!-- 游戏账号（全局绑定 / 换绑 / 解绑）。
         2026-10-04 从「会战仪表盘」的状态条挪过来 —— 首页才是「我的」入口，
         放这儿比塞在仪表盘一排按钮里更好找。 -->
    <AccountBind :account="account" :group-id="bindGroupId" @changed="refreshAccount" />

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
            <el-tag size="small" effect="light" :type="clanTagType(clan.priority)">
              {{ clanTagText(clan.priority) }}
            </el-tag>
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

    <!-- 快捷入口。
         「出刀报告」「通知管理」已作为 Tab 并进「会战仪表盘」，这里不再单独放入口
         （侧边栏 / 手机底栏也一并撤了）。剩下 3 张卡，大屏改成 1/4 宽，不然右边空一半。 -->
    <el-row :gutter="16">
      <el-col :xs="12" :sm="8" :md="6" :lg="6">
        <div class="quick-card kanna-card" @click="go('/dashboard')">
          <el-icon size="32" color="#ec4899"><DataAnalysis /></el-icon>
          <div class="quick-text">会战仪表盘</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="8" :md="6" :lg="6">
        <div class="quick-card kanna-card" @click="go('/box')">
          <el-icon size="32" color="#8b5cf6"><Box /></el-icon>
          <div class="quick-text">BOX/助战</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="8" :md="6" :lg="6">
        <div class="quick-card kanna-card" @click="go('/arena')">
          <el-icon size="32" color="#0ea5e9"><Trophy /></el-icon>
          <div class="quick-text">竞技场中心</div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import { ElMessage } from 'element-plus'
import AccountBind from '@/components/AccountBind.vue'
import type { GroupAccountInfo } from '@/types'

const router = useRouter()
const userStore = useUserStore()

// 权限是「按群」算的（后端 basedata.GroupPriority）：
// 0 只读 / 1 网页端管理员 / 2 群主·群管 / 3 bot 主人
// 群主和群管在各自群里自动就是 2 级，不需要任何人手动授权。
const CLAN_PRIORITY_TEXT: Record<number, string> = {
  0: '普通成员',
  1: '管理员',
  2: '群主 / 群管',
  3: 'bot 主人'
}
const CLAN_PRIORITY_TAG: Record<
  number,
  'info' | 'success' | 'warning' | 'danger'
> = {
  0: 'info',
  1: 'success',
  2: 'warning',
  3: 'danger'
}

function clanTagText(level?: number) {
  return CLAN_PRIORITY_TEXT[Number(level) || 0] ?? '普通成员'
}

function clanTagType(level?: number) {
  return CLAN_PRIORITY_TAG[Number(level) || 0] ?? 'info'
}

// 已绑定公会里拿到的最高身份（每个群的等级可能不一样）
const maxClanPriority = computed(() =>
  userStore.clanList.reduce((max, c) => Math.max(max, Number(c.priority) || 0), 0)
)

const priorityText = computed(() => clanTagText(maxClanPriority.value))

// ================= 游戏账号（全局） =================
// 账号信息不在 store 里持久化（避免绑定后显示旧角色），每次进首页都从 /home 拉一次。
const EMPTY_ACCOUNT: GroupAccountInfo = {
  bound: false,
  name: '',
  platform: 0,
  viewer_id: null
}
const account = ref<GroupAccountInfo>({ ...EMPTY_ACCOUNT })

/**
 * 绑定 / 解绑接口是 `/{group_id}/bind_account` 形态（group_id 只做访问校验，
 * 账号本身是全局的、写进库的永远是 group_id = 0），所以挑一个有权限的群就行：
 * 优先当前选中的，其次公会列表里的第一个；一个群都没有时给 0，组件里按钮会禁用。
 */
const bindGroupId = computed(
  () => userStore.currentClanId || userStore.clanList[0]?.group_id || 0
)

/** 拉一次首页信息（顺带刷新公会列表和游戏账号），绑定 / 解绑成功后也走它 */
async function refreshAccount() {
  try {
    const info = await userStore.fetchUserInfo()
    account.value = info.account || { ...EMPTY_ACCOUNT }
  } catch (e) {
    /* 401 由 store（markLoggedOut）和路由守卫统一处理 */
  }
}

onMounted(refreshAccount)

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

/* ================= 手机端（< 768px） ================= */
@media (max-width: 767px) {
  .home-page {
    gap: 14px;
  }
  /* 欢迎卡：头像+问候 与 两个统计数字 改为上下两段 */
  .welcome-card {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }
  .welcome-left {
    gap: 12px;
  }
  .avatar-big {
    width: 54px;
    height: 54px;
    font-size: 26px;
  }
  .welcome-left h2 {
    font-size: 17px;
  }
  .saying {
    font-size: 11px;
  }
  .welcome-right {
    gap: 0;
    justify-content: space-around;
    padding-top: 10px;
    border-top: 1px dashed rgba(236, 72, 153, 0.2);
  }
  .stat-item {
    flex: 1;
    min-width: 0;
  }
  .stat-value {
    font-size: 24px;
  }
  .section-title {
    font-size: 15px;
    margin-top: 4px;
  }
  .clan-card,
  .quick-card {
    margin-bottom: 12px;
  }
  .quick-card {
    padding: 18px 8px;
    gap: 8px;
  }
  .quick-text {
    font-size: 13px;
  }
}
</style>
