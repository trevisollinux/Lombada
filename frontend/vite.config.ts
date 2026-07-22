import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// VITE_BASE permite gerar um build estático de demonstração ('./') sem
// afetar o build de produção, que continua servido em /app-v2/.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const base = env.VITE_BASE || '/app-v2/'

  return {
    base,
    plugins: [react()],
    build: {
      outDir: 'dist',
      emptyOutDir: true,
      sourcemap: true,
    },
    server: {
      port: 5173,
      proxy: {
        '/api': 'http://localhost:8000',
        '/auth': 'http://localhost:8000',
      },
    },
  }
})
