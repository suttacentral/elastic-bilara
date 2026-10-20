// Run: node scripts/test_tags_ui.cjs /path/to/chrome
// Actual tag page markup and Alpine, fixture-only requests; no live data writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { execFileSync } = require('node:child_process');
const browser = process.argv[2];
assert.ok(browser, 'Pass a Chrome/Chromium executable');
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'bilara-tags-'));
const root = path.resolve(__dirname, '../frontend');
const fileUrl = name => pathToFileURL(path.join(root, name)).href;
const source = fs.readFileSync(path.join(root, 'tags.html'), 'utf8');
const main = source.match(/<main[\s\S]*?<\/main>/)[0];
const styles = source.match(/<style>[\s\S]*?<\/style>/)[0];

async function runChecks() {
    const check = (condition, message) => { if (!condition) throw new Error(message); };
    const waitFor = async predicate => {
        for (let i = 0; i < 200; i++) {
            if (predicate()) return;
            await new Promise(resolve => setTimeout(resolve, 50));
        }
        throw new Error('Timed out waiting for ' + predicate.toString());
    };
    const input = (selector, value) => {
        const element = document.querySelector(selector);
        element.value = value;
        element.dispatchEvent(new Event('input', { bubbles: true }));
    };
    try {
        await waitFor(() => window.Alpine && document.querySelector('button[title="Edit"]'));
        const state = Alpine.$data(document.querySelector('main'));
        await waitFor(() => state.syncState === 'failed');
        check(requests.filter(r => r.url === 'tags/').length === 1, 'Initialization must load tags once');
        check(document.querySelector('.tags-sync').textContent.includes('failed'), 'Persisted failed state is missing');
        document.querySelector('.tags-sync button').click();
        await waitFor(() => state.syncState === 'synced');
        check(document.querySelector('.tags-sync button').getClientRects().length === 0, 'Retry must hide after success');
        document.querySelector('.btn-add').click();
        await Alpine.nextTick();
        input('#new-tag-name', 'fresh');
        input('#new-tag-definition', 'Created in browser');
        document.querySelector('.form-actions .btn-save').click();
        await waitFor(() => state.tags.length === 2 && !state.saving && state.syncState === 'synced');
        document.querySelector('button[title="Edit"]').click();
        await Alpine.nextTick();
        input('input[x-model="editingTag.tag"]', 'renamed');
        document.querySelector('button[title="Save"]').click();
        await waitFor(() => state.tags[0].tag === 'renamed' && !state.saving);
        document.querySelector('button[title="Delete"]').click();
        await waitFor(() => state.tags.length === 1 && !state.saving && state.syncState === 'synced');
        check(state.tags[0].tag === 'fresh', 'Delete removed the wrong tag');
        check(requests.some(r => r.url === 'tags/old/' && r.options.method === 'PATCH'), 'Rename request missing');
        check(requests.some(r => r.url === 'tags/renamed/' && r.options.method === 'DELETE'), 'Delete request missing');
        check(document.querySelector('[role="status"]').textContent.includes('unpublished'), 'Final sync message missing');
        check(runtimeErrors.length === 0, runtimeErrors.join('; '));
        document.querySelector('#results').textContent = JSON.stringify({ passed: true });
    } catch (error) {
        document.querySelector('#results').textContent = JSON.stringify({ passed: false, error: error.message, runtimeErrors });
    }
}

try {
    const fixture = `<!DOCTYPE html><html><head><meta charset="UTF-8">
        <link rel="stylesheet" href="${fileUrl('static/css/main.css')}">${styles}
        <script>
            window.runtimeErrors = [];
            window.addEventListener('error', e => runtimeErrors.push(e.message));
            window.requests = [];
            window.confirm = () => true;
            window.alert = message => { throw new Error(message); };
            window.definitions = [{ tag: 'old', expansion: '', definition: '' }];
            window.syncState = { status: 'failed', can_retry: true, error: 'Temporary outage' };
            window.requestWithTokenRetry = async (url, options = {}) => {
                requests.push({ url, options });
                let result;
                if (url === 'tags/sync/') result = syncState;
                else if (url === 'tags/sync/retry/') result = syncState = { status: 'synced' };
                else if (!options.method) result = definitions;
                else {
                    const name = decodeURIComponent(url.split('/')[1]);
                    if (options.method === 'POST') { result = JSON.parse(options.body); definitions.push(result); }
                    if (options.method === 'PATCH') { result = JSON.parse(options.body); definitions = definitions.map(t => t.tag === name ? result : t); }
                    if (options.method === 'DELETE') { definitions = definitions.filter(t => t.tag !== name); result = { detail: 'deleted' }; }
                    syncState = { status: 'synced' };
                    result = { ...result, _sync: { status: 'pending' } };
                }
                return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(result)) };
            };
        </script>
        <script src="${fileUrl('static/js/tags.js')}"></script>
        <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.15.3/dist/cdn.min.js"></script>
        </head><body>${main}<pre id="results">pending</pre>
        <script>window.addEventListener('load', () => (${runChecks.toString()})());</script></body></html>`;
    const filename = path.join(directory, 'fixture.html');
    fs.writeFileSync(filename, fixture);
    const output = execFileSync(browser, ['--headless', '--no-sandbox', '--disable-gpu', '--no-first-run',
        '--allow-file-access-from-files', '--virtual-time-budget=20000', '--window-size=1280,960',
        `--user-data-dir=${path.join(directory, 'profile')}`, '--dump-dom', pathToFileURL(filename).href],
        { encoding: 'utf8', timeout: 45000, maxBuffer: 4 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
    const match = output.match(/<pre id="results">([^<]+)<\/pre>/);
    assert.ok(match && match[1] !== 'pending', 'Browser did not finish');
    const result = JSON.parse(match[1].replaceAll('&quot;', '"').replaceAll('&amp;', '&').replaceAll('&gt;', '>').replaceAll('&lt;', '<'));
    assert.equal(result.passed, true, JSON.stringify(result));
    console.log('PASS: real Alpine tag page, create/rename/delete, persisted status and retry.');
} finally {
    fs.rmSync(directory, { recursive: true, force: true });
}
