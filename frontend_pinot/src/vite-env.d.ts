/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DASHBOARD_BACKEND?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}