<template>
  <div class="dashboard-page">
    <!-- 无公会提示 -->
    <el-empty
      v-if="!groupId"
      description="请先从上方选择一个公会"
    />

    <template v-else>
      <!-- 顶部概览（5 张卡：今日/昨日/正在出刀/排名/状态；大屏 5 等分见样式 .overview 覆盖） -->
      <el-row :gutter="16" class="overview">
        <el-col :xs="12" :sm="8" :md="6" v-for="item in overviewCards" :key="item.label">
          <div class="ov-card kanna-card" :style="{ borderTop: `3px solid ${item.color}` }">
            <!-- 排名阶级徽章（仅公会排名卡） -->
            <div
              v-if="item.tier"
              class="ov-tier"
              :title="item.tier.tip"
              :style="{
                background: `linear-gradient(155deg, ${item.tier.c1} 0%, ${item.tier.c2} 100%)`,
                filter: `drop-shadow(0 3px 6px ${item.tier.c1}66)`
              }"
            >
              <span class="ov-tier-name">{{ item.tier.name }}</span>
              <span class="ov-tier-range">{{ item.tier.range }}</span>
            </div>
            <div class="ov-label">{{ item.label }}</div>
            <div class="ov-value" :style="{ color: item.color }">
              {{ item.value }}
              <small v-if="item.suffix">{{ item.suffix }}</small>
            </div>
            <div class="ov-desc">{{ item.desc }}</div>
          </div>
        </el-col>
      </el-row>

      <!-- 状态条 -->
      <div class="status-bar kanna-card mt-16">
        <div class="status-left">
          <el-tag size="default" :type="loopStateTagType" effect="dark">
            <el-icon v-if="data.state.includes('开启')" class="spin"><Loading /></el-icon>
            {{ data.state || '未开启' }}
          </el-tag>
          <!-- 出刀监控切换按钮（方案A：只允许当前登录QQ号开自己绑定的账号） -->
          <el-tooltip
            v-if="isMonitorRunning"
            :content="canStopMonitor
              ? '当前监控已在运行，点击可取消'
              : '只有监控人本人或 bot 主人可以取消出刀监控'"
            placement="bottom"
          >
            <el-button
              size="default"
              type="danger"
              :loading="monitorLoading"
              :disabled="!canStopMonitor"
              @click="confirmStopMonitor"
            >
              <el-icon><VideoPause /></el-icon>
              取消出刀监控
            </el-button>
          </el-tooltip>
          <el-tooltip
            v-else
            content="用当前登录QQ号自己绑定的角色账号开启出刀监控（绑一次所有群通用）"
            placement="bottom"
          >
            <el-button
              size="default"
              type="success"
              :loading="monitorLoading"
              @click="openStartMonitorDialog"
            >
              <el-icon><VideoPlay /></el-icon>
              开启出刀监控
            </el-button>
          </el-tooltip>
          <span class="clan-name">{{ data.clan_name || '未知公会' }}</span>
          <span class="stage">{{ data.stage || '暂无阶段信息' }}</span>
          <span class="day-num">第 {{ data.day_num || 0 }} 天</span>

          <!-- 游戏账号绑定：一个 QQ 只有一个号，绑一次所有群通用（换公会不用重绑）。
               和 QQ 私聊【绑定账号】写的是同一条。 -->
          <el-divider direction="vertical" />
          <el-tooltip :content="accountTip" placement="bottom">
            <el-tag size="default" :type="accountTagType" effect="plain" class="account-tag">
              <el-icon><User /></el-icon>
              {{ accountLabel }}
            </el-tag>
          </el-tooltip>
          <el-button size="small" plain @click="openBindDialog">
            {{ bindButtonText }}
          </el-button>
          <el-popconfirm
            v-if="account.bound"
            title="确定解绑游戏账号吗？（所有群都会变成未绑定，需要重新绑）"
            confirm-button-text="确定解绑"
            cancel-button-text="再想想"
            @confirm="submitUnbind"
          >
            <template #reference>
              <el-button size="small" type="danger" plain :loading="accountDialog.unbinding">
                解绑
              </el-button>
            </template>
          </el-popconfirm>
        </div>
        <div class="status-right">
          <el-tag size="small" type="warning" effect="plain" v-if="sseEnabled">
            <el-icon><Connection /></el-icon>实时同步中
          </el-tag>
          <el-tag size="small" type="info" effect="plain" v-else>
            <el-icon><Warning /></el-icon>实时同步未开启
          </el-tag>
          <el-button
            size="small"
            :type="sseEnabled ? 'danger' : 'success'"
            plain
            @click="toggleSSE"
          >
            {{ sseEnabled ? '关闭实时' : '开启实时' }}
          </el-button>
          <el-button size="small" @click="loadDashboard(true)">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>
      </div>

      <!-- BOSS 状态 -->
      <!-- 按每张 row 显示 3 格进行分页渲染：
           当 boss 数不足一行 3 的倍数（典型 5 王，第一行 3 只 + 第二行 2 只），
           会在"第二行最右边的空白格"自动补一张"实时数字时钟"卡片。 -->
      <div class="section-title mt-16">
        <el-icon><Sword /></el-icon>
        <span>BOSS 状态</span>
      </div>
      <template v-for="(row, rowIdx) in bossRows" :key="rowIdx">
        <el-row :gutter="16" class="boss-row" :class="{ 'mt-16': rowIdx > 0 }">
          <el-col
            v-for="(cell, colIdx) in row"
            :key="cell.key"
            :xs="24"
            :sm="12"
            :md="8"
            :lg="8"
          >
            <!-- 普通 BOSS 卡片 -->
            <div v-if="cell.kind === 'boss'" class="boss-card kanna-card">
              <div class="boss-top">
                <div class="boss-id-block">
                  <!-- BOSS 头像：unitId 对应 redive 图标资源，加载失败时回退为序号徽标 -->
                  <img
                    v-if="cell.boss?.id && !bossImgFailed[cell.bossIdx as number]"
                    class="boss-avatar"
                    :src="bossAvatarUrl(cell.boss.id)"
                    alt="BOSS"
                    @error="bossImgFailed[cell.bossIdx as number] = true"
                  />
                  <div v-else class="boss-avatar boss-avatar--fallback">
                    {{ (cell.bossIdx as number) + 1 }}
                  </div>
                  <div>
                    <div class="boss-no">第 {{ (cell.bossIdx as number) + 1 }} 王</div>
                    <div class="boss-name">{{ cell.boss?.name || '未知' }}</div>
                  </div>
                </div>
                <div class="boss-lap" v-if="cell.boss?.lap">
                  {{ cell.boss?.lap }} 周目
                </div>
              </div>

              <!-- HP 进度条 -->
              <div class="hp-bar" v-if="cell.boss?.max_hp">
                <el-progress
                  :percentage="bossHpPercent(cell.boss as any)"
                  :color="hpBarColor(cell.bossIdx as number)"
                  :stroke-width="14"
                  :show-text="false"
                />
                <div class="hp-text">
                  <span>{{ formatNum((cell.boss as any).current_hp) }}</span>
                  <span class="text-muted"> / {{ formatNum((cell.boss as any).max_hp) }}</span>
                </div>
              </div>
              <div class="hp-text text-muted" v-else>暂无血量信息</div>

              <!-- 状态标签（图标+中文文字，避免仅凭 tooltip 猜含义） -->
              <div class="boss-stats">
                <div class="stat-tag stat-tag--primary" :title="`预约 ${(cell.boss as any).subscribe} 人`">
                  <el-icon class="stat-icon"><BellFilled /></el-icon>
                  <span class="stat-text">预约</span>
                  <span class="stat-num">{{ (cell.boss as any).subscribe }}</span>
                </div>
                <div class="stat-tag stat-tag--success" :title="`申请出刀 ${(cell.boss as any).apply} 人`">
                  <el-icon class="stat-icon"><EditPen /></el-icon>
                  <span class="stat-text">申请</span>
                  <span class="stat-num">{{ (cell.boss as any).apply }}</span>
                </div>
                <div class="stat-tag stat-tag--warning" :title="`战斗中 ${(cell.boss as any).fighter} 人`">
                  <el-icon class="stat-icon"><Position /></el-icon>
                  <span class="stat-text">战斗</span>
                  <span class="stat-num">{{ (cell.boss as any).fighter }}</span>
                </div>
                <div class="stat-tag stat-tag--danger" :title="`挂树 ${(cell.boss as any).tree} 人`">
                  <el-icon class="stat-icon"><Failed /></el-icon>
                  <span class="stat-text">挂树</span>
                  <span class="stat-num">{{ (cell.boss as any).tree }}</span>
                </div>
              </div>

              <!-- 快捷操作 -->
              <div class="boss-actions">
                <el-button
                  size="small"
                  plain
                  class="boss-record-btn"
                  @click="openBossDaoDialog(cell.boss as any, (cell.bossIdx as number) + 1)"
                >
                  <el-icon><Tickets /></el-icon>
                  出刀记录
                </el-button>
                <div class="boss-actions-right">
                  <el-button size="small" type="primary" plain @click="openNoticeDialog(cell.boss as any, 0)">
                    预约
                  </el-button>
                  <el-button size="small" type="success" plain @click="openNoticeDialog(cell.boss as any, 2)">
                    申请
                  </el-button>
                  <el-button size="small" type="danger" plain @click="openNoticeDialog(cell.boss as any, 1)">
                    挂树
                  </el-button>
                </div>
              </div>
            </div>

            <!-- 实时数字时钟卡片：填在第二行最右边的空位 -->
            <div v-else class="clock-card kanna-card">
              <div class="clock-top">
                <div class="clock-label">
                  <el-icon style="margin-right: 4px; vertical-align: -2px"><Timer /></el-icon>
                  当前时间
                </div>
                <el-tag size="small" effect="plain" type="success">同步中</el-tag>
              </div>
              <div class="clock-time">{{ clockTime }}</div>
              <div class="clock-date">
                {{ clockDate }} · {{ clockWeekday }}
              </div>
              <div class="clock-day-tip">
                今日会战第 <b>{{ data.day_num || '--' }}</b> 天
              </div>
            </div>
          </el-col>
        </el-row>
      </template>

      <!-- 出刀明细 + 最近出刀 + 出刀分布图（三栏布局，中间栏放你图里圈的红框） -->
      <el-row :gutter="16" class="mt-16">
        <!-- 左：今日出刀分布 -->
        <el-col :lg="9" :md="12" :xs="24">
          <div class="kanna-card h-full">
            <div class="card-title">今日出刀分布</div>
            <el-table :data="data.report" size="small" stripe style="width: 100%">
              <el-table-column label="刀数" width="100">
                <template #default="{ row }">
                  <div class="dao-num-badge" :style="{ background: daoNumColor(row.dao_num) }">
                    {{ row.dao_num === 0 ? '未出刀' : row.dao_num + ' 刀' }}
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="玩家">
                <template #default="{ row }">
                  <span
                    v-for="(name, i) in row.names"
                    :key="i"
                    class="dist-player-tag"
                    :style="distTagStyle(row.dao_num)"
                  >
                    {{ name }}
                  </span>
                  <span v-if="!row.names || row.names.length === 0" class="text-muted text-sm">
                    暂无
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="人数" width="80" align="center">
                <template #default="{ row }">
                  <b>{{ row.names?.length || 0 }}</b>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-col>
        <!-- 中：最近出刀 Top 20（截图红框中间位置） -->
        <el-col :lg="9" :md="12" :xs="24">
          <div class="kanna-card h-full">
            <div class="card-title" style="display:flex; align-items:center; justify-content:space-between">
              <span>最近出刀（Top 20）</span>
              <el-tag size="small" effect="plain" type="info">共 {{ lastDaoList.length }} 条</el-tag>
            </div>
            <el-table
              v-if="lastDaoList.length"
              :data="lastDaoList"
              size="small"
              stripe
              height="320"
              style="width: 100%"
            >
              <el-table-column label="玩家" min-width="110" header-align="center">
                <template #default="{ row }">
                  <div class="dao-player">
                    <el-avatar
                      :size="28"
                      class="dao-avatar"
                      :style="{ background: avatarBgColor(row.name) }"
                    >
                      {{ (row.name || '?').slice(0, 1) }}
                    </el-avatar>
                    <span class="dao-name">{{ row.name || '--' }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="伤害" width="100" align="right" header-align="center">
                <template #default="{ row }">
                  <b class="dao-damage">
                    {{ row.damage?.toLocaleString ? row.damage.toLocaleString() : row.damage }}
                  </b>
                </template>
              </el-table-column>
              <el-table-column label="目标" width="90" align="center">
                <template #default="{ row }">
                  <span class="text-muted" style="font-size:12px">
                    {{ row.lap ? `${row.lap}周目` : '-' }}{{ row.boss ? ` ${row.boss}王` : '' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="82" align="center">
                <template #default="{ row }">
                  <el-tag size="small" :type="daoTypeTag(row.type)">
                    {{ row.type || '—' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="时间" width="82" align="center">
                <template #default="{ row }">
                  <span class="dao-time">{{ formatDaoTime(row.date) }}</span>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="今日暂无出刀记录" :image-size="80" style="padding:12px 0" />
          </div>
        </el-col>
        <!-- 右：今日伤害排行（横向条形 Top 10，按玩家聚合的今日真实伤害） -->
        <el-col :lg="6" :md="12" :xs="24">
          <div class="kanna-card h-full">
            <div class="card-title" style="display:flex; align-items:center; justify-content:space-between">
              <span>今日伤害排行</span>
              <el-tooltip content="今日全员累计伤害（Top 10 之外的人也计入）" placement="top">
                <el-tag size="small" effect="plain" type="info">
                  全员 {{ formatShortNum(data.day_damage_total) }}
                </el-tag>
              </el-tooltip>
            </div>
            <div v-if="dayDamageRankList.length" style="height: 300px">
              <v-chart :option="dayDamageRankOption" autoresize />
            </div>
            <el-empty v-else description="暂无数据" :image-size="80" />
          </div>
        </el-col>
      </el-row>

      <!-- 会战档线 -->
      <div class="kanna-card" style="margin-top: 14px">
        <div class="rankline-header">
          <div class="card-title" style="margin: 0">
            会战档线
            <el-tag v-if="rankLine.clanBattleId" size="small" type="info" effect="plain" style="margin-left: 8px">
              编号 {{ rankLine.clanBattleId }}
            </el-tag>
            <!-- 数据更新时间：后端做了本地缓存、游戏侧又半小时才更新一次，
                 不把抓取时间标出来，用户看到旧数据也无从判断 -->
            <el-tooltip v-if="rankLineUpdatedText" :content="rankLineSourceTip" placement="top">
              <el-tag
                size="small"
                :type="rankLine.stale ? 'warning' : rankLine.cached ? 'info' : 'success'"
                effect="plain"
                style="margin-left: 6px"
              >
                数据 {{ rankLineUpdatedText }}
              </el-tag>
            </el-tooltip>
          </div>
          <div class="rankline-tools">
            <el-input
              v-model="rankLine.customInput"
              placeholder="自定义排名，如 500,2000"
              size="small"
              style="width: 190px"
              clearable
              @keyup.enter="loadRankLines(rankLine.customInput)"
            />
            <el-button size="small" type="primary" plain :loading="rankLine.loading" @click="loadRankLines(rankLine.customInput)">
              查询
            </el-button>
            <el-tooltip content="忽略本地缓存，强制去游戏侧抓一次最新档线（需出刀监控运行中）" placement="bottom">
              <el-button size="small" :loading="rankLine.loading" @click="loadRankLines(undefined, true)">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </el-tooltip>
          </div>
        </div>

        <el-alert
          v-if="rankLine.error"
          :title="rankLine.error"
          type="warning"
          :closable="false"
          style="margin: 8px 0"
        />
        <el-empty
          v-else-if="!rankLine.lines.length && !rankLine.loading"
          description="暂无档线数据，点右上角【刷新】抓取（需出刀监控运行中）"
          :image-size="70"
          style="padding: 16px 0"
        />
        <el-table
          v-else
          :data="rankLineRows"
          size="small"
          v-loading="rankLine.loading"
          :row-class-name="rankRowClass"
          style="margin-top: 8px"
        >
          <el-table-column label="档位" width="90" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                effect="plain"
                :type="row.isMy ? 'danger' : row.isLast ? 'success' : undefined"
              >{{ row.rank }} 名</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="合计分数" min-width="120" align="center">
            <template #default="{ row }">
              <b
                v-if="row.damage !== null"
                class="rank-score"
                :class="{ 'my-clan-name': row.isMy, 'last-rank-name': row.isLast }"
              >{{ row.damage.toLocaleString() }}</b>
              <span v-else class="text-muted">无</span>
            </template>
          </el-table-column>
          <el-table-column label="守线公会" min-width="130" align="center">
            <template #default="{ row }">
              <span :class="{ 'my-clan-name': row.isMy, 'last-rank-name': row.isLast }">{{ row.clan_name || '--' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="会长" width="130" align="center">
            <template #default="{ row }">{{ row.leader_name || '--' }}</template>
          </el-table-column>
          <el-table-column label="人数" width="60" align="center">
            <template #default="{ row }">{{ row.member_num ?? '--' }}</template>
          </el-table-column>
          <el-table-column label="档位奖励" min-width="150" align="center">
            <template #default="{ row }">
              <span v-if="row.reward" class="reward-cell">
                💎{{ row.reward.gem }} · 🪙{{ row.reward.coin }} · 🧩{{ row.reward.shard }}
              </span>
              <span v-else class="text-muted">--</span>
            </template>
          </el-table-column>
          <el-table-column label="我会差距" min-width="160" align="center">
            <template #default="{ row }">
              <template v-if="rankLine.my && rankLine.my.rank">
                <span v-if="row.isMy && rankLine.my.damage !== null" class="gap-ok">
                  当前 {{ rankLine.my.damage.toLocaleString() }}
                </span>
                <template v-else-if="rankLine.my.rank <= row.rank">
                  <span v-if="row.damage !== null && rankLine.my.damage !== null" class="gap-ok">
                    超出 {{ (rankLine.my.damage - row.damage).toLocaleString() }}
                  </span>
                  <span v-else-if="row.damage === null" class="text-muted">无</span>
                  <el-tag v-else type="success" effect="light" size="small">已达标</el-tag>
                </template>
                <template v-else-if="row.damage !== null && rankLine.my.damage !== null">
                  <span :class="rankLine.my.damage >= row.damage ? 'gap-ok' : 'gap-lack'">
                    {{ rankLine.my.damage >= row.damage ? `超出 ${(rankLine.my.damage - row.damage).toLocaleString()}` : `还差 ${(row.damage - rankLine.my.damage).toLocaleString()}` }}
                  </span>
                </template>
                <span v-else class="text-muted">无</span>
              </template>
              <span v-else class="text-muted">--</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 添加通知弹窗 -->
      <el-dialog
        v-model="noticeDialog.visible"
        :title="noticeDialog.title"
        width="420px"
        :close-on-click-modal="false"
      >
        <el-form :model="noticeDialog.form" label-position="top">
          <el-form-item label="BOSS">
            <el-select v-model="noticeDialog.form.boss">
              <el-option
                v-for="(b, i) in data.boss"
                :key="i"
                :label="`${i + 1}王 - ${b.name}`"
                :value="i + 1"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="周目（0=当前）">
            <el-input-number v-model="noticeDialog.form.lap" :min="0" :max="999" />
          </el-form-item>
          <el-form-item label="留言（可选）">
            <el-input
              v-model="noticeDialog.form.text"
              type="textarea"
              :rows="2"
              maxlength="50"
              show-word-limit
              placeholder="比如：补偿/手动/90s后等"
            />
          </el-form-item>
          <el-alert
            v-if="noticeDialog.form.notice_type === 5"
            title="SL 每天只能记录一次"
            type="warning"
            show-icon
            :closable="false"
          />
        </el-form>
        <template #footer>
          <el-button @click="noticeDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="submitNotice">确定</el-button>
        </template>
      </el-dialog>

      <!-- BOSS 出刀记录弹窗：按时间倒序查看对该 BOSS 的所有出刀 -->
      <el-dialog
        v-model="bossDaoDialog.visible"
        :title="bossDaoDialog.title"
        width="640px"
        :close-on-click-modal="true"
      >
        <div class="boss-dao-summary">
          <el-tag size="small" effect="plain" type="info">共 {{ bossDaoDialog.list.length }} 刀</el-tag>
          <el-tag size="small" effect="plain" type="warning">
            合计伤害 {{ bossDaoDialog.totalDamage.toLocaleString() }}
          </el-tag>
          <el-tag size="small" effect="plain" type="success">当前 {{ bossDaoDialog.lap }} 周目</el-tag>
        </div>
        <el-table
          v-loading="bossDaoDialog.loading"
          :data="bossDaoDialog.list"
          size="small"
          stripe
          max-height="420"
          style="width: 100%"
        >
          <el-table-column
            label="玩家"
            min-width="110"
            header-align="center"
            prop="name"
            sortable
            :sort-method="(a: DaoInfo, b: DaoInfo) => String(a.name || '').localeCompare(String(b.name || ''), 'zh-CN')"
          >
            <template #default="{ row }">
              <div class="dao-player">
                <el-avatar
                  :size="26"
                  class="dao-avatar"
                  :style="{ background: avatarBgColor(row.name) }"
                >
                  {{ (row.name || '?').slice(0, 1) }}
                </el-avatar>
                <span class="dao-name">{{ row.name || '--' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            label="伤害"
            width="110"
            align="right"
            header-align="center"
            prop="damage"
            sortable
            :sort-method="(a: DaoInfo, b: DaoInfo) => (Number(a.damage) || 0) - (Number(b.damage) || 0)"
          >
            <template #default="{ row }">
              <b class="dao-damage">
                {{ row.damage?.toLocaleString ? row.damage.toLocaleString() : row.damage }}
              </b>
            </template>
          </el-table-column>
          <el-table-column label="周目" width="80" align="center">
            <template #default="{ row }">
              <span class="text-muted" style="font-size:12px">{{ row.lap ? `${row.lap} 周目` : '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column
            label="类型"
            width="86"
            align="center"
            prop="type"
            sortable
            :sort-method="(a: DaoInfo, b: DaoInfo) => String(a.type || '').localeCompare(String(b.type || ''), 'zh-CN')"
          >
            <template #default="{ row }">
              <el-tag size="small" :type="daoTypeTag(row.type)">
                {{ row.type || '—' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="时间"
            width="110"
            align="center"
            prop="date"
            sortable
            :sort-method="(a: DaoInfo, b: DaoInfo) => (Number(a.date) || 0) - (Number(b.date) || 0)"
          >
            <template #default="{ row }">
              <span class="dao-time">{{ formatBossDaoTime(row.date) }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty
          v-if="!bossDaoDialog.loading && !bossDaoDialog.list.length"
          description="该 BOSS 本次会战还没有被出过刀"
          :image-size="80"
        />
      </el-dialog>

      <!-- 开启出刀监控：选择自己绑定的角色账号（方案A） -->
      <el-dialog
        v-model="startMonitorDialog.visible"
        title="开启出刀监控"
        width="460px"
        :close-on-click-modal="false"
        :close-on-press-escape="false"
      >
        <el-alert
          type="success"
          show-icon
          :closable="false"
          title="方案A：只允许使用当前登录QQ号自己绑定的角色账号启动监控。"
          description="列表里只有你自己绑定的账号，别人绑定的不会出现在这里。"
          style="margin-bottom: 16px"
        />
        <el-form label-position="top">
          <el-form-item
            label="选择要用来启动监控的角色账号"
            required
            :error="startMonitorDialog.errorMsg"
          >
            <el-select
              v-model="startMonitorDialog.selectedAccountId"
              placeholder="请选择一个绑定的角色账号"
              style="width: 100%"
              :loading="startMonitorDialog.loadingAccounts"
              filterable
            >
              <el-option
                v-for="acc in startMonitorDialog.accounts"
                :key="acc.account_id"
                :label="`${acc.name}（${PLATFORM_NAMES[acc.platform] || '服务器' + acc.platform} · viewer_id=${acc.viewer_id ?? '未同步'}）`"
                :value="acc.account_id"
              />
            </el-select>
          </el-form-item>
          <div class="tip-block">
            <div>🔸 启动后会自动登录角色，拉取公会战顶部信息，开始轮询。</div>
            <div>🔸 启动过程需要几秒到十几秒（取决于登录是否需要刷新 access_key）。</div>
            <div>🔸 监控启动成功后页面会自动刷新，请不要重复点击。</div>
          </div>
        </el-form>
        <template #footer>
          <el-button @click="startMonitorDialog.visible = false" :disabled="monitorLoading">取消</el-button>
          <el-button
            type="primary"
            :disabled="!startMonitorDialog.selectedAccountId"
            :loading="monitorLoading"
            @click="submitStartMonitor"
          >
            立即启动
          </el-button>
        </template>
      </el-dialog>

      <!-- 绑定游戏账号（按群）：在这里绑的号只在这个群生效 -->
      <el-dialog
        v-model="accountDialog.visible"
        title="绑定游戏账号"
        width="500px"
        :close-on-click-modal="false"
        @closed="resetAccountForm"
      >
        <el-alert
          type="info"
          show-icon
          :closable="false"
          title="绑一次所有群通用（换公会也不用重绑）"
          description="和 QQ 私聊机器人【绑定账号】写的是同一条，在哪个群的仪表盘里绑都一样。绑定过程会真实登录一次游戏来校验账号并读取角色昵称，请确保信息正确。"
          style="margin-bottom: 16px"
        />
        <el-form label-position="top">
          <el-form-item label="服务器" required>
            <el-radio-group v-model="accountDialog.form.platform">
              <el-radio-button :value="0">官服（B站）</el-radio-button>
              <el-radio-button :value="1">渠道服</el-radio-button>
              <el-radio-button :value="2">台服</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <!-- 官服：B站账号 + B站密码 -->
          <template v-if="accountDialog.form.platform === 0">
            <el-form-item label="B站账号" required>
              <el-input
                v-model="accountDialog.form.bili_account"
                placeholder="B站手机号 / 邮箱 / 用户名"
                clearable
              />
            </el-form-item>
            <el-form-item label="B站密码" required>
              <el-input
                v-model="accountDialog.form.bili_password"
                type="password"
                show-password
                placeholder="B站密码"
              />
            </el-form-item>
          </template>

          <!-- 渠服：login_id + token -->
          <template v-else-if="accountDialog.form.platform === 1">
            <el-form-item label="login_id" required>
              <el-input
                v-model="accountDialog.form.login_id"
                placeholder="提取器给出的 login_id"
                clearable
              />
            </el-form-item>
            <el-form-item label="token" required>
              <el-input
                v-model="accountDialog.form.token"
                placeholder="access_key，或提取器导出的 XML 片段（整段粘贴）"
                clearable
              />
            </el-form-item>
          </template>

          <!-- 台服：short_udid + udid + viewer_id -->
          <template v-else>
            <el-form-item label="short_udid" required>
              <el-input v-model="accountDialog.form.short_udid" clearable />
            </el-form-item>
            <el-form-item label="udid" required>
              <el-input v-model="accountDialog.form.udid" clearable />
            </el-form-item>
            <el-form-item label="viewer_id" required>
              <el-input-number
                v-model="accountDialog.form.viewer_id"
                :min="1"
                :controls="false"
                style="width: 100%"
              />
            </el-form-item>
          </template>

          <el-alert
            v-if="accountDialog.errorMsg"
            type="error"
            show-icon
            :closable="false"
            :title="accountDialog.errorMsg"
            style="margin-bottom: 12px"
          />
          <div class="tip-block">
            <div>🔸 绑定需要真实登录一次游戏，通常几秒到十几秒（官服换 access_key 会久一些）。</div>
            <div>🔸 重复绑定会覆盖原来那一条（一个 QQ 只保留一个游戏账号）。</div>
            <div>🔸 解绑对所有群一起生效；想换号直接重新绑定覆盖即可。</div>
          </div>
        </el-form>
        <template #footer>
          <el-button @click="accountDialog.visible = false" :disabled="accountDialog.loading">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="accountDialog.loading"
            @click="submitBindAccount"
          >
            绑定
          </el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
// GridComponent 管 xAxis / yAxis / grid，条形图必需（只有饼图时用不到）
import {
  GridComponent,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/store/user'
import {
  getDashboard,
  setNotice,
  getMonitorAccounts,
  switchMonitor,
  getBossDao,
  getRankLines,
  bindAccount,
  unbindAccount,
} from '@/api'
import type { RankLine } from '@/api'
import { createSSEConnection } from '@/utils/sse'
import { API_BASE } from '@/utils/request'
import { PLATFORM_NAMES } from '@/types'
import type {
  DashboardResponse,
  DayDamageRank,
  BossInfoCounter,
  NoticeCacheModel,
  DaoInfo,
  MonitorAccountOption,
  BindAccountForm,
  GroupAccountInfo,
} from '@/types'
import type { EChartsOption } from 'echarts'
import dayjs from 'dayjs'

use([CanvasRenderer, BarChart, GridComponent, TitleComponent, TooltipComponent, LegendComponent])

const props = defineProps<{ groupId?: number }>()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 解析路由参数中的 groupId（优先级：URL > props > store）
const groupId = computed<number>(() => {
  const p = Number(route.params.groupId) || props.groupId || userStore.currentClanId
  return p
})

const loading = ref(false)
const sseEnabled = ref(false)
let sseClient: EventSource | null = null

const data = reactive<DashboardResponse>({
  priority: 0,
  clan_priority: 0,
  user_id: 0,
  name: '',
  clan_name: '',
  stage: '',
  dao: 0,
  yesterday_dao: 0,
  rank: 0,
  state: '',
  boss: [],
  report: [],
  day_num: 0,
  last_dao: [],
  // 今日伤害排行 Top 10 + 全员总量（后端按玩家聚合今日出刀算出，右栏条形图用）
  day_damage_rank: [],
  day_damage_total: 0,
  day_score_total: 0,
  monitor_user_id: 0,
  account: {
    bound: false,
    account_id: null,
    name: '',
    platform: 0,
    viewer_id: null
  }
})

const bossCount = computed(() => Math.max(1, data.boss.length || 5))

// —— BOSS 头像 —— //
// 后端 dashboard 的 boss.id 即当期 BOSS unitId（来自 pcr.satroki.tech 的会战数据），
// 图标资源与 pcrjjc2-clanbattle 一样取自 redive 图标库；加载失败时回退显示序号
const bossImgFailed = reactive<Record<number, boolean>>({})
const bossAvatarUrl = (unitId: number) =>
  `https://redive.estertion.win/icon/unit/${unitId}.webp`

// 把 boss 卡片按每 3 个一张 row 分页；若最后一张 row 不满 3 格，末尾补时钟格占剩下的位置
// 这样典型的 5 王布局就是：第一行 [1王 2王 3王] + 第二行 [4王 5王 数字时钟]（时钟自动填在第二行最右空白处）
const bossRows = computed<Array<Array<{ kind: 'boss' | 'clock'; key: string; boss?: BossInfoCounter; bossIdx?: number }>>>(() => {
  const bosses = Array.isArray(data.boss) ? data.boss : []
  const COL_PER_ROW = 3
  const rows: Array<Array<{ kind: 'boss' | 'clock'; key: string; boss?: BossInfoCounter; bossIdx?: number }>> = []
  for (let i = 0; i < bosses.length; i += COL_PER_ROW) {
    const slice = bosses.slice(i, i + COL_PER_ROW)
    const row: any[] = slice.map((b, j) => ({
      kind: 'boss' as const,
      key: `boss-${i + j}`,
      boss: b,
      bossIdx: i + j
    }))
    // 只有最后一张 row 可能不满 3 格，才塞时钟补空白（满 3 格时不塞，避免第一行 3 只也多出一张）
    if (i + COL_PER_ROW >= bosses.length && row.length < COL_PER_ROW) {
      while (row.length < COL_PER_ROW) {
        row.push({ kind: 'clock' as const, key: `clock-${row.length}` })
      }
    }
    rows.push(row)
  }
  // 极端：没有任何 boss 时，至少给一张空行塞时钟防止页面塌陷
  if (rows.length === 0) {
    rows.push([{ kind: 'clock', key: 'clock-0' }])
  }
  return rows
})

// —— 实时数字时钟 —— //
const now = ref(new Date())
let clockTimer: any = null
// 档线自动刷新：监控启动后刷一次，之后每小时的 1 分 / 31 分各刷一次
let rankAutoTimer: any = null
let lastRankAutoSlot = ''

const clockTime = computed(() => dayjs(now.value).format('HH:mm:ss'))
const clockDate = computed(() => dayjs(now.value).format('YYYY 年 MM 月 DD 日'))
const clockWeekday = computed(() => {
  const map = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  return map[dayjs(now.value).day()]
})

// —— 公会排名阶级（SSS~C，与档线奖励档位无关，为纯展示性阶级划分） —— //
function rankTier(rank: number) {
  const list = [
    { min: 1, max: 50, name: 'SSS', c1: '#f59e0b', c2: '#fde68a' },
    { min: 51, max: 200, name: 'SS', c1: '#f97316', c2: '#fdba74' },
    { min: 201, max: 500, name: 'S', c1: '#ef4444', c2: '#fca5a5' },
    { min: 501, max: 3000, name: 'AAA', c1: '#a855f7', c2: '#d8b4fe' },
    { min: 3001, max: 10000, name: 'AA', c1: '#6366f1', c2: '#a5b4fc' },
    { min: 10001, max: 20000, name: 'A', c1: '#0ea5e9', c2: '#7dd3fc' },
    { min: 20001, max: 30000, name: 'BBB', c1: '#14b8a6', c2: '#5eead4' },
    { min: 30001, max: 40000, name: 'BB', c1: '#22c55e', c2: '#86efac' },
    { min: 40001, max: 60000, name: 'B', c1: '#64748b', c2: '#94a3b8' },
    { min: 60001, max: Infinity, name: 'C', c1: '#9ca3af', c2: '#d1d5db' },
  ]
  const t = list.find((x) => rank <= x.max)!
  const range = t.max === Infinity ? `${t.min}位以上` : `${t.min}-${t.max}位`
  return { name: t.name, c1: t.c1, c2: t.c2, range, tip: `当前阶级 ${t.name}（${range}）` }
}

const overviewCards = computed<any[]>(() => {
  // 正在出刀总人数 = 5 个 BOSS 的 fighter（战斗中）人数之和
  const fightingCount = (data.boss || []).reduce(
    (sum, b) => sum + (Number(b.fighter) || 0),
    0
  )
  return [
    {
      label: '今日出刀',
      value: data.dao,
      suffix: ' / 3 刀/人',
      desc: '公会全员今日累计出刀数（未满三人也显示总刀数）',
      color: '#ec4899'
    },
    {
      label: '昨日出刀',
      value: data.yesterday_dao,
      suffix: ' 刀',
      desc: '公会全员昨日出刀数',
      color: '#f59e0b'
    },
    {
      label: '正在出刀',
      value: fightingCount,
      suffix: ' 人',
      desc: fightingCount > 0 ? '当前正在挑战BOSS的成员总数' : '当前无人正在出刀',
      color: fightingCount > 0 ? '#f97316' : '#9ca3af'
    },
    {
      label: '公会排名',
      value: data.rank || '--',
      suffix: data.rank ? ' 名' : '',
      desc: '当前公会的会战排名',
      color: '#10b981',
      tier: data.rank ? rankTier(Number(data.rank)) : null,
    },
    {
      label: '会战状态',
      value: data.state.includes('开启') ? '进行中' : '未开启',
      suffix: '',
      desc: data.state || '会战监控未启用',
      color: data.state.includes('开启') ? '#3b82f6' : '#9ca3af'
    }
  ]
})

const loopStateTagType = computed<'danger' | 'success' | 'info'>(() => {
  if (data.state.includes('开启') && data.state.includes('高占用')) return 'danger'
  if (data.state.includes('开启')) return 'success'
  return 'info'
})

// ========== 游戏账号绑定（全局） ==========
// 一个 QQ 只有一个游戏账号（后端 Account.group_id = 0），在哪个群都一样用 ——
// 换公会 / 进新群都不需要重新绑定。历史上按群区分的「本群专用号」已废弃。
// 兜底一份「未绑定」，避免后端还没下发 account 字段时模板里读 undefined 报错
const EMPTY_ACCOUNT: GroupAccountInfo = {
  bound: false,
  account_id: null,
  name: '',
  platform: 0,
  viewer_id: null
}
const account = computed<GroupAccountInfo>(() => data.account || EMPTY_ACCOUNT)

const accountLabel = computed(() => {
  const acc = account.value
  if (!acc || !acc.bound) return '未绑定游戏账号'
  return acc.name || '未命名角色'
})

const accountTagType = computed<'success' | 'info' | 'warning'>(() => {
  const acc = account.value
  if (!acc || !acc.bound) return 'warning'
  return 'success'
})

const accountTip = computed(() => {
  const acc = account.value
  if (!acc || !acc.bound) {
    return '还没有绑定游戏账号：点右侧按钮绑定，或在QQ私聊机器人发送【绑定账号帮助】'
  }
  const platform = PLATFORM_NAMES[acc.platform] || `服务器${acc.platform}`
  return `已绑定的游戏账号（所有群通用）｜${platform}｜viewer_id：${acc.viewer_id ?? '未同步'}`
})

const bindButtonText = computed(() => {
  const acc = account.value
  if (!acc || !acc.bound) return '绑定游戏账号'
  return '换绑'
})

const accountDialog = reactive<{
  visible: boolean
  loading: boolean
  unbinding: boolean
  errorMsg: string
  form: {
    platform: number
    bili_account: string
    bili_password: string
    login_id: string
    token: string
    short_udid: string
    udid: string
    viewer_id: number | null
  }
}>({
  visible: false,
  loading: false,
  unbinding: false,
  errorMsg: '',
  form: {
    platform: 0,
    bili_account: '',
    bili_password: '',
    login_id: '',
    token: '',
    short_udid: '',
    udid: '',
    viewer_id: null
  }
})

function resetAccountForm() {
  accountDialog.form = {
    platform: 0,
    bili_account: '',
    bili_password: '',
    login_id: '',
    token: '',
    short_udid: '',
    udid: '',
    viewer_id: null
  }
  accountDialog.errorMsg = ''
}

function openBindDialog() {
  accountDialog.errorMsg = ''
  accountDialog.visible = true
}

/** 前端先做一遍必填校验，省一次「提交→后端报错→再改」的往返 */
function validateAccountForm(): string {
  const f = accountDialog.form
  if (f.platform === 0) {
    if (!f.bili_account.trim() || !f.bili_password.trim()) return '请填写 B站账号和 B站密码'
  } else if (f.platform === 1) {
    if (!f.login_id.trim() || !f.token.trim()) return '请填写 login_id 和 token'
  } else if (!f.short_udid.trim() || !f.udid.trim() || !f.viewer_id) {
    return '请填写 short_udid、udid 和 viewer_id'
  }
  return ''
}

async function submitBindAccount() {
  const invalid = validateAccountForm()
  if (invalid) {
    accountDialog.errorMsg = invalid
    return
  }
  accountDialog.errorMsg = ''
  accountDialog.loading = true
  try {
    const f = accountDialog.form
    const payload: BindAccountForm = { platform: f.platform }
    if (f.platform === 0) {
      payload.bili_account = f.bili_account.trim()
      payload.bili_password = f.bili_password.trim()
    } else if (f.platform === 1) {
      payload.login_id = f.login_id.trim()
      payload.token = f.token.trim()
    } else {
      payload.short_udid = f.short_udid.trim()
      payload.udid = f.udid.trim()
      payload.viewer_id = f.viewer_id
    }
    const res = await bindAccount(groupId.value, payload)
    ElMessage.success(`绑定成功：${res?.name || '角色'}（本群专用）`)
    accountDialog.visible = false
    // 绑定可能换了角色，出刀报告里的「我的出刀」也会跟着变，整体刷一次
    await loadDashboard(true)
  } catch (e: any) {
    accountDialog.errorMsg = e?.response?.data?.detail || e?.message || '绑定失败'
  } finally {
    accountDialog.loading = false
  }
}

async function submitUnbind() {
  accountDialog.unbinding = true
  try {
    const res = await unbindAccount(groupId.value)
    ElMessage.success(typeof res === 'string' ? res : '解绑成功')
    await loadDashboard(true)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '解绑失败')
  } finally {
    accountDialog.unbinding = false
  }
}

// ========== 出刀监控开关（方案A） ==========
// 当前后端：data.state 包含"开启"视为"监控循环正在跑"
const isMonitorRunning = computed(() =>
  (data.state || '').includes('开启'),
)

// 能否「取消」出刀监控：监控人本人，或 bot 主人（clan_priority === 3）。
// 出刀监控是拿某个人的游戏账号在跑的，所以群主/群管也不允许取消别人的监控。
const canStopMonitor = computed(() => {
  if (Number(data.clan_priority) >= 3) return true
  const monitor = Number(data.monitor_user_id || 0)
  return monitor > 0 && Number(data.user_id) === monitor
})

const monitorLoading = ref(false)

// ========== BOSS 出刀记录弹窗 ==========
const bossDaoDialog = reactive<{
  visible: boolean
  loading: boolean
  title: string
  boss: number
  lap: number
  list: DaoInfo[]
  totalDamage: number
}>({
  visible: false,
  loading: false,
  title: '出刀记录',
  boss: 0,
  lap: 0,
  list: [],
  totalDamage: 0,
})

// 会战记录跨多天，时间列带日期
function formatBossDaoTime(ts: number) {
  return ts ? dayjs(ts * 1000).format('MM-DD HH:mm') : '--'
}

async function openBossDaoDialog(boss: BossInfoCounter, bossNo: number) {
  // 注意：boss.id 是游戏内部 boss_id（如 323200），接口要的是 1~5 的王编号
  bossDaoDialog.boss = bossNo
  bossDaoDialog.lap = boss.lap || 0
  bossDaoDialog.list = []
  bossDaoDialog.totalDamage = 0
  bossDaoDialog.title = `第 ${bossNo} 王 · ${boss.name} 出刀记录（本次会战）`
  bossDaoDialog.visible = true
  bossDaoDialog.loading = true
  try {
    const list = await getBossDao(groupId.value, bossNo)
    bossDaoDialog.list = Array.isArray(list) ? list : []
    bossDaoDialog.totalDamage = bossDaoDialog.list.reduce(
      (sum, r) => sum + (Number(r.damage) || 0),
      0
    )
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '拉取出刀记录失败')
  } finally {
    bossDaoDialog.loading = false
  }
}

// 开启监控弹窗状态
const startMonitorDialog = reactive<{
  visible: boolean
  accounts: MonitorAccountOption[]
  selectedAccountId: number | null
  loadingAccounts: boolean
  errorMsg: string
}>({
  visible: false,
  accounts: [],
  selectedAccountId: null,
  loadingAccounts: false,
  errorMsg: '',
})

async function openStartMonitorDialog() {
  startMonitorDialog.visible = true
  startMonitorDialog.selectedAccountId = null
  startMonitorDialog.errorMsg = ''
  startMonitorDialog.accounts = []
  startMonitorDialog.loadingAccounts = true
  try {
    const list = await getMonitorAccounts(groupId.value)
    startMonitorDialog.accounts = Array.isArray(list) ? list : []
    if (!startMonitorDialog.accounts.length) {
      startMonitorDialog.errorMsg =
        '还没有可用的角色账号，请先在状态条上绑定游戏账号。'
      return
    }
    // 只有一个账号时直接预选上
    if (startMonitorDialog.accounts.length === 1) {
      startMonitorDialog.selectedAccountId = startMonitorDialog.accounts[0].account_id
    }
  } catch (e: any) {
    startMonitorDialog.errorMsg = e?.response?.data?.detail || e?.message || '拉取绑定账号失败'
  } finally {
    startMonitorDialog.loadingAccounts = false
  }
}

async function submitStartMonitor() {
  if (!startMonitorDialog.selectedAccountId) {
    startMonitorDialog.errorMsg = '请先选择一个角色账号'
    return
  }
  startMonitorDialog.errorMsg = ''
  monitorLoading.value = true
  try {
    const res = await switchMonitor(groupId.value, {
      action: 'on',
      account_id: startMonitorDialog.selectedAccountId,
    })
    const msg = res?.message || '已启动出刀监控'
    ElMessage.success(msg)
    startMonitorDialog.visible = false
    // 启动可能需要几秒到十几秒才真正进入循环，先手动拉一次仪表盘（展示阶段信息）
    // 之后每 3s 拉一次，最多等 60s，直到后端状态变为"开启"
    await loadDashboard(true)
    let ticks = 0
    const waitForRunning = setInterval(async () => {
      ticks++
      if (ticks > 20) { // 20*3s=60s 超时
        clearInterval(waitForRunning)
        ElMessage.warning('启动命令已发出，但状态还在"未开启"，可以点【刷新】查看最新状态。')
        return
      }
      if (isMonitorRunning.value) {
        clearInterval(waitForRunning)
        // 监控已启动：稍等监控循环稳定后自动刷新一次档线
        setTimeout(() => loadRankLines(), 3000)
        return
      }
      await loadDashboard(true)
    }, 3000)
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '启动失败'
    startMonitorDialog.errorMsg = detail
    ElMessage.error(detail)
  } finally {
    monitorLoading.value = false
  }
}

async function confirmStopMonitor() {
  try {
    await ElMessageBox.confirm(
      '确定要取消当前的出刀监控吗？\n（稍后一轮循环会自动退出）',
      '取消出刀监控',
      {
        type: 'warning',
        confirmButtonText: '确定取消',
        cancelButtonText: '我再想想',
      }
    )
  } catch {
    return
  }
  monitorLoading.value = true
  try {
    const res = await switchMonitor(groupId.value, { action: 'off' })
    ElMessage.success(typeof res === 'string' ? res : (res?.message || '已取消'))
    // 接口已经把 loop_check=0，loadDashboard 后 data.state 立刻会是"关闭"
    setTimeout(() => loadDashboard(true), 400)
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '取消失败'
    ElMessage.error(detail)
  } finally {
    monitorLoading.value = false
  }
}

// 今日伤害排行（后端按玩家聚合今日出刀得出，已按伤害倒序）。
// 之前这里是拿 data.report 按「刀数」分组算「人数」，标题却写「伤害占比」——
// 既和伤害无关，又和左栏「今日出刀分布」读同一份数据，等于把左栏又画了一遍。
const dayDamageRankList = computed<DayDamageRank[]>(() => {
  const src = Array.isArray(data.day_damage_rank) ? data.day_damage_rank : []
  return src.filter((r) => (r.damage || 0) > 0)
})

// 最近出刀 Top 20（后端已按时间倒序，这里仅作安全兜底 & 取前 20）
const lastDaoList = computed<DaoInfo[]>(() => {
  const src = Array.isArray(data.last_dao) ? data.last_dao : []
  return [...src]
    .sort((a, b) => (b.date || 0) - (a.date || 0))
    .slice(0, 20)
})

function daoTypeTag(type: string): 'primary' | 'success' | 'warning' | 'danger' {
  if (!type) return 'info' as any
  const t = type
  if (t.includes('尾刀')) return 'warning'
  if (t.includes('补偿')) return 'danger'
  if (t.includes('完整') || t.includes('正常')) return 'success'
  return 'primary'
}

function formatDaoTime(ts: number) {
  if (!ts) return '--'
  return dayjs(ts * 1000).format('HH:mm:ss')
}

// 给"最近出刀"列表里的每个玩家分配一个不同颜色的头像背景（同一玩家稳定同色，不同玩家尽量差异大）
const AVATAR_PALETTE = [
  '#ec4899', // 原粉（保留作为基色之一）
  '#f472b6', // 浅粉
  '#db2777', // 深玫红
  '#be123c', // 玫红
  '#f97316', // 橙
  '#fb923c', // 亮橙
  '#f59e0b', // 琥珀
  '#eab308', // 金黄
  '#ca8a04', // 暖黄
  '#84cc16', // 青草绿
  '#22c55e', // 翠绿
  '#10b981', // 薄荷
  '#14b8a6', // 湖青
  '#06b6d4', // 青蓝
  '#3b82f6', // 宝蓝
  '#6366f1', // 靛蓝
  '#8b5cf6', // 薰衣紫
  '#a855f7', // 紫
  '#c026d3', // 洋紫
  '#ef4444'  // 红
]
function avatarBgColor(name: string | undefined | null): string {
  const s = (name || '?').trim() || '?'
  // 简单字符串哈希：把字符 Unicode 累加成一个稳定整数，mod 调色板长度
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  const idx = Math.abs(h) % AVATAR_PALETTE.length
  return AVATAR_PALETTE[idx]
}

// 今日出刀分布：按刀数给徽标配色（刀数越多越绿，越少越红，未出刀为灰）
function daoNumColor(dao: number): string {
  const map: Record<number, string> = {
    3: '#10b981', // 3 刀 绿（已出满）
    2.5: '#14b8a6', // 2.5 刀 青
    2: '#f59e0b', // 2 刀 琥珀
    1.5: '#f97316', // 1.5 刀 橙
    1: '#f43f5e', // 1 刀 玫红
    0.5: '#ef4444', // 0.5 刀（补时） 红
    0: '#94a3b8', // 未出刀 灰
  }
  return map[dao] || '#6366f1'
}

// 今日出刀分布：玩家名标签跟随该行刀数配色（同色浅底 + 同色文字/边框）
function distTagStyle(dao: number): Record<string, string> {
  const color = daoNumColor(dao)
  return {
    background: color + '1a',
    borderColor: color + '59',
    color: color,
  }
}

// 横向条形：这一栏只有 6/24 宽，饼图在这个宽度下 30 个分片根本看不出谁高谁低；
// 横向条形能同时给出绝对值（条长 + 末端标签）和相对占比（tooltip）。
const dayDamageRankOption = computed<EChartsOption>(() => {
  // ECharts 的 category 轴是从下往上排的，先反转，让伤害最高的出现在最上面
  const rows = [...dayDamageRankList.value].reverse()
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const row = rows[Array.isArray(params) ? params[0].dataIndex : params.dataIndex]
        if (!row) return ''
        return (
          `${row.name}<br/>` +
          `伤害 ${formatNum(row.damage)}（${row.damage_rate}%）<br/>` +
          `分数 ${formatNum(row.score)}（${row.score_rate}%）<br/>` +
          `今日 ${row.dao} 刀`
        )
      }
    },
    grid: { left: 4, right: 56, top: 4, bottom: 4, containLabel: true },
    // 窄栏里 x 轴的刻度数值意义不大（条长本身就表达了），关掉省空间
    xAxis: { type: 'value', show: false },
    yAxis: {
      type: 'category',
      data: rows.map((r) => r.name || '未知'),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { fontSize: 11, width: 56, overflow: 'truncate' }
    },
    series: [
      {
        type: 'bar',
        data: rows.map((r) => r.damage),
        barMaxWidth: 14,
        itemStyle: { color: '#ec4899', borderRadius: [0, 4, 4, 0] },
        emphasis: { itemStyle: { color: '#db2777' } },
        label: {
          show: true,
          position: 'right',
          fontSize: 11,
          color: '#831843',
          formatter: (p: any) => formatShortNum(p.value)
        }
      }
    ]
  }
})

// 通知弹窗
const noticeDialog = reactive<{
  visible: boolean
  title: string
  form: NoticeCacheModel
}>({
  visible: false,
  title: '',
  form: {
    group_id: 0,
    notice_type: 0,
    user_id: 0,
    boss: 1,
    lap: 0,
    text: ''
  }
})

function bossHpPercent(boss: BossInfoCounter) {
  if (!boss.max_hp) return 0
  return Math.max(0, Math.min(100, Math.round((boss.current_hp / boss.max_hp) * 100)))
}
function hpBarColor(idx: number) {
  const colors = ['#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6']
  return colors[idx % colors.length]
}
function formatNum(n: number) {
  if (!n && n !== 0) return '0'
  return n.toLocaleString()
}
/** 把伤害/分数缩写成「3.3亿」「1234万」—— 窄栏里条形末端的标签放不下完整数字 */
function formatShortNum(n: number) {
  const v = Number(n) || 0
  if (v >= 1e8) return (v / 1e8).toFixed(1) + '亿'
  if (v >= 1e4) return Math.round(v / 1e4) + '万'
  return String(v)
}

async function loadDashboard(forceMsg = false) {
  if (!groupId.value) return
  try {
    loading.value = true
    const res = await getDashboard(groupId.value)
    Object.assign(data, res)
    if (forceMsg) ElMessage.success('已刷新')
  } finally {
    loading.value = false
  }
}

function toggleSSE() {
  if (sseEnabled.value) {
    stopSSE()
  } else {
    startSSE()
  }
}

function startSSE() {
  stopSSE()
  if (!groupId.value) return
  const url = `${API_BASE}/${groupId.value}/renew_dashboard`
  sseClient = createSSEConnection(url, {
    onMessage: (newData: DashboardResponse) => {
      Object.assign(data, newData)
    },
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

function openNoticeDialog(boss: BossInfoCounter, noticeType: number) {
  const idx = data.boss.indexOf(boss)
  const titleMap: Record<number, string> = {
    0: '预约 BOSS',
    1: '挂树上报',
    2: '申请出刀',
    5: '记录 SL'
  }
  noticeDialog.title = titleMap[noticeType] || '添加通知'
  noticeDialog.form = {
    group_id: groupId.value,
    notice_type: noticeType,
    user_id: userStore.userId,
    boss: (idx >= 0 ? idx + 1 : 1) || 1,
    lap: boss.lap || 0,
    text: ''
  }
  noticeDialog.visible = true
}

async function submitNotice() {
  try {
    await setNotice({ ...noticeDialog.form, group_id: Number(noticeDialog.form.group_id) })
    ElMessage.success('操作成功，QQ 群内会同步公告')
    noticeDialog.visible = false
    await nextTick()
    loadDashboard()
  } catch (e) {
    /* 拦截器已弹错 */
  }
}

// 监听 groupId 变化（挂载时 immediate 触发一次）
watch(
  groupId,
  (id) => {
    if (!id) return
    // 同步到路由（如果不一致）
    const routeGroup = Number(route.params.groupId)
    if (routeGroup !== id) {
      router.replace(`/dashboard/${id}`)
    }
    // 注意：菜单跳转进来的 URL 不带 groupId 参数，上面 replace 后 groupId 值不变、
    // watch 不会再次触发，因此这里不能 return，必须始终加载数据
    loadDashboard()
    // 默认开启实时（延时再开 SSE 避免阻塞首屏；切换公会时 startSSE 内部会重连）
    setTimeout(startSSE, 800)
  },
  { immediate: true }
)

// ================= 会战档线 =================
const rankLine = reactive({
  loading: false,
  error: '',
  clanBattleId: 0,
  lines: [] as (RankLine | null)[],
  my: null as RankLine | null,
  customInput: '',
  customRanks: [] as number[],
  // 以下三项来自后端：档线在服务端本地缓存（游戏侧每半小时才更新一次），
  // cached = 本次没去抓游戏接口；stale = 抓取失败退回了过期缓存；
  // updatedAt = 这份数据的抓取时间（Unix 秒）
  cached: false,
  stale: false,
  monitorRunning: false,
  updatedAt: 0,
})

// null 档位补全为占位行，保证表格按请求顺序展示；
// 我会若不在档位列表中，按排名顺序动态插入并高亮
interface RankRow extends RankLine {
  isMy?: boolean
  /** 服务器实际最后一名公会所在档位（后端会自动把它追加进档位列表），用绿色高亮 */
  isLast?: boolean
}
const rankLineRows = computed<RankRow[]>(() => {
  const rows: RankRow[] = rankLine.lines.map(
    (line, i) =>
      line || {
        rank: rankLine.customRanks[i] ?? i + 1,
        damage: null,
        clan_name: null,
        leader_name: null,
        leader_viewer_id: null,
        member_num: null,
        reward: null,
      }
  )
  const my = rankLine.my
  if (my && my.rank) {
    // 排名恰好等于某档位时，直接高亮该行
    const exist = rows.find((r) => r.rank === my.rank)
    if (exist) {
      exist.isMy = true
    } else {
      // 本公会档位奖励 = 我会已达成的最高档位（首个排名 >= 我会排名的档位）
      const achieved = rows.find((r) => r.rank >= my.rank!)
      const myRow: RankRow = { ...my, reward: achieved?.reward ?? null, isMy: true }
      // 表格按档位升序展示：插到第一个比我排名靠后的档位之前
      const idx = rows.findIndex((r) => r.rank > my.rank!)
      if (idx === -1) rows.push(myRow)
      else rows.splice(idx, 0, myRow)
    }
  }
  // 标记"最后一名"：有公会数据的档位里排名最大的那一个。
  // 后端 query_rank_lines 会把"服务器实际最后一名公会"的排名追加进档位列表，
  // 所以带数据档位的最大 rank 就是榜单末位，前端给它绿色高亮以示区分。
  let lastRank: number | null = null
  for (const r of rows) {
    if (r.damage === null || r.damage === undefined) continue
    if (lastRank === null || r.rank > lastRank) lastRank = r.rank
  }
  if (lastRank !== null) {
    const lastRow = rows.find((r) => r.rank === lastRank)
    if (lastRow) lastRow.isLast = true
  }
  return rows
})

const rankRowClass = ({ row }: { row: RankRow }) =>
  row.isMy ? 'my-clan-row' : row.isLast ? 'last-rank-row' : ''

/**
 * 档线数据的抓取时间文案（状态条上展示）。
 * 后端把档线缓存在本地库里、游戏侧又每半小时才更新一次，所以必须把「这份数据
 * 是什么时候抓的」标出来，否则用户看到的是旧数据却无从判断。
 */
const rankLineUpdatedText = computed(() => {
  if (!rankLine.updatedAt) return ''
  const d = new Date(rankLine.updatedAt * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
})

/** 数据来源说明：缓存 / 过期缓存 / 刚刚抓取 */
const rankLineSourceTip = computed(() => {
  if (rankLine.stale) {
    return rankLine.monitorRunning
      ? '本次抓取失败，显示的是上一次缓存的数据'
      : '出刀监控未开启，显示的是上一次缓存的数据（开启监控后才会更新）'
  }
  if (rankLine.cached) {
    return '本地缓存数据（游戏侧档线每半小时更新一次，缓存 25 分钟内不重复抓取）'
  }
  return '刚刚从游戏侧抓取的最新数据'
})

/**
 * 加载档线。
 * - force=false（默认）：后端优先返回本地缓存，缓存过期才去游戏侧抓。页面打开、
 *   切换档位、以及每半小时的定时刷新都走这条 —— 多个页面同时开着也只会真抓一次。
 * - force=true：忽略缓存强制抓一次（「刷新」按钮用），仅出刀监控运行中有效。
 */
async function loadRankLines(custom?: string, force = false) {
  if (!groupId.value || rankLine.loading) return
  rankLine.loading = true
  rankLine.error = ''
  // 解析自定义排名：支持逗号/空格分隔
  let ranks: number[] | undefined
  if (custom && custom.trim()) {
    const parsed = custom
      .split(/[,，\s]+/)
      .map((x) => Number(x.trim()))
      .filter((x) => Number.isInteger(x) && x > 0)
    if (!parsed.length) {
      rankLine.loading = false
      rankLine.error = '排名格式不对，示例：500,2000'
      return
    }
    ranks = parsed
  }
  try {
    const res = await getRankLines(groupId.value, ranks, force)
    rankLine.clanBattleId = res.clan_battle_id
    rankLine.lines = res.lines || []
    rankLine.my = res.my || null
    rankLine.customRanks = ranks || res.default_ranks || []
    rankLine.cached = res.cached === true
    rankLine.stale = res.stale === true
    rankLine.monitorRunning = res.monitor_running === true
    rankLine.updatedAt = res.updated_at || 0
  } catch (e: any) {
    // 这里不清空已有数据：后端在抓取失败时会退回上一次的缓存，能走到这个分支
    // 说明连缓存都没有（比如从没抓过），保留旧表格比直接空掉更不容易误解。
    rankLine.error = e?.response?.data?.detail || e?.message || '档线查询失败'
  } finally {
    rankLine.loading = false
  }
}

// 切换公会时清掉上一家的档线并重新读取：后端缓存是按群存的，切群必须换一份。
// 注意这个 watch 不能写在上方那个 immediate 的 groupId watch 里 —— 那边在 setup
// 阶段就同步执行了，而 rankLine 是后面才声明的 const，会撞上暂时性死区。
watch(groupId, () => {
  rankLine.clanBattleId = 0
  rankLine.lines = []
  rankLine.my = null
  rankLine.customRanks = []
  rankLine.updatedAt = 0
  rankLine.cached = false
  rankLine.stale = false
  rankLine.error = ''
  loadRankLines()
})

onMounted(() => {
  // 打开页面先读一次档线：后端有本地缓存时直接命中、秒出，一次游戏接口都不打，
  // 所以「每次打开网页都要抓一次」的开销就没了；只有没缓存时才真的去抓。
  loadRankLines()
  // 数字时钟：每秒刷新（所有 boss 行共用）
  clockTimer = setInterval(() => {
    now.value = new Date()
  }, 1000)
  // SSE 连接已移入上方 groupId watch（保证任何进入路径都会开启实时）
  // 档线定时自动刷新：仅在出刀监控运行期间，每小时的 1 分 / 31 分各刷一次。
  // 这里故意不带 force —— 走 TTL 判断，多个页面同时开着也只会真的抓一次。
  rankAutoTimer = setInterval(() => {
    if (!groupId.value || !isMonitorRunning.value || rankLine.loading) return
    const d = new Date()
    const m = d.getMinutes()
    if (m !== 1 && m !== 31) return
    // 用"日期+小时+分钟"作为槽位标识，避免同一分钟内重复刷新
    const slot = `${d.getFullYear()}${d.getMonth() + 1}${d.getDate()}_${d.getHours()}_${m}`
    if (slot === lastRankAutoSlot) return
    lastRankAutoSlot = slot
    loadRankLines()
  }, 20000)
})

onBeforeUnmount(() => {
  stopSSE()
  if (clockTimer) {
    clearInterval(clockTimer)
    clockTimer = null
  }
  if (rankAutoTimer) {
    clearInterval(rankAutoTimer)
    rankAutoTimer = null
  }
})
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.overview .ov-card {
  position: relative;
  margin-bottom: 16px;
  transition: transform 0.2s;
}
/* 排名阶级徽章：六边形盾牌，垂直居中于卡片右侧 */
.ov-tier {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  width: 54px;
  height: 60px;
  clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
  cursor: default;
}
.ov-tier-name {
  font-size: 17px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: 1px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
}
.ov-tier-range {
  margin-top: 3px;
  font-size: 9px;
  line-height: 1;
  opacity: 0.92;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}
.overview .ov-card:hover {
  transform: translateY(-2px);
}
/* 5 张概览卡：大屏（≥1200px）时 5 等分一行，避免第 5 张孤行 */
@media (min-width: 1200px) {
  .overview :deep(.el-col) {
    flex: 0 0 20%;
    max-width: 20%;
  }
}
.ov-label {
  color: #6b7280;
  font-size: 13px;
}
.ov-value {
  margin: 6px 0;
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
}
.ov-value small {
  font-size: 14px;
  font-weight: 400;
  opacity: 0.7;
  margin-left: 4px;
}
.ov-desc {
  color: #9ca3af;
  font-size: 12px;
}
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.status-left,
.status-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.clan-name {
  font-weight: 600;
  color: #831843;
  font-size: 15px;
}
.stage {
  color: #374151;
  padding: 3px 10px;
  background: #eff6ff;
  border-radius: 999px;
  font-size: 12px;
}
.day-num {
  color: #374151;
  padding: 3px 10px;
  background: #fef3c7;
  border-radius: 999px;
  font-size: 12px;
}
/* 状态条上的游戏账号标签（点它旁边的按钮可绑定/换绑/解绑） */
.account-tag {
  cursor: default;
}
.account-tag :deep(.el-icon) {
  margin-right: 4px;
  vertical-align: -2px;
}
/* 开启出刀监控 dialog 提示块 */
.tip-block {
  background: #fff1f2;
  border: 1px solid #fecdd3;
  border-radius: 8px;
  padding: 10px 12px;
  line-height: 1.8;
  font-size: 12px;
  color: #831843;
}
.tip-block > div {
  margin: 2px 0;
}
.spin {
  animation: spin 1s linear infinite;
  margin-right: 2px;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #831843;
  padding: 12px 0 8px;
}
/* BOSS 行内的 el-col 改为纵向 flex 容器：el-row 默认 align-items:stretch 会把
   el-col 拉到整行高度，配合卡片的 flex:1，同一行内所有卡片（含右侧「当前时间」
   时钟卡）自动等高——高度由该行内容最高的卡片决定，不依赖写死的 min-height。
   注意：卡片保留 margin-bottom 作为行间距，故等高的是卡片本身而非整格。 */
.boss-row :deep(.el-col) {
  display: flex;
  flex-direction: column;
}
.boss-card,
.clock-card {
  /* 只加 flex-grow（保留 flex-basis:auto）：
     若写成 flex:1 会把 basis 变成 0%，列高由内容决定时会塌陷 */
  flex-grow: 1;
}
.boss-card {
  margin-bottom: 16px;
  min-height: 212px;
  display: flex;
  flex-direction: column;
}
.clock-card {
  margin-bottom: 16px;
  min-height: 212px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 8px;
  text-align: center;
  background:
    linear-gradient(135deg, rgba(252, 231, 243, 0.85) 0%, rgba(255, 255, 255, 0.95) 60%, rgba(254, 249, 195, 0.85) 100%);
  border: 1px solid rgba(244, 114, 182, 0.25);
  box-shadow: 0 1px 2px rgba(236, 72, 153, 0.06), inset 0 0 0 1px rgba(255, 255, 255, 0.6);
}
.clock-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.clock-label {
  color: #9d174d;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.clock-time {
  font-family: 'Consolas', 'SF Mono', 'JetBrains Mono', Menlo, monospace;
  font-size: 42px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: 2px;
  color: #831843;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 2px 4px rgba(236, 72, 153, 0.25);
  padding: 6px 0 4px;
}
.clock-date {
  font-size: 13px;
  color: #be185d;
  font-weight: 500;
  letter-spacing: 0.5px;
}
.clock-day-tip {
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px dashed rgba(236, 72, 153, 0.3);
  font-size: 12px;
  color: #6b7280;
}
.clock-day-tip b {
  color: #be185d;
  font-size: 14px;
  padding: 0 2px;
}
.boss-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}
/* BOSS 头像 + 名称块 */
.boss-id-block {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.boss-avatar {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  border-radius: 12px;
  object-fit: cover;
  background: linear-gradient(135deg, #fdf2f8 0%, #fef9c3 100%);
  border: 1px solid rgba(236, 72, 153, 0.25);
  box-shadow: 0 2px 6px rgba(236, 72, 153, 0.18);
}
.boss-avatar--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 800;
  color: #be185d;
}
.boss-no {
  color: #9ca3af;
  font-size: 12px;
}
.boss-name {
  font-weight: 600;
  font-size: 17px;
  color: #1f2937;
  margin-top: 2px;
}
.boss-lap {
  padding: 3px 10px;
  background: linear-gradient(90deg, #fce7f3, #fef3c7);
  color: #9d174d;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.hp-bar {
  margin-bottom: 6px;
}
.hp-text {
  font-size: 12px;
  font-weight: 600;
  text-align: right;
  margin-bottom: 12px;
}
.boss-stats {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 14px;
}
/* 纯 div 手写 pill：完全不受 Element Plus 不同 type 的样式影响 */
.stat-tag {
  --tag-bg: #fff;
  --tag-border: #e5e7eb;
  --tag-fg: #374151;
  --tag-num-bg: rgba(255, 255, 255, 0.7);

  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 4px;
  height: 28px;                 /* 统一固定高度：对齐的根本 */
  padding: 0 8px 0 6px;
  background: var(--tag-bg);
  color: var(--tag-fg);
  border: 1px solid var(--tag-border);
  border-radius: 6px;
  font-size: 12px;
  line-height: 1;
  font-weight: 500;
  box-sizing: border-box;
  white-space: nowrap;
  user-select: none;
}
.stat-tag--primary {
  --tag-bg: #ecfeff;
  --tag-border: #a5f3fc;
  --tag-fg: #0e7490;
  --tag-num-bg: #cffafe;
}
.stat-tag--success {
  --tag-bg: #ecfdf5;
  --tag-border: #a7f3d0;
  --tag-fg: #047857;
  --tag-num-bg: #d1fae5;
}
.stat-tag--warning {
  --tag-bg: #fffbeb;
  --tag-border: #fde68a;
  --tag-fg: #b45309;
  --tag-num-bg: #fef3c7;
}
.stat-tag--danger {
  --tag-bg: #fef2f2;
  --tag-border: #fecaca;
  --tag-fg: #b91c1c;
  --tag-num-bg: #fee2e2;
}
/* 图标：统一 16×16 居中 */
.stat-icon {
  width: 16px;
  height: 16px;
  font-size: 16px;
  line-height: 1;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: inherit;
}
/* 文字：12px 一字不差 */
.stat-text {
  font-size: 12px;
  line-height: 1;
  letter-spacing: 0.5px;
  color: inherit;
}
/* 数字 pill：固定 20px 高，不再撑高 tag */
.stat-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  margin-left: 2px;
  font-size: 12px;
  line-height: 1;
  font-weight: 700;
  color: inherit;
  border-radius: 4px;
  background: var(--tag-num-bg);
  box-sizing: border-box;
}
.boss-actions {
  display: flex;
  gap: 8px;
  justify-content: space-between;
  align-items: center;
  border-top: 1px dashed #f3f4f6;
  padding-top: 12px;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #831843;
  margin-bottom: 14px;
}
.h-full {
  height: 100%;
}
.mt-16 {
  margin-top: 16px;
}
/* 最近出刀表格 - 对齐 & 视觉美化 */
.dao-player {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
}
.dao-avatar {
  margin-right: 8px;
  color: #fff;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.15), inset 0 0 0 1px rgba(255, 255, 255, 0.25);
}
/* 今日出刀分布 - 刀数徽标（颜色由 daoNumColor 按刀数动态绑定） */
.dao-num-badge {
  display: inline-block;
  min-width: 52px;
  text-align: center;
  padding: 3px 10px;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  line-height: 18px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.15), inset 0 0 0 1px rgba(255, 255, 255, 0.2);
}
/* 今日出刀分布 - 玩家名标签（底色/文字色随刀数配色动态绑定） */
.dist-player-tag {
  display: inline-block;
  margin: 2px 4px 2px 0;
  padding: 1px 8px;
  border-radius: 4px;
  border: 1px solid transparent;
  font-size: 12px;
  line-height: 18px;
}
.dao-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  max-width: 96px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dao-damage {
  font-size: 13px;
  color: #be185d;
  font-variant-numeric: tabular-nums;
}
.dao-time {
  font-size: 12px;
  color: #6b7280;
  font-family: 'Consolas', 'SF Mono', Menlo, monospace;
  font-variant-numeric: tabular-nums;
}
/* BOSS 卡片底部操作行：左侧"出刀记录"，右侧预约/申请/挂树 */
.boss-actions .boss-record-btn {
  margin-left: 0;
  color: #8b5cf6;
  border-color: #ddd6fe;
  background: #f5f3ff;
}
.boss-actions .boss-record-btn:hover {
  color: #7c3aed;
  border-color: #c4b5fd;
  background: #ede9fe;
}
.boss-actions-right {
  display: flex;
  align-items: center;
}
.boss-actions-right .el-button + .el-button {
  margin-left: 8px;
}
/* BOSS 出刀记录弹窗顶部汇总条 */
.boss-dao-summary {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
/* 会战档线卡片 */
.rankline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}
.rankline-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
/* 我会所在档线行：粉色高亮 */
:deep(.el-table__body tr.my-clan-row > td.el-table__cell) {
  background: #fdf2f8;
}
:deep(.el-table__body tr.my-clan-row:hover > td.el-table__cell) {
  background: #fce7f3;
}
.my-clan-name {
  color: #db2777;
  font-weight: 600;
}
/* 最后一名（服务器实际榜单末位档位）：绿色高亮 */
:deep(.el-table__body tr.last-rank-row > td.el-table__cell) {
  background: #ecfdf5;
}
:deep(.el-table__body tr.last-rank-row:hover > td.el-table__cell) {
  background: #d1fae5;
}
.last-rank-name {
  color: #059669;
  font-weight: 600;
}
/* 档线表格「合计分数」：默认与守线公会名同色（都跟随正文色），
   我会行保持原有合计分数配色，末位行沿用绿色 */
.rank-score {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.rank-score.my-clan-name {
  color: #be185d;
}
.reward-cell {
  font-size: 12px;
  color: #92610a;
  white-space: nowrap;
}
.gap-ok {
  color: #16a34a;
  font-weight: 600;
}
.gap-lack {
  color: #ea580c;
  font-weight: 600;
}
</style>
