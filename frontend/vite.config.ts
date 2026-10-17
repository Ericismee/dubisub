import { defineConfig } from 'vite';
export default defineConfig({server:{proxy:{'/api':'http://127.0.0.1:6060','/health':'http://127.0.0.1:6060'}}});
