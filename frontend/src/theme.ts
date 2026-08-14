// 灵犀语伴设计系统 —— 集中式设计令牌
// 单一事实来源：颜色、渐变、阴影、圆角、字体在此统一维护

export const colors = {
  // 主色系（暖橙，避免单一与过于鲜艳的纯橙）
  primary: "#FF6B35", // 主色（品牌橙）
  primaryHover: "#E85D2A", // 悬停（深橙）
  primaryActive: "#C94F1F", // 按下（更深橙）
  accent: "#FFB26B", // 辅助浅橙（点缀）
  accentSoft: "#FFE8D9", // 浅橙底（图标芯片、选中态背景）

  // 中性暖色（替代纯灰，营造温暖氛围）
  background: "#FAF8F6", // 页面暖白背景
  surface: "#FFF7F2", // 卡片米色表面
  border: "#F0E9E3", // 柔和边框
  borderStrong: "#E3D8CF", // 强调边框

  // 语义色
  success: "#4CAF7D", // 成功（柔和绿）
  warning: "#FFB26B", // 警告（浅橙）
  error: "#D9503B", // 错误（暖红）

  // 文字（满足 WCAG 4.5:1 对比度）
  textPrimary: "#2B2724", // 主要文字（暖黑）
  textSecondary: "#6B6460", // 次要文字
  textMuted: "#9A928C", // 弱化文字（辅助说明）
};

// 品牌渐变令牌
export const gradients = {
  brand: "linear-gradient(135deg, #FF8A4C 0%, #FF6B35 50%, #E85D2A 100%)", // 品牌渐变（封面条、Logo 字标）
  hero: "linear-gradient(135deg, #FF9A5A 0%, #FF6B35 45%, #E85D2A 100%)", // Hero 三段渐变
  chip: "linear-gradient(135deg, #FFE8D9 0%, #FFD6BC 100%)", // 图标芯片渐变
};

// 品牌色阴影令牌（替代生硬黑阴影）
export const shadows = {
  card: "0 2px 8px rgba(255, 107, 53, 0.08)", // 卡片常态
  cardHover: "0 8px 24px rgba(255, 107, 53, 0.16)", // 卡片悬停
  popup: "0 4px 16px rgba(201, 79, 31, 0.14)", // 弹层/对话框
};

// Ant Design Vue 4 主题配置，注入 <a-config-provider>
export const themeConfig = {
  token: {
    colorPrimary: colors.primary,
    colorInfo: colors.primary,
    colorSuccess: colors.success,
    colorWarning: colors.warning,
    colorError: colors.error,
    colorTextBase: colors.textPrimary,
    colorTextSecondary: colors.textSecondary,
    colorBgLayout: colors.background,
    colorBgContainer: colors.surface,
    colorBorder: colors.border,
    colorBorderSecondary: colors.border,
    borderRadius: 8,
    borderRadiusLG: 12,
    fontFamily:
      '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif',
  },
  components: {
    Button: {
      colorPrimaryHover: colors.primaryHover,
      colorPrimaryActive: colors.primaryActive,
      // 仅作用于 size="large" 的主操作按钮（登录、合成等），默认按钮保持 32px
      controlHeightLG: 48,
    },
    Card: {
      borderRadiusLG: 12,
    },
    Menu: {
      // 圆角菜单项 + 品牌软色选中态
      itemBorderRadius: 8,
      itemSelectedBg: colors.accentSoft,
      itemSelectedColor: colors.primaryActive,
      itemHoverBg: "#FFF1E6",
      itemColor: colors.textPrimary,
      itemHeight: 44,
    },
    Layout: {
      siderBg: colors.surface, // 侧边栏米色表面
      headerBg: "rgba(255, 255, 255, 0.75)", // 毛玻璃顶栏底色
    },
    Select: {
      optionSelectedBg: colors.accentSoft,
    },
  },
};
