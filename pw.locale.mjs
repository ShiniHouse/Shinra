import base from './playwright.config.mjs';
export default { ...base, webServer: undefined, use: { ...base.use, baseURL: 'http://127.0.0.1:8961' }, projects: [{ name: 'chrome', use: { channel: 'chrome', viewport: { width: 1400, height: 900 } } }] };
