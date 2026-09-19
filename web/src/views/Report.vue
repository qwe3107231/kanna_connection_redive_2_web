<template>
  <div class="report-page">
    <el-empty v-if="!groupId" description="请先从上方选择一个公会" />

    <template v-else>
      <!-- 概览 -->
      <div class="section-title">
        <el-icon><User /></el-icon>
        <span>
          {{ data.name || '玩家' }}
          <small class="text-muted">· QQ {{ data.user_id }}</small>
        </span>
        <el-tag size="small" type="warning" effect="plain" class="ml-8" v-if="sseEnabled">
          <el-icon><Connection /></el-icon>实时同步
        </el-tag>
        <el-button size="small" class="ml-auto" @click="toggleSSE">
          {{ sseEnabled ? '关闭实时' : '开启实时' }}
        </el-button>
        <el-button size="small" @click="loadReport(true)">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>

      <!-- 「我的出刀」与「全员伤害排行」并排：两栏卡片锁成同一个固定高度。
           左边出刀变多时表体在卡片内部滚动（表头固定，和「出刀明细」一致），
           不再把整张卡片、连同右边图表一起撑长；右边图表撑满同高。 -->
      <el-row :gutter="16" class="mt-8">
        <el-col :xs="24" :md="8">
          <div class="kanna-card rank-card" style="border-top: 3px solid #ec4899">
            <div class="rank-card-head">
              <div class="small-title">我的出刀</div>
              <div class="me-count">共 {{ data.me.length }} 条</div>
            </div>
            <div class="rank-card-body">
              <el-table
                :data="data.me"
                size="small"
                stripe
                height="100%"
                empty-text="暂无出刀"
              >
                <el-table-column label="时间" width="110">
                  <template #default="{ row }">{{ formatTime(row.date) }}</template>
                </el-table-column>
                <el-table-column label="BOSS">
                  <template #default="{ row }">
                    {{ row.lap }}周目{{ row.boss }}王
                  </template>
                </el-table-column>
                <el-table-column label="伤害" width="90" align="right">
                  <template #default="{ row }">{{ formatNum(row.damage) }}</template>
                </el-table-column>
                <el-table-column label="类型" width="80">
                  <template #default="{ row }">
                    <el-tag size="small" :type="daoTagType(row.type)" effect="light">
                      {{ row.type }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="刀数" width="60" align="right">
                  <template #default="{ row }">{{ row.dao }}</template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-col>

        <el-col :xs="24" :md="16">
          <div class="kanna-card rank-card" style="border-top: 3px solid #3b82f6">
            <div class="rank-card-head flex justify-between items-center mb-16">
              <div class="small-title">全员伤害排行</div>
              <div class="chart-legend">
                <span class="dot pink"></span>伤害
                <span class="dot amber"></span>分数
              </div>
            </div>
            <div v-if="data.all.length" class="rank-chart">
              <v-chart :option="rankBarOption" autoresize />
            </div>
            <el-empty v-else description="暂无全员数据" :image-size="80" />
          </div>
        </el-col>
      </el-row>

      <!-- 全员汇总表 -->
      <div class="kanna-card mt-16">
        <div class="flex justify-between items-center mb-16">
          <div class="small-title">全员汇总（{{ data.all.length }} 人）</div>
          <div class="total-box">
            <span class="total-item">总伤害：<b>{{ formatNum(totalDamage) }}</b></span>
            <span class="total-item">总分数：<b>{{ formatNum(totalScore) }}</b></span>
          </div>
        </div>
        <el-table :data="data.all" stripe size="default">
          <el-table-column type="index" label="排名" width="60" align="center" />
          <el-table-column prop="name" label="玩家" min-width="110" />
          <el-table-column label="伤害" min-width="140" sortable :sort-by="(r:any)=>r.damage">
            <template #default="{ row }">
              <div class="num-cell">
                <span class="num-val">{{ formatNum(row.damage) }}</span>
                <el-progress
                  :percentage="damageRate(row.damage)"
                  :show-text="false"
                  :stroke-width="4"
                  color="#ec4899"
                  style="width: 80px; margin-left: 8px"
                />
                <el-tag size="small" effect="plain" type="warning" style="margin-left: 8px">
                  {{ row.damage_rate }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="分数" min-width="140" sortable :sort-by="(r:any)=>r.score">
            <template #default="{ row }">
              <div class="num-cell">
                <span class="num-val">{{ formatNum(row.score) }}</span>
                <el-tag size="small" effect="plain" type="success">
                  {{ row.score_rate }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="累计刀数" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" type="primary" effect="dark">{{ row.dao }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 出刀明细表 -->
      <div class="kanna-card mt-16">
        <div class="flex justify-between items-center mb-16">
          <div class="small-title">出刀明细（{{ data.detail.length }} 条，按时间倒序）</div>
          <el-input
            v-model="keyword"
            placeholder="搜索玩家 / BOSS"
            clearable
            style="width: 220px"
            size="default"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
        <el-table :data="filteredDetail" stripe size="default" max-height="600">
          <el-table-column type="index" label="序号" width="60" align="center" />
          <el-table-column prop="name" label="玩家" width="110" />
          <el-table-column label="BOSS" width="110">
            <template #default="{ row }">
              <el-tag size="small">{{ row.lap }}周目{{ row.boss }}王</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="damage" label="伤害" width="110" align="right" sortable>
            <template #default="{ row }">{{ formatNum(row.damage) }}</template>
          </el-table-column>
          <el-table-column prop="score" label="分数" width="110" align="right" sortable>
            <template #default="{ row }">{{ formatNum(row.score) }}</template>
          </el-table-column>
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="daoTagType(row.type)" effect="light">
                {{ row.type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="170">
            <template #default="{ row }">{{ formatFullTime(row.date) }}</template>
          </el-table-column>
          <el-table-column
            v-if="Number(data.clan_priority) >= 1"
            label="操作"
            width="180"
            align="center"
            fixed="right"
          >
            <template #default="{ row }">
              <el-dropdown
                trigger="click"
                @command="(t: DaoFlagType) => onCorrect(row, t)"
              >
                <el-button size="small" type="primary" plain>
                  修正出刀类型<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="完整刀">完整刀（1.0）</el-dropdown-item>
                    <el-dropdown-item command="尾刀">尾刀（0.5）</el-dropdown-item>
                    <el-dropdown-item command="补偿刀">补偿刀（0.5）</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { useUserStore } from '@/store/user'
import { getReport, correctDao } from '@/api'
import { createSSEConnection } from '@/utils/sse'
import { API_BASE } from '@/utils/request'
import type { ReportResponse, DaoInfo, DaoFlagType } from '@/types'
import type { EChartsOption } from 'echarts'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps<{ groupId?: number }>()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const groupId = computed<number>(() => {
  return Number(route.params.groupId) || props.groupId || userStore.currentClanId
})

const keyword = ref('')
const sseEnabled = ref(false)
let sseClient: EventSource | null = null

const data = reactive<ReportResponse>({
  priority: 0,
  clan_priority: 0,
  user_id: 0,
  name: '',
  all: [],
  detail: [],
  me: []
})

const totalDamage = computed(() => data.all.reduce((s, r) => s + (r.damage || 0), 0))
const totalScore = computed(() => data.all.reduce((s, r) => s + (r.score || 0), 0))

const filteredDetail = computed(() => {
  if (!keyword.value) return data.detail
  const kw = keyword.value.toLowerCase()
  return data.detail.filter(
    (d) =>
      d.name?.toLowerCase().includes(kw) ||
      `${d.lap}周目${d.boss}王`.includes(kw) ||
      String(d.dao_id).includes(kw)
  )
})

const rankBarOption = computed<EChartsOption>(() => {
  const names = data.all.map((r) => r.name).slice(0, 30)
  const damage = data.all.map((r) => r.damage).slice(0, 30)
  const score = data.all.map((r) => r.score).slice(0, 30)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { show: false },
    // 边距要给「轴名 + 旋转的玩家名」留够位置：
    //   top 太小 -> y 轴名「伤害」被切掉（轴名在轴顶端再往上 15px）
    //   bottom 太小 -> 底部旋转 40° 的玩家名被切掉
    // 图表撑满卡片后这两处尤其明显，所以按最大字号留足。
    grid: { left: 64, right: 40, top: 48, bottom: 96 },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { rotate: names.length > 10 ? 40 : 0, fontSize: 11 }
    },
    yAxis: [
      {
        type: 'value',
        name: '伤害',
        axisLabel: {
          formatter: (v: number) => (v >= 1e8 ? (v / 1e8).toFixed(1) + '亿' : (v / 1e4).toFixed(0) + 'w')
        }
      }
    ],
    series: [
      {
        name: '伤害',
        type: 'bar',
        data: damage,
        itemStyle: {
          color: '#ec4899',
          borderRadius: [4, 4, 0, 0]
        },
        emphasis: { itemStyle: { color: '#db2777' } }
      },
      {
        name: '分数',
        type: 'bar',
        data: score,
        itemStyle: {
          color: '#f59e0b',
          borderRadius: [4, 4, 0, 0]
        },
        emphasis: { itemStyle: { color: '#d97706' } }
      }
    ]
  }
})

function formatNum(n: number) {
  if (n == null) return '0'
  return Number(n).toLocaleString()
}
function formatTime(t: number) {
  if (!t) return '-'
  return dayjs(t * 1000).format('MM-DD HH:mm')
}
function formatFullTime(t: number) {
  if (!t) return '-'
  return dayjs(t * 1000).format('YYYY-MM-DD HH:mm:ss')
}
function daoTagType(t: string): '' | 'success' | 'warning' | 'info' | 'danger' {
  if (t.includes('完整')) return 'success'
  if (t.includes('尾刀')) return 'warning'
  if (t.includes('补偿')) return 'info'
  return ''
}
function damageRate(d: number) {
  if (!totalDamage.value) return 0
  return Math.max(0, Math.min(100, (d / totalDamage.value) * 100))
}

async function loadReport(forceMsg = false) {
  if (!groupId.value) return
  try {
    const res = await getReport(groupId.value)
    Object.assign(data, res)
    if (forceMsg) ElMessage.success('已刷新')
  } catch (e) {
    /* 拦截器 */
  }
}

async function onCorrect(row: DaoInfo, type: DaoFlagType) {
  try {
    await ElMessageBox.confirm(
      `确定将 ${row.name} 的出刀记录「${row.lap}周目${row.boss}王」修正为「${type}」吗？`,
      '修正出刀',
      {
        confirmButtonText: '确定修正',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await correctDao({
      type,
      dao_id: row.dao_id,
      group_id: Number(groupId.value)
    })
    ElMessage.success('修正成功')
    await nextTick()
    loadReport()
  } catch (e: any) {
    if (e !== 'cancel') {
      /* 拦截器已提示 */
    }
  }
}

function toggleSSE() {
  if (sseEnabled.value) stopSSE()
  else startSSE()
}

function startSSE() {
  stopSSE()
  if (!groupId.value) return
  const url = `${API_BASE}/${groupId.value}/renew_report`
  sseClient = createSSEConnection(url, {
    onMessage: (newData: ReportResponse) => Object.assign(data, newData),
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

// 菜单跳转进来的 URL 不带 groupId 参数，replace 后 groupId 值不变、watch 不会再次触发，
// 因此这里不能 return，必须始终加载数据
watch(
  groupId,
  (id) => {
    if (!id) return
    const rg = Number(route.params.groupId)
    if (rg !== id) {
      router.replace(`/report/${id}`)
    }
    loadReport()
    setTimeout(startSSE, 1000)
  },
  { immediate: true }
)

onBeforeUnmount(() => stopSSE())
</script>

<style scoped>
.report-page {
  display: flex;
  flex-direction: column;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #831843;
  padding: 4px 0 12px;
}
.ml-auto { margin-left: auto; }
.ml-8 { margin-left: 8px; }
.mt-8 { margin-top: 8px; }
.mt-16 { margin-top: 16px; }
.mb-16 { margin-bottom: 16px; }
.small-title {
  font-size: 15px;
  font-weight: 600;
  color: #831843;
}
.me-count {
  color: #9ca3af;
  font-size: 12px;
  margin-bottom: 10px;
}
/* 「我的出刀」和「全员伤害排行」两栏锁成同一个固定高度。
   这个值 = 左边在 17 条出刀时的自然高度：
     卡片 padding 20*2 + 标题 23 + 「共 N 条」18 + 间距 10 + 表头 32 + 17*32 ≈ 670
   出刀变多时表体在卡片内部滚动（表头固定，和「出刀明细」一样），
   不再把卡片连同右边图表一起撑长；右边图表撑满同高，两边底边对齐。
   以后想调高度，只改这一个变量。 */
.rank-card {
  --rank-card-height: 670px;
  height: var(--rank-card-height);
  display: flex;
  flex-direction: column;
}
.rank-card-head {
  flex: none;
}
.rank-card-body,
.rank-chart {
  flex: 1;
  /* min-height: 0 是关键：flex 子项默认 min-height:auto，
     不加的话表格 / 图表会按内容撑破卡片，而不是在内部滚动 */
  min-height: 0;
}
.rank-card-body {
  /* 兜底：万一表格高度没算准，裁掉溢出而不是撑破卡片 */
  overflow: hidden;
}
.chart-legend {
  display: flex;
  gap: 14px;
  align-items: center;
  font-size: 12px;
  color: #6b7280;
}
.chart-legend .dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 4px;
  vertical-align: middle;
}
.dot.pink { background: #ec4899; }
.dot.amber { background: #f59e0b; }
.num-cell {
  display: flex;
  align-items: center;
  justify-content: flex-start;
}
.num-val {
  font-weight: 600;
  min-width: 90px;
  text-align: left;
}
.total-box {
  display: flex;
  gap: 16px;
}
.total-item {
  font-size: 13px;
  color: #6b7280;
  background: #fffbeb;
  padding: 4px 10px;
  border-radius: 6px;
}
.total-item b {
  color: #831843;
  margin-left: 4px;
}
</style>
