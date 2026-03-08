import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '');

    return {
        base: env.VITE_PROJECT_PATH || '/',
        plugins: [react()],
        server: {
            host: 'localhost',
            port: 3000
        },
        build: {
            outDir: 'dist',
            rollupOptions: {
                input: 'index.html'
            }

        }
    };
});