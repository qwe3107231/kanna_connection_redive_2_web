<!--
  BOX/助战 →「排刀」页签。

  数据链路：
    腾讯文档表格（地址可在本页随时改） → 后端解析成作业
    当前登录用户的 BOX + 本群公会助战 → 后端拼成角色数据
    本组件负责：三刀依次选择、角色冲突过滤、补偿刀追加、助战标记。

  口径（用户确认过的）：
    - 普通一刀 90 秒；
    - 表格里的 90s / 71s 是**补偿刀时间**：90s = 70s 击杀 + 20s 补偿（满补），
      71s = 51s 击杀 + 20s 补偿；
    - 补偿刀从**表格里已有的作业**里选：和本刀主刀有 1~2 个角色不同的队伍也能选
      （继承主刀角色）；只能复用本刀主刀的角色，不能串到其他刀；助战可以随时换；
    - 每个角色只能使用一次；每刀最多借 1 个助战。
-->
<template>
  <div class="arrange-page">
    <el-empty v-if="!groupId" description="请先从上方选择一个公会" />

    <template v-else>
      <!-- ===================== 表格地址 / 别名配置 ===================== -->
      <div class="arrange-config kanna-card">
        <div class="arrange-config-head">
          <div class="arrange-config-title">
            <el-icon><Link /></el-icon>
            <span>在线表格</span>
          </div>
          <div class="arrange-config-meta">
            <template v-if="data?.url">
              <span>上次抓取：{{ fmtTime(data?.fetched_at || 0) }}</span>
              <span v-if="data"> · {{ data.entry_count }} 条作业</span>
              <el-tag v-if="data?.cached" size="small" type="warning" effect="plain">
                使用缓存
              </el-tag>
            </template>
            <span v-else>未设置表格地址</span>
          </div>
        </div>

        <div class="arrange-config-row">
          <el-input
            v-model="urlInput"
            class="arrange-url-input"
            placeholder="https://docs.qq.com/sheet/xxxx?tab=yyyy"
            clearable
            @keyup.enter="saveConfig"
          />
          <el-button type="primary" :loading="saving" @click="saveConfig">
            保存设置
          </el-button>
          <el-button :loading="refreshing" @click="refreshSheet">
            <el-icon v-if="!refreshing"><Refresh /></el-icon>刷新表格
          </el-button>
        </div>

        <el-alert
          v-if="data && data.unknown_names.length"
          type="warning"
          :closable="false"
          show-icon
          class="arrange-unknown-alert"
        >
          <template #title>
            这些角色名没认出来：{{ data.unknown_names.join('、') }}
            <span v-if="unknownTeams.length">
              （共 {{ data.unknown_names.length }} 个名字 /
              {{ unknownTeams.length }} 条作业）
            </span>
          </template>
          <div class="arrange-unknown-body">
            同一个名字在表格里出现多次只列一次；匹配后所有相关作业会一起更新。
            下面直接给每个未识别名字匹配角色，匹配后会自动刷新一次表格，
            确保其他未识别名字也显示出来。
            <div v-if="data.charas?.length" class="arrange-match-list">
              <div
                v-for="stat in unknownNameStats"
                :key="stat.name"
                class="arrange-match-row"
              >
                <span
                  class="arrange-match-name"
                  :title="stat.labels.join('、')"
                >
                  {{ stat.name }}
                </span>
                <span class="arrange-match-count">{{ stat.count }} 条作业</span>
                <el-select
                  :model-value="manualMatches[stat.name]"
                  filterable
                  clearable
                  size="small"
                  placeholder="搜索角色名/别名"
                  no-data-text="没有匹配的角色"
                  class="arrange-match-select"
                  :filter-method="onCharaFilter"
                  @visible-change="onCharaVisibleChange"
                  @change="onManualMatch(stat.name, $event)"
                >
                  <el-option
                    v-for="chara in filteredCharas"
                    :key="chara.unit_id"
                    :label="chara.name"
                    :value="chara.unit_id"
                  />
                </el-select>
              </div>
            </div>
            <div v-else class="arrange-match-fallback">
              当前后端还没有返回角色列表；可以先展开下面的「角色别名」手动输入。
            </div>
            <div class="arrange-unknown-actions">
              <el-button
                size="small"
                type="warning"
                plain
                :loading="refreshing"
                @click="refreshSheet"
              >
                刷新表格后重新识别
              </el-button>
            </div>
          </div>
        </el-alert>

        <div class="arrange-alias">
          <el-button text size="small" @click="showAlias = !showAlias">
            <el-icon><EditPen /></el-icon>
            {{ showAlias ? '收起角色别名' : '角色别名（可选）' }}
          </el-button>
          <div v-show="showAlias" class="arrange-alias-body">
            <el-input
              v-model="aliasesText"
              type="textarea"
              :rows="4"
              placeholder="每行一条：表格里的写法=角色名，例如 xxtx=小小甜心"
            />
            <div class="arrange-alias-tip">
              别名只在解析表格时用；改完点【保存设置】立即生效。
            </div>
          </div>
        </div>
      </div>

      <el-alert
        v-if="error"
        :title="error"
        :type="errorType"
        :closable="false"
        show-icon
      />
      <el-alert
        v-if="data?.message"
        type="info"
        :closable="false"
        show-icon
        class="arrange-message-alert"
      >
        <div class="arrange-message-body">{{ data.message }}</div>
      </el-alert>

      <div v-if="loading && !data" class="arrange-loading">
        <el-icon class="is-loading" :size="26"><Loading /></el-icon>
        <span>正在读取排刀数据…</span>
      </div>

      <template v-if="data?.ok">
        <!-- ===================== 状态条 ===================== -->
        <div class="arrange-toolbar">
          <div class="arrange-toolbar-left">
            <el-tag effect="plain">你的 BOX：{{ data.owned_count }} 个角色</el-tag>
            <el-tag effect="plain">
              本群助战缓存：{{ data.support_count }} 个角色
            </el-tag>
            <el-tag v-if="supportAll" type="success" effect="plain">
              助战：可借全部角色
            </el-tag>
            <el-tag v-else type="info" effect="plain">
              剩余可借助战：{{ remainingSupportCount }}
            </el-tag>
          </div>
          <div class="arrange-toolbar-right">
            <el-button
              v-if="selected.some((id) => id != null)"
              text
              size="small"
              @click="clearAll"
            >
              清空三刀
            </el-button>
            <el-switch v-model="showUnavailable" size="small" />
            <span>显示不可用作业</span>
          </div>
        </div>
        <!-- ===================== 三刀 ===================== -->
        <div class="arrange-grid">
          <div v-for="slot in 3" :key="slot" class="arrange-col">
            <div class="arrange-col-head">
              <span class="arrange-col-title">第 {{ slot }} 刀</span>
              <el-tag size="small" effect="plain">90s</el-tag>
              <el-tag
                v-if="hasSelected[slot - 1]"
                size="small"
                type="success"
                effect="plain"
              >
                已选
              </el-tag>
              <el-tag v-else size="small" type="info" effect="plain">待选</el-tag>
              <span v-if="hasSelected[slot - 1]" class="arrange-col-hint">
                点击卡片更换
              </span>
            </div>

            <!-- 三个占位都可以直接点开选刀弹窗，不再限制必须 1→2→3 -->
            <div
              v-if="!hasSelected[slot - 1]"
              class="arrange-slot-placeholder"
              @click="openNormalDialog(slot - 1)"
            >
              <el-icon :size="24"><Plus /></el-icon>
              <div class="arrange-slot-title">点击选择第 {{ slot }} 刀</div>
              <div class="arrange-slot-tip">
                候选会按另外两刀已用角色实时过滤
              </div>
            </div>

            <template v-else>
              <ArrangeTeamCard
                :team="selectedTeams[slot - 1]"
                :units="unitsMap"
                :borrow-id="parentBorrowId(slot - 1)"
                :selected="true"
                @select="openNormalDialog(slot - 1)"
              />

              <!-- 补偿刀：只要作业里有补偿时间（包括同时写了伤害的 both）就显示 -->
              <div
                v-if="hasReturn(selectedTeams[slot - 1])"
                class="arrange-comp"
              >
                <div class="arrange-comp-title">
                  <span>补偿刀 · 可用 {{ returnLabel(selectedTeams[slot - 1]) }}</span>
                  <el-tag
                    v-if="returnOf(selectedTeams[slot - 1]) >= 90"
                    size="small"
                    type="success"
                    effect="plain"
                  >
                    满补
                  </el-tag>
                </div>

                <template v-if="!hasComp[slot - 1]">
                  <div class="arrange-comp-actions">
                    <el-button size="small" @click="pickSameComp(slot - 1)">
                      本队伍继续
                    </el-button>
                    <el-button size="small" @click="openCompDialog(slot - 1)">
                      选队伍再打一刀
                    </el-button>
                  </div>
                  <div class="arrange-comp-tip">
                    补偿刀从表格作业里选：和本刀主刀有 1~2 个角色不同的队伍也能选
                    （继承主刀角色）；其他刀用过的角色不能碰，助战可以换。
                  </div>
                </template>

                <template v-else>
                  <template v-if="comp[slot - 1]?.kind === 'same'">
                    <div class="arrange-comp-same-label">本队伍继续</div>
                    <ArrangeTeamCard
                      :team="selectedTeams[slot - 1]"
                      :units="unitsMap"
                      :borrow-id="parentBorrowId(slot - 1)"
                      compact
                      :selected="true"
                      @select="openCompDialog(slot - 1)"
                    />
                  </template>
                  <ArrangeTeamCard
                    v-else
                    :team="compTeams[slot - 1]"
                    :units="unitsMap"
                    :borrow-id="compBorrowId(slot - 1)"
                    :selected="true"
                    @select="openCompDialog(slot - 1)"
                  />
                  <div class="arrange-comp-actions">
                    <el-button text size="small" @click="clearComp(slot - 1)">
                      取消补偿刀
                    </el-button>
                  </div>
                </template>
              </div>
            </template>
          </div>
        </div>

        <!-- ===================== 三刀汇总 ===================== -->
        <div v-if="allSelected" class="arrange-summary kanna-card">
          <div class="arrange-summary-title">三刀已选好</div>
          <div class="arrange-summary-tags">
            <el-tag type="success" effect="plain">普通刀 3</el-tag>
            <el-tag v-if="compCount" type="warning" effect="plain">
              补偿刀 {{ compCount }}
            </el-tag>
            <el-tag v-if="totalDamage" type="danger" effect="plain">
              伤害 {{ totalDamage.toFixed(2) }} 亿
            </el-tag>
            <el-tag
              v-for="(time, index) in compTimes"
              :key="`comp-time-${index}`"
              type="info"
              effect="plain"
            >
              补偿 {{ time }}
            </el-tag>
          </div>
          <div class="arrange-summary-used">
            已用角色 {{ usedUnitIds.size }} 个
            <span v-if="borrowCount"> · 助战 {{ borrowCount }} 个</span>
          </div>
          <div class="arrange-summary-actions">
            <el-button type="primary" @click="openCommandDialog">
              <el-icon><Document /></el-icon>
              生成 autoPCR 一键编队指令
            </el-button>
          </div>
        </div>
      </template>
    </template>

    <!-- ===================== 主刀选择弹窗 ===================== -->
    <el-dialog
      v-model="normalDialogVisible"
      :title="`选择第 ${normalDialogSlot + 1} 刀`"
      width="min(1080px, 94vw)"
      top="6vh"
      class="arrange-normal-dialog"
      append-to-body
    >
      <div class="arrange-normal-dialog-toolbar">
        <el-switch v-model="showUnavailable" size="small" />
        <span>显示不可用作业</span>
        <el-button
          v-if="hasSelected[normalDialogSlot]"
          text
          size="small"
          class="arrange-normal-clear"
          @click="clearNormalFromDialog"
        >
          清空这一刀
        </el-button>
      </div>
      <div class="arrange-normal-dialog-list">
        <ArrangeTeamCard
          v-for="team in normalDialogCandidates"
          :key="team.id"
          :team="team"
          :units="unitsMap"
          :feasible="normalDialogCheck(team).feasible"
          :reason="normalDialogCheck(team).reason"
          :borrow-id="normalDialogCheck(team).borrowId"
          :selected="selected[normalDialogSlot] === team.id"
          @select="pickNormalFromDialog(team)"
        />
        <el-empty
          v-if="!normalDialogCandidates.length"
          description="没有能组成的队伍：角色不够，或被另外两刀用了"
          :image-size="60"
        />
      </div>
    </el-dialog>

    <!-- ===================== 补偿刀选队弹窗 ===================== -->
    <el-dialog
      v-model="compDialogVisible"
      title="选择补偿刀队伍"
      width="min(980px, 94vw)"
      top="6vh"
      class="arrange-comp-dialog"
      append-to-body
    >
      <div class="arrange-comp-dialog-head">
        第 {{ compDialogSlot + 1 }} 刀的补偿时间：<b>{{ returnLabel(compDialogParent) }}</b>。
        可以继续用本队伍，或从表格里选一条作业；和本刀主刀有 1~2 个角色不同的队伍也能选
        （继承主刀角色），但其他刀用过的角色不能碰。最多借 1 个助战，助战可以换。
      </div>
      <div class="arrange-comp-dialog-same-label">
        本队伍继续（复用角色，不额外占用角色/助战）
      </div>
      <ArrangeTeamCard
        :team="compDialogParent"
        :units="unitsMap"
        :borrow-id="parentBorrowId(compDialogSlot)"
        compact
        @select="pickSameComp(compDialogSlot)"
      />
      <div class="arrange-comp-dialog-list">
        <ArrangeTeamCard
          v-for="team in compDialogCandidates"
          :key="team.id"
          :team="team"
          :units="unitsMap"
          :borrow-id="compDialogCheck(team).borrowId"
          compact
          @select="pickCompTeam(compDialogSlot, team)"
        />
        <el-empty
          v-if="!compDialogCandidates.length"
          description="没有其他能用的表格作业了；可以选本队伍继续"
          :image-size="60"
        />
      </div>
    </el-dialog>

    <!-- ===================== autoPCR 一键编队指令 ===================== -->
    <el-dialog
      v-model="commandDialogVisible"
      title="autoPCR 一键编队指令"
      width="min(760px, 94vw)"
      top="8vh"
      class="arrange-command-dialog"
      append-to-body
    >
      <div class="arrange-command-tip">
        复制下面整段发到 QQ 即可（<code>#</code> 前缀按你的 bot 配置）。
        前两个参数 <code>1 1</code> = 第 1 面板、第 1 队开始。
      </div>
      <el-input
        v-model="commandText"
        type="textarea"
        :rows="10"
        readonly
        class="arrange-command-text"
      />
      <div class="arrange-command-note">
        autoPCR 只能设置你拥有的角色；助战角色需要你在游戏里手动借
        （未持有的角色会被 autoPCR 跳过）。「本队伍继续」会生成一条相同阵容，
        不需要的话删掉那一行即可。
      </div>
      <template #footer>
        <el-button @click="commandDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="copyCommand">复制指令</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getArrangeData, saveArrangeConfig } from '@/api'
import type { ArrangeData, ArrangeTeam, ArrangeUnit } from '@/types'
import ArrangeTeamCard from '@/components/ArrangeTeamCard.vue'
import { useUserStore } from '@/store/user'

const props = defineProps<{ groupId?: number }>()
const userStore = useUserStore()

const data = ref<ArrangeData | null>(null)
const loading = ref(false)
const refreshing = ref(false)
const saving = ref(false)
const error = ref('')
// 「还没设置表格地址」属于引导提示，用 warning 而不是红色 error
const errorType = computed(() =>
  error.value.includes('表格地址') ? 'warning' : 'error',
)

const urlInput = ref('')
const aliasesText = ref('')
const showAlias = ref(false)
const showUnavailable = ref(false)

const selected = ref<(number | null)[]>([null, null, null])
// 补偿刀：'same' = 本队伍继续；'team' = 从表格里选另一条作业（可复用本刀主刀的角色）
type CompPick = { kind: 'same' } | { kind: 'team'; teamId: number }
const comp = ref<(CompPick | null)[]>([null, null, null])

const normalDialogVisible = ref(false)
const normalDialogSlot = ref(0)
const compDialogVisible = ref(false)
const compDialogSlot = ref(0)

const commandDialogVisible = ref(false)
const commandText = ref('')

// 未识别角色的手动匹配：{ 表格里的写法: 选中的 unit_id }
const manualMatches = ref<Record<string, number | undefined>>({})
// 手动匹配下拉框的搜索词（支持按主名 / 日文名 / 英文名 / 社区别名搜）
const charaKeyword = ref('')

const teams = computed<ArrangeTeam[]>(() => data.value?.teams ?? [])
const unitsMap = computed<Record<string, ArrangeUnit>>(() => data.value?.units ?? {})
const teamById = computed(() => {
  const map = new Map<number, ArrangeTeam>()
  for (const team of teams.value) map.set(team.id, team)
  return map
})
const supportSet = computed(() => new Set<number>(data.value?.support_ids ?? []))
// 助战默认按「全部角色都能借」处理（用户要求）；旧接口没有 support_all 时也按 true。
const supportAll = computed(() => data.value?.support_all !== false)
const unknownTeams = computed(() =>
  (data.value?.teams ?? []).filter((team) => team.unknown_names.length > 0),
)
// 每个未识别名字涉及多少条作业、分别是哪些 BOSS（同一个名字可能出现在多队里）
const unknownNameStats = computed(() => {
  const teams = data.value?.teams ?? []
  return (data.value?.unknown_names ?? []).map((name) => {
    const matched = teams.filter((team) => team.unknown_names.includes(name))
    return {
      name,
      count: matched.length,
      labels: matched.map((team) => team.boss_label),
    }
  })
})

const filteredCharas = computed(() => {
  const keyword = charaKeyword.value.trim().toLowerCase()
  const list = data.value?.charas ?? []
  if (!keyword) return list
  return list.filter((chara) =>
    [chara.name, ...(chara.aliases || [])].some((name) =>
      String(name).toLowerCase().includes(keyword),
    ),
  )
})

const EMPTY_UNIT: ArrangeUnit = {
  unit_id: 0,
  chara_name: '未知角色',
  avatar: '',
  owned: false,
  rarity: 0,
  battle_rarity: 0,
  rank: 0,
  level: 0,
  player_owned: false,
  from_support: false,
  player_name: '',
}

const EMPTY_TEAM: ArrangeTeam = {
  id: -1,
  raw: '',
  stage: '',
  bosses: [],
  boss_label: '',
  boss_text: '',
  units: [],
  unit_names: [],
  unknown_names: [],
  value_kind: 'damage',
  value: 0,
  value_label: '',
  damage_value: 0,
  return_seconds: 0,
  source_row: 0,
  source_col: 0,
}

const selectedTeams = computed<ArrangeTeam[]>(() =>
  selected.value.map(
    (id) => (id == null ? EMPTY_TEAM : teamById.value.get(id) ?? EMPTY_TEAM),
  ),
)
const hasSelected = computed(() => selected.value.map((id) => id != null))

const compTeams = computed<ArrangeTeam[]>(() =>
  comp.value.map((pick, index) => {
    if (!pick) return EMPTY_TEAM
    if (pick.kind === 'same') return selectedTeams.value[index]
    return teamById.value.get(pick.teamId) ?? EMPTY_TEAM
  }),
)
const hasComp = computed(() => comp.value.map((pick) => pick != null))

const allSelected = computed(() => selected.value.every((id) => id != null))

// ---- 选好的刀缓存（按账号单独保存）----
// 切换页签 / 刷新页面后自动恢复；存的是作业原始文本（team.raw），
// 这样表格重新抓取、作业 id 变了也能重新对上。
const SELECTION_STORAGE_PREFIX = 'kanna.arrange.selection.v1'

interface SavedCompPick {
  kind: 'same' | 'team'
  raw?: string
}
interface SavedSelection {
  url: string
  selected: (string | null)[]
  comp: (SavedCompPick | null)[]
}

function selectionStorageKey(): string {
  const uid = Number(userStore.userId || 0)
  return uid > 0 ? `${SELECTION_STORAGE_PREFIX}.${uid}` : ''
}

function readSavedSelection(): SavedSelection | null {
  const key = selectionStorageKey()
  if (!key) return null
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const parsed = JSON.parse(raw) as SavedSelection
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch (e) {
    return null
  }
}

/** 把当前选择写进本地缓存（按账号；只存原始文本，不存易变的 team id）。 */
function writeSavedSelection() {
  const key = selectionStorageKey()
  if (!key) return
  const url = (data.value?.url || '').trim()
  if (!url) return
  const saved: SavedSelection = {
    url,
    selected: selected.value.map((id) =>
      id == null ? null : teamById.value.get(id)?.raw ?? null,
    ),
    comp: comp.value.map((pick) => {
      if (!pick) return null
      if (pick.kind === 'same') return { kind: 'same' }
      const team = teamById.value.get(pick.teamId)
      return team ? { kind: 'team', raw: team.raw } : null
    }),
  }
  try {
    localStorage.setItem(key, JSON.stringify(saved))
  } catch (e) {
    /* 隐私模式 / 配额满：缓存失败不影响使用 */
  }
}

/** 数据加载完后恢复这个账号上次选好的刀；表格地址变了就不恢复。 */
function restoreSavedSelection() {
  selected.value = [null, null, null]
  comp.value = [null, null, null]
  const saved = readSavedSelection()
  const url = (data.value?.url || '').trim()
  if (!saved || !url || saved.url !== url) return
  const byRaw = new Map<string, ArrangeTeam>()
  for (const team of teams.value) {
    if (!byRaw.has(team.raw)) byRaw.set(team.raw, team)
  }
  selected.value = (saved.selected || [])
    .slice(0, 3)
    .map((raw) => (raw ? byRaw.get(raw)?.id ?? null : null))
  comp.value = (saved.comp || []).slice(0, 3).map((pick, index) => {
    if (!pick || selected.value[index] == null) return null
    if (!hasReturn(selectedTeams.value[index])) return null
    if (pick.kind === 'same') return { kind: 'same' } as CompPick
    const team = pick.raw ? byRaw.get(pick.raw) : undefined
    return team ? ({ kind: 'team', teamId: team.id } as CompPick) : null
  })
}

// 任何一次选刀 / 取消都会写回本地缓存（按当前登录账号区分）
watch([selected, comp], () => writeSavedSelection(), { deep: true })

function unitOf(unitId: number): ArrangeUnit {
  return unitsMap.value[String(unitId)] ?? { ...EMPTY_UNIT, unit_id: unitId }
}

/** 作业里的伤害（亿）；没有伤害返回 0。 */
function damageOf(team: ArrangeTeam): number {
  return (
    Number(
      team.damage_value ?? (team.value_kind === 'damage' ? team.value : 0),
    ) || 0
  )
}

/** 作业里的补偿时间（秒）；没有补偿返回 0。 */
function returnOf(team: ArrangeTeam): number {
  return (
    Number(
      team.return_seconds ?? (team.value_kind === 'return' ? team.value : 0),
    ) || 0
  )
}

function hasReturn(team: ArrangeTeam): boolean {
  return returnOf(team) > 0
}

function returnLabel(team: ArrangeTeam): string {
  return `${returnOf(team)}s`
}

interface TeamCheck {
  feasible: boolean
  borrowId: number | null
  missing: number[]
  conflicts: number[]
  reason: string
}

/** 一支队伍在「已用角色集合」下能不能出。 */
function teamCheck(team: ArrangeTeam, used: Set<number>): TeamCheck {
  const unknown = team.unknown_names ?? []
  const unitIds = team.units ?? []
  const unique = new Set(unitIds)
  const conflicts = unitIds.filter((id) => used.has(id))
  const missing = unitIds.filter(
    (id) => !unitsMap.value[String(id)]?.player_owned,
  )
  const canBorrow =
    missing.length === 1 &&
    (supportAll.value || supportSet.value.has(missing[0]))
  const borrowId = canBorrow ? missing[0] : null

  let feasible = true
  let reason = ''
  if (unknown.length) {
    feasible = false
    reason = `未识别：${unknown.join('、')}`
  } else if (unitIds.length !== 5) {
    feasible = false
    reason = `角色数不是 5（表格里写了 ${unitIds.length} 个）`
  } else if (unique.size !== 5) {
    feasible = false
    reason = '同一队里有重复角色'
  } else if (conflicts.length) {
    feasible = false
    reason = `角色已被其他刀用了：${conflicts
      .map((id) => unitOf(id).chara_name)
      .join('、')}`
  } else if (missing.length > 1) {
    feasible = false
    reason = `缺 ${missing.length} 个角色：${missing
      .map((id) => unitOf(id).chara_name)
      .join('、')}`
  } else if (missing.length === 1 && !borrowId) {
    feasible = false
    reason = `缺「${unitOf(missing[0]).chara_name}」，当前不能借`
  }

  return { feasible, borrowId, missing, conflicts, reason }
}

/** 选第 slot 刀时，其他两刀（含它们的补偿刀）已经占用的角色。
 *
 *  三个刀位是独立的，不按 1→2→3 顺序；这里排除的是「除当前槽位之外」的已用角色。
 *  当前槽位自己的补偿刀会在换主刀时清掉，所以也排除。
 */
function usedUnitsForNormal(slot: number): Set<number> {
  const used = new Set<number>()
  selected.value.forEach((id, index) => {
    if (index !== slot && id != null) {
      selectedTeams.value[index].units.forEach((unitId) => used.add(unitId))
    }
  })
  comp.value.forEach((pick, index) => {
    if (index === slot || pick?.kind !== 'team') return
    teamById.value
      .get(pick.teamId)
      ?.units.forEach((unitId) => used.add(unitId))
  })
  return used
}

/** 选第 slot 刀的补偿刀时，**其他刀**（主队 + 补偿队）已经占用的角色。
 *
 *  本刀主刀的角色**不放进 used**：补偿刀可以选一条和本刀主刀有 1~2 个角色不同的
 *  表格作业（继承主刀角色）；但其他刀的角色仍然不能碰 ——
 *  「各刀的补偿只能复用各主刀的角色，不能串到其他刀」。
 */
function usedUnitsForComp(slot: number): Set<number> {
  const used = new Set<number>()
  selected.value.forEach((id, index) => {
    if (index === slot || id == null) return
    selectedTeams.value[index].units.forEach((unitId) => used.add(unitId))
  })
  comp.value.forEach((pick, index) => {
    if (index === slot || pick?.kind !== 'team') return
    teamById.value
      .get(pick.teamId)
      ?.units.forEach((unitId) => used.add(unitId))
  })
  return used
}

// ---- 借人（助战）分配求解 ----
// 规则（用户确认）：
//   * 每刀最多借 1 个角色（主刀 / 补偿刀各算一刀）；
//   * 借来的角色**不占用自己账号的角色**，所以同一角色可以在不同刀里分别“借”；
//   * 自己拥有的角色每天只能用一次（补偿刀可以继承本刀主刀的角色）；
//   * 因此「第 1 刀借霸瞳、第 2 刀借狼」这种方案是合法的：两刀各借一个，
//     自己拥有的两个角色都能留给另一刀。
// 这里用一个小回溯：给每支已选队伍挑一个“借谁”（或不借），检查自己角色的占用不冲突。
interface TeamPlan {
  key: string
  units: number[]
  /** 补偿刀继承的主刀角色：和 parentKey 那队重复时允许复用 */
  inherited?: Set<number>
  parentKey?: string
}

function buildPlanTeams(
  skip?: { kind: 'main' | 'comp'; slot: number },
): TeamPlan[] {
  const plans: TeamPlan[] = []
  selected.value.forEach((id, index) => {
    if (id == null) return
    if (skip?.kind === 'main' && skip.slot === index) return
    plans.push({ key: `main${index}`, units: selectedTeams.value[index].units })
  })
  comp.value.forEach((pick, index) => {
    if (!pick) return
    // 换主刀时该刀的补偿刀会作废，所以评估主刀候选时也把它排除
    if (skip?.kind === 'main' && skip.slot === index) return
    if (skip?.kind === 'comp' && skip.slot === index) return
    const units =
      pick.kind === 'same'
        ? selectedTeams.value[index].units
        : teamById.value.get(pick.teamId)?.units ?? []
    plans.push({
      key: `comp${index}`,
      units,
      inherited: new Set(selectedTeams.value[index].units),
      parentKey: `main${index}`,
    })
  })
  return plans
}

/** 给每支队伍分配“借谁”（最多 1 个）；找不到可行方案返回 null。 */
function solveBorrows(
  plans: TeamPlan[],
): Map<string, number | null> | null {
  const assignment = new Map<string, number | null>()
  // unit_id -> 用了这个自己角色的队伍 key 集合
  const usedBy = new Map<number, Set<string>>()

  function onlyInheritedFromParent(
    unitId: number,
    inherited: Set<number>,
    parentKey?: string,
  ): boolean {
    if (!inherited.has(unitId) || !parentKey) return false
    const users = usedBy.get(unitId)
    return !!users && users.size > 0 && [...users].every((k) => k === parentKey)
  }

  function dfs(index: number): boolean {
    if (index >= plans.length) return true
    const plan = plans[index]
    const inherited = plan.inherited ?? new Set<number>()
    const options: (number | null)[] = [null]
    const needBorrow: number[] = []
    const extraBorrow: number[] = []
    for (const unitId of plan.units) {
      const owned = !!unitsMap.value[String(unitId)]?.player_owned
      const users = usedBy.get(unitId)
      const reused = onlyInheritedFromParent(unitId, inherited, plan.parentKey)
      if (!owned || ((users?.size ?? 0) > 0 && !reused)) {
        needBorrow.push(unitId)
      } else {
        extraBorrow.push(unitId)
      }
    }
    options.push(...needBorrow, ...extraBorrow)

    for (const borrow of options) {
      if (borrow != null && !supportAll.value && !supportSet.value.has(borrow)) {
        continue
      }
      const added: number[] = []
      let ok = true
      for (const unitId of plan.units) {
        if (unitId === borrow) continue
        if (onlyInheritedFromParent(unitId, inherited, plan.parentKey)) continue
        const users = usedBy.get(unitId)
        if (users && users.size > 0) {
          ok = false
          break
        }
        if (!unitsMap.value[String(unitId)]?.player_owned) {
          ok = false
          break
        }
        added.push(unitId)
      }
      if (!ok) continue

      for (const unitId of added) {
        const set = usedBy.get(unitId) ?? new Set<string>()
        set.add(plan.key)
        usedBy.set(unitId, set)
      }
      assignment.set(plan.key, borrow)
      if (dfs(index + 1)) return true
      assignment.delete(plan.key)
      for (const unitId of added) {
        const set = usedBy.get(unitId)
        if (!set) continue
        set.delete(plan.key)
        if (!set.size) usedBy.delete(unitId)
      }
    }
    return false
  }

  return dfs(0) ? assignment : null
}

/** 已选方案里的借人分配（用于显示「借 X」角标、统计助战数量）。 */
const planAssignment = computed<Map<string, number | null>>(
  () => solveBorrows(buildPlanTeams()) ?? new Map(),
)

/** 候选队伍（主刀 / 补偿刀）在当前已选方案下能不能选，以及它会借谁。 */
function candidateCheck(
  team: ArrangeTeam,
  kind: 'main' | 'comp',
  slot: number,
): TeamCheck {
  const plans = buildPlanTeams({ kind, slot })
  plans.push({
    key: 'candidate',
    units: team.units,
    inherited:
      kind === 'comp' ? new Set(selectedTeams.value[slot].units) : undefined,
    parentKey: kind === 'comp' ? `main${slot}` : undefined,
  })
  const assignment = solveBorrows(plans)
  if (assignment) {
    return {
      feasible: true,
      borrowId: assignment.get('candidate') ?? null,
      missing: [],
      conflicts: [],
      reason: '',
    }
  }
  const used =
    kind === 'main' ? usedUnitsForNormal(slot) : usedUnitsForComp(slot)
  const fallback = teamCheck(team, used)
  return {
    ...fallback,
    feasible: false,
    reason: fallback.feasible
      ? '角色和其他刀冲突，且每刀最多借 1 个助战'
      : fallback.reason,
  }
}

function normalCheck(team: ArrangeTeam, slot: number): TeamCheck {
  return candidateCheck(team, 'main', slot)
}

function normalCandidates(slot: number): ArrangeTeam[] {
  return teams.value.filter((team) => {
    // 已经选在别的刀里的同一个作业不重复列出来（它一定会冲突）
    const selectedElsewhere = selected.value.some(
      (id, index) => index !== slot && id === team.id,
    )
    if (selectedElsewhere) return false
    const check = candidateCheck(team, 'main', slot)
    return check.feasible || showUnavailable.value
  })
}

/** 补偿刀可选的表格作业：和本刀主刀有 1~2 个角色不同的队伍也能选（继承主刀角色）。
 *  按「和本刀主刀重合的角色数」从多到少排，越像主刀的越靠前。 */
function compCandidates(slot: number): ArrangeTeam[] {
  const parent = selectedTeams.value[slot]
  const parentIds = new Set(parent.units)
  const overlap = (team: ArrangeTeam) =>
    team.units.filter((id) => parentIds.has(id)).length
  return teams.value
    .filter((team) => {
      if (team.id === parent.id) return false
      // 和本队伍角色完全一样 = 本队伍继续，单独一个按钮，不重复列
      if (
        team.units.length === parent.units.length &&
        team.units.every((id) => parentIds.has(id))
      ) {
        return false
      }
      if (selected.value.some((id) => id === team.id)) return false
      if (
        comp.value.some(
          (pick) => pick?.kind === 'team' && pick.teamId === team.id,
        )
      ) {
        return false
      }
      return candidateCheck(team, 'comp', slot).feasible
    })
    .sort((a, b) => overlap(b) - overlap(a) || a.id - b.id)
}

function compBorrowId(slot: number): number | null {
  const pick = comp.value[slot]
  if (pick?.kind !== 'team') return null
  return planAssignment.value.get(`comp${slot}`) ?? null
}

/** 本队伍继续时复用的就是上面那刀，借的助战也沿用 */
function parentBorrowId(slot: number): number | null {
  if (selected.value[slot] == null) return null
  return planAssignment.value.get(`main${slot}`) ?? null
}

function pickNormal(slot: number, team: ArrangeTeam) {
  const check = normalCheck(team, slot)
  if (!check.feasible) return
  // 点回当前已选的同一队时什么都不改，避免把已经选好的补偿刀顺手清掉
  if (selected.value[slot] === team.id) return
  selected.value[slot] = team.id
  // 换主刀时这一刀的补偿刀作废；其他两刀不动
  comp.value[slot] = null
}

const normalDialogCandidates = computed(() =>
  normalCandidates(normalDialogSlot.value),
)
function normalDialogCheck(team: ArrangeTeam): TeamCheck {
  return candidateCheck(team, 'main', normalDialogSlot.value)
}
function openNormalDialog(slot: number) {
  normalDialogSlot.value = slot
  normalDialogVisible.value = true
}
function pickNormalFromDialog(team: ArrangeTeam) {
  const check = normalDialogCheck(team)
  if (!check.feasible) return
  pickNormal(normalDialogSlot.value, team)
  normalDialogVisible.value = false
}
function clearNormalFromDialog() {
  clearNormal(normalDialogSlot.value)
  normalDialogVisible.value = false
}

function clearNormal(slot: number) {
  // 只清这一刀；其他两刀保留（它们本来就不依赖这个槽位）
  selected.value[slot] = null
  comp.value[slot] = null
}

function clearAll() {
  selected.value = [null, null, null]
  comp.value = [null, null, null]
}

/** autoPCR 的角色名表用的是「·」，bot 角色名里有「‧」；统一一下。 */
function autopcrName(name: string): string {
  return name
    .replace(/‧/g, '·')
    .replace(/・/g, '·')
    .replace(/（/g, '(')
    .replace(/）/g, ')')
    .replace(/\s+/g, '')
}

/** 生成 autoPCR 的 #一键编队 文本：普通三刀 + 有补偿的刀（本队伍继续会重复一队）。 */
function buildAutopcrCommand(): string {
  const lines = ['#一键编队 1 1']
  for (let index = 0; index < 3; index++) {
    if (selected.value[index] == null) continue
    const team = selectedTeams.value[index]
    lines.push(
      `${index + 1}刀-${team.boss_label} ${team.unit_names
        .map(autopcrName)
        .join(' ')}`,
    )
    const pick = comp.value[index]
    if (pick) {
      const compTeam = compTeams.value[index]
      const title = pick.kind === 'same' ? '本队伍' : compTeam.boss_label
      lines.push(
        `${index + 1}刀补偿-${title} ${compTeam.unit_names
          .map(autopcrName)
          .join(' ')}`,
      )
    }
  }
  return lines.join('\n')
}

function openCommandDialog() {
  if (!allSelected.value) {
    ElMessage.warning('先选好三刀再生成指令')
    return
  }
  commandText.value = buildAutopcrCommand()
  commandDialogVisible.value = true
}

async function copyCommand() {
  const text = commandText.value
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制一键编队指令')
    return
  } catch {
    // HTTP 页面 / 浏览器权限不足时 navigator.clipboard 不可用，走旧方案
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  try {
    document.execCommand('copy')
    ElMessage.success('已复制一键编队指令')
  } catch {
    ElMessage.warning('复制失败，请手动选中文本复制')
  }
  textarea.remove()
}

function pickSameComp(slot: number) {
  const parent = selectedTeams.value[slot]
  if (selected.value[slot] == null || !hasReturn(parent)) return
  comp.value[slot] = { kind: 'same' }
  compDialogVisible.value = false
}

function pickCompTeam(slot: number, team: ArrangeTeam) {
  const check = candidateCheck(team, 'comp', slot)
  if (!check.feasible) return
  comp.value[slot] = { kind: 'team', teamId: team.id }
  compDialogVisible.value = false
}

function clearComp(slot: number) {
  comp.value[slot] = null
}

function openCompDialog(slot: number) {
  if (selected.value[slot] == null) return
  compDialogSlot.value = slot
  compDialogVisible.value = true
}

const compDialogParent = computed(
  () => selectedTeams.value[compDialogSlot.value] ?? EMPTY_TEAM,
)
const compDialogCandidates = computed(() =>
  compCandidates(compDialogSlot.value),
)
function compDialogCheck(team: ArrangeTeam): TeamCheck {
  return candidateCheck(team, 'comp', compDialogSlot.value)
}

const compCount = computed(() => comp.value.filter(Boolean).length)
const compTimes = computed(() =>
  comp.value
    .map((pick, index) =>
      pick ? returnLabel(selectedTeams.value[index]) : '',
    )
    .filter(Boolean),
)
// 已用角色 = 自己账号被占用的角色（借来的助战不算，所以不计入）
const usedUnitIds = computed(() => {
  const used = new Set<number>()
  const assignment = planAssignment.value
  for (const plan of buildPlanTeams()) {
    const borrow = assignment.get(plan.key) ?? null
    for (const unitId of plan.units) {
      if (unitId !== borrow) used.add(unitId)
    }
  }
  return used
})
// 只用于「只能借公会助战」模式；默认 supportAll=true 时页面显示「可借全部角色」。
const remainingSupportCount = computed(() => {
  const used = usedUnitIds.value
  return (data.value?.support_ids ?? []).filter(
    (unitId) =>
      !used.has(unitId) && !unitsMap.value[String(unitId)]?.player_owned,
  ).length
})
const borrowCount = computed(() => {
  let count = 0
  planAssignment.value.forEach((borrow) => {
    if (borrow != null) count += 1
  })
  return count
})
const totalDamage = computed(() => {
  let total = 0
  selected.value.forEach((id, index) => {
    if (id != null) {
      total += damageOf(selectedTeams.value[index])
    }
  })
  comp.value.forEach((pick) => {
    if (pick?.kind === 'team') {
      const team = teamById.value.get(pick.teamId)
      if (team) total += damageOf(team)
    }
  })
  return total
})

function fmtTime(timestamp: number): string {
  if (!timestamp) return '—'
  const date = new Date(timestamp * 1000)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getMonth() + 1}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

function parseAliases(text: string): Record<string, string> {
  const result: Record<string, string> = {}
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue
    const separator = line.includes('=') ? '=' : line.includes('＝') ? '＝' : ''
    if (!separator) continue
    const index = line.indexOf(separator)
    const key = line.slice(0, index).trim()
    const value = line.slice(index + 1).trim()
    if (key && value) result[key] = value
  }
  return result
}

/** 保存一组别名（未识别角色手动匹配 / 别名编辑共用）。 */
async function persistAliases(
  aliases: Record<string, string>,
  successMessage: string,
) {
  if (!props.groupId) return
  const url = (urlInput.value || data.value?.url || '').trim()
  if (!url) {
    ElMessage.warning('请先填写表格地址')
    return
  }
  saving.value = true
  try {
    const result = await saveArrangeConfig(props.groupId, { url, aliases })
    urlInput.value = result.url
    aliasesText.value = Object.entries(result.aliases || {})
      .map(([key, value]) => `${key}=${value}`)
      .join('\n')
    ElMessage.success(successMessage)
    // 手动匹配后强制抓一次表格：如果用户刚在表格里新增了其他未识别名字，
    // 只读缓存会把它们藏起来（之前就出现过匹配一个后其他名字看不到）。
    await loadData(true)
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    saving.value = false
  }
}

function onManualMatch(name: string, value: number | string | undefined) {
  const unitId = Number(value)
  if (!Number.isFinite(unitId)) return
  const chara = (data.value?.charas || []).find(
    (item) => item.unit_id === unitId,
  )
  if (!chara) return
  manualMatches.value[name] = unitId
  const aliases = { ...parseAliases(aliasesText.value), [name]: chara.name }
  void persistAliases(aliases, `已把「${name}」匹配为「${chara.name}」`)
}

function onCharaFilter(query: string) {
  charaKeyword.value = query
}

function onCharaVisibleChange(visible: boolean) {
  // 每次打开下拉框都从全部角色开始，避免上一行输入的搜索词影响下一行
  if (visible) charaKeyword.value = ''
}

function fillConfig(source: ArrangeData) {
  urlInput.value = source.url || ''
  aliasesText.value = Object.entries(source.aliases || {})
    .map(([key, value]) => `${key}=${value}`)
    .join('\n')
}

async function loadData(refresh = false) {
  if (!props.groupId) return
  loading.value = true
  error.value = ''
  try {
    const result = await getArrangeData(props.groupId, refresh)
    data.value = result
    fillConfig(result)
    if (!result.ok) error.value = result.message || '读取排刀数据失败'
    // 作业 id 会随表格变化：按作业原始文本恢复这个账号上次选好的刀
    // （切页签 / 刷新页面不会再把三刀清空）
    restoreSavedSelection()
    manualMatches.value = {}
    charaKeyword.value = ''
    normalDialogVisible.value = false
    compDialogVisible.value = false
  } catch (e) {
    error.value = '读取排刀数据失败，请稍后再试'
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (!props.groupId) return
  if (!urlInput.value.trim()) {
    ElMessage.warning('请填写腾讯文档表格地址')
    return
  }
  saving.value = true
  try {
    const result = await saveArrangeConfig(props.groupId, {
      url: urlInput.value.trim(),
      aliases: parseAliases(aliasesText.value),
    })
    urlInput.value = result.url
    aliasesText.value = Object.entries(result.aliases || {})
      .map(([key, value]) => `${key}=${value}`)
      .join('\n')
    ElMessage.success('设置已保存')
    // 保存后强制抓一次表格：用户很可能刚在表格里加了新作业/新名字，
    // 只读缓存会让新的未识别角色不显示。
    await loadData(true)
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    saving.value = false
  }
}

async function refreshSheet() {
  if (!props.groupId) return
  refreshing.value = true
  try {
    await loadData(true)
    if (data.value?.cached) {
      ElMessage.warning('抓取失败，仍在使用上次缓存')
    } else if (data.value?.ok) {
      ElMessage.success('表格已刷新')
    }
  } finally {
    refreshing.value = false
  }
}

watch(
  () => props.groupId,
  (id) => {
    if (id) {
      void loadData(false)
    } else {
      data.value = null
      error.value = ''
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.arrange-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.arrange-config {
  padding: 16px;
}
.arrange-config-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.arrange-config-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: var(--kanna-heading);
}
.arrange-config-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--kanna-text-faint);
}
.arrange-config-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.arrange-url-input {
  flex: 1;
  min-width: 260px;
}
.arrange-config-tip {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--kanna-text-faint);
}
.arrange-config-tip code,
.arrange-unknown-body code {
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--kanna-hover);
  color: var(--kanna-text);
}
.arrange-unknown-alert {
  margin-top: 10px;
}
.arrange-unknown-body {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
}
.arrange-match-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}
.arrange-match-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.arrange-match-name {
  min-width: 96px;
  max-width: 180px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--kanna-hover);
  color: var(--kanna-text);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.arrange-match-count {
  font-size: 11px;
  color: var(--kanna-text-faint);
  white-space: nowrap;
}
.arrange-match-select {
  width: 240px;
  max-width: 100%;
}
.arrange-match-fallback {
  margin-top: 6px;
  color: var(--kanna-text-faint);
}
.arrange-unknown-actions {
  margin-top: 10px;
}
.arrange-alias {
  margin-top: 8px;
}
.arrange-alias-body {
  margin-top: 6px;
}
.arrange-alias-tip {
  margin-top: 4px;
  font-size: 12px;
  color: var(--kanna-text-faint);
}
.arrange-message-alert {
  white-space: normal;
}
.arrange-message-body {
  white-space: pre-line;
  line-height: 1.6;
  font-size: 12px;
}
.arrange-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px;
  color: var(--kanna-text-faint);
}
.arrange-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.arrange-toolbar-left,
.arrange-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.arrange-toolbar-right {
  font-size: 12px;
  color: var(--kanna-text-faint);
}
.arrange-toolbar-note {
  margin-top: -4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--kanna-text-faint);
}
.arrange-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(280px, 1fr));
  gap: 16px;
  align-items: start;
}
.arrange-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}
.arrange-col-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.arrange-col-title {
  font-weight: 700;
  color: var(--kanna-heading);
}
.arrange-col-hint {
  margin-left: auto;
  font-size: 11px;
  color: var(--kanna-text-faint);
  white-space: nowrap;
}
.arrange-slot-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 150px;
  padding: 24px 12px;
  border: 1px dashed var(--kanna-border);
  border-radius: 10px;
  color: var(--kanna-text-faint);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.arrange-slot-placeholder:hover {
  border-color: var(--el-color-primary);
  background: var(--kanna-hover);
  color: var(--el-color-primary);
}
.arrange-slot-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--kanna-text);
}
.arrange-slot-tip {
  font-size: 11px;
  line-height: 1.5;
  text-align: center;
}
.arrange-comp {
  border-left: 3px solid var(--el-color-warning);
  padding: 4px 0 4px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.arrange-comp-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-color-warning-dark-2);
}
.arrange-comp-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.arrange-comp-same-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--el-color-warning-dark-2);
}
.arrange-comp-tip {
  font-size: 11px;
  line-height: 1.5;
  color: var(--kanna-text-faint);
}
.arrange-normal-dialog-head {
  font-size: 13px;
  line-height: 1.6;
  color: var(--kanna-text-faint);
  margin-bottom: 8px;
}
.arrange-normal-dialog-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--kanna-text-faint);
}
.arrange-normal-clear {
  margin-left: auto;
}
.arrange-normal-dialog-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 8px;
  max-height: 62vh;
  overflow-y: auto;
  padding: 2px;
}
.arrange-summary {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.arrange-summary-title {
  font-weight: 700;
  color: var(--kanna-heading);
}
.arrange-summary-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.arrange-summary-used {
  font-size: 13px;
  color: var(--kanna-text);
}
.arrange-summary-tip {
  font-size: 12px;
  color: var(--kanna-text-faint);
}
.arrange-summary-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 2px;
}
.arrange-comp-dialog-head {
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 10px;
}
.arrange-comp-dialog-same-label {
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--kanna-text-faint);
}
.arrange-comp-dialog-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 8px;
  max-height: 60vh;
  overflow-y: auto;
  padding: 2px;
  margin-top: 10px;
}
.arrange-command-tip {
  font-size: 12px;
  line-height: 1.6;
  color: var(--kanna-text-faint);
  margin-bottom: 8px;
}
.arrange-command-tip code {
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--kanna-hover);
  color: var(--kanna-text);
}
.arrange-command-text {
  margin-bottom: 8px;
}
.arrange-command-text :deep(.el-textarea__inner) {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
}
.arrange-command-note {
  font-size: 12px;
  line-height: 1.6;
  color: var(--kanna-text-faint);
}

@media (max-width: 1100px) {
  .arrange-grid {
    grid-template-columns: 1fr;
  }
  .arrange-normal-dialog-list {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  }
}
@media (max-width: 767px) {
  .arrange-config-row {
    flex-direction: column;
    align-items: stretch;
  }
  .arrange-url-input {
    min-width: 0;
    width: 100%;
  }
  .arrange-config-row .el-button {
    width: 100%;
    margin-left: 0;
  }
}
</style>
