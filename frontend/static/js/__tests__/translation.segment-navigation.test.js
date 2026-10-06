const fs = require('fs');
const path = require('path');

const createTranslation = new Function(
    fs.readFileSync(path.join(__dirname, '../translation.js'), 'utf8')
    + '\nreturn fetchTranslation();',
);
const page = new DOMParser().parseFromString(
    fs.readFileSync(path.join(__dirname, '../../../translation.html'), 'utf8'),
    'text/html',
);
const resultsTemplate = [...page.querySelectorAll('template')]
    .find(element => element.getAttribute('x-for') === 'entry in resultEntries');
const linkExpression = resultsTemplate.content.querySelector('a').getAttribute(':href');
const resultHref = new Function('entry', `return (${linkExpression});`);
const gridTemplate = page.querySelector('template[x-if="!loading && !loadError"]');
const gridInit = gridTemplate.content.querySelector('.translation-grid__body').getAttribute('x-init');

function mountGrid(uids) {
    const grid = document.createElement('div');
    for (const uid of uids) {
        const row = document.createElement('div');
        row.className = 'translation-row';
        row.dataset.uid = uid;
        row.scrollIntoView = jest.fn();
        grid.append(row);
    }
    document.body.append(grid);
    return grid;
}

beforeEach(() => {
    document.body.innerHTML = '';
    window.history.replaceState({}, '',
        '/translation.html?prefix=mn2&source=root-pli-ms&muid=translation-en-sujato');
});

test('search links preserve the exact segment and selected projects', () => {
    const urls = ['mn1:1.1', 'mn1:20.3'].map(uid => {
        const url = new URL(resultHref({ uid }), window.location.href);
        expect(url.searchParams.get('uid')).toBe(uid);
        expect(url.searchParams.get('prefix')).toBe('mn1');
        expect(url.searchParams.get('source')).toBe('root-pli-ms');
        expect(url.searchParams.get('muid')).toBe('translation-en-sujato');
        return url.href;
    });
    expect(urls[0]).not.toBe(urls[1]);
});

test('a search link scrolls to its segment after the grid rows render', () => {
    window.history.replaceState({}, '', resultHref({ uid: 'mn1:20.3' }));
    const context = createTranslation();
    const grid = mountGrid([]);
    const callbacks = [];
    new Function('scope', `with (scope) { ${gridInit}; }`)({
        $el: grid,
        $nextTick: callback => callbacks.push(callback),
        scrollToUrlSegment: context.scrollToUrlSegment.bind(context),
    });
    // Alpine's x-for creates the rows before nextTick callbacks execute.
    const rendered = mountGrid(['mn1:1.1', 'mn1:20.3', 'mn1:20.30']);
    grid.append(...rendered.children);
    const [first, target, similar] = grid.children;
    expect(target.scrollIntoView).not.toHaveBeenCalled();
    expect(callbacks).toHaveLength(1);
    callbacks.forEach(callback => callback());
    expect(target.scrollIntoView).toHaveBeenCalledWith({ block: 'center', inline: 'nearest' });
    expect(first.scrollIntoView).not.toHaveBeenCalled();
    expect(similar.scrollIntoView).not.toHaveBeenCalled();
});

test.each(['', '&uid=', '&uid=mn1%3A99.9'])('leaves the scroll position alone without a matching segment: %s', suffix => {
    window.history.replaceState({}, '', `${window.location.href}${suffix}`);
    const grid = mountGrid(['mn1:1.1', 'mn1:20.3']);
    createTranslation().scrollToUrlSegment(grid);
    for (const row of grid.children) expect(row.scrollIntoView).not.toHaveBeenCalled();
});

test('preserves the segment when the document prefix resolves to a merged range', () => {
    window.history.replaceState({}, '', resultHref({ uid: 'an1.21:1.1' }));
    const resolvedUrl = new URL(window.location.href);
    resolvedUrl.searchParams.set('prefix', 'an1.21-30');
    window.history.replaceState({}, '', resolvedUrl);
    const grid = mountGrid(['an1.20:1.1', 'an1.21:1.1']);
    createTranslation().scrollToUrlSegment(grid);
    expect(grid.children[0].scrollIntoView).not.toHaveBeenCalled();
    expect(grid.children[1].scrollIntoView).toHaveBeenCalledTimes(1);
});
