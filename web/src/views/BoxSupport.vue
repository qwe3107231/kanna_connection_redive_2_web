<template>
  <div class="box-page">
    <el-empty v-if="!groupId" description="请先从上方选择一个公会" />

    <template v-else>
      <!-- 使用说明：默认收起，点「使用说明」才展开。
           这段说明有 10 行，常驻会把查询区推到屏幕外，所以做成按钮 + 折叠。 -->
      <div class="help-bar">
        <el-button text size="small" class="help-toggle" @click="showHelp = !showHelp">
          <el-icon><InfoFilled /></el-icon>
          {{ showHelp ? '收起使用说明' : '使用说明' }}
          <el-icon class="help-arrow" :class="{ 'is-open': showHelp }">
            <ArrowDown />
          </el-icon>
        </el-button>
      </div>

      <el-collapse-transition>
        <div v-show="showHelp" class="intro-card kanna-card">
          <div class="intro-head">
            <el-icon :size="18"><InfoFilled /></el-icon>
            <span>BOX / 助战查询</span>
          </div>
          <p class="intro-text">
            数据来自机器人缓存的 BOX / 助战记录，<b>查询本身不会登录游戏、也不会顶号</b>。
            结果以头像列出，<b>点开头像看详细面板</b>（星级 / 等级 / 品级 / 专武 / 装备）。
            头像底部的星星按游戏规则画：<b class="lg-gold">金色</b>=战斗星级，
            <b class="lg-blue">亮蓝</b>=已拥有但被「调星」调下去的，
            <b class="lg-grey">淡蓝</b>=还没到。
            数据不是最新的话，点右侧的<b>刷新缓存</b>按钮 —— 它会临时登录你的游戏账号
            （<b>会短暂顶号</b>），等价于在群里发【刷新box缓存】/【刷新助战缓存】。
            「我的助战」里每张卡片的<b>更换支援</b>同样会顶号，对应群里的
            【上地下城支援】/【上公会战支援】/【上关卡支援】。
          </p>
        </div>
      </el-collapse-transition>

      <!-- 功能切换 + 查询 -->
      <div class="toolbar kanna-card mt-16">
        <div class="toolbar-head">
          <el-radio-group v-model="activeTab" class="type-group">
            <el-radio-button value="self">个人 BOX</el-radio-button>
            <el-radio-button value="clan">公会 BOX</el-radio-button>
            <el-radio-button value="support">公会助战</el-radio-button>
            <el-radio-button value="mine">我的助战</el-radio-button>
          </el-radio-group>

          <!-- 只有「个人 BOX」有「未拥有」概念：灰度列出没有的角色，一眼看出缺什么。
               注意别用 <label> 包 el-switch —— label 会把点击转发给开关内部的
               input，和开关自己的点击处理叠在一起变成「点两次」，开关看起来没反应。 -->
          <div v-if="activeTab === 'self'" class="missing-toggle">
            <el-switch v-model="showMissing" size="small" />
            <span @click="showMissing = !showMissing">显示未拥有</span>
          </div>
        </div>

        <div class="query-row">
          <el-input
            v-if="activeTab !== 'mine'"
            v-model="roleName"
            class="role-input"
            :placeholder="rolePlaceholder"
            clearable
            @keyup.enter="doQuery"
          />
          <el-button
            type="primary"
            :loading="loading"
            :disabled="activeTab === 'clan' && !roleName.trim()"
            @click="doQuery"
          >
            <el-icon v-if="!loading"><Search /></el-icon>查询
          </el-button>

          <!-- 刷新缓存：点一下把「个人 BOX」和「本群公会助战」两份缓存都刷新
               （等价于在群里把两条指令各发一次）。会顶号，所以点之前先弹确认。 -->
          <el-button
            class="refresh-btn"
            :loading="refreshing"
            :disabled="loading"
            :title="refreshHint"
            @click="doRefresh"
          >
            <el-icon v-if="!refreshing"><Refresh /></el-icon>
            {{ refreshLabel }}
          </el-button>
        </div>

        <div class="tip-text">{{ currentTip }}</div>
      </div>

      <!-- 结果：头像网格 -->
      <div class="result-card kanna-card mt-16">
        <div v-if="loading" class="loading-state">
          <el-icon class="is-loading" :size="26"><Loading /></el-icon>
          <span>正在查询，请稍候…</span>
        </div>

        <el-alert
          v-else-if="result && !result.ok"
          :title="result.message"
          type="info"
          show-icon
          :closable="false"
        />

        <template v-else-if="result && result.units.length">
          <div class="result-meta">
            <span v-if="activeTab === 'self'">
              已拥有 <b class="meta-owned">{{ result.owned_count }}</b>
              <template v-if="result.missing_count">
                · 未拥有 <b class="meta-missing">{{ result.missing_count }}</b>
              </template>
            </span>
            <span v-else>共 {{ result.count }} 个角色</span>
            <span class="result-hint">· 点开头像查看详情</span>
          </div>

          <!-- 我的助战：照游戏「支援设定」界面画成三栏卡片（地下城 / 团队战·露娜之塔 /
               冒险），每栏固定 2 个位，空位也占一格。卡片字段与游戏里那张卡一致：
               头像 + 角色名 + 角色等级 + 角色 Rank，底下是【更换支援】按钮。
               按钮对应 QQ 端的【上地下城支援】/【上公会战支援】/【上关卡支援】，
               会登录游戏账号（顶号），所以点之前先弹确认。 -->
          <div v-if="activeTab === 'mine'" class="support-board">
            <div v-for="grp in supportBoard" :key="grp.key" class="support-col">
              <div class="support-col-title">{{ grp.title }}</div>

              <div
                v-for="slot in grp.slots"
                :key="slot.position"
                class="support-card"
                :class="{ 'support-card-empty': !slot.unit }"
              >
                <div class="support-card-head">
                  <div
                    v-if="slot.unit"
                    class="support-card-avatar"
                    :title="slot.unit.chara_name"
                    @click="openDetail(slot.unit)"
                  >
                    <img
                      class="avatar-img"
                      :src="slot.unit.avatar"
                      :alt="slot.unit.chara_name"
                      loading="lazy"
                    />
                  </div>
                  <div v-else class="support-card-avatar support-card-avatar-empty">
                    <el-icon :size="22"><Plus /></el-icon>
                  </div>

                  <div class="support-card-info">
                    <div
                      class="support-card-name"
                      :class="{ 'support-card-name-empty': !slot.unit }"
                      :title="slot.unit ? slot.unit.chara_name : ''"
                    >
                      {{ slot.unit ? slot.unit.chara_name : '未设定' }}
                    </div>
                    <template v-if="slot.unit">
                      <div class="support-card-row">
                        <span class="support-card-label">角色等级</span>
                        <span class="support-card-value">{{ slot.unit.level }}</span>
                      </div>
                      <div class="support-card-row">
                        <span class="support-card-label">角色 Rank</span>
                        <span class="support-card-value">{{ slot.unit.rank }}</span>
                      </div>
                    </template>
                    <div v-else class="support-card-row">
                      <span class="support-card-label">这个支援位还空着</span>
                    </div>
                  </div>
                </div>

                <el-button
                  class="support-card-btn"
                  size="small"
                  :disabled="changing || !grp.mode"
                  @click="openPicker(grp, slot.unit)"
                >
                  {{ slot.unit ? '更换支援' : '设置支援' }}
                </el-button>
              </div>
            </div>
          </div>

          <div v-else class="avatar-grid">
            <div
              v-for="(unit, index) in result.units"
              :key="`${unit.unit_id}-${unit.pcrid}-${index}`"
              class="avatar-cell"
              :class="{ 'avatar-missing': !unit.owned }"
              :title="unit.owned ? unit.chara_name : `${unit.chara_name}（未拥有）`"
              @click="openDetail(unit)"
            >
              <div class="avatar-box">
                <img
                  class="avatar-img"
                  :src="unit.avatar"
                  :alt="unit.chara_name"
                  loading="lazy"
                />
              </div>
              <!-- 公会 BOX / 助战里同一个角色常被多人拥有，只头像会分不清 -->
              <div v-if="showPlayerName" class="avatar-name">
                {{ unit.player_name || '未知玩家' }}
              </div>
            </div>
          </div>
        </template>

        <el-empty v-else description="还没有查询结果" />
      </div>
    </template>

    <!-- 二级菜单：角色详情 -->
    <el-dialog
      v-model="detailVisible"
      :title="detail ? `${detail.chara_name} 详情` : '角色详情'"
      width="560px"
      class="unit-detail-dialog"
    >
      <div v-if="detail" class="detail-body">
        <div class="detail-head">
          <img
            class="detail-avatar"
            :class="{ 'avatar-missing-img': !detail.owned }"
            :src="detail.avatar"
            :alt="detail.chara_name"
          />
          <div class="detail-head-info">
            <div class="detail-name">
              {{ detail.chara_name }}
              <el-tag v-if="!detail.owned" type="info" size="small" effect="plain">
                未拥有
              </el-tag>
            </div>
            <div v-if="detail.owned" class="detail-sub">
              {{ detail.player_name || '未知玩家' }}
              <span v-if="detail.pcrid"> · ID {{ detail.pcrid }}</span>
            </div>
            <div v-else class="detail-sub">你的 BOX 里还没有这个角色</div>
            <div v-if="supportPosText" class="detail-sub">{{ supportPosText }}</div>
          </div>
        </div>

        <template v-if="detail.owned">
          <el-descriptions :column="2" border size="small" class="detail-desc">
            <el-descriptions-item label="星级">{{ detail.rarity }} 星</el-descriptions-item>
            <el-descriptions-item label="战斗星级">
              <!-- 调星：会战里可以把战斗星级调得比拥有星级低（改变 TP 获取节奏）。
                   两者不同时给个提示，不然用户会以为数据错了。 -->
              {{ detail.battle_rarity || detail.rarity }}
              <span
                v-if="detail.battle_rarity && detail.battle_rarity !== detail.rarity"
                class="lowered-tag"
              >
                已调星
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="等级">{{ detail.level }}</el-descriptions-item>
            <el-descriptions-item label="品级">{{ detail.rank }}</el-descriptions-item>
            <el-descriptions-item label="专武">{{ uniqueText }}</el-descriptions-item>
            <el-descriptions-item label="好感">
              <!-- 好感加成文字很长（「物理攻击力：1055，回复量上升：35」），直接铺在
                   表格里很难看：平时只显示「N 级 / 加成」短标签，点一下才弹出完整加成。
                   只有助战有加成文字（个人 BOX / 我的助战只有等级，游戏接口不给助战
                   的好感等级），所以个人 BOX 那边就是个纯文字，没有可点的标签。 -->
              <el-popover v-if="loveBonus" placement="top" trigger="click" :width="260">
                <template #reference>
                  <span class="love-chip">
                    {{ loveText }}
                    <el-icon class="love-chip-icon"><ArrowDown /></el-icon>
                  </span>
                </template>
                <div class="love-bonus-text">{{ loveBonus }}</div>
              </el-popover>
              <span v-else>{{ loveText }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="连结爆发">{{ detail.union_burst }}</el-descriptions-item>
            <el-descriptions-item label="EX 技能">{{ detail.ex }}</el-descriptions-item>
            <el-descriptions-item label="技能 1">{{ detail.main_1 }}</el-descriptions-item>
            <el-descriptions-item label="技能 2">{{ detail.main_2 }}</el-descriptions-item>
          </el-descriptions>

          <div class="detail-section">装备</div>
          <div class="equip-grid">
            <div v-for="cell in equipCells" :key="cell.label" class="equip-cell">
              <div class="equip-label">{{ cell.label }}</div>
              <div class="equip-value">{{ cell.text }}</div>
            </div>
          </div>

          <div class="detail-section">会战 EX 装备</div>
          <div class="equip-grid equip-grid-3">
            <div v-for="cell in exEquipCells" :key="cell.label" class="equip-cell">
              <div class="equip-label">{{ cell.label }}</div>
              <div class="ex-equip-body">
                <img
                  v-if="cell.icon"
                  class="ex-equip-icon"
                  :src="cell.icon"
                  :alt="cell.label"
                  loading="lazy"
                />
                <div class="equip-value" :class="{ 'equip-empty': !cell.id }">
                  {{ cell.text }}
                </div>
              </div>
            </div>
          </div>
        </template>

        <el-alert
          v-else
          title="未拥有这个角色，所以没有等级 / 专武 / 装备数据。"
          type="info"
          show-icon
          :closable="false"
        />
      </div>
    </el-dialog>

    <!-- 选人弹窗：点【更换支援】/【设置支援】后，从自己的 BOX 里挑一个角色挂上去。
         只列 Lv>10 的（游戏规定 Lv10 以上才能当支援）。 -->
    <el-dialog
      v-model="pickerVisible"
      :title="pickerTitle"
      width="640px"
      class="support-picker-dialog"
    >
      <div class="picker-head">
        <el-input
          v-model="pickerKeyword"
          class="picker-search"
          placeholder="输入角色名筛选"
          clearable
        />
        <span class="picker-count">{{ pickerUnits.length }} 个可选</span>
      </div>

      <div class="picker-body">
        <div v-if="pickerLoading" class="picker-loading">
          <el-icon class="is-loading" :size="22"><Loading /></el-icon>
          <span>正在读取你的 BOX…</span>
        </div>

        <el-alert
          v-else-if="pickerMessage"
          :title="pickerMessage"
          type="info"
          show-icon
          :closable="false"
        />

        <el-empty
          v-else-if="!pickerUnits.length"
          :description="
            pickerKeyword ? '没有匹配的角色' : '没有可上阵的角色（等级需 > 10）'
          "
        />

        <div v-else class="picker-grid">
          <div
            v-for="u in pickerUnits"
            :key="u.unit_id"
            class="picker-cell"
            :class="{ 'picker-cell-active': u.unit_id === pickerSelected }"
            :title="`${u.chara_name} Lv.${u.level}`"
            @click="pickerSelected = u.unit_id"
          >
            <div class="picker-avatar">
              <img :src="u.avatar" :alt="u.chara_name" loading="lazy" />
            </div>
            <div class="picker-name">{{ u.chara_name }}</div>
            <div class="picker-lv">Lv.{{ u.level }}</div>
          </div>
        </div>
      </div>

      <template #footer>
        <span class="picker-footer-tip">会临时登录你的游戏账号，把正在游戏的你挤下线</span>
        <el-button @click="pickerVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!pickerSelected"
          :loading="changing"
          @click="confirmChange"
        >
          确定更换
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  changeSupport,
  queryBox,
  queryClanBox,
  queryClanSupport,
  queryMySupport,
  refreshCache,
} from '@/api'
import type { BoxQueryResult, BoxUnit } from '@/types'
import { useUserStore } from '@/store/user'

const props = defineProps<{ groupId?: number }>()
const route = useRoute()
const userStore = useUserStore()

// 与 Dashboard / Report / Notice 一致：URL 参数 > props > store
const groupId = computed<number>(
  () => Number(route.params.groupId) || props.groupId || userStore.currentClanId,
)

type TabKey = 'self' | 'clan' | 'support' | 'mine'
const activeTab = ref<TabKey>('self')
// 顶部的使用说明默认收起（那段文字太长，常驻会把查询区挤出首屏）
const showHelp = ref(false)
const roleName = ref('')
const loading = ref(false)
const refreshing = ref(false)
const result = ref<BoxQueryResult | null>(null)
// 个人 BOX：是否把「未拥有」的角色也灰度列出来（一眼看出缺什么）
const showMissing = ref(true)

const detail = ref<BoxUnit | null>(null)
const detailVisible = ref(false)

const TIPS: Record<TabKey, string> = {
  self: '默认显示整个 box（含未拥有，灰度显示）；也可以输入角色名只看某一个。',
  clan: '查本群所有绑定过公会的成员里，谁有这个角色（不支持「所有」）。',
  support: '默认显示本群缓存的全部公会战助战（对应 QQ 端的【精确助战】）；也可以输入角色名筛选。',
  mine: '你当前挂着的助战，按游戏「支援设定」的三栏排成卡片（对应 QQ 端的【我的助战】）；卡片的【更换支援】会把这一栏换成你从 BOX 里挑的角色（会顶号）。',
}
const currentTip = computed(() => TIPS[activeTab.value])

// 搜索框提示按页签给：公会助战一进来就是全部，不写「所有」；
// 公会 BOX 后端也不支持「所有」（人多会卡死），同样不写。
const ROLE_PLACEHOLDER: Record<TabKey, string> = {
  self: '输入角色名（如 环奈 / 所有）',
  clan: '输入角色名（如 环奈）',
  support: '输入角色名（如 环奈）',
  mine: '',
}
const rolePlaceholder = computed(() => ROLE_PLACEHOLDER[activeTab.value])

// 进入这几个页签就自动查一次，不用先点「查询」：
//   个人 BOX / 公会助战 → 默认查「所有」；我的助战 → 本身就是全部（也没有搜索框）
const AUTO_LOAD_TABS: TabKey[] = ['self', 'support', 'mine']
const isAutoLoad = (tab: TabKey) => AUTO_LOAD_TABS.includes(tab)
// 不填角色名也能查的页签（不填 = 看全部）
const allowEmptyQuery = (tab: TabKey) => tab === 'self' || tab === 'support'

// 「我的助战」三栏：顺序照游戏「支援设定」界面（左→右：地下城 / 团队战·露娜之塔 /
// 冒险），每栏固定 2 个位。
//   positions = 该栏在库里的助战位编号（口径见 `database/models.py` 的
//     support_position 注释：1/2 冒险、3/4 地下城、5/6 团队战·露娜之塔）
//   mode = QQ 端【上XX支援】用的栏位编号（1 地下城 / 2 团队战·露娜塔 / 3 关卡），
//     更换支援要按它传
const SUPPORT_COLUMNS: {
  key: string
  title: string
  mode: number
  positions: number[]
}[] = [
  { key: 'dungeon', title: '地下城', mode: 1, positions: [3, 4] },
  { key: 'clan', title: '团队战 · 露娜之塔', mode: 2, positions: [5, 6] },
  { key: 'adventure', title: '冒险', mode: 3, positions: [1, 2] },
]

// 每栏固定 2 格，把后端给的助战按 support_position 填进对应的格子；
// 空的格子也要占位（和游戏界面一样），这样一眼能看出哪个位还空着。
const supportBoard = computed(() => {
  const units = result.value?.units ?? []
  const cols = SUPPORT_COLUMNS.map((col) => ({
    ...col,
    slots: col.positions.map((position) => ({
      position,
      unit: units.find((u) => u.support_position === position) ?? null,
    })),
  }))
  // 库里出现认不出来的助战位（脏数据 / 以后游戏加了新栏位）时，别让这些角色
  // 凭空消失 —— 单独兜一栏出来。这一栏没有对应的 mode，按钮会禁用。
  const known = new Set(SUPPORT_COLUMNS.flatMap((c) => c.positions))
  const rest = units.filter((u) => !known.has(u.support_position))
  if (rest.length) {
    cols.push({
      key: 'other',
      title: '其他',
      mode: 0,
      positions: rest.map((u) => u.support_position),
      slots: rest.map((u) => ({ position: u.support_position, unit: u })),
    })
  }
  return cols
})

// 个人 BOX / 我的助战 里玩家名就是你自己，重复显示没意义；
// 公会 BOX / 助战 才是「同角色多人拥有」，必须靠名字区分。
const showPlayerName = computed(
  () => activeTab.value === 'clan' || activeTab.value === 'support',
)

// 进入页面 / 切群 / 切页签时的默认加载
function autoLoad() {
  if (!groupId.value) return
  if (isAutoLoad(activeTab.value) || roleName.value.trim()) doQuery()
}

// 切换功能时清掉上一次的结果、输入与详情，避免张冠李戴；
// 个人 BOX / 公会助战 / 我的助战 切过来就直接出内容
watch(activeTab, () => {
  result.value = null
  roleName.value = ''
  closeDetail()
  autoLoad()
})

// 挂载时（immediate）以及切群后 groupId 变化时重新加载。
// immediate 时 store 里的 currentClanId 可能还是 0，doQuery 会自己挡掉，
// 等 store 加载完 groupId 变了会再触发一次。
watch(
  groupId,
  () => {
    result.value = null
    closeDetail()
    autoLoad()
  },
  { immediate: true },
)

// 已经查过「所有」了再切开关，不该让用户重新点一次查询
watch(showMissing, () => {
  if (activeTab.value === 'self' && result.value?.ok) doQuery()
})

function openDetail(unit: BoxUnit) {
  detail.value = unit
  detailVisible.value = true
}

function closeDetail() {
  detailVisible.value = false
  detail.value = null
}

// 专武：-1 / 0 都当没装备（-1 是后端约定的「未装备」，0 是旧数据）
const uniqueText = computed(() => {
  const u = detail.value
  if (!u || !u.unique_level || u.unique_level < 0) return '未装备'
  return u.unique_level2 && u.unique_level2 > 0
    ? `${u.unique_level} / ${u.unique_level2}`
    : String(u.unique_level)
})

// 好感加成文字：只有助战有（个人 BOX / 我的助战拿不到，游戏接口也不给助战的好感等级）
const loveBonus = computed(() => detail.value?.special_attribute || '')

// 好感：个人 BOX / 我的助战有真实等级就显示「N 级」；助战没有等级，显示「加成」。
// 完整加成文字在点击弹出的 popover 里 —— 平铺进表格太长，不好看。
const loveText = computed(() => {
  const u = detail.value
  if (!u) return '—'
  if (u.love_level) return `${u.love_level} 级`
  return u.special_attribute ? '加成' : '—'
})

// 助战位 -> 中文。位置口径见 `database/models.py` 的 support_position 注释：
// 1/2 冒险、3/4 地下城、5/6 团队战·露娜塔，每栏各 2 个位。
const SUPPORT_POS_LABEL: Record<number, string> = {
  1: '冒险助战位 1',
  2: '冒险助战位 2',
  3: '地下城助战位 1',
  4: '地下城助战位 2',
  5: '团队战助战位 1',
  6: '团队战助战位 2',
}
const supportPosText = computed(() => {
  const pos = detail.value?.support_position ?? 0
  return pos ? SUPPORT_POS_LABEL[pos] || `助战位 ${pos}` : ''
})

const EQUIP_LABELS = ['左上', '右上', '左中', '右中', '左下', '右下']

// 装备值可能是数字（强化星级）也可能是文字（未装备 / 无）
function equipText(value: string) {
  if (!value) return '—'
  return /^\d+$/.test(value) ? `${value}★` : value
}

const equipCells = computed(() => {
  const u = detail.value
  if (!u) return []
  const values = [u.equip_1, u.equip_2, u.equip_3, u.equip_4, u.equip_5, u.equip_6]
  return EQUIP_LABELS.map((label, i) => ({
    label,
    text: equipText(values[i] ?? ''),
  }))
})

const exEquipCells = computed(() => {
  const u = detail.value
  if (!u) return []
  const ids = [u.cb_ex_equip_1, u.cb_ex_equip_2, u.cb_ex_equip_3]
  const levels = [u.cb_ex_equip_1_level, u.cb_ex_equip_2_level, u.cb_ex_equip_3_level]
  // 图标地址后端给（和 QQ 端出图用同一份缓存资源），前端不拼路径
  const icons = [u.cb_ex_equip_1_icon, u.cb_ex_equip_2_icon, u.cb_ex_equip_3_icon]
  return [0, 1, 2].map((i) => ({
    label: `EX ${i + 1}`,
    id: ids[i],
    icon: icons[i] || '',
    text: ids[i] ? `Lv.${levels[i]}` : '未装备',
  }))
})

async function doQuery() {
  if (!groupId.value) return
  const tab = activeTab.value
  // 个人 BOX / 公会助战：不填角色名 = 看全部（进入这两个页签时也会自动查一次）；
  // 我的助战压根没有搜索框，也不需要角色名。
  const name = roleName.value.trim() || (allowEmptyQuery(tab) ? '所有' : '')
  if (!name && tab !== 'mine') {
    ElMessage.warning('请输入角色名')
    return
  }

  loading.value = true
  result.value = null
  closeDetail()
  try {
    if (tab === 'self') {
      result.value = await queryBox(groupId.value, name, showMissing.value)
    } else if (tab === 'clan') {
      result.value = await queryClanBox(groupId.value, name)
    } else if (tab === 'support') {
      result.value = await queryClanSupport(groupId.value, name)
    } else {
      result.value = await queryMySupport(groupId.value)
    }
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    loading.value = false
  }
}

// ---- 刷新缓存 ----
//
// 只有一个按钮：点一下**把两份缓存都刷新**（个人 BOX + 本群公会助战），
// 等价于在群里先后发【刷新box缓存】和【刷新助战缓存】。
// 两份共用同一次登录（不会比只刷一份更慢），但都会**真的登录游戏账号**（顶号），
// 所以点之前必须弹确认。
const refreshLabel = '刷新缓存'
const refreshHint =
  '重新登录你的游戏账号（会短暂顶号），一次把「个人 BOX」和「本群公会助战」两份缓存都刷新'

async function doRefresh() {
  if (!groupId.value || refreshing.value) return
  try {
    await ElMessageBox.confirm(
      '刷新会临时登录你的游戏账号（把正在游戏的你挤下线），一次刷新「个人 BOX」和「本群公会助战」两份缓存，大约需要几秒。确定现在刷新吗？',
      '刷新缓存',
      { type: 'warning', confirmButtonText: '确定刷新', cancelButtonText: '再等等' },
    )
  } catch {
    // 用户取消
    return
  }

  refreshing.value = true
  try {
    const res = await refreshCache(groupId.value)
    if (!res.ok) {
      // 没绑号 / 正在刷新中 / 整体失败
      ElMessage.warning(res.message)
      return
    }
    // 个人 BOX 刷成了、只有公会助战没刷成（例如现在不是会战期间）时用 warning，
    // 文案里已经把两边都讲清楚了。
    if (res.support_error) ElMessage.warning(res.message)
    else ElMessage.success(res.message)
    // BOX 缓存重拉过之后，选人弹窗里那份也得作废重取（等级可能变了）
    myBoxUnits.value = []
    // 刷完自动重查一遍，用户不用再点一次「查询」
    await doQuery()
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    refreshing.value = false
  }
}

// ---- 更换支援（「我的助战」） ----
//
// 对应 QQ 群的【上地下城支援】/【上公会战支援】/【上关卡支援】，后端调的是同一个
// `support_query.util.change_support_unit`。⚠️ 它是**写操作**：会登录你的游戏账号
// 并真的改游戏里的支援设定（顶号），所以确认弹窗里必须把这点说清楚。
const changing = ref(false)
const pickerVisible = ref(false)
const pickerLoading = ref(false)
const pickerKeyword = ref('')
const pickerSelected = ref(0)
const pickerMode = ref(0)
const pickerColumnTitle = ref('')
// 打开弹窗时那一格里原来是谁（0 = 空位）；用它拦掉「选了一个已经挂在这个位的角色」
// 这种必然失败、却会白白顶号一次的提交
const pickerCurrentId = ref(0)
const pickerMessage = ref('')
// 自己 BOX 的全部已拥有角色（懒加载 + 缓存，刷新 BOX 缓存后作废）
const myBoxUnits = ref<BoxUnit[]>([])

const pickerTitle = computed(() =>
  pickerColumnTitle.value ? `更换「${pickerColumnTitle.value}」支援` : '更换支援',
)

// 只列 Lv>10 的（游戏规定 Lv10 以上才能当支援），再按输入的角色名筛一遍
const pickerUnits = computed(() => {
  const kw = pickerKeyword.value.trim()
  return myBoxUnits.value.filter(
    (u) => u.owned && u.level > 10 && (!kw || u.chara_name.includes(kw)),
  )
})

async function ensureMyBox() {
  if (!groupId.value || myBoxUnits.value.length || pickerLoading.value) return
  pickerLoading.value = true
  try {
    // include_missing=false：选人只要已拥有的，未拥有的灰度占位在这里没意义
    const res = await queryBox(groupId.value, '所有', false)
    if (res.ok) {
      myBoxUnits.value = res.units
    } else {
      pickerMessage.value = res.message || '读取你的 BOX 失败'
    }
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    pickerLoading.value = false
  }
}

function openPicker(
  grp: { key: string; title: string; mode: number },
  unit: BoxUnit | null,
) {
  if (!grp.mode) return
  pickerMode.value = grp.mode
  pickerColumnTitle.value = grp.title
  pickerCurrentId.value = unit ? unit.unit_id : 0
  pickerKeyword.value = ''
  pickerSelected.value = 0
  pickerMessage.value = ''
  pickerVisible.value = true
  void ensureMyBox()
}

async function confirmChange() {
  if (!groupId.value || !pickerSelected.value || changing.value) return
  const unit = pickerUnits.value.find((u) => u.unit_id === pickerSelected.value)
  if (!unit) return
  if (unit.unit_id === pickerCurrentId.value) {
    // 后端在真正改之前就会因为「已经在支援中」退回来，但那一步已经登录过账号了
    // —— 白顶一次号，所以这里先拦掉
    ElMessage.warning(`${unit.chara_name} 已经挂在这个位上了`)
    return
  }

  try {
    await ElMessageBox.confirm(
      `会把「${unit.chara_name}」挂到「${pickerColumnTitle.value}」支援。` +
        '这一步会临时登录你的游戏账号（把正在游戏的你挤下线），并真的改游戏里的支援设定；' +
        '栏位满了会顶掉挂得最久的那一个。确定吗？',
      '更换支援',
      { type: 'warning', confirmButtonText: '确定更换', cancelButtonText: '再想想' },
    )
  } catch {
    // 用户取消
    return
  }

  changing.value = true
  try {
    const res = await changeSupport(groupId.value, {
      unit_id: unit.unit_id,
      mode: pickerMode.value,
    })
    if (res.ok) {
      // 后端提示可能是两行（「成功终止…\n成功将…」），弹窗里换成一行更好看
      ElMessage.success(res.message.replace(/\n/g, '；'))
      pickerVisible.value = false
      // 后端换完已经顺手改过本地缓存的助战位了，重查一次就是最新的
      await doQuery()
    } else {
      ElMessage.warning(res.message)
    }
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    changing.value = false
  }
}
</script>

<style scoped>
.box-page {
  display: flex;
  flex-direction: column;
}
.mt-16 {
  margin-top: 16px;
}
.intro-card {
  padding: 16px 18px;
}
/* 使用说明的折叠开关：一条细栏，靠右对齐，展开后下面才是说明卡片 */
.help-bar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 4px;
}
.help-toggle {
  color: #9ca3af;
  font-size: 12px;
}
.help-toggle:hover {
  color: var(--kanna-primary);
}
.help-arrow {
  transition: transform 0.2s ease;
}
.help-arrow.is-open {
  transform: rotate(180deg);
}
.intro-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #831843;
}
.intro-text {
  margin: 8px 0 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.7;
}
/* 说明文字里的星星颜色小标记（与头像底部实际画的星星颜色对应） */
.lg-gold {
  color: #c98a12;
}
.lg-blue {
  color: #2b6fe0;
}
.lg-grey {
  color: #8b95a3;
}
.toolbar {
  padding: 16px 18px;
}
.type-group {
  flex-wrap: wrap;
}
.toolbar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.missing-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #6b7280;
  cursor: pointer;
  user-select: none;
}
.query-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
}
.role-input {
  max-width: 320px;
}
/* 刷新缓存按钮：固定在「查询」右边，文案不随页签变（两份缓存一次刷完） */
.refresh-btn {
  flex: none;
}
.tip-text {
  margin-top: 10px;
  color: #9ca3af;
  font-size: 12px;
  line-height: 1.6;
}
.result-card {
  padding: 16px 18px;
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
.result-meta {
  color: #9ca3af;
  font-size: 12px;
  margin-bottom: 12px;
}
.result-hint {
  margin-left: 4px;
  color: #c4c8ce;
}
.meta-owned {
  color: #db2777;
}
.meta-missing {
  color: #9ca3af;
}

/* 「我的助战」三栏卡片：照游戏「支援设定」界面（地下城 / 团队战·露娜之塔 / 冒险），
   每栏固定 2 个位、空位也占一格。桌面端并排三栏，窄屏自动落成一列。 */
.support-board {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.support-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px solid #eef0f3;
  border-radius: 10px;
  padding: 10px 12px 12px;
  background: rgba(0, 0, 0, 0.012);
  min-width: 0;
}
.support-col-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.support-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid #eef0f3;
  border-radius: 10px;
  padding: 8px;
  background: #fff;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.support-card:hover {
  border-color: #f9a8d4;
  box-shadow: 0 4px 12px rgba(219, 39, 119, 0.1);
}
/* 空位：虚线框 + 淡色，和已挂上的卡片一眼区分开 */
.support-card-empty {
  border-style: dashed;
  background: rgba(0, 0, 0, 0.012);
}
.support-card-empty:hover {
  border-color: #d1d5db;
  box-shadow: none;
}
.support-card-head {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.support-card-avatar {
  width: 56px;
  height: 56px;
  flex: none;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #eef0f3;
  background: rgba(0, 0, 0, 0.03);
  cursor: pointer;
}
.support-card-avatar-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c4c8ce;
  cursor: default;
}
.support-card-info {
  flex: 1;
  min-width: 0;
}
.support-card-name {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.support-card-name-empty {
  color: #9ca3af;
  font-weight: 500;
}
.support-card-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  font-size: 12px;
  min-width: 0;
}
.support-card-label {
  color: #9ca3af;
  flex: none;
}
.support-card-value {
  color: #374151;
  font-weight: 600;
}
.support-card-btn {
  width: 100%;
}

/* ---- 更换支援：选人弹窗 ---- */
.picker-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.picker-search {
  max-width: 260px;
}
.picker-count {
  color: #9ca3af;
  font-size: 12px;
}
/* 角色多（一整个 box）时让列表自己滚，别把弹窗撑出屏幕 */
.picker-body {
  max-height: 46vh;
  overflow-y: auto;
}
.picker-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #9ca3af;
  padding: 40px 0;
}
.picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: 10px 8px;
}
.picker-cell {
  cursor: pointer;
  text-align: center;
  min-width: 0;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 4px 2px;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.picker-cell:hover {
  background: rgba(219, 39, 119, 0.05);
}
.picker-cell-active {
  border-color: #db2777;
  background: rgba(219, 39, 119, 0.08);
}
.picker-avatar {
  aspect-ratio: 1 / 1;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #eef0f3;
  background: rgba(0, 0, 0, 0.03);
}
.picker-avatar img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.picker-name {
  margin-top: 3px;
  font-size: 12px;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.picker-lv {
  font-size: 11px;
  color: #9ca3af;
}
.picker-footer-tip {
  float: left;
  font-size: 12px;
  color: #9ca3af;
  line-height: 32px;
}

/* ================= 头像网格 ================= */
.avatar-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(76px, 1fr));
  gap: 14px 10px;
}
.avatar-cell {
  cursor: pointer;
  text-align: center;
  /* 窄屏下数字/长名字不要从中间断开 */
  min-width: 0;
}
.avatar-box {
  position: relative;
  aspect-ratio: 1 / 1;
  border-radius: 10px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.03);
  border: 1px solid #eef0f3;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}
.avatar-cell:hover .avatar-box {
  transform: translateY(-2px);
  border-color: #f9a8d4;
  box-shadow: 0 6px 14px rgba(219, 39, 119, 0.16);
}
.avatar-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-name {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.3;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 未拥有：整块灰度 + 降透明度，和已拥有的一眼区分开 */
.avatar-missing .avatar-box {
  filter: grayscale(1);
  opacity: 0.4;
}
.avatar-missing:hover .avatar-box {
  opacity: 0.7;
  border-color: #d1d5db;
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.08);
}
.avatar-missing-img {
  filter: grayscale(1);
  opacity: 0.5;
}

/* ================= 详情弹窗 ================= */
.detail-body {
  display: flex;
  flex-direction: column;
}
.detail-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}
.detail-avatar {
  width: 84px;
  height: 84px;
  border-radius: 12px;
  border: 1px solid #eef0f3;
  background: rgba(0, 0, 0, 0.03);
  flex: none;
}
.detail-head-info {
  min-width: 0;
}
.detail-name {
  font-size: 17px;
  font-weight: 600;
  color: #111827;
}
.detail-sub {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
}
.detail-desc {
  margin-bottom: 4px;
}
/* 「已调星」小标：战斗星级 != 拥有星级时才出现 */
.lowered-tag {
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 4px;
  font-size: 11px;
  color: #2b6fe0;
  background: rgba(43, 111, 224, 0.1);
}

/* 好感：平时只显示短标签（N 级 / 加成），点开才看完整加成 */
.love-chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: #db2777;
  cursor: pointer;
  border-bottom: 1px dashed rgba(219, 39, 119, 0.45);
  line-height: 1.4;
}
.love-chip-icon {
  font-size: 11px;
}
.love-bonus-text {
  font-size: 13px;
  line-height: 1.7;
  color: #374151;
  /* 别用 break-all —— 会把「回复量上升：35」的 35 拆成两行 */
  word-break: normal;
}
.detail-section {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.equip-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.equip-grid-3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.equip-cell {
  border: 1px solid #eef0f3;
  border-radius: 8px;
  padding: 6px 8px;
  background: rgba(0, 0, 0, 0.015);
  min-width: 0;
}
.equip-label {
  font-size: 11px;
  color: #9ca3af;
}
.equip-value {
  margin-top: 2px;
  font-size: 13px;
  color: #374151;
  word-break: break-all;
}
.equip-empty {
  color: #c4c8ce;
}
/* 会战 EX 装备：图标 + 等级并排 */
.ex-equip-body {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 3px;
}
.ex-equip-icon {
  width: 34px;
  height: 34px;
  border-radius: 6px;
  border: 1px solid #eef0f3;
  background: rgba(0, 0, 0, 0.02);
  object-fit: contain;
  flex: none;
}

/* ================= 手机端（< 768px） ================= */
@media (max-width: 767px) {
  .intro-card,
  .toolbar,
  .result-card {
    padding: 12px;
  }
  .intro-head {
    font-size: 15px;
  }
  .query-row {
    flex-wrap: wrap;
  }
  .role-input {
    max-width: none;
    flex: 1;
    min-width: 0;
  }
  /* 手机上「查询」+「刷新缓存」挤一行会很难看，让刷新按钮落到下一行靠右 */
  .refresh-btn {
    margin-left: auto;
  }
  .avatar-grid {
    grid-template-columns: repeat(auto-fill, minmax(64px, 1fr));
    gap: 12px 8px;
  }
  /* 三栏在手机上落成一列，否则每栏太窄头像看不清 */
  .support-board {
    grid-template-columns: 1fr;
  }
  /* 选人弹窗：手机上让搜索框占满一行，底部那行小字挤不下就不显示 */
  .picker-head {
    flex-wrap: wrap;
  }
  .picker-search {
    max-width: none;
    flex: 1;
  }
  .picker-footer-tip {
    display: none;
  }
  .detail-head {
    gap: 10px;
  }
  .detail-avatar {
    width: 64px;
    height: 64px;
  }
  .equip-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
