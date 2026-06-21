const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage();
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
  page.on('response', response => {
    if (!response.ok()) console.log('HTTP ERROR:', response.status(), response.url());
  });
  await page.goto('https://localhost/', { waitUntil: 'networkidle0' });
  console.log("Landing page loaded.");
  await page.goto('https://localhost/login.html', { waitUntil: 'networkidle0' });
  console.log("Login page loaded.");
  await browser.close();
})();
