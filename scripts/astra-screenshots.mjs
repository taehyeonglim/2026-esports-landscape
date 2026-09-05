import { chromium } from '@playwright/test';
import { spawn } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
const output = process.argv[2];
await mkdir(output, { recursive: true });
const server = spawn('python3', ['-m', 'http.server', '8769', '--bind', '127.0.0.1', '--directory', 'dist'], { stdio: 'ignore' });
let browser;
try {
  for (let i = 0; i < 50; i++) {
    try { if ((await fetch('http://127.0.0.1:8769')).ok) break; } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  browser = await chromium.launch();
  for (const [name, width, height, path] of [['desktop',1440,1000,'/'],['mobile',390,844,'/'],['research',1440,1000,'/research/']]) {
    const page = await browser.newPage({ viewport: { width, height } });
    await page.goto(`http://127.0.0.1:8769${path}`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: `${output}/${name}.png`, fullPage: true });
    await page.close();
  }
} finally { await browser?.close(); server.kill(); }
