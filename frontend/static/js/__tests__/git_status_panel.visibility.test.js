const fs = require('fs');
const path = require('path');

const panelSource = fs.readFileSync(path.resolve(__dirname, '../git_status_panel.js'), 'utf8');
eval(panelSource);

describe('git status administrator visibility', () => {
    let panel;

    beforeEach(() => {
        panel = gitStatusPanel();
        panel.isAdmin = true;
        panel.username = 'ann';
        panel.files = [
            { path: 'translation/en/ann/sutta/mn/mn1.json', status: 'modified' },
            { path: 'comment/en/joanna/sutta/mn/mn1.json', status: 'modified' },
            { path: 'translation/en/bodhi/sutta/mn/mn1.json', status: 'modified' }
        ];
        panel.fetchStatus = jest.fn().mockResolvedValue();
    });

    test('administrators see only their own files by default', () => {
        expect(panel.showOtherUsersChanges).toBe(false);
        expect(panel.filteredFiles.map(file => file.path)).toEqual([
            'translation/en/ann/sutta/mn/mn1.json'
        ]);
    });

    test('administrator can include other users files', async () => {
        await panel.setShowOtherUsersChanges(true);

        expect(panel.filteredFiles).toHaveLength(3);
        expect(panel.fetchStatus).toHaveBeenCalledTimes(1);
    });

    test('ownership uses complete path segments', () => {
        expect(panel.isFileOwnedByCurrentUser(panel.files[0])).toBe(true);
        expect(panel.isFileOwnedByCurrentUser(panel.files[1])).toBe(false);
    });

    test('hiding other users clears a hidden selected file and resets pagination', async () => {
        panel.showOtherUsersChanges = true;
        panel.selectedFile = panel.files[2].path;
        panel.selectedFileData = panel.files[2];
        panel.diffContent = 'diff';
        panel.parsedDiffLines = [{ text: 'diff', type: 'context' }];
        panel.currentPage = 2;

        await panel.setShowOtherUsersChanges(false);

        expect(panel.selectedFile).toBeNull();
        expect(panel.selectedFileData).toBeNull();
        expect(panel.diffContent).toBe('');
        expect(panel.parsedDiffLines).toEqual([]);
        expect(panel.currentPage).toBe(1);
    });

    test('fetches all-user scope only when the administrator toggle is enabled', async () => {
        const requestPanel = gitStatusPanel();
        requestPanel.isAdmin = true;
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: jest.fn().mockResolvedValue({ files: [] })
        });

        await requestPanel.fetchStatus();
        expect(global.fetch).toHaveBeenLastCalledWith(
            '/api/v1/git/status',
            expect.any(Object)
        );

        requestPanel.showOtherUsersChanges = true;
        await requestPanel.fetchStatus();
        expect(global.fetch).toHaveBeenLastCalledWith(
            '/api/v1/git/status?include_other_users=true',
            expect.any(Object)
        );
    });
});
