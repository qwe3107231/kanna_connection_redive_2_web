<!--
  排刀队伍卡片（三刀选择 / 补偿刀弹窗共用）。

  一张卡 = 表格里的一条作业：BOSS 标签 + 补偿时间/伤害 + 5 个角色头像。
  借用助战的那个角色会在头像上加蓝色「助战」角标 —— 这是排刀页面最关键的提示，
  用户要知道这一刀缺的角色是借来的，而不是自己真有。
-->
<template>
  <div
    class="arrange-team-card"
    :class="{
      'is-selected': selected,
      'is-disabled': disabled || feasible === false,
      'is-compact': compact,
    }"
    :title="team.raw"
    @click="onClick"
  >
    <div class="arrange-team-head">
      <el-tag size="small" :type="stageType" effect="light" class="arrange-team-boss">
        {{ team.boss_label }}
      </el-tag>
      <span class="arrange-team-value" :class="{ 'is-comp': hasCompValue }">
        {{ valueText }}
      </span>
      <el-tag
        v-if="isFullComp"
        size="small"
        type="success"
        effect="plain"
        class="arrange-team-full"
      >
        满补
      </el-tag>
      <span v-if="borrowId" class="arrange-team-borrow">
        借 {{ borrowName }}
      </span>
    </div>

    <div class="arrange-team-avatars">
      <div
        v-for="(unitId, index) in team.units"
        :key="`${unitId}-${index}`"
        class="arrange-team-avatar"
        :class="{ 'is-borrowed': unitId === borrowId }"
      >
        <GameUnitAvatar :unit="displayUnit(unitId)" />
        <span v-if="unitId === borrowId" class="arrange-borrow-badge">助战</span>
      </div>
      <!-- 名字没认全时，缺的位置用灰色占位补齐 5 格，别让卡片看起来缺一块 -->
      <div
        v-for="index in Math.max(0, 5 - team.units.length)"
        :key="`missing-${index}`"
        class="arrange-team-avatar is-empty"
      >
        <el-icon :size="16"><QuestionFilled /></el-icon>
      </div>
    </div>

    <div class="arrange-team-names">
      {{ team.unit_names.length ? team.unit_names.join(' · ') : team.raw }}
    </div>

    <div v-if="team.unknown_names.length" class="arrange-team-reason">
      未识别：{{ team.unknown_names.join('、') }}
    </div>
    <div v-else-if="feasible === false && reason" class="arrange-team-reason">
      {{ reason }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ArrangeTeam, ArrangeUnit } from '@/types'
import GameUnitAvatar from '@/components/GameUnitAvatar.vue'

const props = withDefaults(
  defineProps<{
    team: ArrangeTeam
    units: Record<string, ArrangeUnit>
    /** 这一刀缺的角色（从助战借），null = 五个全有 */
    borrowId?: number | null
    /** 能不能出；false 时卡片置灰并显示 reason */
    feasible?: boolean
    reason?: string
    selected?: boolean
    disabled?: boolean
    compact?: boolean
  }>(),
  {
    borrowId: null,
    feasible: true,
    reason: '',
    selected: false,
    disabled: false,
    compact: false,
  },
)

const emit = defineEmits<{ (e: 'select'): void }>()

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

function displayUnit(unitId: number): ArrangeUnit {
  return props.units[String(unitId)] ?? { ...EMPTY_UNIT, unit_id: unitId }
}

const borrowName = computed(() =>
  props.borrowId ? displayUnit(props.borrowId).chara_name : '',
)

const stageType = computed(() => {
  switch (props.team.stage) {
    case 'B':
      return 'primary'
    case 'C':
      return 'warning'
    case 'D':
      return 'danger'
    default:
      return 'success'
  }
})

function damageOf(team: ArrangeTeam): number {
  return Number(
    team.damage_value ?? (team.value_kind === 'damage' ? team.value : 0),
  ) || 0
}

function returnOf(team: ArrangeTeam): number {
  return Number(
    team.return_seconds ?? (team.value_kind === 'return' ? team.value : 0),
  ) || 0
}

function fmtValue(value: number): string {
  return Number.isInteger(value) ? String(value) : String(value)
}

const valueText = computed(() => {
  const parts: string[] = []
  const damage = damageOf(props.team)
  const returnSeconds = returnOf(props.team)
  if (damage > 0) parts.push(`伤害 ${fmtValue(damage)}亿`)
  if (returnSeconds > 0) parts.push(`补偿 ${fmtValue(returnSeconds)}s`)
  return parts.length ? parts.join(' · ') : props.team.value_label || '—'
})

const hasCompValue = computed(() => returnOf(props.team) > 0)

// 90s = 70s 击杀 + 20s 补偿，满补；用户特意强调过这个口径。
const isFullComp = computed(() => returnOf(props.team) >= 90)

function onClick() {
  if (props.disabled || props.feasible === false) return
  emit('select')
}
</script>

<style scoped>
.arrange-team-card {
  padding: 8px;
  border: 2px solid transparent;
  border-radius: 10px;
  background: var(--kanna-surface);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}
.arrange-team-card:hover {
  border-color: var(--kanna-border);
  transform: translateY(-1px);
}
.arrange-team-card.is-selected {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 3px var(--el-color-primary-light-8);
}
.arrange-team-card.is-disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.arrange-team-card.is-disabled:hover {
  transform: none;
  border-color: transparent;
}
.arrange-team-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  min-height: 22px;
}
.arrange-team-boss {
  flex-shrink: 0;
}
.arrange-team-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--kanna-text);
  white-space: nowrap;
}
.arrange-team-value.is-comp {
  color: var(--el-color-warning-dark-2);
}
.arrange-team-full {
  transform: scale(0.9);
}
.arrange-team-borrow {
  margin-left: auto;
  font-size: 11px;
  color: #2563eb;
  white-space: nowrap;
}
.arrange-team-avatars {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 4px;
}
.arrange-team-avatar {
  position: relative;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  background: var(--kanna-hover);
}
.arrange-team-avatar.is-borrowed {
  outline: 2px solid #3b82f6;
  outline-offset: -1px;
}
.arrange-team-avatar.is-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--kanna-text-faint);
  border: 1px dashed var(--kanna-border);
}
.arrange-borrow-badge {
  position: absolute;
  left: 50%;
  bottom: 0;
  transform: translateX(-50%);
  padding: 1px 3px;
  border-radius: 4px 4px 0 0;
  background: #3b82f6;
  color: #fff;
  font-size: 9px;
  line-height: 1.2;
  white-space: nowrap;
}
.arrange-team-names {
  margin-top: 5px;
  font-size: 11px;
  line-height: 1.35;
  color: var(--kanna-text-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.arrange-team-reason {
  margin-top: 3px;
  font-size: 11px;
  color: var(--el-color-danger);
  line-height: 1.3;
}
.arrange-team-card.is-compact {
  padding: 6px;
}
.arrange-team-card.is-compact .arrange-team-avatars {
  gap: 3px;
}
</style>
