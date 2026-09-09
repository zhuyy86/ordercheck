// Run with PLAYWRIGHT_MODULE pointing to an installed playwright package if needed.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1150 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    await page.goto('http://127.0.0.1:8501', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: '校验并生成报告', exact: true }).click();
    await page.getByText('通过金额合计', { exact: true }).waitFor();
    const metric = page.locator('[data-testid="stMetricValue"]');
    assert.deepStrictEqual((await metric.allTextContents()).map(s => s.trim()), ['12', '5', '7', '140.30']);
    fs.mkdirSync('docs', { recursive: true });
    await page.screenshot({ path: 'docs/demo-overview.png', fullPage: true, animations: 'disabled' });
    await page.getByRole('tab', { name: '待复核记录', exact: true }).click();
    await page.getByRole('button', { name: '下载 Excel 报告', exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: 'docs/demo-review.png', fullPage: true, animations: 'disabled' });
    const downloadEvent = page.waitForEvent('download');
    await page.getByRole('button', { name: '下载完整报告包 ZIP', exact: true }).click();
    const download = await downloadEvent;
    fs.mkdirSync('outputs', { recursive: true });
    await download.saveAs(path.resolve('outputs/browser-report.zip'));
    assert(fs.statSync('outputs/browser-report.zip').size > 1000);
    await page.getByText('上传自己的文件', { exact: true }).click();
    await page.locator('input[type=file]').setInputFiles(['examples/north.csv','examples/south.csv']);
    await page.getByRole('button', { name: '校验并生成报告', exact: true }).click();
    await page.waitForFunction(() => [...document.querySelectorAll('[data-testid="stMetricValue"]')]
      .map(e => e.textContent.trim()).join('|') === '8|2|6|10.30');
    assert.strictEqual(await page.locator('[data-testid="stException"]').count(), 0);
    assert.deepStrictEqual(errors, []);
    console.log('PASS: demo metrics, review tab, ZIP download, real file upload, no page errors.');
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exit(1); });
