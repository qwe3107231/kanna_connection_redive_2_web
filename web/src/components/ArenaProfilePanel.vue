<template>
  <div class="pf-card">
    <div class="pf-head">
      <img class="pf-avatar" :src="avatarUrl(result.unit_id)" alt="" />
      <div class="pf-main">
        <div class="pf-name">{{ result.name || '（无昵称）' }}</div>
        <div class="pf-comment">
          {{ result.comment || '（无签名）' }}
        </div>
        <div class="pf-clan" v-if="result.clan_name">
          公会：{{ result.clan_name }}
        </div>
      </div>
      <div class="pf-id">ID {{ result.viewer_id }}</div>
    </div>

    <!-- 基础信息：只留最常用的 4 项，其余按游戏资料页做成下面的分组卡片 -->
    <div class="pf-grid">
      <div class="pf-item">
        <span class="k">团队等级</span>
        <span class="v">{{ result.team_level }}</span>
      </div>
      <div class="pf-item">
        <span class="k">总战力</span>
        <span class="v">{{ result.total_power.toLocaleString() }}</span>
      </div>
      <div class="pf-item">
        <span class="k">好友数</span>
        <span class="v">{{ result.friend_num }}</span>
      </div>
      <div class="pf-item">
        <span class="k">上次登录时间</span>
        <span class="v">{{ fmtTime(result.last_login_time) }}</span>
      </div>
    </div>

    <!-- 对方挂的助战（游戏资料页本来就有；后端 profile/get_profile 自带）。
         三组各一张小卡片：分组色标签 + 金框头像 + 角色名，空位也占一格。 -->
    <template v-if="hasSupport">
      <div class="pf-sub">助战</div>
      <div class="pf-support">
        <div
          v-for="g in supportGroups"
          :key="g.key"
          class="pf-support-group"
          :class="`pf-support-group-${g.key}`"
        >
          <div class="pf-support-title">{{ g.title }}</div>
          <div class="pf-support-slots">
            <div
              v-for="slot in g.slots"
              :key="slot.position"
              class="pf-support-slot"
              :class="{ 'pf-support-slot-empty': !slot.unit }"
              :title="
                slot.unit
                  ? `${slot.unit.chara_name} Lv.${slot.unit.level} / Rank ${slot.unit.rank}`
                  : '未设定'
              "
            >
              <div class="pf-support-avatar-box">
                <img
                  v-if="slot.unit"
                  class="pf-support-avatar"
                  :src="avatarUrl(slot.unit.unit_id, slot.unit.rarity, slot.unit.battle_rarity)"
                  :alt="slot.unit.chara_name"
                  loading="lazy"
                />
                <div v-else class="pf-support-none">未设定</div>
              </div>
              <div class="pf-support-name">
                {{ slot.unit ? slot.unit.chara_name : '' }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 游戏资料页同款卡片：左边「图标 + 名称牌」，右边「彩色标签 + 点线 + 数值」。
         分组顺序照游戏：竞技场 → 公主竞技场 → 解锁数 → 露娜之塔 → 关卡达成数 → 深域。 -->
    <div class="pf-gcard">
      <div class="pf-gplate">
        <div class="pf-gname">竞技场</div>
      </div>
      <div class="pf-gbody">
        <div class="pf-grow">
          <span class="pf-gpill">创建日</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">{{ fmtDate(result.arena_time) }}</span>
        </div>
        <div class="pf-grow">
          <span class="pf-gpill">排名</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">
            {{ result.arena_rank ? `${result.arena_rank} 位` : '- 位' }}
            <span v-if="result.arena_group" class="pf-gsub">
              （第 {{ result.arena_group }} 场）
            </span>
          </span>
        </div>
      </div>
    </div>

    <div class="pf-gcard">
      <div class="pf-gplate">
        <div class="pf-gname">公主竞技场</div>
      </div>
      <div class="pf-gbody">
        <div class="pf-grow">
          <span class="pf-gpill">创建日</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">{{ fmtDate(result.grand_arena_time) }}</span>
        </div>
        <div class="pf-grow">
          <span class="pf-gpill">排名</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">
            {{ result.grand_arena_rank ? `${result.grand_arena_rank} 位` : '- 位' }}
            <span v-if="result.grand_arena_group" class="pf-gsub">
              （第 {{ result.grand_arena_group }} 场）
            </span>
          </span>
        </div>
      </div>
    </div>

    <div class="pf-gcard">
      <div class="pf-gplate">
        <div class="pf-gname">解锁数</div>
      </div>
      <div class="pf-gbody">
        <div class="pf-grow">
          <span class="pf-gpill">角色</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">{{ result.unit_num }}</span>
        </div>
        <div class="pf-grow">
          <span class="pf-gpill">剧情</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">{{ result.open_story_num }}</span>
        </div>
      </div>
    </div>

    <div class="pf-gcard">
      <div class="pf-gplate">
        <div class="pf-gname">露娜之塔</div>
      </div>
      <div class="pf-gbody">
        <div class="pf-grow">
          <span class="pf-gpill">已通关的阶层</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">{{ result.tower_cleared_floor_num }} 层</span>
        </div>
        <div class="pf-grow">
          <span class="pf-gpill">特别挑战关卡</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">{{ result.tower_cleared_ex_quest_count }}</span>
        </div>
      </div>
    </div>

    <div class="pf-gcard">
      <div class="pf-gplate">
        <div class="pf-gname">关卡达成数</div>
      </div>
      <div class="pf-gbody">
        <div class="pf-grow">
          <span class="pf-gpill">普通</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">{{ result.quest_normal }}</span>
        </div>
        <div class="pf-grow">
          <span class="pf-gpill pf-gpill-red">困难</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">{{ result.quest_hard }}</span>
        </div>
        <div class="pf-grow">
          <span class="pf-gpill pf-gpill-purple">高难</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">{{ result.quest_very_hard }}</span>
        </div>
        <div class="pf-grow">
          <span class="pf-gpill pf-gpill-green">支线</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">{{ result.quest_byway }}</span>
        </div>
      </div>
    </div>

    <div class="pf-gcard">
      <div class="pf-gplate">
        <div class="pf-gname">深域</div>
      </div>
      <div class="pf-gbody">
        <div class="pf-grow" v-for="(t, i) in result.talent" :key="i">
          <span class="pf-gpill" :class="TALENT_PILLS[i]">{{ TALENT_NAMES[i] }}</span>
          <span class="pf-gline"></span>
          <span class="pf-gvalue">{{ fmtTalent(t) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ArenaProfileResult } from '@/types'
import { API_BASE } from '@/utils/request'

// 从 Arena.vue 的「查 ID」资料卡抽出来的组件：竞技场查 ID 与好友详情弹窗共用，
// 保证两处看到的资料卡一模一样（外观 / 字段都只在这一份里改）。
const props = defineProps<{ result: ArenaProfileResult; groupId: number }>()

// 助战分组：与「我的助战」三栏顺序保持一致（地下城 → 团队战·露娜之塔 → 冒险/好友），
// 每组 2 个位。后端 `jjckiller.model._support_units_for_profile` 已把 position
// 归一化成组内 1/2/3/4，这里按组把「有挂的」填进对应格子，空的也占一格（和游戏界面一样）。
const SUPPORT_GROUPS = [
  { key: 'dungeon', title: '地下城支援', positions: [1, 2] },
  { key: 'clan', title: '团队战支援', positions: [3, 4] },
  { key: 'friend', title: '好友支援', positions: [1, 2] },
] as const

const supportGroups = computed(() => {
  const units = props.result.support_units ?? []
  return SUPPORT_GROUPS.map((g) => ({
    key: g.key,
    title: g.title,
    slots: g.positions.map((position) => ({
      position,
      unit: units.find((u) => u.group === g.key && u.position === position) ?? null,
    })),
  }))
})
const hasSupport = computed(() =>
  supportGroups.value.some((g) => g.slots.some((s) => s.unit)),
)

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
  return `${API_BASE}/${props.groupId}/box/avatar/${unitId}?${params.toString()}`
}

/** 时间戳（秒；个别接口给的是毫秒会自动换算）→ M-D HH:mm */
function fmtTime(ts: number) {
  if (!ts) return '-'
  const seconds = ts > 1e12 ? Math.floor(ts / 1000) : ts
  const d = new Date(seconds * 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** 时间戳 → YYYY/M/D（游戏资料页「创建日」的写法）；0 = 未知 */
function fmtDate(ts: number) {
  if (!ts) return '-'
  const seconds = ts > 1e12 ? Math.floor(ts / 1000) : ts
  const d = new Date(seconds * 1000)
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

/** 深域进度：clear_count → 「大关-小关」，0 显示 0-0（与 autopcr 一致） */
function fmtTalent(value: number) {
  if (!value || value <= 0) return '0-0'
  return `${Math.floor((value - 1) / 10) + 1}-${((value - 1) % 10) + 1}`
}

// 深域 5 属性的名字与标签配色（火红 / 水蓝 / 风绿 / 光橙 / 暗紫）
const TALENT_NAMES = ['火', '水', '风', '光', '暗']
const TALENT_PILLS = [
  'pf-gpill-red',
  'pf-gpill-blue',
  'pf-gpill-green',
  'pf-gpill-orange',
  'pf-gpill-purple',
]
</script>

<style scoped>
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
  border-bottom: 1px dashed var(--kanna-divider-blue);
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
  color: var(--kanna-pink-deep);
}
.pf-comment {
  margin-top: 4px;
  font-size: 13px;
  color: var(--kanna-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pf-clan {
  margin-top: 4px;
  font-size: 12px;
  color: var(--kanna-text-faint);
}
.pf-id {
  flex: none;
  font-size: 13px;
  color: var(--kanna-text-faint);
}
.pf-sub {
  font-size: 13px;
  font-weight: 600;
  color: var(--kanna-text-secondary);
  padding-top: 6px;
  border-top: 1px dashed var(--kanna-divider-blue);
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
  color: var(--kanna-text-faint);
  min-width: 0;
}
.pf-item .v {
  flex: none;
  font-size: 14px;
  font-weight: 600;
  color: var(--kanna-text-secondary);
  text-align: right;
  word-break: break-all;
}
.pf-item .v em {
  font-size: 12px;
  font-weight: 400;
  font-style: normal;
  color: var(--kanna-text-faint);
}

/* ================= 游戏资料页同款分组卡片 ================= */
/* 左边「浅蓝名称牌」，右边「彩色标签 + 点线 + 数值」 */
.pf-gcard {
  display: flex;
  align-items: stretch;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 12px;
  border: 1px solid rgba(120, 150, 200, 0.28);
  background: linear-gradient(180deg, #ffffff 0%, #f7faff 100%);
  box-shadow: 0 1px 4px rgba(74, 144, 226, 0.08);
}
.pf-gplate {
  flex: none;
  width: 132px;
  display: flex;
  align-items: center;
  min-width: 0;
}
.pf-gname {
  flex: 1;
  min-width: 0;
  padding: 5px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #3f4c63;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: linear-gradient(180deg, #eaf3ff, #d8e9ff);
  border: 1px solid rgba(120, 150, 200, 0.35);
}
.pf-gbody {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
}
.pf-grow {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pf-gpill {
  flex: none;
  min-width: 92px;
  padding: 2px 10px;
  text-align: center;
  font-size: 12px;
  line-height: 18px;
  color: #fff;
  border-radius: 5px;
  background: linear-gradient(180deg, #5b9ef0 0%, #3d7fd8 100%);
}
.pf-gpill-red {
  background: linear-gradient(180deg, #f06292 0%, #d9365e 100%);
}
.pf-gpill-purple {
  background: linear-gradient(180deg, #a78bfa 0%, #7c3aed 100%);
}
.pf-gpill-green {
  background: linear-gradient(180deg, #66bb6a 0%, #3f9a4d 100%);
}
.pf-gpill-orange {
  background: linear-gradient(180deg, #f6b352 0%, #e08a1e 100%);
}
.pf-gpill-blue {
  background: linear-gradient(180deg, #5b9ef0 0%, #3d7fd8 100%);
}
.pf-gline {
  flex: 1;
  min-width: 16px;
  border-bottom: 2px dotted #9dbdf0;
  transform: translateY(-3px);
}
.pf-gvalue {
  flex: none;
  font-size: 14px;
  font-weight: 600;
  color: var(--kanna-text-secondary);
  text-align: right;
  white-space: nowrap;
}
.pf-gvalue .pf-gsub {
  font-size: 11px;
  font-weight: 400;
  color: var(--kanna-text-faint);
}

/* ================= 助战（好友支援 / 地下城支援 / 团队战支援） ================= */
/* 三组各一张小卡片：分组色标签 + 金框头像 + 角色名，空位占一格虚线框。
   分组配色：好友=粉、地下城=蓝、团队战=紫，和 kanna 粉色主题协调又不单调。 */
.pf-support {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.pf-support-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 10px 8px 8px;
  border-radius: 10px;
  border: 1px solid var(--kanna-border);
  background: linear-gradient(180deg, rgba(255, 246, 250, 0.95), rgba(255, 255, 255, 0.65));
  box-shadow: 0 1px 4px rgba(236, 72, 153, 0.06);
}
.pf-support-title {
  padding: 1px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  color: #fff;
  white-space: nowrap;
  background: linear-gradient(180deg, #f472b6, #db2777);
  box-shadow: 0 1px 3px rgba(219, 39, 119, 0.25);
}
.pf-support-group-dungeon {
  border-color: rgba(74, 144, 226, 0.16);
  background: linear-gradient(180deg, rgba(243, 248, 255, 0.95), rgba(255, 255, 255, 0.65));
  box-shadow: 0 1px 4px rgba(74, 144, 226, 0.07);
}
.pf-support-group-dungeon .pf-support-title {
  background: linear-gradient(180deg, #60a5fa, #2563eb);
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.25);
}
.pf-support-group-clan {
  border-color: rgba(139, 92, 246, 0.16);
  background: linear-gradient(180deg, rgba(247, 244, 255, 0.95), rgba(255, 255, 255, 0.65));
  box-shadow: 0 1px 4px rgba(139, 92, 246, 0.07);
}
.pf-support-group-clan .pf-support-title {
  background: linear-gradient(180deg, #a78bfa, #7c3aed);
  box-shadow: 0 1px 3px rgba(124, 58, 237, 0.25);
}
.pf-support-slots {
  display: flex;
  justify-content: center;
  gap: 8px;
}
.pf-support-slot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
/* 金框头像：外圈渐变金边 + 轻微投影，和游戏里支援角色的框一致 */
.pf-support-avatar-box {
  position: relative;
  width: 68px;
  height: 68px;
  padding: 2px;
  border-radius: 11px;
  background: linear-gradient(160deg, #ffe9a8 0%, #f0c14b 45%, #c9962a 100%);
  box-shadow: 0 2px 6px rgba(180, 120, 20, 0.22);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.pf-support-slot:not(.pf-support-slot-empty):hover .pf-support-avatar-box {
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(180, 120, 20, 0.3);
}
.pf-support-avatar {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 9px;
  object-fit: cover;
  background: #cfd5e6;
}
/* 空位：去掉金框，换成虚线占位（和头像同尺寸，不会把行高撑歪） */
.pf-support-slot-empty .pf-support-avatar-box {
  padding: 0;
  background: transparent;
  box-shadow: none;
}
.pf-support-none {
  width: 100%;
  height: 100%;
  border-radius: 11px;
  border: 1px dashed rgba(120, 150, 200, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: var(--kanna-text-faint);
  background: rgba(255, 255, 255, 0.55);
}
.pf-support-name {
  max-width: 80px;
  min-height: 14px;
  font-size: 11px;
  line-height: 1.25;
  color: var(--kanna-text-secondary);
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ================= 夜间模式：蓝色系游戏 UI 覆盖 =================
 * 浅色下的白色 / 浅蓝渐变卡片原样保留，深色下换成同色系深蓝底，
 * 浅蓝虚线、占位框改成亮蓝，避免深色页面上出现刺眼白卡和看不清的深蓝字。 */
html.dark .pf-avatar,
html.dark .pf-support-avatar {
  background: rgba(120, 150, 200, 0.22);
}
html.dark .pf-item {
  background: rgba(96, 165, 250, 0.1);
}
html.dark .pf-gcard {
  border-color: rgba(147, 197, 253, 0.22);
  background: linear-gradient(180deg, rgba(38, 50, 70, 0.92) 0%, rgba(27, 36, 52, 0.92) 100%);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.35);
}
html.dark .pf-gname {
  color: #cfe0f8;
  background: linear-gradient(180deg, rgba(66, 92, 132, 0.85), rgba(45, 64, 96, 0.9));
  border-color: rgba(147, 197, 253, 0.35);
}
html.dark .pf-gline {
  border-bottom-color: rgba(147, 197, 253, 0.55);
}
html.dark .pf-support-group {
  border-color: rgba(244, 114, 182, 0.24);
  background: linear-gradient(180deg, rgba(52, 34, 46, 0.9), rgba(32, 27, 36, 0.85));
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
}
html.dark .pf-support-group-dungeon {
  border-color: rgba(96, 165, 250, 0.3);
  background: linear-gradient(180deg, rgba(30, 45, 68, 0.9), rgba(26, 33, 48, 0.85));
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
}
html.dark .pf-support-group-clan {
  border-color: rgba(167, 139, 250, 0.3);
  background: linear-gradient(180deg, rgba(42, 34, 62, 0.9), rgba(29, 26, 42, 0.85));
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
}
html.dark .pf-support-slot:not(.pf-support-slot-empty) .pf-support-avatar-box {
  background: linear-gradient(160deg, #e8cf8a 0%, #c99c3a 45%, #8f6b1f 100%);
}
html.dark .pf-support-none {
  border-color: rgba(147, 197, 253, 0.32);
  background: rgba(255, 255, 255, 0.05);
}
/* 手机端：三栏并排放不下，改成一行一组（标签在左、两个头像在右） */
@media (max-width: 767px) {
  .pf-support {
    grid-template-columns: 1fr;
  }
  .pf-support-group {
    flex-direction: row;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
  }
  .pf-support-title {
    flex: none;
    min-width: 76px;
    text-align: center;
  }
  .pf-support-slots {
    flex: 1;
    justify-content: flex-start;
  }
  .pf-support-avatar-box {
    width: 56px;
    height: 56px;
  }
  /* 分组卡片：手机上名称牌收窄、标签和数值缩小，避免挤爆 */
  .pf-gplate {
    width: 104px;
  }
  .pf-gname {
    font-size: 11px;
    padding: 4px 6px;
  }
  .pf-gpill {
    min-width: 78px;
    padding: 2px 8px;
    font-size: 11px;
  }
  .pf-gvalue {
    font-size: 13px;
  }
}
</style>
