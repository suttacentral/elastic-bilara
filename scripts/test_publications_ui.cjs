// Run: node scripts/test_publications_ui.cjs /path/to/chrome
// Uses the real Lit/Alpine components with fixture API responses; no live data writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { execFileSync } = require('node:child_process');
const browser = process.argv[2];
assert.ok(browser, 'Pass a Chrome/Chromium executable');
const adminMode = process.argv[3] === 'admin';
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'bilara-publications-'));
const root = path.resolve(__dirname, '../frontend');
const fileUrl = name => pathToFileURL(path.join(root, name)).href;
const fixture = {
    publication_number: 'scpub1', creator_uid: ['alice', 'bob'], creator_name: ['Alice', 'Bob'],
    creator_github_handle: 'alice', translation_title: 'Original',
    translation_lang_iso: 'en', translation_lang_name: 'English', source_url: 'https://example.test/source',
    first_published: '2014', editions_url: 'https://example.test/current', is_published: true,
    _revision: 'revision',
};

const runChecks = async () => {
    const waitFor = async predicate => {
        for (let i = 0; i < 200; i++) {
            if (predicate()) return;
            await new Promise(resolve => setTimeout(resolve, 50));
        }
        throw new Error('Timed out waiting for: ' + predicate.toString());
    };
    const check = (ok, message) => { if (!ok) throw new Error(message); };
    try {
        await waitFor(() => document.querySelector('button[aria-label="Edit publication"]'));
        const root = document.querySelector('[x-data]');
        const state = Alpine.$data(root);
        await waitFor(() => state.authorized && !state.loading);
        await Alpine.nextTick();
        check(window.requests.filter(item => item.url === 'publications/').length === 1, 'List must load exactly once');
        check(state.isAdmin === window.adminMode, 'Incorrect publication permissions');
        check([...document.querySelectorAll('button')].filter(el => /New Publication|Publish to GitHub/.test(el.textContent)).every(el => Boolean(el.getClientRects().length) === window.adminMode), 'Incorrect admin action visibility: ' + JSON.stringify([...document.querySelectorAll('button')].filter(el => /New Publication|Publish to GitHub/.test(el.textContent)).map(el => ({ text: el.textContent.trim(), display: getComputedStyle(el).display, visible: Boolean(el.getClientRects().length) }))));
        document.querySelector('button[aria-label="Edit publication"]').click();
        await waitFor(() => state.view === 'form' && document.querySelector('input[aria-label="Creator name 2"]'));
        check(document.querySelector('#pub-source_url').readOnly === !window.adminMode, 'Source path must be read only');
        check(document.querySelector('#pub-is-published').disabled === !window.adminMode, 'Published flag must be disabled');
        check(document.querySelector('input[aria-label="Creator name 2"]').value === 'Bob', 'Array author input failed');
        check(!('legacyForm' in state) && !('editions' in state), 'Form must only depend on v2');
        check(document.querySelector('input[aria-label="GitHub handle"]').readOnly === !window.adminMode, 'Editing account permissions are incorrect');
        const title = document.querySelector('#pub-translation_title');
        title.value = 'Updated in browser';
        title.dispatchEvent(new Event('input', { bubbles: true }));
        const name = document.querySelector('input[aria-label="Creator name 2"]');
        name.value = 'Bob Updated';
        name.dispatchEvent(new Event('input', { bubbles: true }));
        document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        await waitFor(() => state.view === 'list' && !state.saving);
        const request = window.requests.find(item => item.options?.method === 'PATCH');
        const body = JSON.parse(request.options.body);
        check(body.changes.translation_title === 'Updated in browser', 'Title change missing');
        check(JSON.stringify(body.changes.creator_name) === '["Alice","Bob Updated"]', 'Array type was not preserved');
        check(!Object.hasOwn(body.changes, 'creator_github_handle'), 'Ownership must not be submitted');
        if (window.adminMode) {
            const button = text => [...document.querySelectorAll('button')].find(el => el.textContent.trim() === text);
            const enter = (selector, value, event = 'input') => {
                const input = document.querySelector(selector);
                check(Boolean(input), 'Missing control: ' + selector);
                input.value = value;
                input.dispatchEvent(new Event(event, { bubbles: true }));
            };
            document.querySelector('button[aria-label="Edit publication"]').click();
            await waitFor(() => state.view === 'form' && !state.loadingDetail);
            button('Edit author structure').click();
            await waitFor(() => document.querySelector('#pub-author-mode'));
            check(document.querySelector('#pub-author-mode').value === 'team', 'Existing team mode missing');
            button('Add author').click();
            await Alpine.nextTick();
            enter('#pub-author-uid-2', 'carol');
            enter('#pub-author-name-2', 'Carol');
            document.querySelector('button[aria-label="Remove author 1"]').click();
            await Alpine.nextTick();
            check(document.querySelector('#pub-author-uid-0').value === 'bob', 'Removing a member misaligned author rows');
            check(document.querySelector('#pub-author-name-1').value === 'Carol', 'Added author name missing');
            enter('#pub-author-mode', 'single', 'change');
            await Alpine.nextTick();
            check(state.singleAuthorIndex === '', 'Team conversion must require a retained author');
            const beforeSelection = window.requests.length;
            document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            await Alpine.nextTick();
            check(window.requests.length === beforeSelection && state.formErrors.authors, 'Missing retained author was submitted');
            enter('#pub-retained-author', '0', 'change');
            await Alpine.nextTick();
            document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            await waitFor(() => state.view === 'list' && !state.saving);
            const converted = JSON.parse(window.requests.filter(item => item.options?.method === 'PATCH').at(-1).options.body);
            check(converted.changes.creator_uid === 'bob' && converted.changes.creator_name === 'Bob Updated', 'Retained author was not submitted');
            check(!Object.hasOwn(converted, 'legacy'), 'Legacy author options were submitted');
            check(!Object.hasOwn(converted.changes, 'creator_github_handle') && state.publications[0].creator_github_handle === 'alice', 'Author edits changed editing access');

            [...document.querySelectorAll('button')].find(el => el.textContent.includes('New Publication')).click();
            await waitFor(() => state.view === 'form' && state.editingPub === null);
            check(state.form.publication_number === 'scpub2', 'New publication number was not loaded');
            check(!document.querySelector('#pub-publication_number').readOnly, 'New number must be editable');
            await waitFor(() => document.querySelector('input[aria-label="Creator UID"]'));
            await Alpine.nextTick();
            const beforeBlankUid = window.requests.length;
            document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            await Alpine.nextTick();
            check(window.requests.length === beforeBlankUid, 'Blank creator UID was submitted');
            await waitFor(() => {
                const uidError = document.querySelector('[x-text="formErrors.creator_uid"]');
                return uidError && uidError.getClientRects().length && uidError.textContent.includes('required');
            });
            const uid = document.querySelector('input[aria-label="Creator UID"]');
            uid.value = 'alice';
            uid.dispatchEvent(new Event('input', { bubbles: true }));
            button('Edit author structure').click();
            await Alpine.nextTick();
            enter('#pub-author-mode', 'team', 'change');
            await Alpine.nextTick();
            button('Add author').click();
            await Alpine.nextTick();
            enter('#pub-author-uid-1', 'bob');
            enter('#pub-author-name-1', 'Bob');
            document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            await waitFor(() => state.view === 'list' && !state.saving);
            const creation = window.requests.find(item => item.options?.method === 'POST');
            const created = JSON.parse(creation.options.body);
            check(JSON.stringify(created.creator_uid) === '["alice","bob"]', 'Administrator team creation failed');
            check(!Object.hasOwn(created, 'legacy'), 'New team must only send v2 fields');
            check(['edition_number', 'publisher', 'publication_type'].every(key => !Object.hasOwn(created, key)), 'Conversion options leaked into new metadata');
        }
        check(window.runtimeErrors.length === 0, window.runtimeErrors.join('; '));
        document.getElementById('results').textContent = JSON.stringify({ passed: true, requests: window.requests.length });
    } catch (error) {
        const state = window.Alpine && document.querySelector('[x-data]') ? Alpine.$data(document.querySelector('[x-data]')) : null;
        document.getElementById('results').textContent = JSON.stringify({ passed: false, error: error.message, runtimeErrors: window.runtimeErrors,
            formErrors: state?.formErrors, editingAuthors: state?.editingAuthors, uidError: document.querySelector('[x-text="formErrors.creator_uid"]')?.outerHTML });
    }
};

try {
    const html = `<!DOCTYPE html><html><head><meta charset="UTF-8">
        <link rel="stylesheet" href="${fileUrl('static/css/main.css')}">
        <link rel="stylesheet" href="${fileUrl('static/css/pages/admin.css')}">
        <link rel="stylesheet" href="${fileUrl('static/css/pages/publications.css')}">
        <script>
            window.runtimeErrors = [];
            window.addEventListener('error', event => window.runtimeErrors.push(event.message));
            window.requests = [];
            window.fixture = ${JSON.stringify(fixture)};
            window.adminMode = ${adminMode};
            window.getCurrentUser = async () => ({ role: window.adminMode ? 'administrator' : 'writer', is_active: true, username: 'alice' });
            window.requestWithTokenRetry = async (url, options) => {
                requests.push({url, options});
                if (url === 'publications/next-number/') return { ok: true, status: 200, json: async () => ({ next_number: 'scpub2' }) };
                if (options?.method === 'POST') window.fixture = { ...JSON.parse(options.body), _revision: 'new-revision' };
                if (options?.method === 'PATCH') Object.assign(fixture, JSON.parse(options.body).changes);
                return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(url === 'publications/' ? [fixture] : fixture)) };
            };
        </script>
        <script src="${fileUrl('static/js/publications.js')}"></script>
        <script type="module" src="${fileUrl(adminMode ? 'static/js/elements/admin/sc-bilara-admin-publications.js' : 'static/js/elements/publications/sc-bilara-publications.js')}"></script>
        <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.15.3/dist/cdn.min.js"></script>
    </head><body class="pub-page"><main class="pub-main">${adminMode ? '<sc-bilara-admin-publications></sc-bilara-admin-publications>' : '<sc-bilara-publications></sc-bilara-publications>'}</main>
    <pre id="results">pending</pre><script>window.addEventListener('load', () => (${runChecks.toString()})());</script></body></html>`;
    const fixturePath = path.join(directory, 'fixture.html');
    fs.writeFileSync(fixturePath, html);
    const output = execFileSync(browser, ['--headless', '--no-sandbox', '--disable-gpu', '--no-first-run',
        '--allow-file-access-from-files', '--virtual-time-budget=20000', '--window-size=1280,960',
        `--user-data-dir=${path.join(directory, 'profile')}`, '--dump-dom', pathToFileURL(fixturePath).href],
        { encoding: 'utf8', timeout: 45000, maxBuffer: 4 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
    const match = output.match(/<pre id="results">([^<]+)<\/pre>/);
    assert.ok(match, 'No browser test result');
    assert.notEqual(match[1], 'pending', 'Browser scripts did not finish');
    const result = JSON.parse(match[1].replaceAll('&quot;', '"').replaceAll('&amp;', '&').replaceAll('&gt;', '>').replaceAll('&lt;', '<'));
    assert.equal(result.passed, true, JSON.stringify(result));
    console.log(`PASS: real Lit/Alpine ${adminMode ? 'administrator' : 'writer'} page, array fields, permissions and submission.`);
} finally {
    fs.rmSync(directory, { recursive: true, force: true });
}
