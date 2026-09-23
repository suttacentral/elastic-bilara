const fs = require('fs');
const path = require('path');

eval(fs.readFileSync(path.resolve(__dirname, '../translation.js'), 'utf8'));
const page = new DOMParser().parseFromString(
    fs.readFileSync(path.resolve(__dirname, '../../../translation.html'), 'utf8'),
    'text/html',
);
const gridExpression = page.querySelector('template[x-if="!loading && !loadError"]')
    .content.querySelector('.translation-grid').getAttribute('x-data');

const SOURCE = 'root-pli-ms';
const TARGET = 'translation-en-user';
const RELATED = 'translation-de-user';
const NEW = 'translation-fr-user';
const projectKey = `bilara:col-order:v2:${TARGET}`;
const legacyKey = prefix => `bilara:col-order:${prefix}:${SOURCE}:${TARGET}`;
const ids = context => context.translations.map(item => item.muid);

async function openSutta({ prefix = 'mn1', target = TARGET, source = SOURCE, projects = [RELATED, NEW] } = {}) {
    window.history.replaceState({}, '', `/translation.html?${new URLSearchParams({ prefix, muid: target, source })}`);
    const context = fetchTranslation();
    // Stub data boundaries; initialization, selection and ordering use production methods.
    context.loadCurrentUserForTranslation = jest.fn().mockResolvedValue({});
    context.loadHyphenatedPrefixRanges = jest.fn().mockResolvedValue();
    context.fetchRelatedProjects = jest.fn().mockResolvedValue([source, target, ...projects]);
    context.fetchRemarkUsers = jest.fn().mockResolvedValue([]);
    context.loadAvailableTags = jest.fn().mockResolvedValue();
    context.fetchData = jest.fn().mockResolvedValue({ data: {}, can_edit: false });
    await context.initialize();
    return context;
}

function gridFor(context) {
    const grid = new Function('translations', `return (${gridExpression});`)(context.translations);
    Object.setPrototypeOf(grid, context);
    grid.$el = document.createElement('div');
    grid.$nextTick = callback => callback();
    grid.initWidths();
    return grid;
}

describe('project-wide translation column order', () => {
    beforeEach(() => {
        localStorage.clear();
        localStorage.setItem(`relatedProjects_${TARGET}`, JSON.stringify([RELATED]));
    });

    afterEach(() => jest.restoreAllMocks());

    test.each(['drag', 'keyboard'])('%s reorder carries to an unseen sutta and survives reopening', async input => {
        const first = await openSutta();
        const grid = gridFor(first);
        if (input === 'drag') {
            const header = document.createElement('div');
            header.className = 'translation-grid__header-cell';
            grid.onHeaderDragStart(2, { target: header, dataTransfer: { setData: jest.fn() } });
            grid.onHeaderDrop(0, { preventDefault: jest.fn() });
        } else {
            grid.onHeaderKeydown(2, { altKey: true, key: 'ArrowLeft', preventDefault: jest.fn() });
            grid.onHeaderKeydown(1, { altKey: true, key: 'ArrowLeft', preventDefault: jest.fn() });
        }

        expect(ids(first)).toEqual([RELATED, SOURCE, TARGET]);
        expect(JSON.parse(localStorage.getItem(projectKey))).toEqual([RELATED, SOURCE, TARGET]);
        expect(localStorage.getItem(legacyKey('mn1'))).toBeNull();
        expect(ids(await openSutta({ prefix: 'mn2' }))).toEqual([RELATED, SOURCE, TARGET]);
        expect(ids(await openSutta())).toEqual([RELATED, SOURCE, TARGET]);
    });

    test('different target projects have independent preferences', async () => {
        const first = await openSutta();
        gridFor(first).moveColumn(2, 0);
        const otherTarget = 'translation-es-user';
        localStorage.setItem(`relatedProjects_${otherTarget}`, JSON.stringify([RELATED]));
        const other = await openSutta({ target: otherTarget });
        expect(ids(other)).toEqual([SOURCE, otherTarget, RELATED]);
        gridFor(other).moveColumn(1, 0);
        expect(ids(await openSutta())).toEqual([RELATED, SOURCE, TARGET]);
    });

    test('source-only pages share by source and remain independent of target projects', async () => {
        localStorage.setItem('relatedProjects_', JSON.stringify([RELATED]));
        const first = await openSutta({ target: '' });
        gridFor(first).moveColumn(1, 0);
        expect(ids(await openSutta({ target: '', prefix: 'mn2' }))).toEqual([RELATED, SOURCE]);
        expect(ids(await openSutta({ target: '', source: 'root-lzh-taisho' })))
            .toEqual(['root-lzh-taisho', RELATED]);
        expect(localStorage.getItem(projectKey)).toBeNull();
    });

    test('migrates the current sutta once and ignores conflicting legacy orders afterward', async () => {
        localStorage.setItem(legacyKey('mn1'), JSON.stringify([RELATED, SOURCE, TARGET]));
        localStorage.setItem(legacyKey('mn2'), JSON.stringify([TARGET, SOURCE, RELATED]));
        expect(ids(await openSutta())).toEqual([RELATED, SOURCE, TARGET]);
        expect(JSON.parse(localStorage.getItem(projectKey))).toEqual([RELATED, SOURCE, TARGET]);
        expect(ids(await openSutta({ prefix: 'mn2' }))).toEqual([RELATED, SOURCE, TARGET]);
        expect(localStorage.getItem(legacyKey('mn1'))).not.toBeNull();
    });

    test('an existing project preference takes precedence over the current legacy record', async () => {
        localStorage.setItem(projectKey, JSON.stringify([TARGET, RELATED, SOURCE]));
        localStorage.setItem(legacyKey('mn1'), JSON.stringify([RELATED, SOURCE, TARGET]));
        expect(ids(await openSutta())).toEqual([TARGET, RELATED, SOURCE]);
    });

    test('keeps unavailable columns in their slots when visible columns are reordered', async () => {
        localStorage.setItem(projectKey, JSON.stringify([SOURCE, RELATED, TARGET, NEW]));
        localStorage.setItem(`relatedProjects_${TARGET}`, JSON.stringify([RELATED, NEW]));
        const partial = await openSutta({ projects: [NEW] });
        expect(ids(partial)).toEqual([SOURCE, TARGET, NEW]);
        gridFor(partial).moveColumn(2, 0);
        expect(JSON.parse(localStorage.getItem(projectKey))).toEqual([NEW, RELATED, SOURCE, TARGET]);
        expect(ids(await openSutta({ prefix: 'mn2' }))).toEqual([NEW, RELATED, SOURCE, TARGET]);
    });

    test('restores a reselected column to its saved position and appends new selections', async () => {
        localStorage.setItem(projectKey, JSON.stringify([RELATED, SOURCE, TARGET]));
        const context = await openSutta();
        await context.toggleRelatedProject(RELATED);
        expect(ids(context)).toEqual([SOURCE, TARGET]);
        expect(JSON.parse(localStorage.getItem(projectKey))).toEqual([RELATED, SOURCE, TARGET]);
        await context.toggleRelatedProject(RELATED);
        expect(ids(context)).toEqual([RELATED, SOURCE, TARGET]);
        await context.toggleRelatedProject(NEW);
        expect(ids(context)).toEqual([RELATED, SOURCE, TARGET, NEW]);
        expect(ids(await openSutta({ prefix: 'mn2' }))).toEqual([RELATED, SOURCE, TARGET, NEW]);
    });

    test('merges newly encountered columns with saved slots when reordered', async () => {
        localStorage.setItem(projectKey, JSON.stringify([SOURCE, RELATED, TARGET]));
        localStorage.setItem(`relatedProjects_${TARGET}`, JSON.stringify([RELATED, NEW]));
        const context = await openSutta({ projects: [NEW] });
        expect(ids(context)).toEqual([SOURCE, TARGET, NEW]);
        gridFor(context).moveColumn(2, 0);
        expect(JSON.parse(localStorage.getItem(projectKey))).toEqual([NEW, RELATED, SOURCE, TARGET]);
    });

    test.each(['broken json', '{}', '[1, 2]'])('ignores invalid column preference %s', async stored => {
        localStorage.setItem(projectKey, stored);
        const context = await openSutta();
        expect(ids(context)).toEqual([SOURCE, TARGET, RELATED]);
        gridFor(context).moveColumn(2, 0);
        expect(JSON.parse(localStorage.getItem(projectKey))).toEqual([RELATED, SOURCE, TARGET]);
    });

    test('does not duplicate translations when a saved order has duplicate entries', async () => {
        localStorage.setItem(projectKey, JSON.stringify([RELATED, RELATED, SOURCE, TARGET]));
        expect(ids(await openSutta())).toEqual([RELATED, SOURCE, TARGET]);
    });

    test('keeps the reordered UI and warns once if saving fails', async () => {
        const context = await openSutta();
        const toast = { show: jest.fn() };
        jest.spyOn(document, 'querySelector').mockReturnValue(toast);
        jest.spyOn(console, 'warn').mockImplementation(() => {});
        jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new DOMException('Storage full', 'QuotaExceededError');
        });
        const grid = gridFor(context);
        grid.moveColumn(2, 0);
        grid.moveColumn(2, 1);
        expect(ids(context)).toEqual([RELATED, TARGET, SOURCE]);
        expect(toast.show).toHaveBeenCalledTimes(1);
        expect(toast.show).toHaveBeenCalledWith('Column order could not be saved in this browser.', 'warning');
    });
});
