// 灵犀语伴设计系统 —— 集中式设计令牌
// 单一事实来源：颜色、圆角、字体在此统一维护

export const colors = {
  primary: "#FF7043", // 主色（橙）
  primaryHover: "#F4511E", // 主色悬停（深橙）
  accent: "#FFB74D", // 辅助色（浅橙）
  background: "#F5F5F5", // 页面背景
  surface: "#FFF3E0", // 卡片/次要背景（米色）
  success: "#81C784", // 成功（绿）
  textPrimary: "#424242", // 主要文字
  textSecondary: "#757575", // 次要文字
};

// Ant Design Vue 4 主题配置，注入 <a-config-provider>
export const themeConfig = {
  token: {
    colorPrimary: colors.primary,
    colorInfo: colors.primary,
    colorSuccess: colors.success,
    colorTextBase: colors.textPrimary,
    colorTextSecondary: colors.textSecondary,
    colorBgLayout: colors.background,
    borderRadius: 8,
    borderRadiusLG: 12,
    fontFamily:
      '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif',
  },
  components: {
    Button: {
      colorPrimaryHover: colors.primaryHover,
      // 仅作用于 size="large" 的主操作按钮（登录、合成等），默认按钮保持 32px
      controlHeightLG: 48,
    },
    Card: {
      borderRadiusLG: 12,
    },
  },
};
