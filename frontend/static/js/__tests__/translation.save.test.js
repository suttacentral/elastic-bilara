const fs = require('fs');
const path = require('path');

const utilsSource = fs.readFileSync(path.resolve(__dirname, '../utils.js'), 'utf8');
const translationSource = fs.readFileSync(path.resolve(__dirname, '../translation.js'), 'utf8');
const page = fs.readFileSync(path.resolve(__dirname, '../../../translation.html'), 'utf8');

const { fetchTranslation, BadgeStatus } = new Function(
    `${utilsSource}\n${translationSource}\nreturn { fetchTranslation, BadgeStatus };`,
)();

// Run the page's actual generic keydown binding before its Enter handler.
const keydown = new Function(
    '$event', 'muid', 'uid', 'isSource',
    `${utilsSource}\n${page.match(/x-on:keydown="([^"]+)"/)[1]}`,
);

describe('segment Enter save', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div><textarea></textarea></div>';
        global.requestWithTokenRetry = jest.fn();
    });

    test.each(['root-pli-ms', 'translation-en-sujato'])(
        '%s sends the changed segment and updates its status', async muid => {
            let respond;
            requestWithTokenRetry.mockReturnValue(new Promise(resolve => { respond = resolve; }));
            const editor = fetchTranslation();
            editor.prefix = 'an1.1-10';
            const uid = 'an1.1:1.1';
            const translation = { muid, canEdit: true, isSource: muid.startsWith('root-') };
            const event = { target: document.getElementsByTagName('textarea')[0], shiftKey: false };
            keydown(event, muid, uid, translation.isSource);

            const saving = editor.handleEnter(event, uid, 'changed', translation, 'original');
            // Observe early rejections even when the request assertion fails first.
            saving.catch(() => {});
            const badge = document.getElementsByTagName('sc-bilara-translation-edit-status')[0];
            expect(requestWithTokenRetry).toHaveBeenCalledWith(
                `projects/${muid}/an1.1-10/`,
                expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ [uid]: 'changed' }) }),
            );
            expect(badge.status).toBe(BadgeStatus.PENDING);
            respond({ ok: true, json: async () => ({ task_id: null }) });
            await saving;
            expect(badge.status).toBe(BadgeStatus.COMMITTED);
        },
    );

    test('a rejected root save displays error status and rejects', async () => {
        requestWithTokenRetry.mockResolvedValue({
            ok: false, status: 500, json: async () => ({ detail: 'Save failed' }),
        });
        const editor = fetchTranslation();
        editor.prefix = 'an1.1-10';
        const muid = 'root-pli-ms';
        const uid = 'an1.1:1.1';
        const event = { target: document.getElementsByTagName('textarea')[0], shiftKey: false };
        keydown(event, muid, uid, true);

        await expect(editor.handleEnter(
            event, uid, 'changed', { muid, canEdit: true, isSource: true }, 'original',
        )).rejects.toThrow('Save failed');
        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
        expect(document.getElementsByTagName('sc-bilara-translation-edit-status')[0].status)
            .toBe(BadgeStatus.ERROR);
    });
});
