const fs = require('fs');
eval(fs.readFileSync(require('path').join(__dirname, '../translation.js'), 'utf8'));

describe('structure drafts use the production translation controller', () => {
    let context;
    const root = 'root-pli-ms';
    const html = 'html-pli-ms';
    const plan = () => ({ operation: 'split', uid: 'dn1:1.1', revision: 'r1',
        structure_revision: 's1', splitter_uid: 'dn1:1.2', manual_projects: [html],
        projects: [
            {muid: root, path: 'root/pli/ms/dn1_root-pli-ms.json', before: {'dn1:1.1': 'A'}, data: {'dn1:1.1': 'A', 'dn1:1.2': ''}},
            {muid: html, path: 'html/pli/ms/dn1_html-pli-ms.json', before: {'dn1:1.1': '<p>{}</p>'}, data: {'dn1:1.1': '<p>{}</p>', 'dn1:1.2': ''}, manual: true},
        ]});
    beforeEach(() => {
        jest.useFakeTimers();
        localStorage.clear();
        context = {...fetchTranslation()};
        context.sourceMuid = root;
        context.prefix = 'dn1';
        context.translations = [{muid: root, isSource: true, canEdit: true, data: {'dn1:1.1': 'A'}}];
        context.updateProgress = jest.fn();
        context.invalidateHtmlValidation = jest.fn();
        global.displayMessage = jest.fn();
        global.requestWithTokenRetry = jest.fn(async () => ({ok: true, json: async () => plan()}));
    });
    afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });
    test.each([
        ['split', 'createObject'], ['merge', 'createObject'],
        ['split', 'findOrCreateObject'], ['merge', 'findOrCreateObject'],
    ])('%s refreshes a virtual translation loaded with %s before its first save', async (operation, loader) => {
        const muid = 'translation-en-new';
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => ({
            data: {}, can_edit: true, materialized: false, structure_revision: 'before',
        })});
        const column = await context[loader](muid, context.prefix);
        if (loader === 'createObject') context.translations.push(column);
        expect(column.materialized).toBe(false);
        expect(context.structureRevisions[muid]).toBe('before');

        const preview = {...plan(), operation};
        if (operation === 'merge') {
            preview.splitter_uid = null;
            preview.merger_uid = preview.uid;
            preview.mergee_uid = 'dn1:1.2';
            preview.projects[0].before['dn1:1.2'] = 'B';
            preview.projects[1].before['dn1:1.2'] = '<p>{}</p>';
            preview.projects[0].data = {'dn1:1.1': 'AB'};
            preview.projects[1].data = {'dn1:1.1': '<p>{}</p>'};
        }
        context.translations[0].data = {...preview.projects[0].before};
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => preview});
        await context.startStructureDraft(operation, preview.uid);
        context.structureDraft.reviewed = [html];
        if (operation === 'split') {
            context.setValue(context.translations.find(t => t.muid === html), preview.splitter_uid, '<p>{}</p>');
            context.structureDraft.reviewed = [html];
        }
        requestWithTokenRetry.mockImplementationOnce(async (url, options) => {
            expect(url).toBe(`projects/${operation}/`);
            expect(JSON.parse(options.body).edits).not.toHaveProperty(muid);
            return {ok: true, json: async () => ({...preview, structure_revision: 'after'})};
        });
        await context.confirmStructureDraft(root, context.prefix);
        expect(column.data).toEqual({});
        expect(column.materialized).toBe(false);
        expect(context.structureRevisions[muid]).toBe('after');
        expect(requestWithTokenRetry).toHaveBeenCalledTimes(3);

        global.hideBadge = jest.fn();
        global.displayBadge = jest.fn();
        global.BadgeStatus = {PENDING: 'pending', COMMITTED: 'committed', ERROR: 'error'};
        context.setValue(column, preview.uid, 'First translation');
        requestWithTokenRetry.mockImplementationOnce(async (url, options) => {
            expect(url).toBe(`projects/${muid}/dn1/`);
            expect(options.headers['X-Structure-Revision']).toBe('after');
            expect(JSON.parse(options.body)).toEqual({[preview.uid]: 'First translation'});
            return {ok: true, json: async () => ({materialized: true, task_id: null})};
        });
        await context.updateHandler(muid, {[preview.uid]: 'First translation'});
        expect(column.materialized).toBe(true);
        expect(context.dirtySegments).toEqual({});
    });
    test('structure completion leaves remarks and virtual columns for other texts untouched', () => {
        const columns = [
            {muid: 'remarks-1', prefix: 'dn1', data: {}, materialized: false},
            {muid: 'translation-en-other', prefix: 'dn2', data: {}, materialized: false},
        ];
        context.translations.push(...columns);
        for (const column of columns) context.structureRevisions[column.muid] = 'unchanged';
        context.applyStructureResult(plan());
        for (const column of columns) {
            expect(context.structureRevisions[column.muid]).toBe('unchanged');
            expect(column.data).toEqual({});
        }
    });
    test('editing a reviewed project invalidates only that review, unchanged input preserves it', async () => {
        await context.startStructureDraft('split', 'dn1:1.1');
        context.structureDraft.reviewed = [root, html];
        const column = context.translations.find(t => t.muid === html);
        context.setValue(column, 'dn1:1.1', column.data['dn1:1.1']);
        expect(context.structurePendingReviews()).toEqual([]);
        context.setValue(column, 'dn1:1.2', '<p>{}</p>');
        expect(context.structureDraft.reviewed).toEqual([root]);
        expect(context.structurePendingReviews()).toEqual([html]);
    });
    test('review action blocks missing reviews and retains inline errors for retry', async () => {
        await context.startStructureDraft('split', 'dn1:1.1');
        context.confirmStructureDraft = jest.fn().mockRejectedValue(new Error('Please correct the HTML'));
        await context.submitStructureDraftFromReview();
        expect(context.confirmStructureDraft).not.toHaveBeenCalled();
        expect(context.structureDraftError).toContain('Check each required project');
        context.structureDraft.reviewed = [html];
        await context.submitStructureDraftFromReview();
        expect(context.structureDraftError).toBe('Please correct the HTML');
        expect(context.splitMergeProcessing).toBe(false);
        expect(context.structureDraft).not.toBeNull();
    });
    test('review action preserves result reporting and guards duplicate submission', async () => {
        await context.startStructureDraft('split', 'dn1:1.1');
        context.structureDraft.reviewed = [html];
        context.$nextTick = callback => callback();
        let finish;
        context.confirmStructureDraft = jest.fn(() => new Promise(resolve => { finish = resolve; }));
        const pending = context.submitStructureDraftFromReview();
        await context.submitStructureDraftFromReview();
        expect(context.confirmStructureDraft).toHaveBeenCalledTimes(1);
        finish({affectedFiles: ['file'], prefix: 'dn1', autoPublishedPaths: []});
        await pending;
        expect(context.affectedFiles).toEqual(['file']);
        expect(context.splitting).toBe(false);
        expect(context.splitMergeProcessing).toBe(false);
    });
    test('merge highlights only the retained result, not a shifted segment reusing the removed UID', () => {
        context.merger_uid = 'dn1:1.1';
        context.mergee_uid = 'dn1:1.2';
        expect(context.isMergeHighlightedRow('dn1:1.1')).toBe(true);
        expect(context.isMergeHighlightedRow('dn1:1.2')).toBe(false);
    });
    test.each(['split', 'merge'])('%s only edits operation rows across columns and restores ordinary editing on completion', async operation => {
        const preview = {...plan(), operation};
        for (const project of preview.projects) {
            project.before['dn1:9.1'] = 'unchanged';
            project.data['dn1:9.1'] = 'unchanged';
        }
        if (operation === 'merge') {
            preview.splitter_uid = null;
            preview.merger_uid = preview.uid;
            preview.mergee_uid = 'dn1:1.2';
            // The merged-away UID may be reused by the following shifted row.
            for (const project of preview.projects) project.data['dn1:1.2'] = 'shifted row';
        }
        context.translations[0].data = {...preview.projects[0].before};
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => preview});
        await context.startStructureDraft(operation, preview.uid);
        expect(context.canEditStructureSegment('translation-en-unrelated', preview.uid)).toBe(false);
        const expectedEdits = {};
        for (const column of context.translations) {
            const allowed = operation === 'split' ? [preview.uid, preview.splitter_uid] : [preview.uid];
            expectedEdits[column.muid] = {};
            for (const uid of allowed) {
                expect(context.canEditStructureSegment(column.muid, uid)).toBe(true);
                context.setValue(column, uid, 'draft edit');
                expectedEdits[column.muid][uid] = 'draft edit';
            }
            const locked = operation === 'split' ? ['dn1:9.1'] : ['dn1:9.1', 'dn1:1.2'];
            for (const uid of locked) {
                const original = column.data[uid];
                expect(context.canEditStructureSegment(column.muid, uid)).toBe(false);
                context.setValue(column, uid, 'must not change');
                expect(column.data[uid]).toBe(original);
            }
        }
        context.structureDraft.reviewed = [html];
        context.submitStructureOperation = jest.fn(async submission => submission);
        const submission = await context.confirmStructureDraft(root, 'dn1');
        expect(submission.edits).toEqual(expectedEdits);
        for (const column of context.translations) {
            expect(context.canEditStructureSegment(column.muid, preview.uid)).toBe(false);
            context.setValue(column, preview.uid, 'locked submission');
            expect(column.data[preview.uid]).toBe('draft edit');
        }
        context.applyStructureResult(preview);
        const column = context.translations[0];
        expect(context.canEditStructureSegment(root, 'dn1:9.1')).toBe(true);
        context.setValue(column, 'dn1:9.1', 'ordinary edit');
        expect(column.data['dn1:9.1']).toBe('ordinary edit');
    });
    test('cancelling a draft unlocks rows outside the operation', async () => {
        context.translations[0].data['dn1:9.1'] = 'unchanged';
        await context.startStructureDraft('split', 'dn1:1.1');
        expect(context.canEditStructureSegment(root, 'dn1:9.1')).toBe(false);
        context.cancelStructureDraft();
        expect(context.canEditStructureSegment(root, 'dn1:9.1')).toBe(true);
        context.setValue(context.translations[0], 'dn1:9.1', 'ordinary edit');
        expect(context.translations[0].data['dn1:9.1']).toBe('ordinary edit');
    });
    test.each(['split', 'merge'])('%s blocks input and Enter while awaiting preview, then permits draft edits', async operation => {
        let resolvePreview;
        requestWithTokenRetry.mockImplementationOnce(() => new Promise(resolve => { resolvePreview = resolve; }));
        const column = context.translations[0];
        const starting = context.startStructureDraft(operation, 'dn1:1.1');
        expect(context.canEditStructureSegment(root, 'dn1:1.1')).toBe(false);
        context.setValue(column, 'dn1:1.1', 'typed while waiting');
        expect(column.data['dn1:1.1']).toBe('A');
        expect(context.dirtySegments).toEqual({});
        const textarea = document.createElement('textarea');
        textarea.value = 'A';
        context.updateHandler = jest.fn();
        for (const shiftKey of [false, true]) {
            await context.handleEnter({shiftKey, target: textarea}, 'dn1:1.1', 'changed', column, 'A');
        }
        expect(textarea.value).toBe('A');
        expect(context.updateHandler).not.toHaveBeenCalled();

        resolvePreview({ok: true, json: async () => ({...plan(), operation})});
        expect(await starting).toBe(true);
        expect(context.canEditStructureSegment(root, 'dn1:1.1')).toBe(true);
        context.setValue(column, 'dn1:1.1', 'draft edit');
        context.structureDraft.reviewed = [html];
        context.submitStructureOperation = jest.fn(async submission => submission);
        const submission = await context.confirmStructureDraft(root, 'dn1');
        expect(submission.edits[root]).toEqual({'dn1:1.1': 'draft edit'});
    });
    test('failed preview restores ordinary input and Enter saving', async () => {
        let rejectPreview;
        requestWithTokenRetry.mockImplementationOnce(() => new Promise((resolve, reject) => { rejectPreview = reject; }));
        const starting = context.startStructureDraft('split', 'dn1:1.1');
        expect(context.canEditStructureSegment(root, 'dn1:1.1')).toBe(false);
        rejectPreview(new Error('preview failed'));
        expect(await starting).toBe(false);
        expect(context.canEditStructureSegment(root, 'dn1:1.1')).toBe(true);
        const column = context.translations[0];
        context.setValue(column, 'dn1:1.1', 'ordinary edit');
        expect(column.data['dn1:1.1']).toBe('ordinary edit');
        expect(context.dirtySegments[root + ':dn1:1.1']).toBe('A');
        context.updateHandler = jest.fn();
        await context.handleEnter({shiftKey: false, target: document.createElement('textarea')},
            'dn1:1.1', 'ordinary edit', column, 'A');
        expect(context.updateHandler).toHaveBeenCalled();
    });
    test.each(['split', 'merge'])('%s locks related columns during preview and draft, then unlocks on cancel', async operation => {
        let resolvePreview;
        requestWithTokenRetry.mockImplementationOnce(() => new Promise(resolve => { resolvePreview = resolve; }));
        const starting = context.startStructureDraft(operation, 'dn1:1.1');
        expect(context.relatedProjectsLocked()).toBe(true);
        expect(await context.toggleRelatedProject(root)).toBe(false);
        expect(await context.toggleRelatedProject('translation-en-demo')).toBe(false);
        expect(await context.startStructureDraft(operation, 'dn1:1.1')).toBe(false);
        expect(context.translations).toHaveLength(1);
        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);

        resolvePreview({ok: true, json: async () => ({...plan(), operation})});
        expect(await starting).toBe(true);
        expect(context.relatedProjectsLocked()).toBe(true);
        expect(await context.toggleRelatedProject(html)).toBe(false);
        expect(await context.toggleRelatedProject('translation-en-demo')).toBe(false);
        expect(context.translations).toHaveLength(2);
        expect(context.getSavedRelatedProjects()).toEqual([]);
        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);

        context.cancelStructureDraft();
        expect(context.relatedProjectsLocked()).toBe(false);
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => ({data: {'dn1:1.1': 'A'}, can_edit: true})});
        expect(await context.toggleRelatedProject('translation-en-demo')).toBe(true);
        expect(context.translations.map(t => t.muid)).toContain('translation-en-demo');
    });
    test('preview failure releases the related project lock', async () => {
        requestWithTokenRetry.mockRejectedValueOnce(new Error('preview failed'));
        expect(await context.startStructureDraft('split', 'dn1:1.1')).toBe(false);
        expect(context.relatedProjectsLocked()).toBe(false);
        expect(await context.toggleRelatedProject(root)).toBe(true);
        expect(context.translations).toEqual([]);
    });
    test.each([false, true])('all pending related loads block structure previews and release on completion (failure=%s)', async failure => {
        let finishFirst, finishSecond;
        requestWithTokenRetry
            .mockImplementationOnce(() => new Promise(resolve => { finishFirst = resolve; }))
            .mockImplementationOnce(() => new Promise((resolve, reject) => {
                finishSecond = failure ? reject : resolve;
            }));
        const first = context.toggleRelatedProject('translation-en-first');
        const second = context.toggleRelatedProject('translation-en-second');
        for (const operation of ['split', 'merge']) {
            expect(await context.startStructureDraft(operation, 'dn1:1.1')).toBe(false);
        }
        expect(requestWithTokenRetry).toHaveBeenCalledTimes(2);
        const response = {ok: true, json: async () => ({data: {'dn1:1.1': 'A'}, can_edit: true})};
        finishFirst(response);
        await first;
        expect(await context.startStructureDraft('split', 'dn1:1.1')).toBe(false);
        if (failure) {
            finishSecond(new Error('load failed'));
            await expect(second).rejects.toThrow('load failed');
        } else {
            finishSecond(response);
            await second;
        }
        expect(await context.startStructureDraft('split', 'dn1:1.1')).toBe(true);
    });
    test('manual review starts unchecked and blocks submission until every project is checked', async () => {
        await context.startStructureDraft('split', 'dn1:1.1');
        expect(context.structureDraft.reviewed).toEqual([]);
        await expect(context.confirmStructureDraft(root, 'dn1')).rejects.toThrow('Review every manual project');
        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
        expect(context.structureDraft.submission).toBeNull();
        expect(localStorage.getItem(context.structureRecoveryKey())).toBeNull();
    });
    test('corrupt recovery JSON reports a specific error and preserves the record', async () => {
        localStorage.setItem(context.structureRecoveryKey(), '{broken');
        await expect(context.resumeStructureOperation()).rejects.toThrow('Saved structure operation recovery data is corrupted');
        expect(localStorage.getItem(context.structureRecoveryKey())).toBe('{broken');
        expect(requestWithTokenRetry).not.toHaveBeenCalled();
    });
    test('preview comes from server and displays every manual column', async () => {
        await context.splitBasedOnUid(context.translations, 'dn1:1.1');
        expect(context.translations.find(t => t.muid === html).data['dn1:1.2']).toBe('');
        expect(context.structureDraft.preview.revision).toBe('r1');
    });
    test.each(['an1.1:1', 'mn1:1.2', 'dn1:1.2.3', 'dn1:1.2.3.4'])('numeric UID %s is supported by the production format check', uid => {
        expect(isMergeSplitConditionMet(uid)).toBe(true);
    });
    test.each(['mn1:', 'mn1:abc', 'mn1:1..2', 'mn1:1:2', 'mn1:1.2x'])('malformed UID %s is rejected', uid => {
        expect(isMergeSplitConditionMet(uid)).toBe(false);
    });
    test.each([false, true])('merge review identifies both UIDs and the section boundary (crossing=%s)', async crossing => {
        const preview = {...plan(), operation: 'merge', merger_uid: 'dn1:1.1',
            mergee_uid: crossing ? 'dn1:2.1' : 'dn1:1.2', merge_crosses_section: crossing};
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => preview});
        await context.mergeBasedOnUid(context.translations, preview.merger_uid);
        const summary = context.getStructureMergeSummary();
        expect(summary).toContain(preview.merger_uid);
        expect(summary).toContain(preview.mergee_uid);
        expect(summary.includes('crosses a section boundary')).toBe(crossing);
        if (crossing) expect(summary).toContain('only segment');
        context.cancelMerge();
        expect(context.getStructureMergeSummary()).toBe('');
    });
    test('Enter edits a draft without an ordinary save; cancel restores columns', async () => {
        await context.splitBasedOnUid(context.translations, 'dn1:1.1');
        context.updateHandler = jest.fn();
        await context.handleEnter({shiftKey: false, target: {}}, 'dn1:1.2', 'B', context.translations[0], '');
        expect(context.updateHandler).not.toHaveBeenCalled();
        context.cancelSplit();
        expect(context.translations).toHaveLength(1);
        expect(context.translations[0].data).toEqual({'dn1:1.1': 'A'});
        expect(context.structureDraft).toBeNull();
    });
    test('confirmation sends manual edits and applies authoritative result to every column', async () => {
        await context.splitBasedOnUid(context.translations, 'dn1:1.1');
        context.structureDraft.reviewed = [html];
        context.translations[1].data['dn1:1.2'] = '<p>{}</p>';
        const result = plan();
        result.projects[0].data['dn1:1.2'] = 'server';
        requestWithTokenRetry.mockImplementationOnce(async (_url, options) => {
            const body = JSON.parse(options.body);
            expect(body.edits[html]['dn1:1.2']).toBe('<p>{}</p>');
            expect(body.reviewed).toEqual([html]);
            return {ok: true, json: async () => result};
        });
        await context.updateHandlerForSplit(root, 'dn1');
        expect(context.translations[0].data['dn1:1.2']).toBe('server');
        expect(context.structureDraft).toBeNull();
        expect(context.relatedProjectsLocked()).toBe(false);
        expect(await context.toggleRelatedProject(html)).toBe(true);
    });
    test('conflict keeps manual draft available for copying or cancelling', async () => {
        await context.splitBasedOnUid(context.translations, 'dn1:1.1');
        context.structureDraft.reviewed = [html];
        requestWithTokenRetry.mockResolvedValueOnce({ok: false, status: 409, json: async () => ({detail: 'changed'})});
        await expect(context.updateHandlerForSplit(root, 'dn1')).rejects.toThrow('changed');
        expect(context.structureDraft).not.toBeNull();
        expect(context.relatedProjectsLocked()).toBe(true);
        expect(await context.toggleRelatedProject(html)).toBe(false);
    });
    test('publication failure completes the draft and reports files for manual handling', async () => {
        await context.splitBasedOnUid(context.translations, 'dn1:1.1');
        context.structureDraft.reviewed = [html];
        const result = {...plan(), operation_id: 'operation-1', status: 'complete',
            publication_status: 'failed', publication_error: 'Automatic publication could not be queued.',
            auto_publish_pending_paths: ['/root/pli/ms/dn1_root-pli-ms.json']};
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => result});
        const saved = await context.updateHandlerForSplit(root, 'dn1');
        expect(saved.affectedFiles.find(file => file.muid === root).publishMode).toBe('pending');
        expect(context.structureDraft).toBeNull();
        expect(localStorage.getItem(context.structureRecoveryKey())).toBeNull();
        expect(localStorage.getItem(`${context.structureRecoveryKey()}:publication`)).toBeNull();
        expect(jest.getTimerCount()).toBe(0);
        context.setValue(context.translations[0], 'dn1:1.1', 'later edit');
        expect(context.translations[0].data['dn1:1.1']).toBe('later edit');
    });
    test.each(['split', 'merge'])('saved HTML edits in a merge allow a subsequent %s', async nextOperation => {
        const preview = plan();
        preview.operation = 'merge';
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => preview});
        await context.mergeBasedOnUid(context.translations, 'dn1:1.1');
        context.structureDraft.reviewed = [html];
        const htmlColumn = context.translations.find(t => t.muid === html);
        context.setValue(htmlColumn, 'dn1:1.1', '<div>{}</div>');
        context.structureDraft.reviewed = [html];
        const result = JSON.parse(JSON.stringify(preview));
        result.projects.find(p => p.muid === html).data['dn1:1.1'] = '<div>{}</div>';
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => result});
        await context.updateHandlerForMerge(root, 'dn1');
        expect(context.dirtySegments).toEqual({});
        expect(await context.startStructureDraft(nextOperation, 'dn1:1.1')).toBe(true);
        expect(displayMessage).not.toHaveBeenCalled();
    });
    test('an interrupted confirmation checks the same operation instead of submitting twice', async () => {
        await context.splitBasedOnUid(context.translations, 'dn1:1.1');
        context.structureDraft.reviewed = [html];
        requestWithTokenRetry.mockRejectedValueOnce(new Error('connection lost'));
        await expect(context.updateHandlerForSplit(root, 'dn1')).rejects.toThrow('connection lost');
        const operationId = context.structureDraft.submission.operation_id;
        expect(() => context.cancelSplit()).toThrow('must be checked');
        requestWithTokenRetry.mockImplementationOnce(async (url, options) => {
            expect(url).toBe('projects/structure/status/');
            expect(JSON.parse(options.body).operation_id).toBe(operationId);
            return {ok: true, json: async () => ({...plan(), status: 'complete'})};
        });
        await context.updateHandlerForSplit(root, 'dn1');
        expect(context.structureDraft).toBeNull();
        expect(requestWithTokenRetry.mock.calls.filter(([url]) => url === 'projects/split/')).toHaveLength(1);
    });
    async function interruptConfirmation() {
        await context.splitBasedOnUid(context.translations, 'dn1:1.1');
        context.structureDraft.reviewed = [html];
        requestWithTokenRetry.mockRejectedValueOnce(new Error('offline'));
        await expect(context.confirmStructureDraft(root, 'dn1')).rejects.toThrow('offline');
        return localStorage.getItem(context.structureRecoveryKey());
    }
    test.each(['refresh', 'confirm'])('%s replays the exact saved submission after not_found', async entry => {
        const saved = await interruptConfirmation();
        if (entry === 'refresh') context.structureDraft = null;
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => ({status: 'not_found'})});
        requestWithTokenRetry.mockImplementationOnce(async (url, options) => {
            expect(url).toBe('projects/split/');
            expect(options.body).toBe(saved);
            expect(localStorage.getItem(context.structureRecoveryKey())).toBe(saved);
            return {ok: true, json: async () => ({...plan(), status: 'complete'})};
        });
        await (entry === 'refresh' ? context.resumeStructureOperation() : context.confirmStructureDraft(root, 'dn1'));
        expect(requestWithTokenRetry.mock.calls.filter(([url]) => url === 'projects/split/')).toHaveLength(2);
        expect(localStorage.getItem(context.structureRecoveryKey())).toBeNull();
        expect(context.structureDraft).toBeNull();
    });
    test('refresh applies a completed operation without another PATCH', async () => {
        await interruptConfirmation();
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => ({...plan(), status: 'complete'})});
        await context.resumeStructureOperation();
        expect(requestWithTokenRetry.mock.calls.filter(([url]) => url === 'projects/split/')).toHaveLength(1);
        expect(localStorage.getItem(context.structureRecoveryKey())).toBeNull();
    });
    test.each(['status failure', 'invalid JSON', 'unknown status'])('refresh preserves recovery after %s', async failure => {
        const saved = await interruptConfirmation();
        if (failure === 'invalid JSON') {
            requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => ({status: 'not_found'})});
            requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => { throw new Error('invalid JSON'); }});
        } else {
            requestWithTokenRetry.mockResolvedValueOnce({ok: failure !== 'status failure',
                json: async () => ({status: 'unknown', detail: 'status unavailable'})});
        }
        await expect(context.resumeStructureOperation()).rejects.toThrow();
        expect(localStorage.getItem(context.structureRecoveryKey())).toBe(saved);
    });
    test.each([401, 429, 500, 409])('HTTP %s without a definitive rejection keeps recovery and draft locked', async status => {
        const saved = await interruptConfirmation();
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => ({status: 'not_found'})});
        requestWithTokenRetry.mockResolvedValueOnce({ok: false, status, json: async () => ({detail: 'retry'})});
        await expect(context.confirmStructureDraft(root, 'dn1')).rejects.toThrow('retry');
        expect(localStorage.getItem(context.structureRecoveryKey())).toBe(saved);
        expect(() => context.cancelSplit()).toThrow('must be checked');
    });
    test.each(['refresh', 'confirm'])('%s clears only a definitive submission rejection', async entry => {
        await interruptConfirmation();
        if (entry === 'refresh') context.structureDraft = null;
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => ({status: 'not_found'})});
        requestWithTokenRetry.mockResolvedValueOnce({ok: false, status: 409,
            json: async () => ({detail: {code: 'submission_rejected', message: 'preview changed'}})});
        await expect(entry === 'refresh' ? context.resumeStructureOperation() : context.confirmStructureDraft(root, 'dn1')).rejects.toThrow('preview changed');
        expect(localStorage.getItem(context.structureRecoveryKey())).toBeNull();
        if (entry === 'confirm') expect(context.structureDraft.submission).toBeNull();
    });
    test.each(['submit', 'refresh', 'confirm'])('%s displays recoverable failure and keeps the operation', async entry => {
        const saved = await interruptConfirmation();
        const message = 'Structure operation is incomplete. Retry confirmation or reload to resume it.';
        requestWithTokenRetry.mockResolvedValueOnce({ok: false, status: 500, json: async () => ({detail: {
            code: 'structure_operation_incomplete', message,
            operation_id: JSON.parse(saved).operation_id,
        }})});
        const run = () => entry === 'submit' ? context.submitStructureOperation(JSON.parse(saved))
            : entry === 'refresh' ? context.resumeStructureOperation() : context.confirmStructureDraft(root, 'dn1');
        await expect(run()).rejects.toThrow(message);
        expect(localStorage.getItem(context.structureRecoveryKey())).toBe(saved);
        expect(() => context.cancelSplit()).toThrow('must be checked');
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => ({...plan(), status: 'complete'})});
        await context.confirmStructureDraft(root, 'dn1');
        expect(localStorage.getItem(context.structureRecoveryKey())).toBeNull();
    });
    test('confirmation shows recovery instructions for a non-JSON error response', async () => {
        const saved = await interruptConfirmation();
        requestWithTokenRetry.mockResolvedValueOnce({ok: false, status: 500,
            json: async () => { throw new SyntaxError('Unexpected token'); }});
        await expect(context.confirmStructureDraft(root, 'dn1')).rejects.toThrow('Operation is still pending; retry confirmation.');
        expect(localStorage.getItem(context.structureRecoveryKey())).toBe(saved);
    });
    test('refresh waits for replay before loading and preserves recovery on network failure', async () => {
        const saved = await interruptConfirmation();
        context.resolveSource = jest.fn(async () => root);
        context.loadCurrentUserForTranslation = jest.fn();
        context.findOrCreateObject = jest.fn();
        window.history.replaceState({}, '', '?muid=root-pli-ms&prefix=dn1');
        requestWithTokenRetry.mockResolvedValueOnce({ok: true, json: async () => ({status: 'not_found'})});
        let rejectReplay;
        requestWithTokenRetry.mockImplementationOnce(() => new Promise((resolve, reject) => { rejectReplay = reject; }));
        const loading = context.init();
        for (let i = 0; i < 20 && !rejectReplay; i++) await Promise.resolve();
        expect(rejectReplay).toBeDefined();
        expect(context.findOrCreateObject).not.toHaveBeenCalled();
        rejectReplay(new Error('offline'));
        await loading;
        expect(context.loadError).toBe('offline');
        expect(context.loadCurrentUserForTranslation).not.toHaveBeenCalled();
        expect(localStorage.getItem(context.structureRecoveryKey())).toBe(saved);
    });
    test('unsaved ordinary edits block preview and reverting them allows it', async () => {
        const column = context.translations[0];
        context.setValue(column, 'dn1:1.1', 'changed');
        expect(await context.splitBasedOnUid(context.translations, 'dn1:1.1')).toBe(false);
        expect(requestWithTokenRetry).not.toHaveBeenCalled();
        context.setValue(column, 'dn1:1.1', 'A');
        expect(await context.splitBasedOnUid(context.translations, 'dn1:1.1')).toBe(true);
    });
    test.each([true, false])('leaving an untouched tag cell does not create edits (canEdit=%s)', async canEdit => {
        const column = {muid: 'tag-pli-ms', canEdit, data: {'dn1:1.1': '4nt, '}};
        context.translations.push(column);
        context.availableTags = [{tag: '4nt'}];
        const page = fs.readFileSync(require('path').join(__dirname, '../../../translation.html'), 'utf8');
        const handler = page.match(/x-on:blur="([\s\S]*?)"/)[1];
        const textarea = document.createElement('textarea');
        textarea.value = column.data['dn1:1.1'];
        const scope = {
            $el: textarea, $event: {target: textarea, relatedTarget: null},
            translation: column, uid: 'dn1:1.1', isTag: true,
            showHints: true, closeTagSuggestions: jest.fn(),
            availableTags: context.availableTags,
            getValue: context.getValue.bind(context), setValue: context.setValue.bind(context),
        };
        new Function('scope', `with (scope) { ${handler} }`)(scope);
        expect(column.data['dn1:1.1']).toBe('4nt, ');
        expect(textarea.value).toBe('4nt, ');
        expect(context.dirtySegments).toEqual({});
        expect(scope.closeTagSuggestions).toHaveBeenCalled();
        expect(await context.splitBasedOnUid(context.translations, 'dn1:1.1')).toBe(true);
    });
});
