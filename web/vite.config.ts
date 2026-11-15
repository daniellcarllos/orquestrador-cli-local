import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Em desenvolvimento, a API vem do `python3 -m orchestrator serve` (127.0.0.1:8765).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // changeOrigin + origin: o servidor só aceita Host e Origin do próprio painel
      '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true, headers: { origin: 'http://127.0.0.1:8765' } },
    },
  },
})
