// API 地址解析策略：
// - 显式配置 VITE_API_BASE 时优先使用（例如前后端分离部署）；
// - 开发（vite dev / vitest）默认指向 http://<hostname>:8000，后端单独跑在 8000；
// - 生产构建（Docker 单容器内前后端同源）留空，走相对路径，任意宿主端口均可。
const ENV_API_BASE = import.meta.env.VITE_API_BASE

export const API_ORIGIN = ENV_API_BASE ?? (
  import.meta.env.DEV ? `http://${window.location.hostname}:8000` : ''
)

export const API_BASE = `${API_ORIGIN}/api`

export function toImageUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//i.test(path)) return path
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${API_ORIGIN}${normalized}`
}