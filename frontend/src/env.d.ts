/// <reference types="vite/client" />

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<{}, {}, any>;
  export default component;
}

// @ant-design/icons-vue 7.x 不带类型声明文件（package.json 无 typings 字段、
// lib/es 无 .d.ts），此处声明为宽松模块以通过 vue-tsc 类型检查。
// 图标组件运行时由 ant-design-vue 正常提供，声明不影响实际行为。
declare module "@ant-design/icons-vue" {
  import type { DefineComponent } from "vue";
  const icons: Record<string, DefineComponent<any, any, any>>;
  export default icons;
  export const HomeOutlined: DefineComponent<any, any, any>;
  export const SoundOutlined: DefineComponent<any, any, any>;
  export const FileTextOutlined: DefineComponent<any, any, any>;
  export const MenuFoldOutlined: DefineComponent<any, any, any>;
  export const MenuUnfoldOutlined: DefineComponent<any, any, any>;
  export const LogoutOutlined: DefineComponent<any, any, any>;
  export const UserOutlined: DefineComponent<any, any, any>;
  export const BookOutlined: DefineComponent<any, any, any>;
  export const PlusOutlined: DefineComponent<any, any, any>;
  export const DownloadOutlined: DefineComponent<any, any, any>;
  export const UploadOutlined: DefineComponent<any, any, any>;
  export const PlayCircleOutlined: DefineComponent<any, any, any>;
  export const DeleteOutlined: DefineComponent<any, any, any>;
  export const EditOutlined: DefineComponent<any, any, any>;
  export const CheckOutlined: DefineComponent<any, any, any>;
  export const CloseOutlined: DefineComponent<any, any, any>;
  export const InfoCircleOutlined: DefineComponent<any, any, any>;
  export const LoadingOutlined: DefineComponent<any, any, any>;
}
