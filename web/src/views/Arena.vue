<template>
  <div class="arena-page">
    <el-empty v-if="!groupId" description="请先从上方选择一个公会" />

    <template v-else>
      <!-- 状态 + 提醒开关 -->
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
          title="本群没有正在运行的竞技场监控"
          description="排行榜 / 查防守 / 查 ID 需要借用监控已登录的账号去打游戏接口。请先在 QQ 群里发送【竞技场监控】或【#竞技场监控】，再回来查询。"
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
          <el-radio-group v-model="grand">
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
            v-else
            v-model="rank"
            :min="1"
            :max="500"
            controls-position="right"
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
                : '输入排名（1~500），查该名次玩家的信息。'
          }}
        </div>
      </div>

      <!-- 结果 -->
      <div class="result-card kanna-card mt-16">
        <div v-if="loading" class="loading-state">
          <el-icon class="is-loading" :size="26"><Loading /></el-icon>
          <span>正在查询，请稍候…</span>
        </div>

        <el-alert
          v-else-if="imgResult && !imgResult.ok"
          :title="imgResult.message"
          type="info"
          show-icon
          :closable="false"
        />
        <el-alert
          v-else-if="textResult && !textResult.ok"
          :title="textResult.message"
          type="info"
          show-icon
          :closable="false"
        />

        <div v-else-if="imgResult && imgResult.image" class="img-wrap">
          <img :src="imgResult.image" class="result-img" alt="查询结果" />
        </div>

        <pre v-else-if="textResult && textResult.text" class="text-result">{{
          textResult.text
        }}</pre>

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
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getArenaCache,
  getArenaDefence,
  getArenaPlayer,
  getArenaRank,
  getArenaStatus,
  setArenaSetting,
} from '@/api'
import type { ArenaStatus, GrandCacheRow, ImageResult, TextResult } from '@/types'
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
const imgResult = ref<ImageResult | null>(null)
const textResult = ref<TextResult | null>(null)

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

async function doQuery() {
  if (!groupId.value || !status.value.running) return
  loading.value = true
  imgResult.value = null
  textResult.value = null
  try {
    if (queryType.value === 'rank') {
      imgResult.value = await getArenaRank(groupId.value, page.value, grand.value)
    } else if (queryType.value === 'defence') {
      imgResult.value = await getArenaDefence(
        groupId.value,
        rank.value,
        grand.value,
      )
    } else {
      textResult.value = await getArenaPlayer(
        groupId.value,
        rank.value,
        grand.value,
      )
    }
  } catch (e) {
    /* 拦截器统一提示 */
  } finally {
    loading.value = false
  }
}

function fmtTime(ts: number) {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

// 切换查询类型时清空上一次的结果
watch(queryType, () => {
  imgResult.value = null
  textResult.value = null
})

watch(groupId, () => {
  imgResult.value = null
  textResult.value = null
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
.img-wrap {
  overflow: auto;
  max-height: 72vh;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.02);
}
.result-img {
  display: block;
  max-width: 100%;
  height: auto;
}
.text-result {
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.03);
  font-size: 13px;
  line-height: 1.8;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-all;
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
  .img-wrap {
    max-height: 60vh;
  }
}
</style>
