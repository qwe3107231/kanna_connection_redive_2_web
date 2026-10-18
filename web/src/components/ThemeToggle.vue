<template>
  <el-dropdown trigger="click" placement="bottom-end" @command="onCommand">
    <button
      type="button"
      class="theme-toggle"
      :title="buttonTitle"
      :aria-label="buttonTitle"
    >
      <el-icon :size="18">
        <Moon v-if="isDark" />
        <Sunny v-else />
      </el-icon>
    </button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="light">
          <el-icon><Sunny /></el-icon>
          <span>浅色模式</span>
          <el-icon v-if="mode === 'light'" class="theme-toggle-check"><Check /></el-icon>
        </el-dropdown-item>
        <el-dropdown-item command="dark">
          <el-icon><Moon /></el-icon>
          <span>夜间模式</span>
          <el-icon v-if="mode === 'dark'" class="theme-toggle-check"><Check /></el-icon>
        </el-dropdown-item>
        <el-dropdown-item command="auto" divided>
          <el-icon><Monitor /></el-icon>
          <span>跟随系统</span>
          <el-icon v-if="mode === 'auto'" class="theme-toggle-check"><Check /></el-icon>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTheme } from '@/composables/useTheme'

/**
 * 主题切换按钮：一个太阳 / 月亮图标，点开可选「浅色 / 夜间 / 跟随系统」。
 * 图标全部在 main.ts 里全局注册（和 Layout 里 Fold / House 等图标一样）。
 */
const { mode, isDark, setMode } = useTheme()

const buttonTitle = computed(() =>
  isDark.value ? '当前是夜间模式，点击切换主题' : '当前是浅色模式，点击切换主题'
)

function onCommand(cmd: string) {
  if (cmd === 'light' || cmd === 'dark' || cmd === 'auto') {
    setMode(cmd)
  }
}
</script>

<style scoped>
.theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--kanna-text-secondary);
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}
.theme-toggle:hover {
  background: var(--kanna-hover);
  color: var(--kanna-heading);
}
.theme-toggle-check {
  margin-left: auto;
  padding-left: 12px;
  color: var(--kanna-accent-text);
}
:deep(.el-dropdown-menu__item) {
  gap: 8px;
}
@media (max-width: 767px) {
  .theme-toggle {
    width: 30px;
    height: 30px;
  }
}
</style>
