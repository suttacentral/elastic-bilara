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
            const translation = { muid, canEdit: true, isSource: muid.startsWith('root-'), data: {[uid]: 'original'} };
            editor.translations = [translation];
            editor.setValue(translation, uid, 'changed');
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
        const translation = { muid, canEdit: true, isSource: true, data: {[uid]: 'original'} };
        editor.translations = [translation];
        editor.setValue(translation, uid, 'changed');

        await expect(editor.handleEnter(
            event, uid, 'changed', translation, 'original',
        )).rejects.toThrow('Save failed');
        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
        expect(document.getElementsByTagName('sc-bilara-translation-edit-status')[0].status)
            .toBe(BadgeStatus.ERROR);
    });

    describe('saved-value tracking across focus changes', () => {
        let editor, translation, event;
        const muid = 'root-pli-ms';
        const uid = 'dn1:1.1';
        const key = muid + ':' + uid;
        const savedResponse = {ok: true, json: async () => ({materialized: true})};
        const pressEnter = () => editor.handleEnter(event, uid, translation.data[uid], translation, translation.data[uid]);
        const startStructure = operation => editor.startStructureDraft(operation, uid, document.getElementsByTagName('span')[0]);

        beforeEach(() => {
            jest.useFakeTimers();
            document.body.innerHTML += '<span></span>';
            editor = fetchTranslation();
            editor.prefix = 'dn1';
            editor.sourceMuid = muid;
            translation = {muid, canEdit: true, isSource: true, data: {[uid]: 'A'}};
            editor.translations = [translation];
            event = {target: document.getElementsByTagName('textarea')[0], shiftKey: false};
            keydown(event, muid, uid, true);
            requestWithTokenRetry.mockResolvedValue(savedResponse);
        });
        afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });

        test.each(['split', 'merge'])('refocused Enter saves and unblocks %s', async operation => {
            editor.setValue(translation, uid, 'B');
            expect(await startStructure(operation)).toBe(false);
            expect(requestWithTokenRetry).not.toHaveBeenCalled();
            await pressEnter(); // focus has reset originalValue to B
            expect(JSON.parse(requestWithTokenRetry.mock.calls[0][1].body)).toEqual({[uid]: 'B'});
            expect(editor.dirtySegments).toEqual({});
            requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => ({
                operation, uid, manual_projects: [], projects: [{muid, data: {[uid]: 'B'}}],
            })});
            expect(await startStructure(operation)).toBe(true);
        });

        test('an empty saved value still requires saving after refocus', async () => {
            translation.data[uid] = '';
            editor.setValue(translation, uid, 'B');
            await pressEnter();
            expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
            expect(editor.dirtySegments).toEqual({});
        });

        test('failure preserves the pending edit and Enter can retry after refocus', async () => {
            editor.setValue(translation, uid, 'B');
            requestWithTokenRetry.mockResolvedValueOnce({ok: false, status: 500, json: async () => ({detail: 'Save failed'})});
            await expect(pressEnter()).rejects.toThrow('Save failed');
            expect(editor.dirtySegments[key]).toBe('A');
            expect(await startStructure('split')).toBe(false);
            expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
            await pressEnter();
            expect(requestWithTokenRetry).toHaveBeenCalledTimes(2);
            expect(editor.dirtySegments).toEqual({});
        });

        test('reverting to saved content needs no save even when the focus value differs', async () => {
            editor.setValue(translation, uid, 'B');
            editor.setValue(translation, uid, 'A');
            await editor.handleEnter(event, uid, 'A', translation, 'B');
            expect(requestWithTokenRetry).not.toHaveBeenCalled();
            expect(editor.dirtySegments).toEqual({});
        });

        test.each(['C', 'A'])('editing to %s while saving preserves an unsaved change after acknowledgement', async laterValue => {
            let respond;
            requestWithTokenRetry.mockReturnValueOnce(new Promise(resolve => { respond = resolve; }));
            editor.setValue(translation, uid, 'B');
            const saving = pressEnter();
            editor.setValue(translation, uid, laterValue);
            respond(savedResponse);
            await saving;
            expect(editor.dirtySegments[key]).toBe('B');
            expect(await startStructure('merge')).toBe(false);
            await pressEnter();
            expect(JSON.parse(requestWithTokenRetry.mock.calls[1][1].body)).toEqual({[uid]: laterValue});
            expect(editor.dirtySegments).toEqual({});
        });

        test('remarks continue to use their separate save handler and focus comparison', async () => {
            translation.muid = editor.makeRemarkKey(1);
            editor.setValue(translation, uid, 'B');
            editor.updateRemarkHandler = jest.fn().mockResolvedValue();
            await editor.handleEnter(event, uid, 'B', translation, 'A');
            expect(editor.updateRemarkHandler).toHaveBeenCalledWith(uid, 'B');
            await pressEnter();
            expect(editor.updateRemarkHandler).toHaveBeenCalledTimes(1);
            expect(editor.dirtySegments).toEqual({});
            expect(requestWithTokenRetry).not.toHaveBeenCalled();
        });
    });
});
