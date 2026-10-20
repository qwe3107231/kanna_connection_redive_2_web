<!--
  游戏样式的角色头像（BOX / 助战 / 我的助战 / 选人弹窗共用）。

  照游戏「角色一览 / 支援设定」里的单位头像画，层次从下到上：
    - 底图：后端出的角色头像（128px 方图）
    - 外框：品级框 `unit_frame_{1..10}`（颜色随品级变化；线上角色都是 Rank 38 → 第 10 档粉色框）
    - 左下角：星级图标 `common_unit_icon_star_{1..6}`（6★ 是粉色那颗；其余显示战斗星级，
      和会战里「调星」后实际生效的星级一致）
    - 右下角：职业图标 + 属性图标（游戏里这两个是拼在一起的两半小牌）
        · 职业 `icon_unit_role_half_{1..8}`：1 攻击 / 2 破防 / 3 增益 / 4 减益 /
          5 强化 / 6 治疗 / 7 坦克 / 8 干扰
        · 属性 `icon_talent_half_{1..5}`：1 火 / 2 水 / 3 风 / 4 光 / 5 暗
      职业/属性是**静态游戏数据**，表在 `@/data/unit_talent_role.json`（从游戏主库导出）。
      放前端而不是后端，是为了改样式/补角色时不用重启 bot。

  注意：后端头像 URL 会带 `rarity` / `battle_rarity`，传了它后端就把星星直接烤进 PNG
  （QQ 端出图 / 竞技场那边还在用这套）。BOX 页的星级改成前端画，所以这里把这两个参数
  去掉，只要干净的底图。
-->
<template>
  <div class="game-unit-avatar">
    <img
      class="game-unit-avatar-art"
      :src="artSrc"
      :alt="unit.chara_name"
      loading="lazy"
    />
    <template v-if="unit.owned">
      <span class="game-unit-avatar-frame" :style="frameStyle"></span>
      <img
        v-if="starIcon"
        class="game-unit-avatar-star"
        :src="starIcon"
        alt=""
        aria-hidden="true"
      />
      <span v-if="roleIcon || talentIcon" class="game-unit-avatar-badges">
        <img v-if="roleIcon" :src="roleIcon" alt="" aria-hidden="true" />
        <img v-if="talentIcon" :src="talentIcon" alt="" aria-hidden="true" />
      </span>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BoxUnit } from '@/types'
import UNIT_TALENT_ROLE from '@/data/unit_talent_role.json'

const props = defineProps<{ unit: BoxUnit }>()

// { 角色 ID: [属性(1~5), 职业(1~8)] }，0 = 未知（游戏主库里没有这个角色）
const talentRole = UNIT_TALENT_ROLE as Record<string, number[]>

/** 图标资源 URL（Vite 会把 assets/unit_icon 下的 PNG 一起打进构建产物） */
function icon(name: string): string {
  return new URL(`../assets/unit_icon/${name}.png`, import.meta.url).href
}

/** 去掉后端头像 URL 里「把星星烤进图」用的两个参数（详见文件头注释） */
function cleanAvatarUrl(raw: string): string {
  if (!raw) return ''
  try {
    const parsed = new URL(raw, window.location.origin)
    parsed.searchParams.delete('rarity')
    parsed.searchParams.delete('battle_rarity')
    // 原来是相对路径就还回相对路径（页面走 Vite 代理，别把 origin 写死）
    return raw.startsWith('http') ? parsed.toString() : parsed.pathname + parsed.search + parsed.hash
  } catch {
    return raw
  }
}

const artSrc = computed(() => cleanAvatarUrl(props.unit.avatar))

const frameStyle = computed(() => {
  // 品级框：游戏里 unit_frame_1~10 按品级分 10 档。线上角色都是 Rank 38（满品级），
  // 落在第 10 档（粉色框），和游戏里一致；低品级角色按 4 级一档往上取。
  const rank = Number(props.unit.rank) || 0
  const idx = Math.min(10, Math.max(1, Math.ceil(rank / 4)))
  return { backgroundImage: `url(${icon(`frame_${idx}`)})` }
})

const starIcon = computed(() => {
  const rarity = Number(props.unit.rarity) || 0
  if (rarity <= 0) return ''
  // 6★ 固定用粉色第 6 颗；其余显示战斗星级（调星后实际生效的星级），没调过就是拥有星级
  const battle = Number(props.unit.battle_rarity) || rarity
  const star = rarity >= 6 ? 6 : Math.min(6, Math.max(1, battle))
  return icon(`star_${star}`)
})

const talent = computed(() => talentRole[String(props.unit.unit_id)]?.[0] ?? 0)
const role = computed(() => talentRole[String(props.unit.unit_id)]?.[1] ?? 0)
const talentIcon = computed(() =>
  talent.value >= 1 && talent.value <= 5 ? icon(`talent_${talent.value}`) : '',
)
const roleIcon = computed(() =>
  role.value >= 1 && role.value <= 8 ? icon(`role_${role.value}`) : '',
)
</script>

<style scoped>
.game-unit-avatar {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}
/* 底图：稍微内缩，让品级框盖住四周（框的内侧是透明的） */
.game-unit-avatar-art {
  position: absolute;
  inset: 3.5%;
  width: 93%;
  height: 93%;
  object-fit: cover;
  border-radius: 9%;
}
/* 品级框铺满整个头像 */
.game-unit-avatar-frame {
  position: absolute;
  inset: 0;
  background-repeat: no-repeat;
  background-size: 100% 100%;
  pointer-events: none;
}
/* 左下角星级 */
.game-unit-avatar-star {
  position: absolute;
  left: 8%;
  bottom: 7%;
  width: 24%;
  height: auto;
  pointer-events: none;
}
/* 右下角：职业 + 属性两半拼在一起 */
.game-unit-avatar-badges {
  position: absolute;
  right: 0;
  bottom: 4%;
  height: 22.5%;
  display: flex;
  pointer-events: none;
}
.game-unit-avatar-badges img {
  display: block;
  height: 100%;
  width: auto;
}
</style>
