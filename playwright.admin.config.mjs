import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./tests',testMatch:'admin.e2e.mjs',workers:1,timeout:60000,use:{browserName:'chromium',viewport:{width:1280,height:900}},reporter:'list'});
