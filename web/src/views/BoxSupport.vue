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
            点开头像的详情里多了<b>普通 EX 槽</b>：点槽位就能看并换该角色能穿的 EX 装备
            （带属性、能看到同一件现在空闲还是在谁身上，从别人身上拿会<b>互换</b>）。
            EX1/EX2/EX3 可以<b>先各挑一件再一起换</b>（弹窗底部会列出你挑好的结果），
            列表本身不登录，只有点确定更换时才顶号。<b>会战 EX</b> 维持原样，不在这个槽里换。
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

          <!-- 普通 EX 装备：3 个槽的**类别由角色决定**（后端给的 category_name），
               点槽位就弹出该类别下自己所有的 EX 装（带属性 / 现在在谁身上），选中即换。
               读列表不登录；真换会顶号，所以换之前弹确认。会战 EX 不走这里。 -->
          <template v-if="detail.ex_equips.length">
            <div class="detail-section">
              普通 EX 装备
              <span class="section-hint">
                {{ detail.ex_equip_editable ? '点槽位可更换' : '只读' }}
              </span>
            </div>
            <div class="equip-grid equip-grid-3">
              <div
                v-for="cell in detail.ex_equips"
                :key="`ex-${cell.slot}`"
                class="equip-cell ex-slot-cell"
                :class="{ 'ex-slot-readonly': !detail.ex_equip_editable }"
                :title="
                  detail.ex_equip_editable
                    ? `更换「${cell.category_name}」EX 装备`
                    : `${cell.category_name}（别人的 BOX / 助战数据，只能查看）`
                "
                @click="openExPicker(cell.slot)"
              >
                <div class="equip-label">EX {{ cell.slot }} · {{ cell.category_name }}</div>
                <div class="ex-equip-body">
                  <img
                    v-if="cell.icon"
                    class="ex-equip-icon"
                    :src="cell.icon"
                    :alt="cell.name"
                    loading="lazy"
                  />
                  <div v-else class="ex-equip-icon ex-equip-icon-empty">
                    <el-icon :size="16"><Plus /></el-icon>
                  </div>
                  <div class="ex-slot-info">
                    <div class="equip-value" :class="{ 'equip-empty': !cell.equipped }">
                      {{ cell.equipped ? cell.name : '未装备' }}
                    </div>
                    <div v-if="cell.equipped" class="ex-slot-sub">
                      <span class="ex-rarity">{{ cell.rarity_name }}</span>
                      <!-- star=0 有两种情况：没强化过的 1~4 星装备，以及永远没有星级的
                           5 星彩装。都不显示「★0」，只留稀有度标签。 -->
                      <span v-if="cell.star">★{{ cell.star }}</span>
                      <span v-if="cell.clan_battle" class="ex-clan-tag">会战</span>
                    </div>
                    <div v-else class="ex-slot-sub">
                      {{ detail.ex_equip_editable ? '点击选择' : '—' }}
                    </div>
                    <!-- 5 星彩装的词条：同一属性已累加（两条物穿 -> 「物穿 10」），
                         最多 4 项。铜/银/金/粉没有词条，这块不显示；
                         彩装一件都没有词条时显示「空」。
                         锁定与否不显示 —— 那是炼成时的事，和换装无关。 -->
                    <div v-if="cell.equipped && cell.rarity >= 5" class="ex-slot-subs">
                      <div v-if="!cell.sub_statuses.length" class="ex-sub-line ex-sub-empty">
                        词条 空
                      </div>
                      <div
                        v-for="s in cell.sub_statuses"
                        :key="s.status"
                        class="ex-sub-line"
                        :title="`${s.label} ${s.text}`"
                      >
                        <span>{{ s.label }}</span>
                        <b>{{ s.text }}</b>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="exSlotNote" class="ex-slot-note">{{ exSlotNote }}</div>
          </template>
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

    <!-- 普通 EX 装备弹窗：点详情里的「普通 EX 槽」打开。
         用法是**一次挑好三个槽再一起提交**：
           - 顶部三个按钮是角色能穿的三个槽（类别由角色决定），点着切；
           - 在某个槽里点一件装备就选定（相同词条的彩装已合并成一行，点哪行就是哪行）；
           - 切到别的槽时**已经选好的不会被清掉**；
           - 弹窗底部一直显示「本次要换的」三个槽的结果，挑完点一次「确定更换」就一起换。
         列表本身是纯读本地缓存（不登录、不顶号），只有点「确定更换」才登录游戏账号。 -->
    <el-dialog
      v-model="exPickerVisible"
      :title="exPickerTitle"
      width="820px"
      class="ex-picker-dialog"
    >
      <div class="ex-picker-head">
        <el-radio-group
          v-if="exSlotTabs.length"
          v-model="exPickerSlot"
          size="small"
          @change="loadExOptions"
        >
          <el-radio-button v-for="s in exSlotTabs" :key="s.slot" :value="s.slot">
            EX{{ s.slot }} · {{ s.category_name }}
            <span v-if="exSelections[s.slot]" class="ex-tab-mark">✓</span>
          </el-radio-button>
        </el-radio-group>
        <span v-if="exPickerResult?.ok" class="ex-picker-count">
          {{ exCandidates.length }} 种可选
        </span>
      </div>

      <div v-if="exPickerCurrentText" class="ex-picker-current">
        当前：{{ exPickerCurrentText }}
      </div>

      <div class="ex-picker-body">
        <div v-if="exPickerLoading" class="picker-loading">
          <el-icon class="is-loading" :size="22"><Loading /></el-icon>
          <span>正在读取你的 EX 装备…</span>
        </div>

        <el-alert
          v-else-if="exPickerMessage"
          :title="exPickerMessage"
          type="info"
          show-icon
          :closable="false"
        />

        <div v-else class="ex-cand-list">
          <!-- 卸下这个槽（留空）。槽本来就是空的时候不显示，免得白白顶一次号 -->
          <div
            v-if="exPickerResult?.current"
            class="ex-cand ex-cand-none"
            :class="{ 'ex-cand-active': exSelection?.kind === 'unequip' }"
            @click="selectExNone"
          >
            <div class="ex-cand-main">
              <div class="ex-cand-title">
                <span class="ex-cand-name">卸下这个槽（留空）</span>
              </div>
            </div>
          </div>

          <div
            v-for="c in exCandidates"
            :key="c.candidate_key"
            class="ex-cand"
            :class="{
              'ex-cand-active': exSelection?.key === c.candidate_key,
              'ex-cand-current': c.equipped_here,
            }"
            @click="selectExCandidate(c)"
          >
            <img
              v-if="c.icon"
              class="ex-cand-icon"
              :src="c.icon"
              :alt="c.name"
              loading="lazy"
            />
            <div class="ex-cand-main">
              <div class="ex-cand-title">
                <span class="ex-cand-name">{{ c.name }}</span>
                <!-- star=0：没强化过的 1~4 星装备 / 永远没星级的 5 星彩装，都不显示 ★0 -->
                <span v-if="c.star" class="ex-cand-star">★{{ c.star }}</span>
                <span class="ex-rarity">{{ c.rarity_name }}</span>
                <span v-if="c.clan_battle" class="ex-clan-tag">会战</span>
                <span v-if="c.equipped_here" class="ex-cand-badge">当前穿戴</span>
              </div>
              <div class="ex-cand-attrs">
                <template v-if="c.attrs.length">
                  <span v-for="a in c.attrs" :key="a.key" class="ex-attr">
                    {{ a.label }} <b>{{ a.text }}</b>
                  </span>
                </template>
                <span v-else class="ex-attr-empty">无属性</span>
              </div>
              <!-- 5 星彩装的词条：同一属性已累加（两条物穿 -> 「物穿 10」），最多 4 项。
                   彩装一件一行，所以这里就是这一件的词条；「空」表示这件没有词条。 -->
              <div v-if="c.rarity >= 5" class="ex-cand-subs">
                <span class="ex-sub-tag">词条</span>
                <template v-if="c.sub_statuses.length">
                  <span
                    v-for="s in c.sub_statuses"
                    :key="s.status"
                    class="ex-sub-item"
                  >
                    {{ s.label }} <b>{{ s.text }}</b>
                  </span>
                </template>
                <span v-else class="ex-sub-item ex-sub-empty">空</span>
              </div>
              <div class="ex-cand-owner">
                <span>{{ exCandidateOwnerText(c) }}</span>
                <!-- 彩装一件一行，把 serial 显示出来，方便和 autopcr 的输出对号 -->
                <span v-if="c.rarity >= 5" class="ex-cand-serial">#{{
                  c.copies[0]?.serial_id
                }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 已挑好的结果：一直显示在弹窗底部，切槽也不会丢 -->
      <div v-if="exSlotTabs.length" class="ex-picked">
        <div class="ex-picked-title">
          本次要换的（挑好三个槽后一次提交，没选的槽不动）
        </div>
        <div
          v-for="s in exSlotTabs"
          :key="`picked-${s.slot}`"
          class="ex-picked-row"
          :class="{ 'ex-picked-row-active': exPickerSlot === s.slot }"
          @click="switchExSlot(s.slot)"
        >
          <span class="ex-picked-slot">EX{{ s.slot }} · {{ s.category_name }}</span>
          <span
            class="ex-picked-value"
            :class="{ 'ex-picked-empty': !exSelections[s.slot] }"
          >
            {{ exSelectionText(s.slot) }}
          </span>
          <el-button
            v-if="exSelections[s.slot]"
            text
            size="small"
            class="ex-picked-clear"
            @click.stop="clearExSelection(s.slot)"
          >
            清除
          </el-button>
        </div>
      </div>

      <template #footer>
        <span class="picker-footer-tip">
          会临时登录你的游戏账号，把正在游戏的你挤下线
        </span>
        <el-button @click="exPickerVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="exChanging"
          :disabled="!exChangeCount"
          @click="confirmExChange"
        >
          确定更换{{ exChangeCount ? `（${exChangeCount} 个槽）` : '' }}
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
  changeExEquip,
  getExEquipOptions,
  queryBox,
  queryClanBox,
  queryClanSupport,
  queryMySupport,
  refreshCache,
} from '@/api'
import type {
  BoxQueryResult,
  BoxUnit,
  ExEquipCandidate,
  ExEquipChangeForm,
  ExEquipOptionsResult,
  ExEquipSlotInfo,
  ExEquipSubStatus,
} from '@/types'
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

// ---- 普通 EX 装备（角色详情 → 点「普通 EX 槽」） ----
//
// 与「更换支援」是两件事，但规矩一样：
//   - **列装备**走 `GET /box/ex_equip/options`，纯读本地缓存，不登录、不顶号；
//   - **真换**走 `POST /box/ex_equip/change`，会登录你的游戏账号（顶号），先弹确认。
// 换装动作本身（含「从别人身上拿装备时互换而不是把对方扒光」、会战冷却拦截）全在
// 后端 `support_query.util.change_normal_ex_equip`，前端不重复判定。
//
// 会战 EX 不在这里：详情上半部分的「会战 EX 装备」还是原来的只读展示。
const exPickerVisible = ref(false)
const exPickerLoading = ref(false)
const exChanging = ref(false)
const exPickerUnitId = ref(0) // 4 位角色 ID（后端用它查槽位表 + 找角色）
const exPickerCharaName = ref('')
const exPickerSlot = ref(1)

// 普通 EX 槽下面那句说明：分四种情况，别把「别人的数据」和「自己还没刷缓存」混为一谈
const exSlotNote = computed(() => {
  const unit = detail.value
  if (!unit || !unit.ex_equips.length) return ''
  if (!unit.ex_equip_editable) {
    return unit.ex_equip_known
      ? '这是别人的 BOX / 助战数据，普通 EX 槽只能查看。要换装请切到【个人 BOX】——换装永远是换你自己账号上的角色。'
      : '助战缓存里不含普通 EX 装备数据，这一栏只能看到会战 EX。'
  }
  if (!unit.ex_equip_known) {
    return (
      '还没有你的普通 EX 缓存，所以上面只显示槽位类别。点右上角【刷新缓存】' +
      '（会短暂顶号）之后，这里就能看到现在穿的是哪件，也能直接换。'
    )
  }
  return ''
})

// 候选行的「现在在哪」文案（相同词条的几件已合并，这里说明会用哪一件）
function exCandidateOwnerText(c: ExEquipCandidate) {
  const first = c.copies[0]
  if (!first) return ''
  if (c.count <= 1) return first.label
  if (!first.wearer_unit_id) return `共 ${c.count} 件 · 空闲 ${c.free_count} 件`
  return `共 ${c.count} 件 · 空闲 ${c.free_count} 件，将用「${first.label}」那件`
}

// 本次每个槽挑了什么。key = 槽位号；没挑 = 不存在/undefined
type ExPickKind = 'item' | 'unequip'
interface ExPick {
  kind: ExPickKind
  key: string
  serialId: number
  name: string
  star: number
  subStatuses: ExEquipSubStatus[]
  ownerLabel: string
  swappedName: string
}
const exSelections = ref<Record<number, ExPick | undefined>>({})
// 每个槽的候选列表都缓存下来：切回 EX1 时不用重新请求，**选好的也不会被清掉**
const exOptionsBySlot = ref<Record<number, ExEquipOptionsResult | undefined>>({})
const exSlotTabs = ref<ExEquipSlotInfo[]>([])

// 当前槽的列表 + 提示都由「这个槽的请求结果」推出来，不用各自维护一份状态
const exPickerResult = computed(() => exOptionsBySlot.value[exPickerSlot.value] ?? null)
const exCandidates = computed(() => exPickerResult.value?.candidates ?? [])
const exSelection = computed(() => exSelections.value[exPickerSlot.value])
const exPickerMessage = computed(() => {
  const res = exPickerResult.value
  if (!res) return ''
  if (!res.ok) return res.message || '读取这个槽的装备失败'
  return res.message
})
const exChangeCount = computed(
  () => exSlotTabs.value.filter((s) => exSelections.value[s.slot]).length,
)

const exPickerTitle = computed(() =>
  exPickerCharaName.value
    ? `更换「${exPickerCharaName.value}」的普通 EX 装备`
    : '更换普通 EX 装备',
)

// 当前这个槽穿着的装备（后端从缓存里算好，没有就是空槽）
// star=0 不显示星级：1~4 星是「没强化」，5 星彩装是「压根没有星级」
const starText = (star: number) => (star ? `★${star}` : '')
// 彩装 4 条词条的一行摘要（"物攻1.5%、物爆0.8%"）；没有词条（非彩装）时是空串
const subStatusText = (list: ExEquipSubStatus[]) =>
  list.map((s) => `${s.label}${s.text}`).join('、')
const subStatusSuffix = (list: ExEquipSubStatus[]) =>
  list.length ? `（词条：${subStatusText(list)}）` : ''
const exPickerCurrentText = computed(() => {
  const cur = exPickerResult.value?.current
  if (!cur) return ''
  return (
    `${cur.name}${starText(cur.star)}${cur.clan_battle ? '（会战）' : ''}` +
    subStatusSuffix(cur.sub_statuses)
  )
})

// 底部「本次要换的」每一行显示什么
function exSelectionText(slot: number) {
  const pick = exSelections.value[slot]
  if (!pick) return '不变'
  if (pick.kind === 'unequip') return '卸下（留空）'
  return (
    `${pick.name}${starText(pick.star)}${subStatusSuffix(pick.subStatuses)}` +
    (pick.swappedName ? `（与${pick.swappedName}互换）` : '')
  )
}

async function openExPicker(slot: number) {
  const unit = detail.value
  if (!unit) return
  if (!unit.ex_equip_editable) {
    ElMessage.info('这是别人的 BOX / 助战数据，普通 EX 槽只能查看')
    return
  }
  exPickerUnitId.value = unit.unit_id
  exPickerCharaName.value = unit.chara_name
  exPickerSlot.value = slot
  exSelections.value = {}
  exOptionsBySlot.value = {}
  exSlotTabs.value = []
  exPickerVisible.value = true
  await loadExOptions()
}

// 切换槽位：先看有没有缓存，有就直接用（不动已经选好的东西）
async function switchExSlot(slot: number) {
  exPickerSlot.value = slot
  await loadExOptions()
}

async function loadExOptions() {
  if (!groupId.value || !exPickerUnitId.value) return
  const slot = exPickerSlot.value
  if (exOptionsBySlot.value[slot]) return // 切回来不重新请求，选择也就不会丢

  exPickerLoading.value = true
  try {
    const res = await getExEquipOptions(
      groupId.value,
      exPickerUnitId.value,
      slot,
    )
    exOptionsBySlot.value[slot] = res
    if (res.ok && res.slots.length && !exSlotTabs.value.length) {
      exSlotTabs.value = res.slots
    }
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    exPickerLoading.value = false
  }
}

// 点一行就选定它（相同词条的彩装后端已经合并成一行，点哪行就是哪行）
function selectExCandidate(c: ExEquipCandidate) {
  if (c.equipped_here) {
    ElMessage.info(`这个槽现在就是「${c.name}」，不用换`)
    return
  }
  const first = c.copies[0]
  exSelections.value[exPickerSlot.value] = {
    kind: 'item',
    key: c.candidate_key,
    serialId: first?.serial_id ?? 0,
    name: c.name,
    star: c.star,
    subStatuses: c.sub_statuses,
    ownerLabel: exCandidateOwnerText(c),
    swappedName: first && first.wearer_unit_id ? first.wearer_name : '',
  }
}

function selectExNone() {
  exSelections.value[exPickerSlot.value] = {
    kind: 'unequip',
    key: 'none',
    serialId: 0,
    name: '',
    star: 0,
    subStatuses: [],
    ownerLabel: '',
    swappedName: '',
  }
}

function clearExSelection(slot: number) {
  exSelections.value[slot] = undefined
}

// 一次把挑好的 1~3 个槽提交上去（只登录一次、只发一批 equip_ex）
async function confirmExChange() {
  if (!groupId.value || exChanging.value) return
  const changes: ExEquipChangeForm['changes'] = []
  const lines: string[] = []
  for (const tab of exSlotTabs.value) {
    const pick = exSelections.value[tab.slot]
    if (!pick) continue
    changes.push({
      slot: tab.slot,
      serial_id: pick.kind === 'item' ? pick.serialId : 0,
    })
    lines.push(
      pick.kind === 'item'
        ? `EX${tab.slot}（${tab.category_name}）→ ${pick.name}${starText(pick.star)}` +
            subStatusSuffix(pick.subStatuses) +
            (pick.swappedName ? `（与${pick.swappedName}互换）` : '')
        : `EX${tab.slot}（${tab.category_name}）→ 卸下`,
    )
  }
  if (!changes.length) return

  try {
    await ElMessageBox.confirm(
      `将一次更换 ${changes.length} 个槽：\n${lines.join('\n')}\n\n` +
        '这一步会临时登录你的游戏账号（把正在游戏的你挤下线），' +
        '并真的改游戏里的 EX 槽；从别人身上拿装备时会与 TA 互换。确定吗？',
      '更换普通 EX 装备',
      { type: 'warning', confirmButtonText: '确定更换', cancelButtonText: '再想想' },
    )
  } catch {
    // 用户取消
    return
  }

  exChanging.value = true
  try {
    const res = await changeExEquip(groupId.value, {
      unit_id: exPickerUnitId.value,
      changes,
    })
    if (!res.ok) {
      ElMessage.warning(res.message)
      return
    }
    ElMessage.success(res.message)
    // 换完就关掉选装备弹窗、回到角色详情。下面的重拉是纯读缓存（不登录），
    // 拿每个槽的 current 把详情里对应格子就地刷新掉，不用重查整个 BOX。
    exPickerVisible.value = false
    for (const item of res.slots) exSelections.value[item.slot] = undefined
    await reloadAllExOptions()
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    exChanging.value = false
  }
}

// 换完之后重拉三个槽的列表（纯读缓存，不登录），并把详情面板对应格子更新掉
async function reloadAllExOptions() {
  if (!groupId.value || !exPickerUnitId.value) return
  const slots = exSlotTabs.value.length
    ? exSlotTabs.value.map((s) => s.slot)
    : [exPickerSlot.value]
  exOptionsBySlot.value = {}
  for (const slot of slots) {
    try {
      const res = await getExEquipOptions(groupId.value, exPickerUnitId.value, slot)
      exOptionsBySlot.value[slot] = res
      if (res.ok) applyExCurrentToDetail(slot, res.current)
    } catch (e) {
      /* 单个槽失败不影响其它槽 */
    }
  }
}

// 换完之后把详情弹窗里那个槽就地更新（后端响应里没有整套 BoxUnit，不重查 BOX）
function applyExCurrentToDetail(slot: number, current: ExEquipCandidate | null) {
  const unit = detail.value
  if (!unit) return
  const cell = unit.ex_equips.find((c) => c.slot === slot)
  if (!cell) return
  if (current) {
    cell.equipped = true
    cell.equipment_id = current.equipment_id
    cell.name = current.name
    cell.rarity = current.rarity
    cell.rarity_name = current.rarity_name
    cell.star = current.star
    cell.clan_battle = current.clan_battle
    cell.icon = current.icon
    cell.sub_statuses = current.sub_statuses
  } else {
    cell.equipped = false
    cell.equipment_id = 0
    cell.name = ''
    cell.rarity = 0
    cell.rarity_name = ''
    cell.star = 0
    cell.clan_battle = false
    cell.icon = ''
    cell.sub_statuses = []
  }
  // 能显示就说明这份账号确实有 EX 缓存了
  unit.ex_equip_known = true
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
/* 空装备槽的占位图标（虚线框 + 加号，提示这里可以点） */
.ex-equip-icon-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c4c8ce;
  border-style: dashed;
}
/* 普通 EX 槽：整格可点，点开选装备 */
.ex-slot-cell {
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.ex-slot-cell:hover {
  border-color: #f9a8d4;
  background: rgba(219, 39, 119, 0.04);
  box-shadow: 0 4px 12px rgba(219, 39, 119, 0.1);
}
/* 别人的 BOX / 助战数据：普通 EX 槽只读，点它不给换装入口 */
.ex-slot-readonly {
  cursor: default;
}
.ex-slot-readonly:hover {
  border-color: #eef0f3;
  background: rgba(0, 0, 0, 0.015);
  box-shadow: none;
}
.ex-slot-info {
  min-width: 0;
}
.ex-slot-sub {
  margin-top: 2px;
  font-size: 11px;
  color: #9ca3af;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
/* 稀有度（铜/银/金/粉/彩）与「会战」小标签 */
.ex-rarity,
.ex-clan-tag {
  display: inline-block;
  padding: 0 4px;
  border-radius: 3px;
  font-size: 10px;
  line-height: 15px;
  background: rgba(0, 0, 0, 0.05);
  color: #6b7280;
}
.ex-clan-tag {
  background: rgba(219, 39, 119, 0.12);
  color: #db2777;
}
.ex-slot-note {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: #9ca3af;
}
/* 5 星彩装的 4 条词条（详情里那个小格子） */
.ex-slot-subs {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.ex-sub-line {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  line-height: 1.5;
  color: #6b7280;
  white-space: nowrap;
}
.ex-sub-line b {
  color: #374151;
}
.detail-section .section-hint {
  margin-left: 6px;
  font-size: 11px;
  font-weight: 400;
  color: #c4c8ce;
}

/* ---- 普通 EX 装备：选装备弹窗 ---- */
.ex-picker-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.ex-picker-count {
  font-size: 12px;
  color: #9ca3af;
}
.ex-picker-current {
  margin-bottom: 10px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(219, 39, 119, 0.06);
  color: #831843;
  font-size: 13px;
}
/* 装备可能有几十种，列表自己滚，别把弹窗撑出屏幕 */
.ex-picker-body {
  max-height: 46vh;
  overflow-y: auto;
}
.ex-cand-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ex-cand {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid #eef0f3;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.ex-cand:hover {
  border-color: #f9a8d4;
  background: rgba(219, 39, 119, 0.03);
}
.ex-cand-active {
  border-color: #db2777;
  background: rgba(219, 39, 119, 0.07);
}
/* 正穿在这个槽上的那一组：左边一条粉线，一眼看出「现在就是它」 */
.ex-cand-current {
  border-left: 3px solid #db2777;
}
.ex-cand-icon {
  width: 42px;
  height: 42px;
  border-radius: 6px;
  border: 1px solid #eef0f3;
  background: rgba(0, 0, 0, 0.02);
  object-fit: contain;
  flex: none;
}
.ex-cand-main {
  flex: 1;
  min-width: 0;
}
.ex-cand-title {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #111827;
}
.ex-cand-name {
  font-weight: 600;
}
.ex-cand-star {
  color: #c98a12;
  font-size: 12px;
}
.ex-cand-badge {
  padding: 0 5px;
  border-radius: 3px;
  font-size: 10px;
  line-height: 16px;
  color: #db2777;
  background: rgba(219, 39, 119, 0.12);
}
.ex-cand-attrs {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 12px;
  color: #6b7280;
}
.ex-attr b {
  color: #374151;
}
.ex-attr-empty {
  color: #c4c8ce;
}
/* 5 星彩装的 4 条词条（选装备列表里那一行） */
.ex-cand-subs {
  margin-top: 3px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 10px;
  font-size: 12px;
  color: #6b7280;
}
.ex-sub-tag {
  padding: 0 4px;
  border-radius: 3px;
  font-size: 10px;
  line-height: 16px;
  color: #831843;
  background: rgba(219, 39, 119, 0.12);
}
.ex-sub-item b {
  color: #374151;
}
/* 彩装的词条是「空」（这件没炼出词条） */
.ex-sub-empty {
  color: #c4c8ce;
}
/* 彩装那一行的 serial 编号（方便和 autopcr 的输出对号） */
.ex-cand-serial {
  color: #c4c8ce;
}
/* 已经在这个槽里选好东西的小勾（槽位按钮上） */
.ex-tab-mark {
  margin-left: 4px;
  color: #db2777;
  font-weight: 700;
}
/* 「卸下这个槽」那一行 */
.ex-cand-none {
  border-style: dashed;
}
.ex-cand-none .ex-cand-name {
  font-weight: 500;
  color: #6b7280;
}
.ex-cand-owner {
  margin-top: 4px;
  font-size: 11px;
  color: #9ca3af;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* ---- 「本次要换的」结果区（弹窗底部，一直显示）---- */
.ex-picked {
  margin-top: 10px;
  border: 1px solid #eef0f3;
  border-radius: 8px;
  padding: 8px 10px;
  background: rgba(219, 39, 119, 0.03);
}
.ex-picked-title {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 6px;
}
.ex-picked-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 4px;
  border-radius: 5px;
  font-size: 12px;
  cursor: pointer;
  min-width: 0;
}
.ex-picked-row:hover {
  background: rgba(219, 39, 119, 0.06);
}
/* 当前正在看的那个槽，左边加一条粉线 */
.ex-picked-row-active {
  border-left: 3px solid #db2777;
  padding-left: 6px;
}
.ex-picked-slot {
  flex: none;
  color: #6b7280;
}
.ex-picked-value {
  flex: 1;
  min-width: 0;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ex-picked-empty {
  color: #c4c8ce;
}
.ex-picked-clear {
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
  /* EX 装备弹窗：手机上图标小一点 */
  .ex-cand-icon {
    width: 34px;
    height: 34px;
  }
  .ex-picked-value {
    white-space: normal;
  }
}
</style>
