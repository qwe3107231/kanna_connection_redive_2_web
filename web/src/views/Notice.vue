<template>
  <div class="notice-page">
    <el-empty v-if="!groupId" description="请先从上方选择一个公会" />

    <template v-else>
      <!-- 顶部操作栏 -->
      <div class="action-bar kanna-card">
        <div class="tabs-group">
          <el-radio-group v-model="activeTab" size="default">
            <el-radio-button value="subscribe">
              <el-icon><Calendar /></el-icon>预约 ({{ data.subscribe.length }})
            </el-radio-button>
            <el-radio-button value="apply">
              <el-icon><Aim /></el-icon>申请 ({{ data.apply.length }})
            </el-radio-button>
            <el-radio-button value="tree">
              <el-icon><Tree /></el-icon>挂树 ({{ data.tree.length }})
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="actions">
          <el-tag size="small" type="warning" effect="plain" v-if="sseEnabled">
            <el-icon><Connection /></el-icon>实时同步
          </el-tag>
          <el-button size="small" @click="toggleSSE">
            {{ sseEnabled ? '关闭实时' : '开启实时' }}
          </el-button>
          <el-button size="small" @click="loadNotice(true)">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
          <el-tooltip
            :disabled="canAddNotice"
            :content="noticeTip"
            placement="bottom"
          >
            <el-button
              type="primary"
              size="small"
              :disabled="!canAddNotice"
              @click="openAddDialog"
            >
              <el-icon><Plus /></el-icon>添加通知
            </el-button>
          </el-tooltip>
        </div>
      </div>

      <!-- 列表 -->
      <div class="list-card kanna-card mt-16">
        <div v-if="activeList.length === 0" class="empty-state">
          <el-empty :description="emptyText" />
        </div>

        <el-timeline v-else>
          <el-timeline-item
            v-for="(item, idx) in activeList"
            :key="`${item.notice_type}-${item.user_id}-${item.boss}-${item.lap}-${idx}`"
            :type="timelineColor(item.notice_type)"
            :timestamp="formatFullTime(item.time || 0)"
            placement="top"
            size="large"
          >
            <div class="notice-item">
              <div class="notice-head">
                <div class="notice-user">
                  <el-avatar :size="32" style="background: #ec4899">
                    {{ String(item.user_id).slice(-1) }}
                  </el-avatar>
                  <div class="uinfo">
                    <div class="uname">
                      <b>{{ getUserDisplayName(item.user_id) }}</b>
                      <span class="uid-text">QQ: {{ item.user_id }}</span>
                    </div>
                    <div class="u-boss">
                      <el-tag size="small" :type="timelineColor(item.notice_type)">
                        {{ typeLabel(item.notice_type) }}
                        {{ item.lap ? `· 第${item.lap}周目` : '· 当前周目' }}
                        · {{ item.boss }}王
                      </el-tag>
                    </div>
                  </div>
                </div>
                <div class="notice-actions" v-if="canCancel(item)">
                  <el-popconfirm
                    :title="
                      isMineNotice(item)
                        ? '确定取消这条通知吗？（QQ群内会同步公告）'
                        : '确定替 TA 取消这条通知吗？（QQ群内会同步公告）'
                    "
                    confirm-button-text="确定取消"
                    cancel-button-text="再想想"
                    @confirm="onCancel(item)"
                  >
                    <template #reference>
                      <el-button size="small" type="danger" plain>
                        <el-icon><Delete /></el-icon>
                        {{ isMineNotice(item) ? '取消' : '代取消' }}
                      </el-button>
                    </template>
                  </el-popconfirm>
                </div>
              </div>
              <div class="notice-text" v-if="item.text">
                💬 {{ item.text }}
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>

      <!-- 添加通知弹窗 -->
      <el-dialog
        v-model="addDialog.visible"
        title="添加通知"
        width="440px"
        :close-on-click-modal="false"
      >
        <el-form :model="addDialog.form" label-position="top">
          <el-form-item label="通知类型" required>
            <el-radio-group v-model="addDialog.form.notice_type">
              <el-radio :value="0">预约 BOSS</el-radio>
              <el-radio :value="2">申请出刀</el-radio>
              <el-radio :value="1">挂树</el-radio>
              <el-radio :value="5">记录 SL</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="BOSS 编号" required v-if="addDialog.form.notice_type !== 5">
            <el-select v-model="addDialog.form.boss" placeholder="选择 BOSS">
              <el-option v-for="i in 5" :key="i" :label="`${i}王`" :value="i" />
            </el-select>
          </el-form-item>
          <el-form-item label="周目（0=当前周目）" v-if="addDialog.form.notice_type !== 5">
            <el-input-number v-model="addDialog.form.lap" :min="0" :max="999" />
          </el-form-item>
          <el-form-item label="留言（可选）" v-if="addDialog.form.notice_type !== 5">
            <el-input
              v-model="addDialog.form.text"
              type="textarea"
              :rows="2"
              maxlength="50"
              show-word-limit
              placeholder="例：补偿/90s后出"
            />
          </el-form-item>
          <el-alert
            v-if="addDialog.form.notice_type === 5"
            title="SL 每日仅可记录一次，重复提交会被拒绝"
            type="warning"
            show-icon
            :closable="false"
          />
        </el-form>
        <template #footer>
          <el-button @click="addDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="onSubmitAdd">确定</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { useUserStore } from '@/store/user'
import { getNoticeList, setNotice, deleteNotice } from '@/api'
import { createSSEConnection } from '@/utils/sse'
import { API_BASE } from '@/utils/request'
import type { NoticeResponse, NoticeCacheModel } from '@/types'

const props = defineProps<{ groupId?: number }>()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const groupId = computed<number>(() => {
  return Number(route.params.groupId) || props.groupId || userStore.currentClanId
})

const activeTab = ref<'subscribe' | 'apply' | 'tree'>('subscribe')
const sseEnabled = ref(false)
let sseClient: EventSource | null = null

const data = reactive<NoticeResponse>({
  priority: 0,
  clan_priority: 0,
  has_account: false,
  user_id: 0,
  subscribe: [],
  apply: [],
  tree: []
})

const addDialog = reactive<{
  visible: boolean
  form: NoticeCacheModel
}>({
  visible: false,
  form: {
    group_id: 0,
    notice_type: 0,
    user_id: 0,
    boss: 1,
    lap: 0,
    text: ''
  }
})

const activeList = computed<NoticeCacheModel[]>(() => {
  const list = data[activeTab.value] || []
  return [...list].sort((a, b) => (b.time || 0) - (a.time || 0))
})

const emptyText = computed(() => {
  const map = { subscribe: '暂无预约', apply: '暂无申请', tree: '树上空空如也~' }
  return map[activeTab.value]
})

function typeLabel(t: number) {
  const map: Record<number, string> = {
    0: '预约',
    1: '挂树',
    2: '申请',
    5: 'SL'
  }
  return map[t] || '未知'
}

function timelineColor(t: number): 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  switch (t) {
    case 0: return 'primary'  // 预约
    case 2: return 'success'  // 申请
    case 1: return 'danger'   // 挂树
    case 5: return 'warning'  // SL
    default: return 'info'
  }
}

function getUserDisplayName(userId: number) {
  // 如果当前用户就是自己，显示"我"
  if (userId === userStore.userId) {
    return userStore.userName || '我'
  }
  return `玩家 ${userId}`
}

function formatFullTime(t: number) {
  if (!t) return '时间未知'
  return dayjs(t * 1000).format('YYYY-MM-DD HH:mm:ss')
}

async function loadNotice(forceMsg = false) {
  if (!groupId.value) return
  try {
    const res = await getNoticeList(groupId.value)
    Object.assign(data, res)
    if (forceMsg) ElMessage.success('已刷新')
  } catch (e) {
    /* 拦截器已处理 */
  }
}

function toggleSSE() {
  if (sseEnabled.value) stopSSE()
  else startSSE()
}
function startSSE() {
  stopSSE()
  if (!groupId.value) return
  const url = `${API_BASE}/${groupId.value}/renew_notice`
  sseClient = createSSEConnection(url, {
    onMessage: (newData: NoticeResponse) => Object.assign(data, newData),
    onError: () => {
      sseEnabled.value = false
      ElMessage.warning('实时连接断开，已自动关闭')
    }
  })
  sseEnabled.value = true
}
function stopSSE() {
  if (sseClient) {
    sseClient.close()
    sseClient = null
  }
  sseEnabled.value = false
}

// 通知权限（后端按群算，见 basedata.GroupPriority）：
//   - 预约 / 申请 / 挂树 / SL 都是「自己的事」，0 级就能做，但必须先绑定游戏账号
//   - 取消自己的通知不限等级；取消别人的通知属于「管理他人的通知」，需要本群 2 级
// 注意这里用页面响应里的 clan_priority，而不是全局的 userStore.priority ——
// 同一个人在 A 群可能是群管、在 B 群只是普通成员。
const clanPriority = computed(() => Number(data.clan_priority) || 0)
const myId = computed(() => Number(userStore.userId))
// 添加通知：0 级即可，唯一门槛是有绑定游戏账号。
// 账号是全局的（一个 QQ 一个号，绑一次所有群通用），所以 data.has_account
// 和 userStore.hasAccount 必然一致 —— 这里仍读接口返回的那个，
// 只是为了沿用「以页面响应为准」这条老路径。
const canAddNotice = computed(() => data.has_account === true)
// 管理他人的通知：本群 2 级（群主 / 群管自动获得）
const canManageOthers = computed(() => clanPriority.value >= 2)

/** 这条通知是不是自己发的 */
function isMineNotice(item: NoticeCacheModel) {
  return Number(item.user_id) === myId.value
}

/** 能不能取消这条通知：自己的随时可以，别人的要 2 级 */
function canCancel(item: NoticeCacheModel) {
  return isMineNotice(item) || canManageOthers.value
}

// 「添加通知」按钮置灰时的悬停提示（0 级也能加，唯一门槛是绑定了游戏账号）
const noticeTip = computed(() =>
  data.has_account === true
    ? ''
    : '还没有绑定游戏账号，请在仪表盘上绑定，或在QQ私聊机器人发送【绑定账号帮助】',
)

function openAddDialog() {
  if (!canAddNotice.value) {
    ElMessage.warning(noticeTip.value)
    return
  }
  addDialog.form = {
    group_id: Number(groupId.value),
    notice_type: activeTab.value === 'subscribe' ? 0 : activeTab.value === 'apply' ? 2 : 1,
    user_id: userStore.userId,
    boss: 1,
    lap: 0,
    text: ''
  }
  addDialog.visible = true
}

async function onSubmitAdd() {
  try {
    await setNotice({ ...addDialog.form, group_id: Number(addDialog.form.group_id) })
    ElMessage.success('添加成功，QQ 群内会同步公告')
    addDialog.visible = false
    await nextTick()
    loadNotice()
  } catch (e) {
    /* 拦截器已提示 */
  }
}

async function onCancel(item: NoticeCacheModel) {
  try {
    await deleteNotice({
      ...item,
      group_id: Number(groupId.value),
      user_id: item.user_id
    })
    ElMessage.success('已取消')
    loadNotice()
  } catch (e) {
    /* 拦截器 */
  }
}

// 菜单跳转进来的 URL 不带 groupId 参数，replace 后 groupId 值不变、watch 不会再次触发，
// 因此这里不能 return，必须始终加载数据
watch(
  groupId,
  (id) => {
    if (!id) return
    const rg = Number(route.params.groupId)
    if (rg !== id) {
      router.replace(`/notice/${id}`)
    }
    loadNotice()
    setTimeout(startSSE, 1200)
  },
  { immediate: true }
)

onBeforeUnmount(() => stopSSE())
</script>

<style scoped>
.notice-page {
  display: flex;
  flex-direction: column;
}
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.tabs-group :deep(.el-radio-button__inner) {
  padding: 8px 16px;
}
.list-card {
  min-height: 360px;
}
.mt-16 { margin-top: 16px; }
.empty-state {
  padding: 20px 0;
}
.notice-item {
  flex: 1;
}
.notice-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}
.notice-user {
  display: flex;
  align-items: center;
  gap: 10px;
}
.uinfo .uname {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.uinfo .uid-text {
  color: #9ca3af;
  font-size: 12px;
  font-weight: 400;
}
.u-boss {
  margin-top: 4px;
}
.notice-text {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fffbeb;
  color: #92400e;
  border-radius: 6px;
  font-size: 13px;
  border: 1px dashed #fde68a;
}
</style>
