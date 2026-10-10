<template>
  <div class="def-result">
    <div class="def-head">
      防守方：<b>{{ result.name }}</b>
      <span class="def-rank">{{ result.rank }}位</span>
    </div>

    <div class="def-team" v-for="(team, ti) in result.defence" :key="'d' + ti">
      <span class="def-tag">防守 {{ ti + 1 }} 队</span>
      <div class="unit-strip">
        <img
          v-for="(u, i) in team"
          :key="i"
          class="unit-icon"
          :src="avatarUrl(u.unit_id, u.rarity, u.battle_rarity)"
          alt=""
        />
        <span v-if="!team.length" class="unit-empty">（无可查队伍）</span>
      </div>
    </div>

    <div class="sol-head">进攻作业</div>
    <div class="sol-list">
      <div class="sol-row" v-for="(s, i) in result.solutions" :key="i">
        <div class="unit-strip">
          <img
            v-for="(u, j) in s.units"
            :key="j"
            class="unit-icon"
            :src="avatarUrl(u.unit_id, u.rarity, u.battle_rarity)"
            alt=""
          />
        </div>
        <div class="sol-meta">
          <span v-if="s.label" class="sol-label">{{ s.label }}</span>
          <span v-if="s.team_type === 'normal'" class="sol-vote">
            <span class="up">👍 {{ s.up }}</span>
            <span class="down">👎 {{ s.down }}</span>
          </span>
          <span v-if="s.comment" class="sol-comment">{{ s.comment }}</span>
        </div>
      </div>
      <el-empty v-if="!result.solutions.length" description="没有查到作业" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ArenaDefenceResult } from '@/types'
import { API_BASE } from '@/utils/request'

const props = defineProps<{ result: ArenaDefenceResult; groupId: number }>()

/** 头像档位：与后端 `_avatar_star` 一致（1 / 3 / 6 三档） */
function starOf(rarity: number) {
  if (rarity >= 6) return 6
  if (rarity >= 3) return 3
  if (rarity >= 1) return 1
  return 3
}

/** 角色头像（4 位 id）；传了 rarity / battle_rarity 后端会在头像底部叠星星 */
function avatarUrl(unitId: number, rarity = 0, battleRarity = 0) {
  const params = new URLSearchParams({ star: String(starOf(rarity)) })
  if (rarity > 0) params.set('rarity', String(rarity))
  if (battleRarity > 0) params.set('battle_rarity', String(battleRarity))
  return `${API_BASE}/${props.groupId}/box/avatar/${unitId}?${params.toString()}`
}
</script>

<style scoped>
.def-result {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.def-head {
  font-size: 15px;
  color: #4a515a;
}
.def-head b {
  color: #831843;
}
.def-rank {
  margin-left: 8px;
  font-size: 13px;
  color: #9ca3af;
}
.def-team {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.def-tag {
  flex: none;
  padding: 2px 10px;
  font-size: 12px;
  color: #fff;
  background: #c62828;
  border-radius: 5px;
}
.unit-strip {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.unit-icon {
  width: 48px;
  height: 48px;
  border-radius: 6px;
  object-fit: cover;
  background: #cfd5e6;
}
.unit-empty {
  font-size: 12px;
  color: #9ca3af;
}
.sol-head {
  font-size: 13px;
  font-weight: 600;
  color: #4a515a;
  padding-top: 4px;
  border-top: 1px dashed rgba(120, 150, 200, 0.3);
}
.sol-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sol-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(74, 144, 226, 0.06);
  flex-wrap: wrap;
}
.sol-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #4b5563;
}
.sol-label {
  padding: 1px 8px;
  font-size: 12px;
  color: #fff;
  background: #f59e0b;
  border-radius: 4px;
}
.sol-vote .up {
  color: #16a34a;
  margin-right: 8px;
}
.sol-vote .down {
  color: #dc2626;
}
.sol-comment {
  color: #6b7280;
}

@media (max-width: 767px) {
  .unit-icon {
    width: 42px;
    height: 42px;
  }
}
</style>
