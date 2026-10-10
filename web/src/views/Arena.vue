<template>
  <div class="arena-page">
    <el-empty v-if="!groupId" description="请先从上方选择一个公会" />

    <template v-else>
      <!-- 状态 + 监控开关 + 提醒开关 -->
      <div class="status-card kanna-card">
        <div class="card-head">
          <div class="head-left">
            <el-icon :size="18"><Trophy /></el-icon>
            <span>竞技场中心</span>
          </div>
          <div class="head-right">
            <el-tag
              :type="status.running ? 'success' : 'info'"
              size="small"
              effect="light"
            >
              {{ status.running ? '监控运行中' : '监控未运行' }}
            </el-tag>
            <!-- 个人监控开关：等价于群里发【竞技场监控】/【取消竞技场监控】 -->
            <el-button
              v-if="!status.running"
              type="primary"
              size="small"
              :loading="monitorLoading"
              @click="toggleMonitor"
            >
              <el-icon><VideoPlay /></el-icon>开启监控
            </el-button>
            <el-button
              v-else-if="status.is_monitor"
              type="danger"
              size="small"
              :loading="monitorLoading"
              @click="toggleMonitor"
            >
              <el-icon><VideoPause /></el-icon>取消监控
            </el-button>
            <el-button size="small" @click="loadStatus">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
          </div>
        </div>

        <div v-if="status.running" class="status-grid">
          <div class="stat">
            <span class="k">竞技场</span>
            <span class="v">
              {{ status.jjc_rank }}
              <em>({{ status.jjc_group }} 场)</em>
            </span>
          </div>
          <div class="stat">
            <span class="k">公主竞技场</span>
            <span class="v">
              {{ status.grand_rank }}
              <em>({{ status.grand_group }} 场)</em>
            </span>
          </div>
          <div class="stat">
            <span class="k">监控编号</span>
            <span class="v">HN100{{ status.loop_num }}</span>
          </div>
          <div class="stat">
            <span class="k">监控人</span>
            <span class="v">
              {{ status.monitor_user_id }}
              <em v-if="status.is_monitor">（你）</em>
            </span>
          </div>
        </div>

        <el-alert
          v-else
          type="info"
          show-icon
          :closable="false"
          title="当前没有正在运行的竞技场监控"
          description="点右上角【开启监控】即可（等价于群里发【竞技场监控】）。排行榜 / 查防守 / 查 ID 都要借用这个已登录的账号去打游戏接口。"
        />

        <div class="switch-row">
          <div class="switch-item">
            <span>竞技场提醒</span>
            <el-switch v-model="status.jjc_notice" @change="saveSetting" />
          </div>
          <div class="switch-item">
            <span>公主竞技场提醒</span>
            <el-switch v-model="status.grand_notice" @change="saveSetting" />
          </div>
        </div>
      </div>

      <!-- 查询 -->
      <div class="query-card kanna-card mt-16">
        <div class="query-groups">
          <el-radio-group v-model="queryType">
            <el-radio-button value="rank">排行榜</el-radio-button>
            <el-radio-button value="defence">查防守</el-radio-button>
            <el-radio-button value="player">查 ID</el-radio-button>
          </el-radio-group>
          <el-radio-group v-if="queryType !== 'player'" v-model="grand">
            <el-radio-button :value="false">竞技场</el-radio-button>
            <el-radio-button :value="true">公主竞技场</el-radio-button>
          </el-radio-group>
        </div>

        <div class="query-row">
          <el-input-number
            v-if="queryType === 'rank'"
            v-model="page"
            :min="1"
            :max="5"
            controls-position="right"
          />
          <el-input-number
            v-else-if="queryType === 'defence'"
            v-model="rank"
            :min="1"
            :max="500"
            controls-position="right"
          />
          <el-input
            v-else
            v-model="playerId"
            class="id-input"
            placeholder="输入玩家ID"
            clearable
            @keyup.enter="doQuery"
          />
          <el-button
            type="primary"
            :loading="loading"
            :disabled="!status.running"
            @click="doQuery"
          >
            <el-icon v-if="!loading"><Search /></el-icon>查询
          </el-button>
        </div>

        <div class="tip-text">
          {{
            queryType === 'rank'
              ? '排行榜每页 10 名，可选 1~5 页。'
              : queryType === 'defence'
                ? '输入排名（1~500），查该名次的防守阵容与作业。'
                : '输入玩家游戏 ID（纯数字），直接查该玩家资料（等级 / 战力 / 竞技场 / 关卡 / 深域进度）。'
          }}
        </div>
      </div>

      <!-- 结果 -->
      <div class="result-card kanna-card mt-16">
        <div v-if="loading" class="loading-state">
          <el-icon class="is-loading" :size="26"><Loading /></el-icon>
          <span>正在查询，请稍候…</span>
        </div>

        <!-- 排行榜（网页绘制，还原原图风格） -->
        <template v-else-if="queryType === 'rank' && rankResult">
          <el-alert
            v-if="!rankResult.ok"
            :title="rankResult.message"
            type="info"
            show-icon
            :closable="false"
          />
          <div v-else class="rank-list">
            <div class="rank-title">
              {{ rankResult.grand ? '公主' : '' }}竞技场 {{ rankResult.group }} 场 · 第
              {{ rankResult.page }} 页
            </div>
            <div class="rank-row" v-for="row in rankResult.rows" :key="row.rank">
              <img
                class="rk-avatar rk-clickable"
                :src="avatarUrl(row.unit_id)"
                alt=""
                title="点击查看防守阵容"
                @click="openDefence(row)"
              />
              <div class="rk-body">
                <div class="rk-top">
                  <span class="rk-badge"><i></i>{{ row.rank }}位</span>
                  <span
                    class="rk-name rk-clickable"
                    title="点击查看防守阵容"
                    @click="openDefence(row)"
                    >{{ row.name }}</span
                  >
                </div>
                <div class="rk-field">
                  <span class="rk-pill">玩家ID</span>
                  <span class="rk-line"></span>
                  <span class="rk-value">{{ row.viewer_id }}</span>
                </div>
                <div class="rk-field">
                  <span class="rk-pill">胜利次数</span>
                  <span class="rk-line"></span>
                  <span class="rk-value">{{
                    row.win_num === null || row.win_num === undefined
                      ? '不适用'
                      : row.win_num
                  }}</span>
                </div>
              </div>
            </div>
            <el-empty v-if="!rankResult.rows.length" description="没有查到排行榜数据" />
          </div>
        </template>

        <!-- 查防守（网页绘制） -->
        <template v-else-if="queryType === 'defence' && defenceResult">
          <el-alert
            v-if="!defenceResult.ok"
            :title="defenceResult.message"
            type="info"
            show-icon
            :closable="false"
          />
          <ArenaDefencePanel v-else :result="defenceResult" :group-id="groupId" />
        </template>

        <!-- 查 ID：按游戏 ID 查玩家资料（网页绘制） -->
        <template v-else-if="queryType === 'player' && profileResult">
          <el-alert
            v-if="!profileResult.ok"
            :title="profileResult.message"
            type="info"
            show-icon
            :closable="false"
          />
          <div v-else class="pf-card">
            <div class="pf-head">
              <img
                class="pf-avatar"
                :src="avatarUrl(profileResult.unit_id)"
                alt=""
              />
              <div class="pf-main">
                <div class="pf-name">{{ profileResult.name || '（无昵称）' }}</div>
                <div class="pf-comment">
                  {{ profileResult.comment || '（无签名）' }}
                </div>
                <div class="pf-clan" v-if="profileResult.clan_name">
                  公会：{{ profileResult.clan_name }}
                </div>
              </div>
              <div class="pf-id">ID {{ profileResult.viewer_id }}</div>
            </div>

            <div class="pf-grid">
              <div class="pf-item">
                <span class="k">团队等级</span>
                <span class="v">{{ profileResult.team_level }}</span>
              </div>
              <div class="pf-item">
                <span class="k">总战力</span>
                <span class="v">{{ profileResult.total_power.toLocaleString() }}</span>
              </div>
              <div class="pf-item">
                <span class="k">持有角色数</span>
                <span class="v">{{ profileResult.unit_num }}</span>
              </div>
              <div class="pf-item">
                <span class="k">好友数</span>
                <span class="v">{{ profileResult.friend_num }}</span>
              </div>
              <div class="pf-item">
                <span class="k">竞技场排名</span>
                <span class="v">{{ profileResult.arena_rank }}</span>
              </div>
              <div class="pf-item">
                <span class="k">竞技场分组</span>
                <span class="v">{{ profileResult.arena_group }}</span>
              </div>
              <div class="pf-item">
                <span class="k">公主竞技场排名</span>
                <span class="v">{{ profileResult.grand_arena_rank }}</span>
              </div>
              <div class="pf-item">
                <span class="k">公主竞技场分组</span>
                <span class="v">{{ profileResult.grand_arena_group }}</span>
              </div>
              <div class="pf-item">
                <span class="k">已解锁剧情数</span>
                <span class="v">{{ profileResult.open_story_num }}</span>
              </div>
              <div class="pf-item">
                <span class="k">已通关塔层数</span>
                <span class="v">{{ profileResult.tower_cleared_floor_num }}</span>
              </div>
              <div class="pf-item">
                <span class="k">已通关塔额外关卡数</span>
                <span class="v">{{ profileResult.tower_cleared_ex_quest_count }}</span>
              </div>
              <div class="pf-item">
                <span class="k">上次登录时间</span>
                <span class="v">{{ fmtTime(profileResult.last_login_time) }}</span>
              </div>
            </div>

            <div class="pf-sub">关卡进度</div>
            <div class="pf-grid">
              <div class="pf-item">
                <span class="k">普通关卡进度</span>
                <span class="v">{{ profileResult.quest_normal }}</span>
              </div>
              <div class="pf-item">
                <span class="k">困难关卡进度</span>
                <span class="v">{{ profileResult.quest_hard }}</span>
              </div>
              <div class="pf-item">
                <span class="k">Very Hard关卡进度</span>
                <span class="v">{{ profileResult.quest_very_hard }}</span>
              </div>
              <div class="pf-item">
                <span class="k">支线关卡进度</span>
                <span class="v">{{ profileResult.quest_byway }}</span>
              </div>
            </div>

            <div class="pf-sub">深域进度</div>
            <div class="pf-grid">
              <div class="pf-item" v-for="(t, i) in profileResult.talent" :key="i">
                <span class="k">{{
                  ['深域火属性进度', '深域水属性进度', '深域风属性进度', '深域光属性进度', '深域暗属性进度'][i]
                }}</span>
                <span class="v">{{ fmtTalent(t) }}</span>
              </div>
            </div>
          </div>
        </template>

        <el-empty v-else description="还没有查询结果" />
      </div>

      <!-- 公主竞技场防守缓存 -->
      <div class="cache-card kanna-card mt-16">
        <div class="card-head">
          <div class="head-left">
            <el-icon :size="18"><Files /></el-icon>
            <span>防守缓存</span>
            <span class="sub">（监控过程中记录的对手防守，纯本地缓存）</span>
          </div>
          <el-button size="small" :loading="cacheLoading" @click="loadCache">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>

        <el-table :data="cacheRows" size="small" v-loading="cacheLoading">
          <el-table-column label="时间" width="120">
            <template #default="{ row }">{{ fmtTime(row.vs_time) }}</template>
          </el-table-column>
          <el-table-column prop="pcrid" label="对手 ID" width="120" />
          <el-table-column label="位置" width="80">
            <template #default="{ row }">第 {{ row.row }} 队</template>
          </el-table-column>
          <el-table-column label="防守阵容">
            <template #default="{ row }">{{ row.names.join(' / ') }}</template>
          </el-table-column>
          <template #empty>还没有缓存记录</template>
        </el-table>
      </div>

      <!-- 点排行榜里的头像 / 名字 → 弹窗看这个人的防守阵容与作业 -->
      <el-dialog
        v-model="defenceDialogVisible"
        :title="defenceDialogTitle"
        width="min(560px, 92vw)"
        top="6vh"
      >
        <div v-if="defenceDialogLoading" class="loading-state">
          <el-icon class="is-loading" :size="24"><Loading /></el-icon>
          <span>正在查询，请稍候…</span>
        </div>
        <el-alert
          v-else-if="defenceDialogResult && !defenceDialogResult.ok"
          :title="defenceDialogResult.message"
          type="info"
          show-icon
          :closable="false"
        />
        <ArenaDefencePanel
          v-else-if="defenceDialogResult"
          :result="defenceDialogResult"
          :group-id="groupId"
        />
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getArenaCache,
  getArenaDefence,
  getArenaProfile,
  getArenaRank,
  getArenaStatus,
  setArenaSetting,
  switchArenaMonitor,
} from '@/api'
import type {
  ArenaDefenceResult,
  ArenaProfileResult,
  ArenaRankResult,
  ArenaRankRow,
  ArenaStatus,
  GrandCacheRow,
} from '@/types'
import { API_BASE } from '@/utils/request'
import ArenaDefencePanel from '@/components/ArenaDefencePanel.vue'
import { useUserStore } from '@/store/user'

const props = defineProps<{ groupId?: number }>()
const route = useRoute()
const userStore = useUserStore()

const groupId = computed<number>(
  () => Number(route.params.groupId) || props.groupId || userStore.currentClanId,
)

const status = ref<ArenaStatus>({
  running: false,
  jjc_notice: true,
  grand_notice: true,
  jjc_rank: 0,
  jjc_group: 0,
  grand_rank: 0,
  grand_group: 0,
  loop_num: 0,
  monitor_user_id: 0,
  is_monitor: false,
})

const queryType = ref<'rank' | 'defence' | 'player'>('rank')
const grand = ref(false)
const page = ref(1)
const rank = ref(1)
const loading = ref(false)
const monitorLoading = ref(false)
const rankResult = ref<ArenaRankResult | null>(null)
const defenceResult = ref<ArenaDefenceResult | null>(null)
const playerId = ref('')
const profileResult = ref<ArenaProfileResult | null>(null)

// 点排行榜行 → 弹窗看该玩家的防守阵容
const defenceDialogVisible = ref(false)
const defenceDialogLoading = ref(false)
const defenceDialogTitle = ref('防守阵容')
const defenceDialogResult = ref<ArenaDefenceResult | null>(null)

const cacheRows = ref<GrandCacheRow[]>([])
const cacheLoading = ref(false)

async function loadStatus() {
  if (!groupId.value) return
  try {
    status.value = await getArenaStatus(groupId.value)
  } catch (e) {
    /* 拦截器统一提示 */
  }
}

/** 头像档位：与后端 `_avatar_star` 一致（1 / 3 / 6 三档） */
function starOf(rarity: number) {
  if (rarity >= 6) return 6
  if (rarity >= 3) return 3
  if (rarity >= 1) return 1
  return 3
}

/** 角色头像地址（复用 BOX 的头像接口）；传 rarity / battle_rarity 时底部叠星级 */
function avatarUrl(unitId: number, rarity = 0, battleRarity = 0) {
  const params = new URLSearchParams({ star: String(starOf(rarity)) })
  if (rarity > 0) params.set('rarity', String(rarity))
  if (battleRarity > 0) params.set('battle_rarity', String(battleRarity))
  return `${API_BASE}/${groupId.value}/box/avatar/${unitId}?${params.toString()}`
}

async function loadCache() {
  if (!groupId.value) return
  cacheLoading.value = true
  try {
    cacheRows.value = await getArenaCache(groupId.value)
  } catch (e) {
    /* 拦截器统一提示 */
  } finally {
    cacheLoading.value = false
  }
}

async function saveSetting() {
  if (!groupId.value) return
  try {
    await setArenaSetting(groupId.value, {
      jjc_notice: status.value.jjc_notice,
      grand_notice: status.value.grand_notice,
    })
    ElMessage.success('设置成功')
  } catch (e) {
    // 失败时把开关状态拉回真实值，避免界面显示和实际不一致
    await loadStatus()
  }
}

/** 开启 / 取消个人监控（等价群里【竞技场监控】/【取消竞技场监控】） */
async function toggleMonitor() {
  if (!groupId.value) return

  if (!status.value.running) {
    try {
      await ElMessageBox.confirm(
        '开启监控会用你绑定的游戏账号登录游戏（若你正在游戏会被顶下线），并持续监视排名变化。确定开启吗？',
        '开启个人竞技场监控',
        { type: 'warning', confirmButtonText: '开启', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
    monitorLoading.value = true
    try {
      const res = await switchArenaMonitor(groupId.value, { action: 'on' })
      ElMessage.success(res.message || '监控启动中')
      pollStatus()
    } catch {
      /* 拦截器统一提示 */
    } finally {
      monitorLoading.value = false
    }
    return
  }

  monitorLoading.value = true
  try {
    await switchArenaMonitor(groupId.value, { action: 'off' })
    ElMessage.success('已取消竞技场监控')
    await loadStatus()
  } catch {
    /* 拦截器统一提示 */
  } finally {
    monitorLoading.value = false
  }
}

/** 开启后循环刷新几次状态，等监控循环真正跑起来 */
function pollStatus(times = 8) {
  let n = 0
  const tick = async () => {
    n += 1
    await loadStatus()
    if (!status.value.running && n < times) setTimeout(tick, 2500)
  }
  setTimeout(tick, 1500)
}

async function doQuery() {
  if (!groupId.value || !status.value.running) return
  if (queryType.value === 'player') {
    const id = playerId.value.trim()
    if (!/^\d+$/.test(id) || Number(id) <= 0) {
      ElMessage.warning('请输入正确的玩家 ID（纯数字）')
      return
    }
  }
  loading.value = true
  rankResult.value = null
  defenceResult.value = null
  profileResult.value = null
  try {
    if (queryType.value === 'rank') {
      rankResult.value = await getArenaRank(groupId.value, page.value, grand.value)
    } else if (queryType.value === 'defence') {
      defenceResult.value = await getArenaDefence(
        groupId.value,
        rank.value,
        grand.value,
      )
    } else {
      profileResult.value = await getArenaProfile(
        groupId.value,
        playerId.value.trim(),
      )
    }
  } catch (e) {
    /* 拦截器统一提示 */
  } finally {
    loading.value = false
  }
}

/** 点排行榜里的头像 / 名字：按该名次查这个人的防守阵容（复用现有的查防守接口） */
async function openDefence(row: ArenaRankRow) {
  if (!groupId.value) return
  defenceDialogTitle.value = `${row.name}（${row.rank}位）的防守阵容`
  defenceDialogResult.value = null
  defenceDialogVisible.value = true
  defenceDialogLoading.value = true
  try {
    defenceDialogResult.value = await getArenaDefence(
      groupId.value,
      row.rank,
      grand.value,
    )
  } catch (e) {
    /* 拦截器统一提示 */
  } finally {
    defenceDialogLoading.value = false
  }
}

/** 时间戳（秒；个别接口给的是毫秒会自动换算）→ M-D HH:mm */
function fmtTime(ts: number) {
  if (!ts) return '-'
  const seconds = ts > 1e12 ? Math.floor(ts / 1000) : ts
  const d = new Date(seconds * 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** 深域进度：clear_count → 「大关-小关」，0 显示 0-0（与 autopcr 一致） */
function fmtTalent(value: number) {
  if (!value || value <= 0) return '0-0'
  return `${Math.floor((value - 1) / 10) + 1}-${((value - 1) % 10) + 1}`
}

// 切换查询类型时清空上一次的结果
watch(queryType, () => {
  rankResult.value = null
  defenceResult.value = null
  profileResult.value = null
})

// 切换竞技场 / 公主竞技场同样清空，避免两种场次的结果串台
watch(grand, () => {
  rankResult.value = null
  defenceResult.value = null
  profileResult.value = null
})

watch(groupId, () => {
  rankResult.value = null
  defenceResult.value = null
  profileResult.value = null
  cacheRows.value = []
  loadStatus()
  loadCache()
})

onMounted(() => {
  loadStatus()
  loadCache()
})
</script>

<style scoped>
.arena-page {
  display: flex;
  flex-direction: column;
}
.mt-16 {
  margin-top: 16px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #831843;
}
.head-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.sub {
  font-size: 12px;
  font-weight: 400;
  color: #9ca3af;
}
.status-card,
.query-card,
.result-card,
.cache-card {
  padding: 16px 18px;
}
.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(236, 72, 153, 0.05);
}
.stat .k {
  font-size: 12px;
  color: #9ca3af;
}
.stat .v {
  font-size: 16px;
  font-weight: 600;
  color: #374151;
}
.stat .v em {
  font-size: 12px;
  font-weight: 400;
  font-style: normal;
  color: #9ca3af;
}
.switch-row {
  display: flex;
  gap: 28px;
  flex-wrap: wrap;
  padding-top: 12px;
  border-top: 1px dashed rgba(236, 72, 153, 0.18);
}
.switch-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #4b5563;
}
.query-groups {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.query-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
}
.tip-text {
  margin-top: 10px;
  color: #9ca3af;
  font-size: 12px;
}
.result-card {
  min-height: 200px;
}
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #9ca3af;
  padding: 60px 0;
}
.id-input {
  max-width: 280px;
}

/* ================= 查 ID：玩家资料卡（网页绘制） ================= */
.pf-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  /* 与排行榜结果同宽（手机端窄条），左对齐 */
  width: 100%;
  max-width: 560px;
}
.pf-head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 12px;
  border-bottom: 1px dashed rgba(120, 150, 200, 0.3);
}
.pf-avatar {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  object-fit: cover;
  flex: none;
  background: #cfd5e6;
}
.pf-main {
  flex: 1;
  min-width: 0;
}
.pf-name {
  font-size: 17px;
  font-weight: 700;
  color: #831843;
}
.pf-comment {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pf-clan {
  margin-top: 4px;
  font-size: 12px;
  color: #9ca3af;
}
.pf-id {
  flex: none;
  font-size: 13px;
  color: #9ca3af;
}
.pf-sub {
  font-size: 13px;
  font-weight: 600;
  color: #4a515a;
  padding-top: 6px;
  border-top: 1px dashed rgba(120, 150, 200, 0.3);
}
.pf-grid {
  display: grid;
  /* 一行只放 2 个词条，窄条下更整齐 */
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
}
.pf-item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(74, 144, 226, 0.06);
}
.pf-item .k {
  font-size: 12px;
  color: #9ca3af;
  min-width: 0;
}
.pf-item .v {
  flex: none;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  text-align: right;
  word-break: break-all;
}
.pf-item .v em {
  font-size: 12px;
  font-weight: 400;
  font-style: normal;
  color: #9ca3af;
}

/* ================= 排行榜（还原 player.png 风格） ================= */
.rank-list {
  display: flex;
  flex-direction: column;
  /* 按手机端的窄条宽度显示；PC 上左对齐，不要居中（居中的窄条在宽卡片里很空） */
  width: 100%;
  max-width: 560px;
}
.rank-title {
  font-size: 13px;
  color: #9ca3af;
  margin-bottom: 8px;
}
.rank-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 4px;
  border-bottom: 1px solid rgba(120, 150, 200, 0.18);
}
.rank-row:last-child {
  border-bottom: none;
}
.rk-avatar {
  width: 66px;
  height: 66px;
  border-radius: 8px;
  object-fit: cover;
  flex: none;
  background: #cfd5e6;
}
.rk-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rk-top {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.rk-badge {
  position: relative;
  flex: none;
  min-width: 62px;
  padding: 3px 12px;
  text-align: center;
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(180deg, #ef5350 0%, #c62828 100%);
  border-radius: 4px;
  box-shadow: 0 1px 2px rgba(198, 40, 40, 0.35);
  /* 两侧的黄金装饰角 */
  border-left: 4px solid #f0c14b;
  border-right: 4px solid #f0c14b;
}
.rk-name {
  font-size: 15px;
  font-weight: 700;
  color: #4a515a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rk-field {
  display: flex;
  align-items: center;
  gap: 10px;
}
.rk-pill {
  flex: none;
  min-width: 84px;
  padding: 2px 10px;
  text-align: center;
  font-size: 13px;
  color: #fff;
  background: #4a90e2;
  border-radius: 5px;
}
.rk-line {
  flex: 1;
  min-width: 20px;
  border-bottom: 2px dotted #8ab4f0;
  transform: translateY(-3px);
}
.rk-value {
  flex: none;
  font-size: 15px;
  font-weight: 600;
  color: #4a515a;
}

/* 头像 / 名字可点，点了看这个人的防守阵容 */
.rk-clickable {
  cursor: pointer;
}
.rk-name.rk-clickable:hover {
  color: #c62828;
  text-decoration: underline;
}
.rk-avatar.rk-clickable:hover {
  outline: 2px solid #4a90e2;
}

/* ================= 手机端（< 768px） ================= */
@media (max-width: 767px) {
  .status-card,
  .query-card,
  .result-card,
  .cache-card {
    padding: 12px;
  }
  .head-left {
    font-size: 15px;
  }
  .sub {
    display: none;
  }
  .query-row {
    flex-wrap: wrap;
  }
  .rk-avatar {
    width: 56px;
    height: 56px;
  }
  .rk-pill {
    min-width: 72px;
    font-size: 12px;
  }
}
</style>
