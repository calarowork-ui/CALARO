import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// `npm run dev` talks to the API on :8000. If the Docker stack is also running,
// /grafana is forwarded to Caddy on :80 so the Monitoring tab works in dev too.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/grafana': { target: 'http://localhost:80', changeOrigin: false, ws: true },
    },
  },
})
