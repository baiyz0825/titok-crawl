import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: Number(process.env.PORT) || 15173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:18000',
        changeOrigin: true,
      },
      '/media': {
        target: process.env.VITE_API_URL || 'http://localhost:18000',
        changeOrigin: true,
      },
    },
  },
})
