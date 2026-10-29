<template>
  <div class="box-page">
    <el-empty v-if="!groupId" description="请先从上方选择一个公会" />

    <template v-else>
      <!-- 功能切换 + 查询 -->
      <div class="toolbar kanna-card mt-16">
        <div class="toolbar-head">
          <el-radio-group v-model="activeTab" class="type-group">
            <el-radio-button value="self">个人 BOX</el-radio-button>
            <el-radio-button value="clan">公会 BOX</el-radio-button>
            <el-radio-button value="support">公会助战</el-radio-button>
            <el-radio-button value="mine">我的助战</el-radio-button>
            <el-radio-button value="arrange">排刀</el-radio-button>
            <el-radio-button value="friend">好友</el-radio-button>
          </el-radio-group>

          <!-- 竞技场监控开关（对应「竞技场中心」页的同一个功能）：
               开启后账号会一直保持登录，本页的【刷新缓存】/【刷新好友】/好友操作
               都会复用这个已登录的 client，不用每操作一次就重新登录（也少顶号）。
               出刀监控在跑同一个号时，后端 login.query 同样会复用它的登录 —— 不开关也一样。
               开关本身会登录游戏账号（顶号），所以开启前先弹确认。 -->
          <div class="monitor-box">
            <el-tag
              :type="arenaRunning ? 'success' : 'info'"
              size="small"
              effect="light"
              class="monitor-tag"
            >
              {{ arenaRunning ? '竞技场监控运行中' : '竞技场监控未运行' }}
            </el-tag>
            <el-button
              v-if="!arenaRunning"
              size="small"
              type="primary"
              :loading="arenaMonitorLoading"
              title="开启后账号保持登录，刷新缓存 / 好友操作不用反复登录（已有出刀监控在跑同一个号时同样会复用登录）"
              @click="toggleArenaMonitor"
            >
              开启监控
            </el-button>
            <el-button
              v-else-if="arenaMonitorIsMine"
              size="small"
              type="danger"
              :loading="arenaMonitorLoading"
              @click="toggleArenaMonitor"
            >
              取消监控
            </el-button>
          </div>

          <!-- 只有「个人 BOX」有「未拥有」概念：灰度列出没有的角色，一眼看出缺什么。
               注意别用 <label> 包 el-switch —— label 会把点击转发给开关内部的
               input，和开关自己的点击处理叠在一起变成「点两次」，开关看起来没反应。 -->
          <div v-if="activeTab === 'self'" class="missing-toggle">
            <el-switch v-model="showMissing" size="small" />
            <span @click="showMissing = !showMissing">显示未拥有</span>
          </div>
        </div>

        <div class="query-row">
          <!-- 好友页签没有角色名搜索，换成一排好友专用按钮：
               【刷新好友】读游戏里的好友列表、【添加好友】按玩家 ID 发请求。
               两个都要登录游戏账号（自己开着竞技场/出刀监控时复用登录、不顶号），
               点之前都会先弹确认。 -->
          <template v-if="activeTab === 'friend'">
            <el-button
              type="primary"
              :loading="friendRefreshing"
              @click="doFriendRefresh"
            >
              <el-icon v-if="!friendRefreshing"><Refresh /></el-icon>刷新好友
            </el-button>
            <el-button class="friend-add-btn" @click="openAddFriend">
              <el-icon><Plus /></el-icon>添加好友
            </el-button>
            <el-button class="friend-req-btn" @click="openFriendRequests">
              <el-icon><Bell /></el-icon>好友申请
            </el-button>
          </template>

          <template v-else-if="activeTab !== 'arrange'">
            <!-- 排刀页签不显示角色名查询和 BOX 刷新缓存按钮（表格地址 / 刷新按钮都在下面的排刀卡片里） -->
            <el-input
              v-if="activeTab !== 'mine'"
              v-model="roleName"
              class="role-input"
              :placeholder="rolePlaceholder"
              clearable
              @keyup.enter="doQuery(true)"
            />
            <el-button
              type="primary"
              :loading="loading"
              :disabled="activeTab === 'clan' && !roleName.trim()"
              @click="doQuery(true)"
            >
              <el-icon v-if="!loading"><Search /></el-icon>查询
            </el-button>

            <!-- 刷新缓存：点一下把「个人 BOX」和「本群公会助战」两份缓存都刷新
                 （等价于在群里把两条指令各发一次）。自己开着竞技场/出刀监控时复用登录、
                 不顶号，两边都没开才会顶号，所以点之前先弹确认。 -->
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
          </template>
        </div>

        <!-- 个人 BOX 练度条：紧贴查询框下面（替代原来那句说明）。
             数据来自 `BoxQueryResult.enhance`，只有个人 BOX 查询会带，
             公会 BOX / 助战 / 好友都没有，所以只在 self 页签渲染。
             还没查完（result 为空）或查询失败（ok=false，结果卡里已有原因）时整块不渲染，
             免得闪一条「还没有快照」或者和「没有这个角色」的提示打架。
             空数组约定：后端只返回真有的数据，某一组为空就**整组不画**（只留标签会像加载失败）。 -->
        <template v-if="activeTab === 'self' && result && result.ok">
          <div v-if="enhance && hasEnhanceData" class="enhance-bar">
            <!-- 第一行：MP等级 + 属性强化（火 / 水 / 风 / 光 / 暗 各一个色块） -->
            <div v-if="enhance.mp_level > 0 || enhanceTalents.length" class="enh-row">
              <span class="enh-key">MP等级</span>
              <span class="enh-mp">{{ enhance.mp_level }}</span>
              <template v-if="enhanceTalents.length">
                <span class="enh-key enh-key-attr">属性强化</span>
                <span
                  v-for="t in enhanceTalents"
                  :key="t.key"
                  class="enh-talent"
                  :class="`enh-talent-${t.tone}`"
                  :title="t.tip"
                >{{ t.name }} {{ t.levelText }}</span>
              </template>
            </div>

            <!-- 第二行：属性技能（第几页 / 第几合流 / 左中右三条线 / 余星幽碎片）。
                 口径照 autopcr 的【查深域】：`第3页 第12合流 左2[5级]/中1[3级] (余123)`。 -->
            <div v-if="enhanceSkill" class="enh-row">
              <span class="enh-key">属性技能</span>
              <span class="enh-skill-main">{{ enhanceSkill.main }}</span>
              <span
                v-for="b in enhanceSkill.branches"
                :key="b.key"
                class="enh-skill-branch"
                :title="b.tip"
              >{{ b.text }}</span>
              <span class="enh-skill-left" title="星幽碎片剩余（点属性技能消耗的材料）">
                余 {{ enhanceSkill.leftover }}
              </span>
            </div>

            <!-- 第三行：职介等级（8 个职阶，每个 4 个板块） -->
            <div v-if="enhanceRoles.length" class="enh-row">
              <span class="enh-key">职介等级</span>
              <span v-for="r in enhanceRoles" :key="r.key" class="enh-role">
                <i class="enh-role-name">{{ r.name }}</i>
                <b class="enh-role-val">{{ r.text }}</b>
              </span>
            </div>

            <!-- 快照时间 + 怎么更新 -->
            <div class="enh-foot">
              <span>快照 {{ fmtEnhanceTime(enhance.updated_at) }}</span>
              <span class="enh-foot-tip">点【刷新缓存】后更新</span>
            </div>
          </div>

          <!-- 有快照但三块全空（老区服没这些系统 / 数据没读到）：一行灰字，不画空标签 -->
          <div v-else-if="enhance" class="enh-empty">
            练度数据：这个号没有读到（点【刷新缓存】重试）
          </div>

          <!-- 还没刷过缓存 / 后端还没重启：一行灰字，不报错也不留空白块 -->
          <div v-else class="enh-empty">练度数据：还没有快照，点【刷新缓存】后显示（开着监控时复用登录，否则会短暂顶号）</div>
        </template>

        <div v-if="currentTip" class="tip-text">{{ currentTip }}</div>
      </div>

      <!-- 结果：头像网格 -->
      <div
        class="result-card kanna-card mt-16"
        :class="{ 'result-card-arrange': activeTab === 'arrange' }"
      >
        <!-- 排刀：表格抓取 / 三刀选择 / 补偿刀都在独立组件里，数据结构与
             BOX 查询完全不同，放在最前面单独一个分支。 -->
        <div v-if="activeTab === 'arrange'" class="arrange-result-wrap">
          <ArrangePlanner :group-id="groupId" />
        </div>

        <!-- 好友：列表 / 排序 / 解除 / 详情。好友页签的数据结构和其它页签完全不同，
             所以放在最前面单独一整个分支，后面原有的分支全部改成 v-else-if。 -->
        <div v-else-if="activeTab === 'friend'">
          <div v-if="friendLoading" class="loading-state">
            <el-icon class="is-loading" :size="26"><Loading /></el-icon>
            <span>正在读取好友列表，请稍候…</span>
          </div>

          <template v-else-if="friendList?.ok">
            <template v-if="sortedFriends.length">
              <!-- 顶部工具条：好友人数 + 排序 + 缓存时间（模仿游戏内好友列表的样式） -->
              <div class="friend-bar">
                <div class="friend-count">
                  好友 <b>{{ friendCount }}/{{ friendLimit }}</b> 人
                </div>
                <div class="friend-bar-right">
                  <el-select
                    v-model="friendSortKey"
                    size="small"
                    class="friend-sort-select"
                  >
                    <el-option label="玩家等级" value="level" />
                    <el-option label="全角色战力" value="power" />
                    <el-option label="好友数" value="friend_num" />
                    <el-option label="最后登录" value="last_login" />
                  </el-select>
                  <el-button
                    size="small"
                    class="friend-sort-dir"
                    @click="friendSortAsc = !friendSortAsc"
                  >
                    <el-icon><Sort /></el-icon>
                    {{ friendSortAsc ? '升序' : '降序' }}
                  </el-button>
                  <span class="friend-cache-time">{{ friendCacheText }}</span>
                </div>
              </div>

              <div class="friend-list">
                <div
                  v-for="f in sortedFriends"
                  :key="f.viewer_id"
                  class="friend-row"
                >
                  <!-- 头像由后端拼好、不带 rarity 参数 —— 好友列表照游戏里那样不画星级 -->
                  <div
                    class="friend-avatar"
                    title="查看好友详情"
                    @click="openFriendDetail(f)"
                  >
                    <img :src="f.avatar" :alt="f.name" loading="lazy" />
                  </div>

                  <div class="friend-main">
                    <div
                      class="friend-name"
                      title="查看好友详情"
                      @click="openFriendDetail(f)"
                    >
                      {{ f.name }}
                    </div>

                    <div class="friend-field">
                      <span class="friend-pill">玩家等级</span>
                      <span class="friend-line"></span>
                      <span class="friend-value">{{ f.level }}</span>
                    </div>
                    <div class="friend-field">
                      <span class="friend-pill">全角色战力</span>
                      <span class="friend-line"></span>
                      <span class="friend-value">{{
                        f.total_power.toLocaleString()
                      }}</span>
                    </div>
                    <div class="friend-field">
                      <span class="friend-pill">好友</span>
                      <span class="friend-line"></span>
                      <span class="friend-value">{{ f.friend_num }}/{{ friendLimit }}</span>
                    </div>
                  </div>

                  <div class="friend-side">
                    <div class="friend-login">
                      最后登录时间:{{ fmtLastLogin(f.last_login_time) }}
                    </div>
                    <el-button
                      class="friend-remove-btn"
                      size="small"
                      :loading="friendRemoving === f.viewer_id"
                      @click="doRemoveFriend(f)"
                    >
                      解除好友
                    </el-button>
                  </div>
                </div>
              </div>
            </template>

            <el-empty v-else description="好友列表是空的，点【添加好友】发送请求吧" />
          </template>

          <el-alert
            v-else
            :title="
              friendList?.message ||
              '还没有好友缓存，点上方【刷新好友】读取（开着竞技场/出刀监控时复用登录，否则会短暂顶号）'
            "
            type="info"
            show-icon
            :closable="false"
          />
        </div>

        <div v-else-if="loading" class="loading-state">
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

          <!-- 我的助战：照游戏「支援设定」界面画成三栏卡片（地下城·追忆的战场 /
               团队战·露娜之塔 / 关卡·活动），每栏固定 2 个位，空位也占一格。卡片字段与游戏里那张卡一致：
               头像 + 角色名 + 角色等级 + 角色 Rank，底下是【更换支援】按钮。
               按钮对应 QQ 端的【上地下城支援】/【上公会战支援】/【上关卡支援】，
               会登录游戏账号（自己开着竞技场/出刀监控时复用登录、不顶号），所以点之前先弹确认。 -->
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
                    class="support-card-avatar support-card-avatar-game"
                    :title="slot.unit.chara_name"
                    @click="openDetail(slot.unit)"
                  >
                    <GameUnitAvatar :unit="slot.unit" />
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
                      <!-- 战斗星级：会战里「调星」后实际生效的星级，和头像左下角那颗一致。
                           battle_rarity 非 0 说明真的调过，给个小标记（沿用详情弹窗的样式）。 -->
                      <div class="support-card-row">
                        <span class="support-card-label">战斗星级</span>
                        <span class="support-card-value">
                          {{ effectiveStar(slot.unit) }}★
                          <span v-if="isStarAdjusted(slot.unit)" class="lowered-tag">
                            已调星
                          </span>
                        </span>
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
              <div class="avatar-box" :class="{ 'avatar-box-game': unit.owned }">
                <GameUnitAvatar :unit="unit" />
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
          <div
            class="detail-avatar"
            :class="{
              'detail-avatar-game': detail.owned,
              'avatar-missing-img': !detail.owned,
            }"
          >
            <GameUnitAvatar :unit="detail" />
          </div>
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
                   battle_rarity 非 0 = 调过星（口径与卡片 / 选人弹窗的 isStarAdjusted 一致：
                   从 3★ 调回 5★ 时 battle_rarity=5，也算调过星）。 -->
              {{ detail.battle_rarity || detail.rarity }}
              <span v-if="detail.battle_rarity" class="lowered-tag"> 已调星 </span>
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
               读列表不登录；真换要登录游戏账号（自己开着竞技场/出刀监控时复用登录、不顶号），
               所以换之前弹确认。会战 EX 不走这里。 -->
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
         只列 Lv>10 的（游戏规定 Lv10 以上才能当支援）。
         打开时会**预选这一格现在挂着的角色**：想只改战斗星级时不用再点一次头像。 -->
    <el-dialog
      v-model="pickerVisible"
      :title="pickerTitle"
      width="640px"
      class="support-picker-dialog"
      @closed="onPickerClosed"
    >
      <div class="picker-head">
        <el-input
          v-model="pickerKeyword"
          class="picker-search"
          placeholder="输入角色名 / 别名筛选"
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
              <GameUnitAvatar :unit="u" />
            </div>
            <div class="picker-name">{{ u.chara_name }}</div>
            <div class="picker-lv">Lv.{{ u.level }}</div>
          </div>
        </div>
      </div>

      <!-- 战斗星级（调星）：只有 5★ 角色能调 —— 6★ 已满、低星还没到可调档位（游戏规则，
           后端也会拒）。0 = 不调整：用 0 而不是 null，省掉 el-radio-group 的 null 类型麻烦，
           提交时 0 直接不传 star。
           预选的角色本来就在这个支援位时，选一个新星级就能「只调星、不换人」（后端支持）。 -->
      <div v-if="pickerSelectedUnit" class="picker-star">
        <div class="picker-star-head">
          <span class="picker-star-label">战斗星级</span>
          <span class="picker-star-current">
            当前：{{ pickerEffectiveStar }}★
            <span v-if="isStarAdjusted(pickerSelectedUnit)" class="lowered-tag">已调星</span>
          </span>
        </div>
        <el-radio-group v-if="pickerCanChangeStar" v-model="pickerStar" size="small">
          <el-radio-button :value="0">不调整</el-radio-button>
          <el-radio-button :value="3">3★</el-radio-button>
          <el-radio-button :value="4">4★</el-radio-button>
          <el-radio-button :value="5">5★</el-radio-button>
        </el-radio-group>
        <div v-else class="picker-star-tip">
          只有 5 星角色可以调整战斗星级（当前 {{ pickerSelectedUnit.rarity }} 星）
        </div>
      </div>

      <template #footer>
        <span class="picker-footer-tip">{{ pickerFooterTip }}</span>
        <el-button @click="pickerVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!pickerSelected || (pickerSameUnit && !pickerStarChanged)"
          :loading="changing"
          @click="confirmChange"
        >
          {{ pickerSameUnit ? '确定调整' : '确定更换' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 普通 EX 装备弹窗：点详情里的「普通 EX 槽」打开。
         用法是**一次挑好三个槽再一起提交**：
           - 顶部三个按钮是角色能穿的三个槽（类别由角色决定），点着切；
           - 在某个槽里点一件装备就选定（相同词条的彩装已合并成一行，点哪行就是哪行）；
           - 切到别的槽时**已经选好的不会被清掉**；
           - 弹窗底部一直显示「本次要换的」三个槽的结果，挑完点一次「确定更换」就一起换。
         列表本身是纯读本地缓存（不登录、不顶号），只有点「确定更换」才登录游戏账号
          （自己开着竞技场/出刀监控时复用登录、不顶号）。 -->
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
        <span class="picker-footer-tip">会登录游戏账号</span>
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

    <!-- 添加好友：按对方玩家 ID 发好友请求。
         好友上限 40 人；发请求要登录你的游戏账号（自己开着竞技场/出刀监控时复用登录、不顶号），
         所以确认时再弹一次警告。 -->
    <el-dialog
      v-model="addFriendVisible"
      title="添加好友"
      width="420px"
      class="add-friend-dialog"
    >
      <div class="add-friend-body">
        <div class="add-friend-label">对方玩家 ID</div>
        <el-input
          v-model="addFriendId"
          placeholder="输入玩家ID（纯数字）"
          clearable
          @keyup.enter="confirmAddFriend"
        />
        <div class="add-friend-tip">
          好友上限 40 人。发送请求后对方同意才会出现在好友列表里；发送前会确认一次登录方式。
        </div>
      </div>
      <template #footer>
        <el-button @click="addFriendVisible = false">取消</el-button>
        <el-button type="primary" :loading="friendAdding" @click="confirmAddFriend">
          发送请求
        </el-button>
      </template>
    </el-dialog>

    <!-- 好友申请：游戏「好友管理」界面的两个页签（待审核列表 / 申请中的名单）。
         数据是实时的、不落缓存，打开弹窗和每次操作都要登录一次游戏账号
         （自己开着竞技场监控或出刀监控时复用登录、不会顶号）。点头像 / 名字可看详细资料。 -->
    <el-dialog
      v-model="friendRequestsVisible"
      title="好友申请"
      width="min(640px, 94vw)"
      top="6vh"
      class="friend-requests-dialog"
    >
      <div v-if="friendRequestsLoading" class="loading-state">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <span>正在读取好友申请，请稍候…</span>
      </div>

      <el-alert
        v-else-if="friendRequestsResult && !friendRequestsResult.ok"
        :title="friendRequestsResult.message"
        type="info"
        show-icon
        :closable="false"
      />

      <el-tabs v-else-if="friendRequestsResult" v-model="friendRequestsTab">
        <el-tab-pane
          :label="`待审核列表（${friendRequestsResult.pending.length}）`"
          name="pending"
        >
          <el-empty
            v-if="!friendRequestsResult.pending.length"
            description="没有待审核的好友申请"
            :image-size="70"
          />
          <div v-else class="friend-req-list">
            <div
              v-for="f in friendRequestsResult.pending"
              :key="f.viewer_id"
              class="friend-req-row"
            >
              <div
                class="friend-req-avatar"
                title="查看 TA 的详细资料"
                @click="openFriendDetail(f)"
              >
                <img :src="f.avatar" :alt="f.name" loading="lazy" />
              </div>
              <div class="friend-req-main">
                <div class="friend-req-top">
                  <div
                    class="friend-req-name"
                    title="查看 TA 的详细资料"
                    @click="openFriendDetail(f)"
                  >
                    {{ f.name }}
                  </div>
                  <div class="friend-req-login">
                    最后登录:{{ fmtLastLogin(f.last_login_time) }}
                  </div>
                </div>
                <div class="friend-req-chips">
                  <span class="friend-req-chip">
                    玩家等级 <b>{{ f.level }}</b>
                  </span>
                  <span class="friend-req-chip">
                    全角色战力 <b>{{ f.total_power.toLocaleString() }}</b>
                  </span>
                  <span class="friend-req-chip">
                    好友 <b>{{ f.friend_num }}/40</b>
                  </span>
                </div>
              </div>
              <div class="friend-req-actions">
                <el-button
                  size="small"
                  :loading="friendRequestActing === f.viewer_id"
                  @click="doRejectRequest(f)"
                >
                  拒绝
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  :loading="friendRequestActing === f.viewer_id"
                  @click="doAcceptRequest(f)"
                >
                  许可
                </el-button>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane
          :label="`申请中的名单（${friendRequestsResult.requested.length}）`"
          name="requested"
        >
          <el-empty
            v-if="!friendRequestsResult.requested.length"
            description="没有申请中的好友"
            :image-size="70"
          />
          <div v-else class="friend-req-list">
            <div
              v-for="f in friendRequestsResult.requested"
              :key="f.viewer_id"
              class="friend-req-row"
            >
              <div
                class="friend-req-avatar"
                title="查看 TA 的详细资料"
                @click="openFriendDetail(f)"
              >
                <img :src="f.avatar" :alt="f.name" loading="lazy" />
              </div>
              <div class="friend-req-main">
                <div class="friend-req-top">
                  <div
                    class="friend-req-name"
                    title="查看 TA 的详细资料"
                    @click="openFriendDetail(f)"
                  >
                    {{ f.name }}
                  </div>
                  <div class="friend-req-login">
                    最后登录:{{ fmtLastLogin(f.last_login_time) }}
                  </div>
                </div>
                <div class="friend-req-chips">
                  <span class="friend-req-chip">
                    玩家等级 <b>{{ f.level }}</b>
                  </span>
                  <span class="friend-req-chip">
                    全角色战力 <b>{{ f.total_power.toLocaleString() }}</b>
                  </span>
                  <span class="friend-req-chip">
                    好友 <b>{{ f.friend_num }}/40</b>
                  </span>
                </div>
              </div>
              <div class="friend-req-actions">
                <el-button
                  size="small"
                  :loading="friendRequestActing === f.viewer_id"
                  @click="doCancelRequest(f)"
                >
                  撤回申请
                </el-button>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- 好友详情：点好友头像 / 名字打开。资料卡与竞技场【查 ID】共用 ArenaProfilePanel，
         只是查询的 ID 换成点的那个人（数据与查 ID 完全一致）。 -->
    <el-dialog
      v-model="friendDetailVisible"
      :title="friendDetailTitle"
      width="min(560px, 92vw)"
      top="6vh"
    >
      <div v-if="friendDetailLoading" class="loading-state">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <span>正在查询，请稍候…</span>
      </div>
      <el-alert
        v-else-if="friendDetailResult && !friendDetailResult.ok"
        :title="friendDetailResult.message"
        type="info"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else-if="friendDetailError"
        :title="friendDetailError"
        type="info"
        show-icon
        :closable="false"
      />
      <ArenaProfilePanel
        v-else-if="friendDetailResult"
        :result="friendDetailResult"
        :group-id="groupId"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  acceptFriendRequest,
  addFriend,
  cancelFriendRequest,
  changeSupport,
  changeExEquip,
  getArenaStatus,
  getExEquipOptions,
  getFriendList,
  getFriendProfile,
  getFriendRequests,
  queryBox,
  queryClanBox,
  queryClanSupport,
  queryMySupport,
  refreshCache,
  refreshFriendList,
  rejectFriendRequest,
  removeFriend,
  switchArenaMonitor,
} from '@/api'
import type {
  ArenaProfileResult,
  BoxEnhanceRoleSlot,
  BoxQueryResult,
  BoxUnit,
  ExEquipCandidate,
  ExEquipChangeForm,
  ExEquipOptionsResult,
  ExEquipSlotInfo,
  ExEquipSubStatus,
  FriendListResult,
  FriendRequestsResult,
  FriendRow,
  SupportChangeForm,
} from '@/types'
import { useUserStore } from '@/store/user'
import ArenaProfilePanel from '@/components/ArenaProfilePanel.vue'
import GameUnitAvatar from '@/components/GameUnitAvatar.vue'
import ArrangePlanner from '@/components/ArrangePlanner.vue'

const props = defineProps<{ groupId?: number }>()
const route = useRoute()
const userStore = useUserStore()

// 与 Dashboard / Report / Notice 一致：URL 参数 > props > store
const groupId = computed<number>(
  () => Number(route.params.groupId) || props.groupId || userStore.currentClanId,
)

type TabKey = 'self' | 'clan' | 'support' | 'mine' | 'friend' | 'arrange'
const activeTab = ref<TabKey>('self')
const roleName = ref('')
// 输入即筛选用的状态。**必须声明在下面带 immediate 的 watcher 之前**：
// 挂载时 watcher 会立刻调 doQuery()，而 doQuery 里要读写这几个变量，
// 声明在它后面会撞暂时性死区（ReferenceError），首屏就查不出东西。
let queryTimer: ReturnType<typeof setTimeout> | null = null
let querySeq = 0
let lastQueryKey = ''
const loading = ref(false)
const refreshing = ref(false)
const result = ref<BoxQueryResult | null>(null)
// 个人 BOX：是否把「未拥有」的角色也灰度列出来（一眼看出缺什么）
const showMissing = ref(true)

// 竞技场监控状态（与「竞技场中心」页是同一个监控）：
// 开启后账号一直保持登录，本页的【刷新缓存】/【刷新好友】/好友操作都会复用
// 这个已登录的 client，不用每操作一次就重新登录（也少顶号）。
// 出刀监控在跑同一个号时后端也会复用它的登录（login.client_cache 按账号共享）。
// 状态要在 watcher（immediate）之前声明，否则 groupId 首次变化时会撞暂时性死区。
const arenaRunning = ref(false)
const arenaMonitorIsMine = ref(false)
const arenaMonitorLoading = ref(false)

const detail = ref<BoxUnit | null>(null)
const detailVisible = ref(false)

const TIPS: Record<TabKey, string> = {
  // 个人 BOX 原来那句「默认显示整个 box…」已经去掉：查询框下面改成练度条了
  // （见模板里的 `.enhance-bar`）。空串不会渲染 `.tip-text`（v-if="currentTip"）。
  self: '',
  clan: '查本群所有绑定过公会的成员里，谁有这个角色（不支持「所有」）。',
  support: '默认显示本群缓存的全部公会战助战（对应 QQ 端的【精确助战】）；也可以输入角色名或别名筛选。',
  mine: '',
  friend: '',
  arrange: '',
}
const currentTip = computed(() => TIPS[activeTab.value])

// 搜索框提示按页签给：公会助战一进来就是全部，不写「所有」；
// 公会 BOX 后端也不支持「所有」（人多会卡死），同样不写。
const ROLE_PLACEHOLDER: Record<TabKey, string> = {
  self: '输入即筛选：角色名或别名（如 环、环奈、nnk / 所有）',
  clan: '输入即筛选：角色名或别名（如 环、环奈、nnk）',
  support: '输入即筛选：角色名或别名（如 环、环奈、nnk）',
  mine: '',
  friend: '',
  arrange: '',
}
const rolePlaceholder = computed(() => ROLE_PLACEHOLDER[activeTab.value])

// 进入这几个页签就自动查一次，不用先点「查询」：
//   个人 BOX / 公会助战 → 默认查「所有」；我的助战 → 本身就是全部（也没有搜索框）
const AUTO_LOAD_TABS: TabKey[] = ['self', 'support', 'mine']
const isAutoLoad = (tab: TabKey) => AUTO_LOAD_TABS.includes(tab)
// 不填角色名也能查的页签（不填 = 看全部）
const allowEmptyQuery = (tab: TabKey) => tab === 'self' || tab === 'support'

// 「我的助战」三栏：顺序照游戏「支援设定」界面（左→右：地下城·追忆的战场 /
// 团队战·露娜之塔 / 关卡·活动），每栏固定 2 个位。
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
  { key: 'dungeon', title: '地下城 · 追忆的战场', mode: 1, positions: [3, 4] },
  { key: 'clan', title: '团队战 · 露娜之塔', mode: 2, positions: [5, 6] },
  { key: 'adventure', title: '关卡 · 活动', mode: 3, positions: [1, 2] },
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

// ---- 战斗星级（调星）----
// 会战里可以把「战斗星级」调得比拥有星级低（改变 TP 获取节奏），AUTOPCR 的挂支援
// 模块也支持。口径与详情弹窗、头像组件一致：`battle_rarity || rarity`，6★ 恒为 6。
// 这两个小工具被「我的助战」卡片和选人弹窗共用，写在一起免得两处口径跑偏。
function effectiveStar(unit: BoxUnit | null): number {
  if (!unit) return 0
  // 6★ 固定 6（游戏里 6★ 不参与调星，头像组件 GameUnitAvatar 也是这么画的），
  // 其余用调星后的星级，没调过（battle_rarity = 0）就回退到拥有星级
  if (unit.rarity >= 6) return 6
  return unit.battle_rarity || unit.rarity
}

// `battle_rarity` 非 0 = 真的调过星（后端口径：0 表示没调过，不是「调到 0 星」）
function isStarAdjusted(unit: BoxUnit | null): boolean {
  return !!unit && Number(unit.battle_rarity) > 0
}

// 个人 BOX / 我的助战 里玩家名就是你自己，重复显示没意义；
// 公会 BOX / 助战 才是「同角色多人拥有」，必须靠名字区分。
const showPlayerName = computed(
  () => activeTab.value === 'clan' || activeTab.value === 'support',
)

// ---- 个人 BOX 练度条（MP等级 / 属性强化 / 职介等级）----
// 后端从游戏 `load/index` 的 `princess_knight_info` / `unit_role_list` 里读出来，
// 只有「个人 BOX」查询（`BoxQueryResult.enhance`）会带，公会 BOX / 助战 / 好友都没有。
// 还没刷过缓存或后端还没重启时 enhance 缺失 / 为 null，模板里退化成一行灰字提示。
const enhance = computed(() => result.value?.enhance ?? null)

// 属性强化的固定顺序（火 / 水 / 风 / 光 / 暗）。后端一般会带 name，
// 这里只是兜底；配色按属性固定（火红 / 水蓝 / 风绿 / 光橙 / 暗紫），
// 与竞技场资料卡的深域（`ArenaProfilePanel.vue` 的 TALENT_PILLS）保持一致。
const TALENT_NAMES = ['火', '水', '风', '光', '暗']

// 职阶的固定顺序（后端按 unit_role_id 排好并带 name，这里只兜底 name 缺失的情况）
const ROLE_NAMES = [
  '攻击型',
  '破防型',
  '增益型',
  '减益型',
  '强化型',
  '治疗型',
  '坦克型',
  '干扰型',
]

/** 属性强化 chip：`火 440`（440 = 换算后的属性等级），累计点数放 title 里不占地方 */
const enhanceTalents = computed(() =>
  (enhance.value?.talents ?? []).map((t, i) => {
    // 颜色和兜底名字都按 talent_id（1~5 = 火 / 水 / 风 / 光 / 暗）算，
    // 后端万一换个顺序返回也不会串色
    const idx = t.talent_id > 0 ? t.talent_id - 1 : i
    const tone = ((idx % TALENT_NAMES.length) + TALENT_NAMES.length) % TALENT_NAMES.length
    const name = t.name || TALENT_NAMES[tone] || `属性${tone + 1}`
    const point = t.point ? ` · 累计点数 ${t.point.toLocaleString()}` : ''
    // level=0 只会在阈值表缺失时出现（换算不出来），别显示成「火 0」误导人
    const levelText = t.level > 0 ? String(t.level) : '未知'
    return {
      key: `${t.talent_id ?? i}-${i}`,
      name,
      level: t.level,
      levelText,
      tip: `属性等级 ${levelText}${point}`,
      tone,
    }
  }),
)

/**
 * 职阶 chip 的数值文案（来源就是 slots）：
 * - 4 个板块的等级 / 星级全相同且都解锁 → 折叠成 `3★2`（等级★星级）
 * - 不一致 → 展开成 `3-2/3-2/4-1/4-1`（等级-星级），没解锁的板块写 `-`
 * - 4 个板块全没解锁 → 直接写「未解锁」，别占一整串横杠
 */
function roleSlotsText(slots: BoxEnhanceRoleSlot[]): string {
  if (!slots.length) return '-'
  const unlocked = slots.filter((s) => s.unlocked)
  if (!unlocked.length) return '未解锁'
  const first = slots[0]
  const same =
    unlocked.length === slots.length &&
    slots.every((s) => s.level === first.level && s.star === first.star)
  if (same) return `${first.level}★${first.star}`
  return slots.map((s) => (s.unlocked ? `${s.level}-${s.star}` : '-')).join('/')
}

const enhanceRoles = computed(() =>
  (enhance.value?.roles ?? []).map((r, i) => ({
    key: `${r.role_id ?? i}-${i}`,
    name: r.name || ROLE_NAMES[i] || `职阶${i + 1}`,
    text: roleSlotsText(r.slots ?? []),
  })),
)

/**
 * 属性技能那一行的文案（口径照 autopcr 的 `get_talent_skill_info`）：
 * - 主文案：`第3页 · 第12合流`；合流之后没有新节点时补 `[4级]`（最后一个合流节点的等级）
 * - 分支 chip：`左2[5级]`（这条线点了 2 个节点、最高 5 级）
 * - 余量：`余 123`（星幽碎片，点属性技能消耗的材料）
 * `skill` 为 null = 没点过属性技能 / 老区服没这系统 → 整行不画。
 */
const enhanceSkill = computed(() => {
  const s = enhance.value?.skill
  if (!s) return null
  const page = s.page > 0 ? `第${s.page}页` : '页数未知'
  const tail =
    !s.branches.length && s.last_joined_level > 0 ? `[${s.last_joined_level}级]` : ''
  return {
    main: `${page} · 第${s.joined_count}合流${tail}`,
    branches: (s.branches ?? []).map((b, i) => ({
      key: `${b.pos}-${i}`,
      text: `${b.pos}${b.count}[${b.level}级]`,
      tip: `${b.pos}线点了 ${b.count} 个节点，最高 ${b.level} 级`,
    })),
    leftover: s.leftover,
  }
})

/**
 * 三块里有没有任何一块能画（放在 enhanceTalents / enhanceRoles 之后声明，
 * 免得以后有人把它改成非惰性求值时撞上暂时性死区）。
 * 后端约定「只返回真有的数据」，所以空数组/0 可能意味着这个号（或这个区服）
 * 压根没有对应系统 —— 这时整块退回一行灰字，别只剩几个空标签。
 */
const hasEnhanceData = computed(
  () =>
    (enhance.value?.mp_level ?? 0) > 0 ||
    enhanceTalents.value.length > 0 ||
    enhanceRoles.value.length > 0 ||
    !!enhance.value?.skill,
)

/** 练度快照时间：0 = 未知（还没读到）；顺手兼容一下毫秒时间戳 */
function fmtEnhanceTime(ts: number) {
  if (!ts) return '未知'
  const seconds = ts > 1e12 ? Math.floor(ts / 1000) : ts
  const d = new Date(seconds * 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

// 进入页面 / 切群 / 切页签时的默认加载
function autoLoad() {
  if (!groupId.value) return
  if (isAutoLoad(activeTab.value) || roleName.value.trim()) doQuery()
}

// ---- 竞技场监控开关（与「竞技场中心」页同一个功能）----
// 开启后账号会一直保持登录：本页的【刷新缓存】/【刷新好友】/好友操作复用这个
// 已登录的 client，不用每操作一次就重新登录，也少顶号。出刀监控在跑同一个号时
// 后端同样会复用它的登录（login.client_cache 按账号共享），不开关也一样。
// 开关本身要登录游戏账号（顶号），所以开启前先弹确认。停止只有监控人本人或
// bot 主人能操作（后端校验）。

/** 查一次监控状态（纯读接口，不登录）。返回是否查成功；失败时保留旧状态不打扰用户。 */
async function refreshArenaStatus(): Promise<boolean> {
  if (!groupId.value) return false
  try {
    const st = await getArenaStatus(groupId.value)
    arenaRunning.value = !!st.running
    arenaMonitorIsMine.value = !!st.is_monitor
    return true
  } catch (e) {
    /* 状态查不到不影响其它功能，保留上一次的值 */
    return false
  }
}

/** 开启 / 取消监控（开启 = 登录账号并常驻；取消 = 停止监控循环） */
async function toggleArenaMonitor() {
  if (!groupId.value || arenaMonitorLoading.value) return

  if (!arenaRunning.value) {
    try {
      await ElMessageBox.confirm(
        '开启监控会用你绑定的游戏账号登录游戏（若你正在游戏会被顶下线），并持续监视排名变化。' +
          '开启后账号保持登录，本页的【刷新缓存】/【刷新好友】/好友操作都会复用这个登录，' +
          '不用每操作一次就重新登录。确定开启吗？',
        '开启竞技场监控',
        { type: 'warning', confirmButtonText: '开启', cancelButtonText: '取消' },
      )
    } catch {
      // 用户取消
      return
    }
    arenaMonitorLoading.value = true
    try {
      const res = await switchArenaMonitor(groupId.value, { action: 'on' })
      ElMessage.success(res.message || '监控启动中')
      pollArenaStatus()
    } catch (e) {
      /* 错误提示由请求拦截器统一处理 */
    } finally {
      arenaMonitorLoading.value = false
    }
    return
  }

  if (!arenaMonitorIsMine.value) {
    ElMessage.info('当前监控不是你开启的，只有监控人本人或 bot 主人可以取消')
    return
  }
  try {
    await ElMessageBox.confirm(
      '取消后账号不再由竞技场监控保持登录；如果也没有出刀监控在跑，本页的【刷新缓存】/【刷新好友】/好友操作会重新登录（可能顶号）。确定取消吗？',
      '取消竞技场监控',
      { type: 'warning', confirmButtonText: '取消监控', cancelButtonText: '再想想' },
    )
  } catch {
    // 用户取消
    return
  }
  arenaMonitorLoading.value = true
  try {
    await switchArenaMonitor(groupId.value, { action: 'off' })
    ElMessage.success('已取消竞技场监控')
    await refreshArenaStatus()
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    arenaMonitorLoading.value = false
  }
}

/** 开启后循环查几次状态，等监控循环真正跑起来（与竞技场中心页同一套做法） */
function pollArenaStatus(times = 8) {
  let n = 0
  const tick = async () => {
    n += 1
    await refreshArenaStatus()
    if (!arenaRunning.value && n < times) setTimeout(tick, 2000)
  }
  setTimeout(tick, 1500)
}

// 竞技场监控是**你自己开的**时，本页的刷新 / 好友操作会复用监控已登录的账号，
// 不会重新登录、也就不会顶号 —— 确认弹窗里不该再吓唬用户。
// 注意：群监控是别人开的时不算（好友操作用的是你自己的号，仍可能登录）。
// 出刀监控在跑同一个号时后端也会复用登录，但这里只查了竞技场监控（没查 = 按可能
// 登录的保守文案提示，不会误报「不会顶号」）。
const reuseMonitorLogin = computed(
  () => arenaRunning.value && arenaMonitorIsMine.value,
)

/** 给确认弹窗用的「登录方式」说明：先校准一次监控状态，查不到时按可能顶号保守提示。 */
async function currentLoginHint(): Promise<string> {
  const ok = await refreshArenaStatus()
  return ok && reuseMonitorLogin.value
    ? '会复用已登录的监控账号（不会顶号）'
    : '如果你自己没开着竞技场监控或出刀监控，会临时登录你的游戏账号（把正在游戏的你挤下线）'
}

// 切换功能时清掉上一次的结果、输入与详情，避免张冠李戴；
// 个人 BOX / 公会助战 / 我的助战 切过来就直接出内容。
// 好友页签的数据结构完全不同：清掉旧列表、只读一次缓存（不登录），不走 autoLoad。
watch(activeTab, () => {
  result.value = null
  roleName.value = ''
  closeDetail()
  // 监控状态是全局的，切页签顺手校准一次（可能刚在竞技场中心开/关过）
  void refreshArenaStatus()
  if (activeTab.value === 'friend') {
    friendList.value = null
    loadFriendList()
    return
  }
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
    void refreshArenaStatus()
    if (activeTab.value === 'friend') {
      friendList.value = null
      loadFriendList()
      return
    }
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
// 1/2 关卡（库里仍叫「冒险」）、3/4 地下城、5/6 团队战·露娜塔，每栏各 2 个位。
const SUPPORT_POS_LABEL: Record<number, string> = {
  1: '关卡助战位 1',
  2: '关卡助战位 2',
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

// ---- 输入即筛选 ----
// 打字停 250ms 就自动查一次，不用点【查询】；后端按名字 / 别名的**子串**匹配，
// 所以打「环」先列出所有带环的角色，继续打「环奈」再收窄（环奈、环奈（振袖）都会在）。
// 计时器 / 序号 / 上次查询条件这几个状态声明在文件上方（immediate watcher 之前）。

function scheduleQuery() {
  if (queryTimer) clearTimeout(queryTimer)
  queryTimer = setTimeout(() => {
    queryTimer = null
    void doQuery(false, true)
  }, 250)
}

/**
 * 查询当前页签。
 *
 * @param force  手动触发（按钮 / 回车）：跳过「条件没变」的去重
 * @param silent 自动筛选触发：不显示加载态、不清空旧结果，免得每敲一个字闪一下
 */
async function doQuery(force = false, silent = false) {
  if (!groupId.value) return
  if (queryTimer) {
    clearTimeout(queryTimer)
    queryTimer = null
  }
  const tab = activeTab.value
  // 排刀页签的数据由 ArrangePlanner 自己加载（还有自己的刷新按钮），不走 BOX 查询
  if (tab === 'arrange') return
  // 个人 BOX / 公会助战：不填角色名 = 看全部（进入这两个页签时也会自动查一次）；
  // 我的助战压根没有搜索框，也不需要角色名。
  const name = roleName.value.trim() || (allowEmptyQuery(tab) ? '所有' : '')
  if (!name && tab !== 'mine') {
    if (!silent) ElMessage.warning('请输入角色名')
    return
  }
  // 自动筛选去重：切页签时清空输入会重复触发一次，同样的条件就不用再查
  const key = `${tab}|${name}|${showMissing.value}`
  if (!force && key === lastQueryKey) return

  const seq = ++querySeq
  if (!silent) {
    loading.value = true
    result.value = null
    closeDetail()
  }
  try {
    let res: BoxQueryResult
    if (tab === 'self') {
      res = await queryBox(groupId.value, name, showMissing.value)
    } else if (tab === 'clan') {
      res = await queryClanBox(groupId.value, name)
    } else if (tab === 'support') {
      res = await queryClanSupport(groupId.value, name)
    } else {
      res = await queryMySupport(groupId.value)
    }
    // 打字快时旧请求可能后到，丢掉过期结果
    if (seq !== querySeq) return
    result.value = res
    if (res?.ok) lastQueryKey = key
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    // 只有「最新的一次查询」能收尾：静默查询把加载态收掉，避免被它顶掉的
    // 非静默查询提前返回后 loading 卡住
    if (seq === querySeq) loading.value = false
  }
}

// 输入即筛选：个人 BOX / 公会 BOX / 公会助战三个页签，打完字自动查
watch(roleName, () => {
  const tab = activeTab.value
  if (tab !== 'self' && tab !== 'clan' && tab !== 'support') return
  // 公会 BOX 没有「所有」，清空输入就清空结果，不弹「请输入角色名」
  if (tab === 'clan' && !roleName.value.trim()) {
    result.value = null
    return
  }
  scheduleQuery()
})

// ---- 好友 ----
//
// 好友列表走游戏 `friend/list` 接口：**读缓存不登录**，所以进页签就自动拉一次；
// 【刷新好友】/【添加好友】/【解除好友】要登录游戏账号（自己开着竞技场/出刀监控时
// 复用登录、不顶号），调用前先确认。
// 这三个写操作后端都返回刷新后的完整列表，前端直接整个替换 `friendList` 即可。
const friendList = ref<FriendListResult | null>(null)
const friendLoading = ref(false)
const friendRefreshing = ref(false)
// 正在解除的那一个（只让它自己的按钮转圈），0 = 没有进行中的解除
const friendRemoving = ref(0)
// 排序纯前端做，默认按玩家等级降序（和游戏里一致）
type FriendSortKey = 'level' | 'power' | 'friend_num' | 'last_login'
const friendSortKey = ref<FriendSortKey>('level')
const friendSortAsc = ref(false)

const friendCount = computed(() => friendList.value?.count ?? 0)
const friendLimit = computed(() => friendList.value?.limit || 40)

const sortedFriends = computed(() => {
  const rows = [...(friendList.value?.friends ?? [])]
  const dir = friendSortAsc.value ? 1 : -1
  rows.sort((a, b) => {
    let diff = 0
    if (friendSortKey.value === 'level') diff = a.level - b.level
    else if (friendSortKey.value === 'power') diff = a.total_power - b.total_power
    else if (friendSortKey.value === 'friend_num') diff = a.friend_num - b.friend_num
    else diff = a.last_login_time - b.last_login_time
    return diff * dir
  })
  return rows
})

// 缓存时间：updated_at=0 表示后端还没刷过（不是「刚刚」），显示成 —
function fmtCacheTime(ts: number) {
  if (!ts) return '—'
  const d = new Date(ts * 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
const friendCacheText = computed(() =>
  friendList.value?.ok ? `缓存于 ${fmtCacheTime(friendList.value.updated_at)}` : '',
)

// 最后登录：0 = 未知；其余按游戏里的口径显示「N天前」
function fmtLastLogin(ts: number) {
  if (!ts) return '未知'
  const diff = Math.floor(Date.now() / 1000) - ts
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  return `${Math.floor(diff / 86400)}天前`
}

// 好友详情弹窗：标题用点开的那一行名字；结果直接复用竞技场【查 ID】的资料卡组件
const friendDetailVisible = ref(false)
const friendDetailLoading = ref(false)
const friendDetailName = ref('')
const friendDetailResult = ref<ArenaProfileResult | null>(null)
// 请求本身失败（网络 / 后端 5xx）时的兜底文案：拦截器只弹 toast，
// 弹窗里得有个提示，不然会是一片空白。
const friendDetailError = ref('')
const friendDetailTitle = computed(() =>
  friendDetailName.value ? `${friendDetailName.value} 的详情` : '好友详情',
)

// 添加好友弹窗
const addFriendVisible = ref(false)
const addFriendId = ref('')
const friendAdding = ref(false)

// 好友申请弹窗（游戏「好友管理」的两个页签：待审核列表 / 申请中的名单）。
// 这两份名单是实时数据、不落缓存，所以打开和每次操作都会临时登录游戏账号。
const friendRequestsVisible = ref(false)
const friendRequestsLoading = ref(false)
const friendRequestsTab = ref<'pending' | 'requested'>('pending')
const friendRequestsResult = ref<FriendRequestsResult | null>(null)
// 正在处理的那一条（只让它自己的按钮转圈），0 = 没有进行中的操作
const friendRequestActing = ref(0)

/** 进好友页签 / 切群后拉一次缓存（纯读后端缓存，不登录、不顶号） */
async function loadFriendList() {
  if (!groupId.value) return
  friendLoading.value = true
  try {
    friendList.value = await getFriendList(groupId.value)
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    friendLoading.value = false
  }
}

/** 【刷新好友】：按监控状态决定是否顶号，先确认再刷 */
async function doFriendRefresh() {
  if (!groupId.value || friendRefreshing.value) return
  const hint = await currentLoginHint()
  try {
    await ElMessageBox.confirm(
      `刷新好友${hint}，从游戏里重新读一遍好友列表。确定现在刷新吗？`,
      '刷新好友',
      { type: 'warning', confirmButtonText: '确定刷新', cancelButtonText: '再等等' },
    )
  } catch {
    // 用户取消
    return
  }

  friendRefreshing.value = true
  try {
    const res = await refreshFriendList(groupId.value)
    if (!res.ok) {
      ElMessage.warning(res.message)
      return
    }
    friendList.value = res
    ElMessage.success(res.message)
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    friendRefreshing.value = false
  }
}

function openAddFriend() {
  addFriendId.value = ''
  addFriendVisible.value = true
}

/** 添加好友：先校验 ID，再弹一次登录确认，最后才真的发请求 */
async function confirmAddFriend() {
  if (!groupId.value || friendAdding.value) return
  const id = addFriendId.value.trim()
  if (!/^\d+$/.test(id) || Number(id) <= 0) {
    ElMessage.warning('请输入正确的玩家 ID（纯数字）')
    return
  }

  const hint = await currentLoginHint()
  try {
    await ElMessageBox.confirm(
      `会给玩家 ID ${id} 发送好友请求。这一步${hint}，` +
        '对方同意后才会出现在好友列表里。确定发送吗？',
      '添加好友',
      { type: 'warning', confirmButtonText: '发送请求', cancelButtonText: '再想想' },
    )
  } catch {
    // 用户取消
    return
  }

  friendAdding.value = true
  try {
    const res = await addFriend(groupId.value, Number(id))
    if (!res.ok) {
      ElMessage.warning(res.message)
      return
    }
    friendList.value = res
    ElMessage.success(res.message)
    addFriendVisible.value = false
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    friendAdding.value = false
  }
}

/** 解除好友：先确认，再调接口 */
async function doRemoveFriend(f: FriendRow) {
  if (!groupId.value || friendRemoving.value) return
  const hint = await currentLoginHint()
  try {
    await ElMessageBox.confirm(
      `确定要解除与「${f.name}」（ID ${f.viewer_id}）的好友关系吗？这一步${hint}。`,
      '解除好友',
      { type: 'warning', confirmButtonText: '解除', cancelButtonText: '再想想' },
    )
  } catch {
    // 用户取消
    return
  }

  friendRemoving.value = f.viewer_id
  try {
    const res = await removeFriend(groupId.value, f.viewer_id)
    if (!res.ok) {
      ElMessage.warning(res.message)
      return
    }
    friendList.value = res
    ElMessage.success(res.message)
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    friendRemoving.value = 0
  }
}

// ---- 好友申请（待审核列表 / 申请中的名单）----
// 游戏「好友管理」界面的两个页签。数据是实时的、不落缓存，所以打开弹窗和
// 同意 / 拒绝 / 撤回都要登录一次游戏账号，操作前先确认
// （自己开着竞技场监控或出刀监控时复用登录、不会顶号）。

/** 打开「好友申请」弹窗：先确认登录方式，再拉待审核 + 申请中两份名单 */
async function openFriendRequests() {
  if (!groupId.value || friendRequestsLoading.value) return
  const hint = await currentLoginHint()
  try {
    await ElMessageBox.confirm(
      `好友申请列表是实时数据，读取${hint}。确定读取吗？`,
      '好友申请',
      { type: 'warning', confirmButtonText: '读取', cancelButtonText: '取消' },
    )
  } catch {
    // 用户取消
    return
  }

  friendRequestsVisible.value = true
  friendRequestsLoading.value = true
  friendRequestsResult.value = null
  friendRequestsTab.value = 'pending'
  try {
    friendRequestsResult.value = await getFriendRequests(groupId.value)
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    friendRequestsLoading.value = false
  }
}

/** 同意好友申请；同意后好友列表会多一个人，顺手重拉 */
async function doAcceptRequest(f: FriendRow) {
  if (!groupId.value || friendRequestActing.value) return
  const hint = await currentLoginHint()
  try {
    await ElMessageBox.confirm(
      `确定同意「${f.name}」（ID ${f.viewer_id}）的好友申请吗？这一步${hint}。`,
      '同意好友申请',
      { type: 'warning', confirmButtonText: '同意', cancelButtonText: '再想想' },
    )
  } catch {
    // 用户取消
    return
  }

  friendRequestActing.value = f.viewer_id
  try {
    const res = await acceptFriendRequest(groupId.value, f.viewer_id)
    if (!res.ok) {
      ElMessage.warning(res.message)
      return
    }
    friendRequestsResult.value = res
    ElMessage.success(res.message)
    // 同意后好友列表多了一个人，重拉一次缓存
    await loadFriendList()
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    friendRequestActing.value = 0
  }
}

/** 拒绝好友申请 */
async function doRejectRequest(f: FriendRow) {
  if (!groupId.value || friendRequestActing.value) return
  const hint = await currentLoginHint()
  try {
    await ElMessageBox.confirm(
      `确定拒绝「${f.name}」（ID ${f.viewer_id}）的好友申请吗？这一步${hint}。`,
      '拒绝好友申请',
      { type: 'warning', confirmButtonText: '拒绝', cancelButtonText: '再想想' },
    )
  } catch {
    // 用户取消
    return
  }

  friendRequestActing.value = f.viewer_id
  try {
    const res = await rejectFriendRequest(groupId.value, f.viewer_id)
    if (!res.ok) {
      ElMessage.warning(res.message)
      return
    }
    friendRequestsResult.value = res
    ElMessage.success(res.message)
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    friendRequestActing.value = 0
  }
}

/** 撤回我发出的好友申请 */
async function doCancelRequest(f: FriendRow) {
  if (!groupId.value || friendRequestActing.value) return
  const hint = await currentLoginHint()
  try {
    await ElMessageBox.confirm(
      `确定撤回发给「${f.name}」（ID ${f.viewer_id}）的好友申请吗？这一步${hint}。`,
      '撤回好友申请',
      { type: 'warning', confirmButtonText: '撤回', cancelButtonText: '再想想' },
    )
  } catch {
    // 用户取消
    return
  }

  friendRequestActing.value = f.viewer_id
  try {
    const res = await cancelFriendRequest(groupId.value, f.viewer_id)
    if (!res.ok) {
      ElMessage.warning(res.message)
      return
    }
    friendRequestsResult.value = res
    ElMessage.success(res.message)
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    friendRequestActing.value = 0
  }
}

/** 点好友头像 / 名字：查这个人的资料（和竞技场【查 ID】同一个返回结构） */
async function openFriendDetail(f: FriendRow) {
  if (!groupId.value) return
  // 每次点都重新确认监控状态（进页签时查的快照可能已经过期）。
  // 没有竞技场监控在跑（或状态查不到，保守处理）时，后端查详情会退回你自己的账号 ——
  // 该号上开着出刀监控时同样会复用、不会登录，但这里没查，按保守文案先问一次；
  // 有竞技场监控时直接借监控 client，不打扰用户。
  const statusOk = await refreshArenaStatus()
  if (!statusOk || !arenaRunning.value) {
    try {
      await ElMessageBox.confirm(
        '当前没有可借用的竞技场监控；如果你自己也没开着出刀监控，查看好友详情会临时登录你的游戏账号（把正在游戏的你挤下线）。',
        '查看好友详情',
        { type: 'warning', confirmButtonText: '确定查看', cancelButtonText: '取消' },
      )
    } catch {
      // 用户取消
      return
    }
  }
  friendDetailName.value = f.name
  friendDetailResult.value = null
  friendDetailError.value = ''
  friendDetailVisible.value = true
  friendDetailLoading.value = true
  try {
    friendDetailResult.value = await getFriendProfile(groupId.value, f.viewer_id)
  } catch (e) {
    // 拦截器已经弹过 toast，这里给弹窗一个兜底提示，避免一片空白
    friendDetailError.value = '查询失败，请稍后再试；也可以先点【刷新好友】登录一次再来看'
  } finally {
    friendDetailLoading.value = false
  }
}

// 切页签 / 切群时把好友相关弹窗收掉，避免弹窗跨页签残留
// （和 BOX 角色详情同一个规矩；这里单独挂 watcher 是为了不打扰上面已有的加载逻辑）。
watch([activeTab, groupId], () => {
  friendDetailVisible.value = false
  addFriendVisible.value = false
})

// ---- 刷新缓存 ----
//
// 只有一个按钮：点一下**把两份缓存都刷新**（个人 BOX + 本群公会助战），
// 等价于在群里先后发【刷新box缓存】和【刷新助战缓存】。
// 两份共用同一次登录（不会比只刷一份更慢）；自己开着竞技场监控或出刀监控时会复用
// 监控的登录、不会顶号，两边都没开才会真的登录一次，所以点之前必须弹确认。
const refreshLabel = '刷新缓存'
const refreshHint = '一次把「个人 BOX」和「本群公会助战」两份缓存都刷新'

async function doRefresh() {
  if (!groupId.value || refreshing.value) return
  const hint = await currentLoginHint()
  try {
    await ElMessageBox.confirm(
      `刷新${hint}，一次刷新「个人 BOX」和「本群公会助战」两份缓存，大约需要几秒。确定现在刷新吗？`,
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
    // 刷完自动重查一遍，用户不用再点一次「查询」（force：数据变了，不能被去重挡掉）
    await doQuery(true)
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
// 并真的改游戏里的支援设定（自己开着竞技场/出刀监控时复用登录、不顶号），
// 所以确认弹窗里必须把这点说清楚。
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
// 要调整到的战斗星级：0 = 不调整（用 0 而不是 null，省掉 el-radio-group 的 null 类型麻烦；
// 提交时 0 直接不传 star）。换人 / 重开弹窗时都会重置，别把上一个角色的选择带过去。
const pickerStar = ref(0)
// 调过星之后下面这份 BOX 缓存里的 battle_rarity 就旧了，需要作废重取。
// 用标记延到弹窗关干净（或下次打开）再清：立刻清会让正在淡出的列表闪成空态。
const pickerBoxStale = ref(false)
// 自己 BOX 的全部已拥有角色（懒加载 + 缓存，刷新 BOX 缓存后作废）
const myBoxUnits = ref<BoxUnit[]>([])

const pickerTitle = computed(() =>
  pickerColumnTitle.value ? `更换「${pickerColumnTitle.value}」支援` : '更换支援',
)

// 只列 Lv>10 的（游戏规定 Lv10 以上才能当支援），再按输入的角色名 / 别名筛一遍。
// 别名来自后端 `BoxUnit.chara_names`（就是 `_pcr_data.CHARA_NAME` 那一整串），
// 所以 nnk / 511 / 猫拳 这类都能搜到；英文别名按不区分大小写匹配。
const pickerUnits = computed(() => {
  const kw = pickerKeyword.value.trim().toLowerCase()
  return myBoxUnits.value.filter((u) => {
    if (!u.owned || u.level <= 10) return false
    if (!kw) return true
    if (u.chara_name.toLowerCase().includes(kw)) return true
    return (u.chara_names ?? []).some((n) => n.toLowerCase().includes(kw))
  })
})

// 弹窗里选中的那个角色（还没选 / 被搜索筛掉了就是 null）
const pickerSelectedUnit = computed(
  () => pickerUnits.value.find((u) => u.unit_id === pickerSelected.value) ?? null,
)

// 当前生效战斗星级（0 = 没选中）
const pickerEffectiveStar = computed(() => effectiveStar(pickerSelectedUnit.value))

// 只有 5★ 能调（6★ 已满、低星没到可调档位，游戏规则如此，后端也会拒）
const pickerCanChangeStar = computed(
  () => pickerSelectedUnit.value?.rarity === 5,
)

// 选中的就是这一格原来挂着的角色 → 后端支持「只调星、不重复挂支援」
const pickerSameUnit = computed(
  () => !!pickerSelected.value && pickerSelected.value === pickerCurrentId.value,
)

// 选了一个和当前生效星级不同的新星级（0 = 不调整，不算改了）
const pickerStarChanged = computed(
  () => pickerStar.value !== 0 && pickerStar.value !== pickerEffectiveStar.value,
)

// 底部那行小字：同角色又没选新星级时，把「点确定也没用」的原因说清楚；
// 同角色选了新星级时说明只会调星、不会重复挂支援。
const pickerFooterTip = computed(() => {
  const loginTip = '会登录游戏账号'
  if (!pickerSameUnit.value) return loginTip
  // 同角色但不是 5★（比如 6★ 已经在位）：界面上没有星级选项、按钮也是灰的，
  // 这时不能再说「选择要调整的战斗星级后可直接调整」，得讲清是星级本身调不了。
  if (!pickerCanChangeStar.value) return '该角色不是 5 星，无法调整战斗星级'
  if (!pickerStarChanged.value) {
    return '已在支援位，选择要调整的战斗星级后可直接调整'
  }
  return `只调整战斗星级（角色已在这个支援位），${loginTip}`
})

// 换人之后不保留上一个角色的星级选择（否则会把 A 的 3★ 带到 B 身上）
watch(pickerSelected, () => {
  pickerStar.value = 0
})

/**
 * 弹窗彻底关掉之后（`@closed` 在离场动画结束后才触发）再作废选人缓存。
 *
 * 调过星之后 `battle_rarity` 变了，下次打开要重新读一份 BOX 才不会显示旧的「当前 N★」。
 * 但**不能**在关窗那一刻同步清：列表会先闪成「没有可上阵的角色」再淡出，很难看。
 */
function onPickerClosed() {
  if (!pickerBoxStale.value) return
  pickerBoxStale.value = false
  myBoxUnits.value = []
}

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
  // 预选这一格现在挂着的角色：想「只改战斗星级」时不用再点一次头像，
  // 也能一眼看出这个位原来是谁（后端支持已在该位时只调星）。
  pickerSelected.value = unit ? unit.unit_id : 0
  pickerStar.value = 0
  pickerMessage.value = ''
  // 上次调过星、弹窗还没关干净就又打开了：这里先把旧缓存清掉，
  // 免得 ensureMyBox 看到「已有缓存」直接跳过、把旧的「当前 N★」又显示出来。
  if (pickerBoxStale.value) {
    pickerBoxStale.value = false
    myBoxUnits.value = []
  }
  pickerVisible.value = true
  void ensureMyBox()
}

async function confirmChange() {
  if (!groupId.value || !pickerSelected.value || changing.value) return
  const unit = pickerSelectedUnit.value
  if (!unit) {
    // 预选的角色还没出现在 pickerUnits 里（BOX 缓存还在读 / 缓存旧了没这个角色）。
    // 以前 pickerSelected 为 0 时按钮是灰的，现在有预选，得明确提示一句，
    // 别让用户点了「确定更换」却什么都没发生。
    ElMessage.warning(
      pickerLoading.value
        ? '正在读取你的 BOX，稍等一下再点'
        : '没在 BOX 缓存里找到这个角色，点【刷新缓存】后再试',
    )
    return
  }
  const sameUnit = pickerSameUnit.value
  // 0 = 不调整，提交时不传 star
  const star = pickerStar.value
  const starChanged = pickerStarChanged.value

  if (sameUnit && !starChanged) {
    // 后端在真正改之前就会因为「已经在支援中」退回来，但那一步已经登录过账号了
    // —— 白顶一次号，所以这里先拦掉（按钮这时也是禁用的，这里兜一层）
    ElMessage.warning(`${unit.chara_name} 已经挂在这个位上了`)
    return
  }

  const hint = await currentLoginHint()
  // 两种情况的确认文案分开写：
  //   - 只调星：角色本来就在这个位，要说清是「改星级」而不是重复挂支援；
  //   - 换人：沿用原来的文案，选了星级时再补一句会一起调。
  const confirmText = sameUnit
    ? `会把「${unit.chara_name}」的战斗星级从 ${pickerEffectiveStar.value}★ 调整为 ${star}★` +
      `（当前已在「${pickerColumnTitle.value}」支援位）。` +
      `这一步${hint}，并真的改游戏里的支援设定。确定吗？`
    : `会把「${unit.chara_name}」挂到「${pickerColumnTitle.value}」支援` +
      (starChanged ? `，并把战斗星级调整为 ${star}★` : '') +
      `。这一步${hint}，并真的改游戏里的支援设定；` +
      '栏位满了会顶掉挂得最久的那一个。确定吗？'
  try {
    await ElMessageBox.confirm(confirmText, sameUnit ? '调整战斗星级' : '更换支援', {
      type: 'warning',
      confirmButtonText: sameUnit ? '确定调整' : '确定更换',
      cancelButtonText: '再想想',
    })
  } catch {
    // 用户取消
    return
  }

  changing.value = true
  try {
    const payload: SupportChangeForm = {
      unit_id: unit.unit_id,
      mode: pickerMode.value,
    }
    // star 只在真要调星级时才带（后端只认 3/4/5；0 = 不调整）
    if (star) payload.star = star
    const res = await changeSupport(groupId.value, payload)
    if (res.ok) {
      // 后端提示可能是两行（「成功终止…\n成功将…」），弹窗里换成一行更好看。
      // 只调星级时后端同样返回 ok=true（message 里说明已调整），别当失败。
      ElMessage.success(res.message.replace(/\n/g, '；'))
      pickerVisible.value = false
      // 只有真调过星（star 非 0）才需要作废选人弹窗那份 BOX 缓存 —— 只有它的
      // battle_rarity 会变旧；单纯换人时缓存还是新的，别让下次开弹窗白多读一次 BOX。
      // 真正清空的时机见 onPickerClosed：要等关窗动画走完，否则列表会闪成空态。
      if (star) pickerBoxStale.value = true
      // 后端换完已经顺手改过本地缓存的助战位了，重查一次就是最新的
      await doQuery(true)
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
//   - **真换**走 `POST /box/ex_equip/change`，会登录你的游戏账号
//     （自己开着竞技场/出刀监控时复用登录、不顶号），先弹确认。
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
      '（开着监控时复用登录，否则会短暂顶号）之后，这里就能看到现在穿的是哪件，也能直接换。'
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

  const hint = await currentLoginHint()
  try {
    await ElMessageBox.confirm(
      `将一次更换 ${changes.length} 个槽：\n${lines.join('\n')}\n\n` +
        `这一步${hint}，` +
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
  color: var(--kanna-text-faint);
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
  color: var(--kanna-pink-deep);
}
.intro-text {
  margin: 8px 0 0;
  color: var(--kanna-text-muted);
  font-size: 13px;
  line-height: 1.7;
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
  /* 左对齐 + 监控开关 margin-left:auto：页签在左，监控/未拥有开关贴右 */
  justify-content: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}
/* 竞技场监控开关：页签右侧的「状态标签 + 开关按钮」 */
.monitor-box {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-left: auto;
}
.monitor-tag {
  flex: none;
}
.missing-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--kanna-text-muted);
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
  color: var(--kanna-text-faint);
  font-size: 12px;
  line-height: 1.6;
}

/* ================= 个人 BOX 练度条（MP等级 / 属性强化 / 职介等级） =================
 * 紧贴查询框下面的一整块：两行数据 + 一行小字（快照时间）。
 * 配色全走 --kanna-* 语义变量，深色模式自动跟着变；只有属性 chip 用固定色
 * （火红 / 水蓝 / 风绿 / 光橙 / 暗紫，和竞技场资料卡的深域一致）。 */
.enhance-bar {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--kanna-border-soft);
  background: var(--kanna-fill-subtle);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.enh-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 8px;
  min-width: 0;
}
/* 行首小标题（MP等级 / 属性强化 / 职介等级） */
.enh-key {
  flex: none;
  font-size: 12px;
  font-weight: 700;
  color: var(--kanna-text-muted);
  letter-spacing: 0.02em;
}
/* 「属性强化」跟在 MP 数值后面，和前面留一点距离 */
.enh-key-attr {
  margin-left: 10px;
}
.enh-mp {
  flex: none;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--kanna-pink-deep);
  font-variant-numeric: tabular-nums;
}
/* 属性 chip：`火 440`，白字 + 属性色渐变（沿用深域那套配色） */
.enh-talent {
  flex: none;
  padding: 1px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  color: #fff;
  white-space: nowrap;
  background: linear-gradient(180deg, #5b9ef0 0%, #3d7fd8 100%);
  box-shadow: 0 1px 3px rgba(74, 144, 226, 0.2);
}
.enh-talent-0 {
  background: linear-gradient(180deg, #f06292 0%, #d9365e 100%);
  box-shadow: 0 1px 3px rgba(217, 54, 94, 0.2);
}
.enh-talent-1 {
  background: linear-gradient(180deg, #5b9ef0 0%, #3d7fd8 100%);
}
.enh-talent-2 {
  background: linear-gradient(180deg, #66bb6a 0%, #3f9a4d 100%);
  box-shadow: 0 1px 3px rgba(63, 154, 77, 0.2);
}
.enh-talent-3 {
  background: linear-gradient(180deg, #f6b352 0%, #e08a1e 100%);
  box-shadow: 0 1px 3px rgba(224, 138, 30, 0.2);
}
.enh-talent-4 {
  background: linear-gradient(180deg, #a78bfa 0%, #7c3aed 100%);
  box-shadow: 0 1px 3px rgba(124, 58, 237, 0.2);
}
/* 属性技能：`第3页 · 第12合流[4级]` + 左/中/右三条线（chip 复用职阶那套浅底样式） */
.enh-skill-main {
  flex: none;
  font-size: 12px;
  font-weight: 700;
  color: var(--kanna-text-secondary);
  font-variant-numeric: tabular-nums;
}
/* 余量（星幽碎片）比正文淡一档，别抢眼 */
.enh-skill-left {
  flex: none;
  font-size: 12px;
  color: var(--kanna-text-faint);
  font-variant-numeric: tabular-nums;
}
/* 职阶 / 属性技能分支 chip：浅底 + 边框，名字灰、数值深色，排不下就换行 */
.enh-role,
.enh-skill-branch {
  flex: none;
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  padding: 1px 9px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
  background: var(--kanna-surface-solid);
  border: 1px solid var(--kanna-border-soft);
}
.enh-role-name {
  font-style: normal;
  font-weight: 600;
  color: var(--kanna-text-muted);
}
.enh-role-val {
  font-weight: 700;
  color: var(--kanna-text-secondary);
  font-variant-numeric: tabular-nums;
}
/* 末尾小字：快照时间 + 怎么更新 */
.enh-foot {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--kanna-text-faint);
}
.enh-foot-tip {
  color: var(--kanna-text-disabled);
}
/* 还没有快照时的一行灰字（不套框，避免空块看起来像加载失败） */
.enh-empty {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--kanna-text-faint);
}

.result-card {
  padding: 16px 18px;
  min-height: 200px;
}
/* 排刀页签里的卡片自己就是 kanna-card，外层不要再套一层底色/内边距 */
.result-card-arrange {
  padding: 0;
  min-height: 0;
  background: transparent;
  border: none;
  box-shadow: none;
}
.arrange-query-hint {
  font-size: 12px;
  line-height: 1.6;
  color: var(--kanna-text-faint);
}
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--kanna-text-faint);
  padding: 60px 0;
}
.result-meta {
  color: var(--kanna-text-faint);
  font-size: 12px;
  margin-bottom: 12px;
}
.result-hint {
  margin-left: 4px;
  color: var(--kanna-text-disabled);
}
.meta-owned {
  color: var(--kanna-accent-text);
}
.meta-missing {
  color: var(--kanna-text-faint);
}

/* 「我的助战」三栏卡片：照游戏「支援设定」界面（地下城·追忆的战场 / 团队战·露娜之塔 / 关卡·活动），
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
  border: 1px solid var(--kanna-border-soft);
  border-radius: 10px;
  padding: 10px 12px 12px;
  background: var(--kanna-fill-subtle);
  min-width: 0;
}
.support-col-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--kanna-text-secondary);
}
.support-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid var(--kanna-border-soft);
  border-radius: 10px;
  padding: 8px;
  background: var(--kanna-surface-solid);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.support-card:hover {
  border-color: var(--kanna-border-pink);
  box-shadow: 0 4px 12px rgba(219, 39, 119, 0.1);
}
/* 空位：虚线框 + 淡色，和已挂上的卡片一眼区分开 */
.support-card-empty {
  border-style: dashed;
  background: var(--kanna-fill-subtle);
}
.support-card-empty:hover {
  border-color: var(--kanna-border-strong);
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
  /* 不裁切：游戏样式的头像组件自己会把底图裁成圆角，overflow:hidden 反而会把
     左下角星级、右下角职业/属性小牌按外层圆角切掉一块。 */
  border: 1px solid var(--kanna-border-soft);
  background: var(--kanna-fill-soft);
  cursor: pointer;
}
.support-card-avatar-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--kanna-text-disabled);
  cursor: default;
}
/* 有角色的格子：头像自己带游戏里的品级框，去掉外层那圈灰边 */
.support-card-avatar-game {
  border-color: transparent;
  background: transparent;
}
.support-card-info {
  flex: 1;
  min-width: 0;
}
.support-card-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--kanna-text-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.support-card-name-empty {
  color: var(--kanna-text-faint);
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
  color: var(--kanna-text-faint);
  flex: none;
}
.support-card-value {
  color: var(--kanna-text-secondary);
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
  color: var(--kanna-text-faint);
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
  color: var(--kanna-text-faint);
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
  background: var(--kanna-primary-soft);
}
.picker-cell-active {
  border-color: var(--kanna-accent-text);
  background: var(--kanna-hover);
}
.picker-avatar {
  aspect-ratio: 1 / 1;
  border-radius: 8px;
}
.picker-name {
  margin-top: 3px;
  font-size: 12px;
  color: var(--kanna-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.picker-lv {
  font-size: 11px;
  color: var(--kanna-text-faint);
}
.picker-footer-tip {
  float: left;
  font-size: 12px;
  color: var(--kanna-text-faint);
  line-height: 32px;
}
/* 战斗星级（调星）：picker-grid 下面那一块，风格和卡片 / 详情里的信息条一致 */
.picker-star {
  margin-top: 12px;
  padding: 8px 10px;
  border: 1px solid var(--kanna-border-soft);
  border-radius: 8px;
  background: var(--kanna-fill-subtle);
}
.picker-star-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
.picker-star-label {
  font-size: 12px;
  color: var(--kanna-text-faint);
}
.picker-star-current {
  font-size: 12px;
  font-weight: 600;
  color: var(--kanna-text-secondary);
}
/* 非 5★ 角色：只给一句灰字说明，不显示 3/4/5 选项（选了后端也会拒） */
.picker-star-tip {
  font-size: 12px;
  line-height: 1.6;
  color: var(--kanna-text-faint);
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
  background: var(--kanna-fill-soft);
  border: 1px solid var(--kanna-border-soft);
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}
.avatar-cell:hover .avatar-box {
  transform: translateY(-2px);
  border-color: var(--kanna-border-pink);
  box-shadow: 0 6px 14px rgba(219, 39, 119, 0.16);
}
/* 已拥有：头像自己带游戏里的品级框，去掉外层那圈灰边 */
.avatar-box-game {
  border-color: transparent;
  background: transparent;
}
.avatar-name {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.3;
  color: var(--kanna-text-muted);
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
  border-color: var(--kanna-border-strong);
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
  border: 1px solid var(--kanna-border-soft);
  background: var(--kanna-fill-soft);
  flex: none;
}
/* 已拥有：头像自己带游戏里的品级框，去掉外层那圈灰边 */
.detail-avatar-game {
  border-color: transparent;
  background: transparent;
}
.detail-head-info {
  min-width: 0;
}
.detail-name {
  font-size: 17px;
  font-weight: 600;
  color: var(--kanna-text-strong);
}
.detail-sub {
  margin-top: 4px;
  font-size: 13px;
  color: var(--kanna-text-muted);
}
.detail-desc {
  margin-bottom: 4px;
}
/* 「已调星」小标：battle_rarity 非 0 = 调过星（详情弹窗 / 「我的助战」卡片 / 选人弹窗同一口径）。
   卡片那格的值是加粗的，这里统一压回正常字重 */
.lowered-tag {
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 400;
  color: #2b6fe0;
  background: rgba(43, 111, 224, 0.1);
}

/* 好感：平时只显示短标签（N 级 / 加成），点开才看完整加成 */
.love-chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: var(--kanna-accent-text);
  cursor: pointer;
  border-bottom: 1px dashed var(--kanna-border-pink);
  line-height: 1.4;
}
.love-chip-icon {
  font-size: 11px;
}
.love-bonus-text {
  font-size: 13px;
  line-height: 1.7;
  color: var(--kanna-text-secondary);
  /* 别用 break-all —— 会把「回复量上升：35」的 35 拆成两行 */
  word-break: normal;
}
.detail-section {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--kanna-text-secondary);
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
  border: 1px solid var(--kanna-border-soft);
  border-radius: 8px;
  padding: 6px 8px;
  background: var(--kanna-fill-subtle);
  min-width: 0;
}
.equip-label {
  font-size: 11px;
  color: var(--kanna-text-faint);
}
.equip-value {
  margin-top: 2px;
  font-size: 13px;
  color: var(--kanna-text-secondary);
  word-break: break-all;
}
.equip-empty {
  color: var(--kanna-text-disabled);
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
  border: 1px solid var(--kanna-border-soft);
  background: var(--kanna-fill-soft);
  object-fit: contain;
  flex: none;
}
/* 空装备槽的占位图标（虚线框 + 加号，提示这里可以点） */
.ex-equip-icon-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--kanna-text-disabled);
  border-style: dashed;
}
/* 普通 EX 槽：整格可点，点开选装备 */
.ex-slot-cell {
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.ex-slot-cell:hover {
  border-color: var(--kanna-border-pink);
  background: var(--kanna-primary-soft);
  box-shadow: 0 4px 12px rgba(219, 39, 119, 0.1);
}
/* 别人的 BOX / 助战数据：普通 EX 槽只读，点它不给换装入口 */
.ex-slot-readonly {
  cursor: default;
}
.ex-slot-readonly:hover {
  border-color: var(--kanna-border-soft);
  background: var(--kanna-fill-subtle);
  box-shadow: none;
}
.ex-slot-info {
  min-width: 0;
}
.ex-slot-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--kanna-text-faint);
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
  background: var(--kanna-fill-strong);
  color: var(--kanna-text-muted);
}
.ex-clan-tag {
  background: var(--kanna-primary-soft-strong);
  color: var(--kanna-accent-text);
}
.ex-slot-note {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--kanna-text-faint);
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
  color: var(--kanna-text-muted);
  white-space: nowrap;
}
.ex-sub-line b {
  color: var(--kanna-text-secondary);
}
.detail-section .section-hint {
  margin-left: 6px;
  font-size: 11px;
  font-weight: 400;
  color: var(--kanna-text-disabled);
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
  color: var(--kanna-text-faint);
}
.ex-picker-current {
  margin-bottom: 10px;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--kanna-primary-soft);
  color: var(--kanna-pink-deep);
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
  border: 1px solid var(--kanna-border-soft);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.ex-cand:hover {
  border-color: var(--kanna-border-pink);
  background: var(--kanna-primary-soft);
}
.ex-cand-active {
  border-color: var(--kanna-accent-text);
  background: var(--kanna-hover);
}
/* 正穿在这个槽上的那一组：左边一条粉线，一眼看出「现在就是它」 */
.ex-cand-current {
  border-left: 3px solid var(--kanna-accent-text);
}
.ex-cand-icon {
  width: 42px;
  height: 42px;
  border-radius: 6px;
  border: 1px solid var(--kanna-border-soft);
  background: var(--kanna-fill-soft);
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
  color: var(--kanna-text-strong);
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
  color: var(--kanna-accent-text);
  background: var(--kanna-primary-soft-strong);
}
.ex-cand-attrs {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 12px;
  color: var(--kanna-text-muted);
}
.ex-attr b {
  color: var(--kanna-text-secondary);
}
.ex-attr-empty {
  color: var(--kanna-text-disabled);
}
/* 5 星彩装的 4 条词条（选装备列表里那一行） */
.ex-cand-subs {
  margin-top: 3px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 10px;
  font-size: 12px;
  color: var(--kanna-text-muted);
}
.ex-sub-tag {
  padding: 0 4px;
  border-radius: 3px;
  font-size: 10px;
  line-height: 16px;
  color: var(--kanna-pink-deep);
  background: var(--kanna-primary-soft-strong);
}
.ex-sub-item b {
  color: var(--kanna-text-secondary);
}
/* 彩装的词条是「空」（这件没炼出词条） */
.ex-sub-empty {
  color: var(--kanna-text-disabled);
}
/* 彩装那一行的 serial 编号（方便和 autopcr 的输出对号） */
.ex-cand-serial {
  color: var(--kanna-text-disabled);
}
/* 已经在这个槽里选好东西的小勾（槽位按钮上） */
.ex-tab-mark {
  margin-left: 4px;
  color: var(--kanna-accent-text);
  font-weight: 700;
}
/* 「卸下这个槽」那一行 */
.ex-cand-none {
  border-style: dashed;
}
.ex-cand-none .ex-cand-name {
  font-weight: 500;
  color: var(--kanna-text-muted);
}
.ex-cand-owner {
  margin-top: 4px;
  font-size: 11px;
  color: var(--kanna-text-faint);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* ---- 「本次要换的」结果区（弹窗底部，一直显示）---- */
.ex-picked {
  margin-top: 10px;
  border: 1px solid var(--kanna-border-soft);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--kanna-primary-soft);
}
.ex-picked-title {
  font-size: 12px;
  color: var(--kanna-text-faint);
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
  background: var(--kanna-primary-soft);
}
/* 当前正在看的那个槽，左边加一条粉线 */
.ex-picked-row-active {
  border-left: 3px solid var(--kanna-accent-text);
  padding-left: 6px;
}
.ex-picked-slot {
  flex: none;
  color: var(--kanna-text-muted);
}
.ex-picked-value {
  flex: 1;
  min-width: 0;
  color: var(--kanna-text-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ex-picked-empty {
  color: var(--kanna-text-disabled);
}
.ex-picked-clear {
  flex: none;
}

/* ================= 好友（模仿游戏内好友列表） ================= */
.friend-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  /* 和游戏一样不让内容在超宽屏上被拉得太散 */
  max-width: 720px;
}
.friend-count {
  font-size: 14px;
  color: var(--kanna-text-secondary);
}
.friend-count b {
  font-size: 17px;
  color: var(--kanna-text-secondary);
}
.friend-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
/* 排序下拉：照游戏里的蓝框白底样式 */
.friend-sort-select {
  width: 132px;
}
.friend-sort-select :deep(.el-select__wrapper) {
  min-height: 30px;
  border-radius: 8px;
  background: var(--kanna-surface-solid);
  box-shadow: 0 0 0 1px #8ab4f0 inset;
}
.friend-sort-select :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px #4a90e2 inset;
}
.friend-sort-select :deep(.el-select__selected-item) {
  color: #2b6fe0;
  font-weight: 600;
}
/* 升序 / 降序按钮：与排序下拉同一套蓝框 */
.friend-sort-dir {
  --el-button-text-color: #2b6fe0;
  --el-button-border-color: #8ab4f0;
  --el-button-bg-color: var(--kanna-surface-solid);
  --el-button-hover-text-color: #2b6fe0;
  --el-button-hover-border-color: #4a90e2;
  --el-button-hover-bg-color: #eef4ff;
}
.friend-cache-time {
  font-size: 11px;
  color: var(--kanna-text-faint);
}
.friend-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  /* 好友卡片不要撑满整个内容区（超宽屏上「解除好友 / 最后登录」会被推到很远），
     上限与游戏内好友列表宽度接近 */
  max-width: 720px;
}
/* 好友卡片：浅粉 / 米白渐变 + 细边框，和 kanna 粉色主题协调 */
.friend-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  border: 1px solid #f6ddcf;
  border-radius: 12px;
  background: linear-gradient(135deg, #fff6f9 0%, #fffaf3 100%);
  box-shadow: 0 1px 3px rgba(219, 39, 119, 0.05);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.friend-row:hover {
  border-color: var(--kanna-border-pink);
  box-shadow: 0 4px 12px rgba(219, 39, 119, 0.1);
}
/* 头像：正方形圆角 + 金色描边；后端给的头像不带 rarity → 不画星级 */
.friend-avatar {
  width: 88px;
  height: 88px;
  flex: none;
  border-radius: 10px;
  overflow: hidden;
  border: 2px solid #e8c46a;
  background: #cfd5e6;
  cursor: pointer;
}
.friend-avatar img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.friend-avatar:hover {
  box-shadow: 0 0 0 2px #4a90e2;
}
.friend-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
/* 名字：点开好友详情（用户要求不显示称号，所以这一行只有名字） */
.friend-name {
  font-size: 17px;
  font-weight: 700;
  color: #2f3b52;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.friend-name:hover {
  color: var(--kanna-danger-strong);
  text-decoration: underline;
}
.friend-field {
  display: flex;
  align-items: center;
  gap: 10px;
  /* 标签和数值之间别拉太远：游戏里就一小段点线（原来 460px 太散） */
  max-width: 320px;
}
.friend-pill {
  flex: none;
  min-width: 96px;
  padding: 2px 10px;
  text-align: center;
  font-size: 13px;
  color: #fff;
  background: linear-gradient(180deg, #5b9ef0 0%, #3d7fd8 100%);
  border-radius: 5px;
}
.friend-line {
  flex: 1;
  min-width: 20px;
  border-bottom: 2px dotted #9dbdf0;
  transform: translateY(-3px);
}
.friend-value {
  flex: none;
  font-size: 15px;
  font-weight: 600;
  color: var(--kanna-text-secondary);
  text-align: right;
}
.friend-side {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  margin-left: auto;
}
.friend-login {
  font-size: 12px;
  color: #e07b1f;
  white-space: nowrap;
}
/* 解除好友：金边浅黄底 */
.friend-remove-btn {
  min-width: 96px;
  --el-button-text-color: #8a5a12;
  --el-button-border-color: #e8c46a;
  --el-button-bg-color: #fffaf0;
  --el-button-hover-text-color: #7a4c0a;
  --el-button-hover-border-color: #d9ad3e;
  --el-button-hover-bg-color: #fff4d8;
}
/* 添加好友弹窗 */
.add-friend-label {
  font-size: 13px;
  color: var(--kanna-text-secondary);
  margin-bottom: 6px;
}
.add-friend-tip {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--kanna-text-faint);
}

/* 好友申请弹窗：待审核列表 / 申请中的名单 */
.friend-req-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 56vh;
  overflow-y: auto;
}
.friend-req-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid #f6ddcf;
  border-radius: 10px;
  background: linear-gradient(135deg, #fff6f9 0%, #fffaf3 100%);
}
.friend-req-avatar {
  width: 60px;
  height: 60px;
  flex: none;
  border-radius: 9px;
  overflow: hidden;
  border: 2px solid #e8c46a;
  background: #cfd5e6;
  cursor: pointer;
}
.friend-req-avatar:hover {
  box-shadow: 0 0 0 2px #4a90e2;
}
.friend-req-avatar img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.friend-req-main {
  flex: 1;
  min-width: 0;
}
.friend-req-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.friend-req-name {
  cursor: pointer;
  font-size: 15px;
  font-weight: 700;
  color: #2f3b52;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.friend-req-name:hover {
  color: var(--kanna-danger-strong);
  text-decoration: underline;
}
.friend-req-login {
  flex: none;
  font-size: 11px;
  color: #e07b1f;
  white-space: nowrap;
}
/* 等级 / 战力 / 好友数：小圆角标签，比一行纯文字清楚 */
.friend-req-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 5px;
}
.friend-req-chip {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 1px 9px;
  border-radius: 999px;
  font-size: 11px;
  color: var(--kanna-text-muted);
  background: rgba(74, 144, 226, 0.08);
  border: 1px solid rgba(74, 144, 226, 0.16);
}
.friend-req-chip b {
  font-size: 12px;
  font-weight: 600;
  color: var(--kanna-text-secondary);
}
.friend-req-actions {
  flex: none;
  display: flex;
  gap: 8px;
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
  /* 练度条：手机上收紧内边距和 chip，8 个职阶自动换行不溢出 */
  .enhance-bar {
    padding: 8px 10px;
    gap: 6px;
  }
  .enh-key-attr {
    margin-left: 0;
  }
  .enh-mp {
    font-size: 15px;
  }
  .enh-talent,
  .enh-role,
  .enh-skill-branch {
    padding: 1px 7px;
    font-size: 11px;
  }
  .enh-row {
    gap: 5px 6px;
  }
  /* 监控开关在手机上不要贴右，跟着页签换行排 */
  .monitor-box {
    margin-left: 0;
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
  /* 好友卡片：手机上卡片换行、右侧信息落到整行，头像和标签一起收紧 */
  .friend-row {
    flex-wrap: wrap;
    gap: 10px;
    padding: 10px;
  }
  .friend-avatar {
    width: 64px;
    height: 64px;
  }
  .friend-pill {
    min-width: 72px;
    font-size: 12px;
  }
  .friend-field {
    max-width: none;
  }
  .friend-side {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    margin-left: 0;
  }
  /* 好友申请：手机上操作按钮落到整行 */
  .friend-req-row {
    flex-wrap: wrap;
  }
  .friend-req-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
/* ================= 夜间模式：游戏拟态配色的深色覆盖 =================
 * 上面这些颜色是照游戏 UI 抄的装饰色（星级金、好友蓝框 / 金边 / 暖色卡片、
 * 头像占位底色、蓝色徽章……）。浅色模式保留原色；深色下在这里统一压暗 /
 * 提亮，避免出现「亮块」和「深色字看不清」。普通文字 / 白底 / 浅灰边框
 * 已经换成 --kanna-* 语义变量，这一块只兜底剩下的装饰色。 */
html.dark .ex-cand-star {
  color: #fbbf24;
}
/* 「已调星」蓝色小标：深色下换成亮蓝，不然深蓝在深底上糊成一团 */
html.dark .lowered-tag {
  color: var(--kanna-info);
  background: rgba(96, 165, 250, 0.16);
}
/* 好友排序下拉：浅色是蓝框白底，深色下边框提亮、底色跟卡片一致 */
html.dark .friend-sort-select :deep(.el-select__wrapper) {
  box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.5) inset;
}
html.dark .friend-sort-select :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px var(--kanna-info) inset;
}
html.dark .friend-sort-select :deep(.el-select__selected-item) {
  color: var(--kanna-info);
}
html.dark .friend-sort-dir {
  --el-button-text-color: var(--kanna-info);
  --el-button-border-color: rgba(96, 165, 250, 0.5);
  --el-button-hover-text-color: var(--kanna-text-strong);
  --el-button-hover-border-color: rgba(96, 165, 250, 0.75);
  --el-button-hover-bg-color: rgba(96, 165, 250, 0.16);
}
/* 好友卡片：浅色是暖粉 / 米白渐变，深色下换成夜色卡片，金粉边框保留但压暗 */
html.dark .friend-row,
html.dark .friend-req-row {
  border-color: rgba(244, 114, 182, 0.22);
  background: linear-gradient(135deg, rgba(48, 38, 53, 0.92) 0%, rgba(38, 32, 42, 0.92) 100%);
}
/* 好友头像占位底色（#cfd5e6 在深色下是一块亮灰）；金色描边保留但压一档 */
html.dark .friend-avatar,
html.dark .friend-req-avatar {
  border-color: rgba(232, 196, 106, 0.7);
  background: rgba(255, 255, 255, 0.1);
}
html.dark .friend-name,
html.dark .friend-req-name {
  color: var(--kanna-text-strong);
}
/* 等级 / 战力标签：游戏里的正蓝渐变，深色下压暗一档，白字更清楚 */
html.dark .friend-pill {
  background: linear-gradient(180deg, #4a86d8 0%, #3365b5 100%);
}
html.dark .friend-line {
  border-bottom-color: rgba(147, 197, 253, 0.45);
}
html.dark .friend-login,
html.dark .friend-req-login {
  color: var(--kanna-warning);
}
/* 解除好友：金边浅黄底 → 金边半透明暖底 */
html.dark .friend-remove-btn {
  --el-button-text-color: #e8c46a;
  --el-button-border-color: rgba(232, 196, 106, 0.45);
  --el-button-bg-color: rgba(232, 196, 106, 0.12);
  --el-button-hover-text-color: #f0d08a;
  --el-button-hover-border-color: rgba(232, 196, 106, 0.65);
  --el-button-hover-bg-color: rgba(232, 196, 106, 0.2);
}
html.dark .friend-req-chip {
  background: rgba(96, 165, 250, 0.12);
  border-color: rgba(96, 165, 250, 0.28);
}
</style>
