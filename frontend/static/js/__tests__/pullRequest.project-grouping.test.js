const fs = require('fs');
const path = require('path');
const vm = require('vm');
const cases = require('../../../../backend/app/tests/fixtures/publication-project-heads.json');
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../pullRequest.js'), 'utf8'), sandbox);

test.each(cases)('publication group for %s is %s', (file, expected) => {
    expect(sandbox.getPublicationProjectHead(file)).toBe(expected);
});

test('Sutta publishing keeps collections and translation projects separate', () => {
    const paths = cases.slice(0, 12).map(([file]) => file);
    const groups = sandbox.groupPublicationPathsByProject(paths);
    expect(groups).toHaveLength(7);
    expect(groups[0]).toEqual(paths.slice(0, 6));
    expect(groups.flat()).toEqual(paths);
});
