import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'

// Development: vite dev server on :5173 proxies /api + /health + /metrics to FastAPI on :8000.
//   Dev server serves assets at root ('/') by default — no base prefix needed.
// Production:  FastAPI mounts frontend/dist/ at /static, so asset URLs must be /static/assets/*.
//   The SPA entrypoint /ui serves index.html which references /static/assets/*.js.
// Vite sets NODE_ENV=development for `vite` (serve), NODE_ENV=production for `vite build`.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/' : '/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/metrics': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/docs': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/openapi.json': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
}))
