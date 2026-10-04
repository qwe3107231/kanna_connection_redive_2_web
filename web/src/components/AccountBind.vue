<template>
  <!-- 游戏账号条：绑定 / 换绑 / 解绑。
       原来长在「会战仪表盘」的状态条上，2026-10-04 用户要求挪到首页（「我的公会」上面）。
       账号是**全局**的（一个 QQ 一个号，`Account.group_id = 0`），绑一次所有群通用，
       和 QQ 私聊【绑定账号】写的是同一条。 -->
  <div class="account-card kanna-card">
    <div class="account-left">
      <div class="account-avatar" :class="{ 'is-bound': account.bound }">
        <el-icon :size="22"><UserFilled /></el-icon>
      </div>
      <div class="account-text">
        <div class="account-line">
          <span class="account-title">游戏账号</span>
          <el-tooltip :content="accountTip" placement="top">
            <el-tag size="small" :type="accountTagType" effect="plain" class="account-tag">
              {{ accountLabel }}
            </el-tag>
          </el-tooltip>
        </div>
        <div class="account-hint">{{ accountHint }}</div>
      </div>
    </div>

    <div class="account-actions">
      <el-button size="small" type="primary" plain :disabled="!canBind" @click="openBindDialog">
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
          <el-button size="small" type="danger" plain :disabled="!canBind" :loading="unbinding">
            解绑
          </el-button>
        </template>
      </el-popconfirm>
    </div>
  </div>

  <!-- 绑定游戏账号（全局）：一个 QQ 一个号，换公会 / 进新群都不用重绑 -->
  <el-dialog
    v-model="visible"
    title="绑定游戏账号"
    width="500px"
    :close-on-click-modal="false"
    @closed="resetForm"
  >
    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="绑一次所有群通用（换公会也不用重绑）"
      description="和 QQ 私聊机器人【绑定账号】写的是同一条，在哪绑都一样。绑定过程会真实登录一次游戏来校验账号并读取角色昵称，请确保信息正确。"
      style="margin-bottom: 16px"
    />
    <el-form label-position="top">
      <el-form-item label="服务器" required>
        <el-radio-group v-model="form.platform">
          <el-radio-button :value="0">官服（B站）</el-radio-button>
          <el-radio-button :value="1">渠道服</el-radio-button>
          <el-radio-button :value="2">台服</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <!-- 官服：B站账号 + B站密码 -->
      <template v-if="form.platform === 0">
        <el-form-item label="B站账号" required>
          <el-input
            v-model="form.bili_account"
            placeholder="B站手机号 / 邮箱 / 用户名"
            clearable
          />
        </el-form-item>
        <el-form-item label="B站密码" required>
          <el-input
            v-model="form.bili_password"
            type="password"
            show-password
            placeholder="B站密码"
          />
        </el-form-item>
      </template>

      <!-- 渠服：login_id + token -->
      <template v-else-if="form.platform === 1">
        <el-form-item label="login_id" required>
          <el-input v-model="form.login_id" placeholder="提取器给出的 login_id" clearable />
        </el-form-item>
        <el-form-item label="token" required>
          <el-input
            v-model="form.token"
            placeholder="access_key，或提取器导出的 XML 片段（整段粘贴）"
            clearable
          />
        </el-form-item>
      </template>

      <!-- 台服：short_udid + udid + viewer_id -->
      <template v-else>
        <el-form-item label="short_udid" required>
          <el-input v-model="form.short_udid" clearable />
        </el-form-item>
        <el-form-item label="udid" required>
          <el-input v-model="form.udid" clearable />
        </el-form-item>
        <el-form-item label="viewer_id" required>
          <el-input-number
            v-model="form.viewer_id"
            :min="1"
            :controls="false"
            style="width: 100%"
          />
        </el-form-item>
      </template>

      <el-alert
        v-if="errorMsg"
        type="error"
        show-icon
        :closable="false"
        :title="errorMsg"
        style="margin-bottom: 12px"
      />
      <div class="tip-block">
        <div>🔸 绑定需要真实登录一次游戏，通常几秒到十几秒（官服换 access_key 会久一些）。</div>
        <div>🔸 重复绑定会覆盖原来那一条（一个 QQ 只保留一个游戏账号）。</div>
        <div>🔸 解绑对所有群一起生效；想换号直接重新绑定覆盖即可。</div>
      </div>
    </el-form>
    <template #footer>
      <el-button @click="visible = false" :disabled="loading">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submitBindAccount">绑定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { bindAccount, unbindAccount } from '@/api'
import { PLATFORM_NAMES } from '@/types'
import type { BindAccountForm, GroupAccountInfo } from '@/types'

const props = defineProps<{
  /** 当前登录用户的游戏账号（全局：一个 QQ 一个号，所有群通用） */
  account: GroupAccountInfo
  /**
   * 绑定 / 解绑请求要带一个 group_id（`/{group_id}/bind_account` 用它做访问校验）。
   * 账号本身是全局的，写进库的永远是 `Account.group_id = 0`，所以随便一个有权限的群都行。
   * 0 = 一个群都没有 —— 这时按钮禁用。
   */
  groupId: number
}>()

const emit = defineEmits<{ (e: 'changed'): void }>()

const accountLabel = computed(() => {
  const acc = props.account
  if (!acc || !acc.bound) return '未绑定游戏账号'
  return acc.name || '未命名角色'
})

const accountTagType = computed<'success' | 'info' | 'warning'>(() =>
  props.account?.bound ? 'success' : 'warning',
)

const accountTip = computed(() => {
  const acc = props.account
  if (!acc || !acc.bound) {
    return '还没有绑定游戏账号：点右侧按钮绑定，或在QQ私聊机器人发送【绑定账号帮助】'
  }
  const platform = PLATFORM_NAMES[acc.platform] || `服务器${acc.platform}`
  return `已绑定的游戏账号（所有群通用）｜${platform}｜viewer_id：${acc.viewer_id ?? '未同步'}`
})

const bindButtonText = computed(() => (props.account?.bound ? '换绑' : '绑定游戏账号'))

/** 一个群都没有时没法调绑定接口（URL 里的 group_id 过不了访问校验） */
const canBind = computed(() => Number(props.groupId) > 0)

const accountHint = computed(() => {
  if (!canBind.value) {
    return '先在 QQ 群里发送【绑定本群公会】，加入一个公会后就能绑定游戏账号了'
  }
  if (props.account?.bound) {
    return '绑一次所有群通用，换公会 / 进新群都不用重绑'
  }
  return '还没绑定游戏账号 —— 绑定后才能用出刀监控、BOX / 助战等功能'
})

const visible = ref(false)
const loading = ref(false)
const unbinding = ref(false)
const errorMsg = ref('')
const form = reactive({
  platform: 0,
  bili_account: '',
  bili_password: '',
  login_id: '',
  token: '',
  short_udid: '',
  udid: '',
  viewer_id: null as number | null,
})

function resetForm() {
  form.platform = 0
  form.bili_account = ''
  form.bili_password = ''
  form.login_id = ''
  form.token = ''
  form.short_udid = ''
  form.udid = ''
  form.viewer_id = null
  errorMsg.value = ''
}

function openBindDialog() {
  errorMsg.value = ''
  visible.value = true
}

/** 前端先做一遍必填校验，省一次「提交→后端报错→再改」的往返 */
function validateForm(): string {
  if (form.platform === 0) {
    if (!form.bili_account.trim() || !form.bili_password.trim()) return '请填写 B站账号和 B站密码'
  } else if (form.platform === 1) {
    if (!form.login_id.trim() || !form.token.trim()) return '请填写 login_id 和 token'
  } else if (!form.short_udid.trim() || !form.udid.trim() || !form.viewer_id) {
    return '请填写 short_udid、udid 和 viewer_id'
  }
  return ''
}

async function submitBindAccount() {
  const invalid = validateForm()
  if (invalid) {
    errorMsg.value = invalid
    return
  }
  errorMsg.value = ''
  loading.value = true
  try {
    const payload: BindAccountForm = { platform: form.platform }
    if (form.platform === 0) {
      payload.bili_account = form.bili_account.trim()
      payload.bili_password = form.bili_password.trim()
    } else if (form.platform === 1) {
      payload.login_id = form.login_id.trim()
      payload.token = form.token.trim()
    } else {
      payload.short_udid = form.short_udid.trim()
      payload.udid = form.udid.trim()
      payload.viewer_id = form.viewer_id
    }
    const res = await bindAccount(props.groupId, payload)
    ElMessage.success(`绑定成功：${res?.name || '角色'}（所有群通用）`)
    visible.value = false
    // 绑定可能换了角色，出刀报告里的「我的出刀」等也会跟着变，让外层整体刷一次
    emit('changed')
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || e?.message || '绑定失败'
  } finally {
    loading.value = false
  }
}

async function submitUnbind() {
  unbinding.value = true
  try {
    const res = await unbindAccount(props.groupId)
    ElMessage.success(typeof res === 'string' ? res : '解绑成功')
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '解绑失败')
  } finally {
    unbinding.value = false
  }
}
</script>

<style scoped>
.account-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 14px;
  /* 只是个「账号条」，比别的卡片矮一点、轻一点 */
  padding: 14px 18px;
}
.account-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.account-avatar {
  flex: none;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  /* 未绑定：暖黄；已绑定：青绿（和右边那个 success 标签呼应） */
  color: #b45309;
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  transition: all 0.2s;
}
.account-avatar.is-bound {
  color: #047857;
  background: linear-gradient(135deg, #d1fae5, #a7f3d0);
}
.account-text {
  min-width: 0;
}
.account-line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.account-title {
  font-size: 14px;
  font-weight: 600;
  color: #831843;
}
.account-tag {
  cursor: default;
}
.account-hint {
  margin-top: 3px;
  font-size: 12px;
  line-height: 1.5;
  color: #9ca3af;
}
.account-actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: 10px;
}
/* Element Plus 会给相邻按钮加 margin-left，这里已经用 gap 排版了，去掉免得间距过大 */
.account-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

/* ================= 手机端（< 768px） ================= */
@media (max-width: 767px) {
  .account-card {
    padding: 14px;
    gap: 12px;
  }
  /* 按钮落到第二行铺满，比挤在右边好按 */
  .account-actions {
    width: 100%;
  }
  .account-actions :deep(.el-button) {
    flex: 1;
    margin-left: 0;
  }
}
</style>
