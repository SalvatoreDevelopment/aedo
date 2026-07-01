import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In sviluppo la dashboard (porta 5173) inoltra /api al server FastAPI (porta 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    // Ascolta su IPv4 esplicito: il Banco del Master apre http://127.0.0.1:5173,
    // e su Windows "localhost" può risolvere a IPv6 (::1) → connessione rifiutata.
    host: '127.0.0.1',
    port: 5173,
    // Se la porta è occupata, fallisci con un errore chiaro invece di spostarti
    // in silenzio su 5174/5175 (dove il link del Banco non punterebbe più).
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
