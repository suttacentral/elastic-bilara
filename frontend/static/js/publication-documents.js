/* Whole-document editing. Preview output is never used as the save payload. */
function publicationDocumentPreview(content, dark = false) {
    if (!window.DOMPurify) throw new Error('HTML preview is unavailable. Reload the page.');
    const clean = window.DOMPurify.sanitize(content, {
        ALLOWED_TAGS: ['article', 'section', 'nav', 'aside', 'header', 'footer', 'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'a', 'abbr', 'b', 'br', 'blockquote', 'cite', 'code', 'dd', 'del', 'dfn', 'dl', 'dt', 'em', 'hr', 'i', 'ins',
            'kbd', 'li', 'mark', 'ol', 'pre', 'q', 's', 'samp', 'small', 'span', 'strong', 'sub', 'sup', 'table', 'tbody',
            'td', 'th', 'thead', 'tfoot', 'tr', 'caption', 'time', 'u', 'ul', 'var'],
        ALLOWED_ATTR: ['id', 'class', 'href', 'lang', 'dir', 'translate', 'epub:type', 'role', 'title', 'colspan', 'rowspan',
            'scope', 'start', 'type', 'value', 'reversed', 'datetime'],
        ADD_URI_SAFE_ATTR: ['lang', 'dir', 'translate', 'epub:type', 'scope', 'datetime', 'start', 'value', 'reversed'],
        ALLOW_DATA_ATTR: false, ALLOW_ARIA_ATTR: false, ALLOWED_URI_REGEXP: /^#/,
    });
    return `<!doctype html><html><head><meta charset="utf-8">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'">
        <style>html{color-scheme:${dark ? 'dark' : 'light'}}body{font:18px/1.75 Georgia,serif;margin:32px auto;padding:0 24px;max-width:760px;overflow-wrap:anywhere}
        h1,h2,h3,h4{line-height:1.3}a{color:${dark ? '#8ab4f8' : '#1758a6'}}blockquote{margin-left:1.5em;border-left:3px solid #aaa;padding-left:1em}
        table{border-collapse:collapse}td,th{padding:.4em;border:1px solid #aaa}dt{font-weight:bold}pre{white-space:pre-wrap}</style></head><body>${clean}</body></html>`;
}

function publicationDocumentEditor() {
    return {
        number: '', publication: null, documents: [], selected: null, content: '', savedContent: '',
        publishedContent: '', publishedRevision: '', revision: '', publishedChanged: false,
        loading: true, loadingDocument: false, saving: false, checking: false, error: '', notice: '', conflict: false,
        mode: 'split', sidebar: 'documents', sidebarOpen: true, query: '', previewHtml: '', diffText: '',
        splitRatio: 50, splitAvailableWidth: 0, splitDrag: null, splitLayoutFrame: null,
        comparison: 'published', validation: { issues: [], headings: [], valid: true, can_save: true }, validationStale: false,
        sync: { status: 'idle' }, publish: { status: 'idle' }, releaseDocuments: [], releaseSelection: [], preparingRelease: false,
        findText: '', replacement: '', matchCase: false, findNotice: '', pendingAction: null,
        historyIndex: 0, historyRestore: null, historyApproval: null,
        previewTimer: null, validationTimer: null, pollTimer: null, destroyed: false, documentSequence: 0, statusVersion: 0,
        get dirty() { return this.content !== this.savedContent; },
        // Match textarea.value's LF representation without changing the saved source bytes.
        get sourceValue() { return this.content.replace(/\r\n?/g, '\n'); },
        get splitMin() { return this.splitAvailableWidth > 0 ? Math.min(50, 240 / this.splitAvailableWidth * 100) : 50; },
        get splitMax() { return 100 - this.splitMin; },
        get splitPosition() { return Math.max(this.splitMin, Math.min(this.splitMax, this.splitRatio)); },
        get filteredDocuments() {
            const query = this.query.trim().toLowerCase();
            return this.documents.filter(doc => `${doc.title} ${doc.filename}`.toLowerCase().includes(query));
        },
        get canPublish() { return !this.dirty && !this.saving && !this.loadingDocument && this.documents.some(doc => doc.changed || doc.request_outdated); },
        get currentTitle() { return this.documents.find(doc => doc.id === this.selected)?.title || ''; },
        get currentFilename() { return this.documents.find(doc => doc.id === this.selected)?.filename || ''; },
        get editions() { return this.documents.find(doc => doc.id === this.selected)?.editions || []; },
        get validationSummary() {
            if (this.validationStale) return 'Content changed. Validation is pending.';
            return this.validation.issues.length ? `${this.validation.issues.length} issue(s). Drafts can be saved; resolve errors before publishing.` : 'No validation errors.';
        },
        get syncLabel() {
            const labels = { idle: 'No draft sync requested', pending: 'Draft saved · waiting to sync', queued: 'Draft saved · waiting to sync',
                syncing: 'Syncing drafts…', retrying: 'Sync interrupted · retrying', synced: 'Drafts synced to unpublished', failed: 'Draft sync failed' };
            return labels[this.sync.status] || this.sync.status;
        },
        get publishLabel() {
            if (this.publish.status === 'synced' && this.publish.request_state === 'merged') return 'Pull request merged';
            if (this.publish.status === 'synced' && this.publish.request_state === 'closed') return 'Pull request closed';
            const labels = { idle: 'No publication request', pending: 'Publication request queued', queued: 'Publication request queued',
                syncing: 'Submitting publication request…', retrying: 'Publication request interrupted · retrying', failed: 'Publication request failed',
                synced: this.publish.url ? 'Pull request submitted · review and merge required' : (this.publish.message || 'Publication request completed') };
            return labels[this.publish.status] || this.publish.status;
        },
        async api(path, options) {
            const response = await requestWithTokenRetry(`publication-documents/${path}`, options);
            const data = await response.json();
            if (!response.ok) {
                const detail = data.detail;
                const message = typeof detail === 'string' ? detail : detail?.message || (Array.isArray(detail) ? detail.map(e => e.msg).join('; ') : 'Document request failed.');
                const error = new Error(message);
                error.status = response.status;
                error.validation = detail?.validation;
                throw error;
            }
            return data;
        },
        json(method, value) { return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) }; },
        path(suffix = '') { return `${encodeURIComponent(this.number)}/documents/${this.selected}${suffix}`; },
        async init() {
            const params = new URLSearchParams(window.location.search);
            this.number = params.get('publication') || '';
            this._beforeUnload = event => { if (this.dirty) { event.preventDefault(); event.returnValue = ''; } };
            const entry = window.history.state?.publicationDocument;
            this.historyIndex = entry?.publication === this.number ? entry.index : 0;
            this._popstate = event => this.navigateHistory(event);
            window.addEventListener('beforeunload', this._beforeUnload);
            window.addEventListener('popstate', this._popstate);
            this.$nextTick(() => {
                if (this.destroyed) return;
                this._splitObserver = new ResizeObserver(() => this.queueSplitLayout());
                this._splitObserver.observe(this.$refs.panes);
                // Mode changes can reveal the divider without resizing its container.
                this._splitObserver.observe(this.$refs.splitter);
            });
            try {
                if (!/^scpub[1-9]\d*$/.test(this.number)) throw new Error('Choose a publication from the Publications page.');
                const user = await getCurrentUser();
                if (!user.is_active || !['writer', 'administrator', 'superuser'].includes(user.role)) throw new Error('An active writer or administrator account is required.');
                await this.loadList();
                const uid = params.get('document') || this.documents[0]?.id;
                if (uid) await this.loadDocument(uid, 'replace');
                this.poll();
            } catch (error) { this.error = error.message; }
            finally { this.loading = false; }
        },
        async loadList() {
            const data = await this.api(`${this.number}/`);
            if (this.destroyed) return;
            this.publication = data.publication;
            this.documents = data.documents;
            this.sync = data.sync;
            this.publish = data.publish;
        },
        documentUrl(uid) {
            return `${window.location.pathname}?${new URLSearchParams({ publication: this.number, ...(uid ? { document: uid } : {}) })}`;
        },
        restoreHistory(fromIndex, action = () => {}) {
            // Move the cursor back without overwriting the entry the user tried to visit.
            // Single steps cannot jump over our destination when more Back/Forward
            // operations are already queued by the browser.
            this.historyRestore = action;
            window.history.go(Math.sign(this.historyIndex - fromIndex));
        },
        async navigateHistory(event) {
            const entry = event.state?.publicationDocument;
            if (entry?.publication !== this.number) return;
            const index = entry.index;
            const uid = new URLSearchParams(window.location.search).get('document');
            if (this.historyRestore) {
                if (index !== this.historyIndex) {
                    window.history.go(Math.sign(this.historyIndex - index));
                    return;
                }
                const action = this.historyRestore;
                this.historyRestore = null;
                action();
                return;
            }
            const approved = this.historyApproval === index;
            this.historyApproval = null;
            if (uid === this.selected) {
                ++this.documentSequence;
                this.loadingDocument = false;
                this.historyIndex = index;
                return;
            }
            if ((this.dirty && !approved) || this.saving || this.pendingAction) {
                this.restoreHistory(index, () => {
                    if (this.saving || this.pendingAction) return;
                    this.guard(() => {
                        this.historyApproval = index;
                        window.history.go(index - this.historyIndex);
                    });
                });
                return;
            }
            // A second traversal supersedes an in-flight load, even when returning
            // to the document still on screen before that load has completed.
            ++this.documentSequence;
            this.loadingDocument = false;
            if (await this.loadDocument(uid, 'none', index) === false) this.restoreHistory(index);
        },
        async loadDocument(uid, historyMode = 'push', historyIndex = this.historyIndex) {
            const sequence = ++this.documentSequence;
            this.loadingDocument = true;
            this.error = ''; this.notice = '';
            clearTimeout(this.validationTimer); clearTimeout(this.previewTimer);
            try {
                if (!this.documents.some(doc => doc.id === uid)) throw new Error('This document is not available in the selected publication.');
                const data = await this.api(`${this.number}/documents/${uid}`);
                if (sequence !== this.documentSequence || this.destroyed) return;
                this.applyDocument(data);
                this.historyIndex = historyIndex + (historyMode === 'push' ? 1 : 0);
                if (historyMode !== 'none') {
                    window.history[historyMode === 'push' ? 'pushState' : 'replaceState']({
                        ...window.history.state,
                        publicationDocument: { publication: this.number, index: this.historyIndex },
                    }, '', this.documentUrl(uid));
                }
                document.title = `${data.filename} · Publications · Bilara`;
                if (this.mode === 'diff') await this.loadDiff();
                return true;
            } catch (error) {
                if (sequence === this.documentSequence) { this.error = error.message; return false; }
            }
            finally { if (sequence === this.documentSequence) this.loadingDocument = false; }
        },
        applyDocument(data, preserveInput = false) {
            this.statusVersion += 1;
            this.selected = data.id;
            this.savedContent = data.content;
            if (!preserveInput) {
                this.content = data.content;
                this.validation = data.validation; this.validationStale = false;
            }
            this.publishedContent = data.published_content; this.publishedRevision = data.published_revision;
            this.revision = data.revision; this.publishedChanged = data.published_changed;
            this.conflict = false;
            this.sync = data.sync; this.publish = data.publish;
            const doc = this.documents.find(doc => doc.id === data.id);
            if (doc) {
                doc.title = data.validation.headings.find(heading => heading.level === 1)?.title ?? data.filename;
                doc.changed = data.content !== data.published_content; doc.request_outdated = data.request_outdated; doc.revision = data.revision;
            }
            this.renderPreview();
        },
        chooseDocument(uid) {
            if (uid === this.selected || this.saving || this.loadingDocument || this.historyRestore || this.historyApproval !== null) return;
            this.guard(() => this.loadDocument(uid));
        },
        guard(action) {
            if (!this.dirty) return action();
            this.pendingAction = action;
            this.$refs.discardDialog.showModal();
        },
        async resolveNavigation(choice) {
            if (choice === 'stay') { this.pendingAction = null; this.$refs.discardDialog.close(); return; }
            if (choice === 'save' && !(await this.save())) return;
            const action = this.pendingAction;
            this.pendingAction = null;
            this.$refs.discardDialog.close();
            if (action) await action();
        },
        leave(event) { event.preventDefault(); this.guard(() => { window.location.href = '/publications'; }); },
        reload() { this.guard(() => this.loadDocument(this.selected, 'replace')); },
        onInput(value) {
            // Textareas normalize CRLF. Preserve the original convention when editing.
            if (value === this.savedContent.replace(/\r\n/g, '\n')) this.content = this.savedContent;
            else this.content = this.savedContent.includes('\r\n') && !/(?<!\r)\n/.test(this.savedContent) ? value.replace(/\r?\n/g, '\r\n') : value;
            this.validationStale = true; this.notice = ''; this.findNotice = '';
            clearTimeout(this.previewTimer); clearTimeout(this.validationTimer);
            this.previewTimer = setTimeout(() => { if (this.mode === 'split' || this.mode === 'preview') this.renderPreview(); }, 400);
            this.validationTimer = setTimeout(() => this.check(false), 1000);
        },
        renderPreview() {
            try {
                const background = getComputedStyle(document.body).backgroundColor;
                const rgb = background.match(/\d+/g)?.map(Number) || [255, 255, 255];
                this.previewHtml = publicationDocumentPreview(this.content, rgb[0] + rgb[1] + rgb[2] < 380);
            } catch (error) { this.error = error.message; this.previewHtml = ''; }
        },
        previewLoaded() {
            const preview = this.$refs.preview?.contentDocument;
            if (!preview) return;
            // Fragment navigation stays inside the sandbox; other navigation is disabled.
            preview.addEventListener('click', event => {
                const link = event.target.closest('a');
                if (!link) return;
                event.preventDefault();
                const href = link.getAttribute('href') || '';
                if (href.startsWith('#')) {
                    try { preview.getElementById(decodeURIComponent(href.slice(1)))?.scrollIntoView({ block: 'start' }); }
                    catch (_) { /* Invalid fragments are reported by validation. */ }
                }
            });
        },
        async setMode(mode) {
            this.stopSplitResize();
            this.mode = mode;
            if (mode === 'diff') await this.loadDiff();
            if (mode === 'split' || mode === 'preview') this.renderPreview();
            if (mode === 'split') this.$nextTick(() => this.queueSplitLayout());
        },
        queueSplitLayout() {
            if (this.destroyed || this.splitLayoutFrame !== null) return;
            // Apply reactive grid changes outside ResizeObserver's delivery cycle.
            this.splitLayoutFrame = requestAnimationFrame(() => {
                this.splitLayoutFrame = null;
                this.updateSplitLayout();
            });
        },
        updateSplitLayout() {
            const dividerWidth = this.$refs.splitter.getBoundingClientRect().width;
            if (this.mode !== 'split' || !dividerWidth) {
                this.stopSplitResize();
                return false;
            }
            this.splitAvailableWidth = this.$refs.panes.getBoundingClientRect().width - dividerWidth;
            return this.splitAvailableWidth > 0;
        },
        startSplitResize(event) {
            if (event.button !== 0 || !event.isPrimary || this.splitDrag || !this.updateSplitLayout()) return;
            event.preventDefault();
            const splitter = event.currentTarget;
            splitter.focus({ preventScroll: true });
            splitter.setPointerCapture(event.pointerId);
            this.splitDrag = { pointerId: event.pointerId, offset: event.clientX - splitter.getBoundingClientRect().left };
        },
        resizeSplit(event) {
            if (!this.splitDrag || event.pointerId !== this.splitDrag.pointerId || !this.updateSplitLayout()) return;
            const left = this.$refs.panes.getBoundingClientRect().left;
            const ratio = (event.clientX - left - this.splitDrag.offset) / this.splitAvailableWidth * 100;
            this.splitRatio = Math.max(this.splitMin, Math.min(this.splitMax, ratio));
        },
        stopSplitResize(event) {
            if (!this.splitDrag || (event && event.pointerId !== this.splitDrag.pointerId)) return;
            const { pointerId } = this.splitDrag;
            this.splitDrag = null;
            if (this.$refs.splitter.hasPointerCapture(pointerId)) this.$refs.splitter.releasePointerCapture(pointerId);
        },
        resizeSplitWithKeyboard(event) {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Enter'].includes(event.key) || !this.updateSplitLayout()) return;
            event.preventDefault();
            this.stopSplitResize();
            const positions = { ArrowLeft: this.splitPosition - 2, ArrowRight: this.splitPosition + 2,
                Home: this.splitMin, End: this.splitMax, Enter: 50 };
            this.splitRatio = Math.max(this.splitMin, Math.min(this.splitMax, positions[event.key]));
        },
        async check(showNotice = true) {
            if (!this.selected || this.loadingDocument) return;
            const content = this.content, uid = this.selected;
            this.checking = true;
            try {
                const result = await this.api(this.path('/validate/'), this.json('POST', { content }));
                if (this.selected === uid && this.content === content && !this.destroyed) {
                    this.validation = result; this.validationStale = false;
                    if (showNotice) this.notice = result.valid ? 'Validation passed.' : 'Review the issues below. Click an issue to locate it.';
                }
            } catch (error) { if (this.selected === uid && !this.destroyed) this.error = error.message; }
            finally { this.checking = false; }
        },
        async loadDiff() {
            const content = this.content, uid = this.selected, comparison = this.comparison;
            try {
                const result = await this.api(this.path(`/diff/?comparison=${comparison}`), this.json('POST', { content }));
                if (this.selected === uid && this.content === content && this.comparison === comparison && !this.destroyed) this.diffText = result.diff || 'No changes.';
            } catch (error) { this.error = error.message; }
        },
        async save() {
            if (!this.dirty) return true;
            if (this.saving || this.conflict || this.loadingDocument) return false;
            const content = this.content, uid = this.selected;
            this.saving = true; this.error = '';
            this.statusVersion += 1;
            try {
                const data = await this.api(this.path(), this.json('PUT', { content, revision: this.revision, published_revision: this.publishedRevision }));
                if (this.selected !== uid || this.destroyed) return false;
                // Later input owns its validation result or pending validation task.
                this.applyDocument(data, this.content !== content);
                this.notice = 'Draft saved. Git synchronization runs in the background.';
                if (this.mode === 'diff') await this.loadDiff();
                return !this.dirty;
            } catch (error) {
                this.error = error.message;
                this.conflict = error.status === 409;
                if (error.validation && this.content === content) { this.validation = error.validation; this.validationStale = false; }
                return false;
            } finally { this.saving = false; }
        },
        locate(issue) {
            if (this.mode === 'preview' || this.mode === 'diff') this.mode = 'source';
            this.$nextTick(() => {
                const editor = this.$refs.source;
                const lines = editor.value.split('\n');
                const start = lines.slice(0, Math.max(0, issue.line - 1)).reduce((sum, line) => sum + line.length + 1, 0) + (issue.column || 1) - 1;
                editor.focus(); editor.setSelectionRange(start, Math.min(editor.value.length, start + 1));
                const lineHeight = parseFloat(getComputedStyle(editor).lineHeight) || 24;
                editor.scrollTop = Math.max(0, (issue.line - 3) * lineHeight);
            });
        },
        goToHeading(heading, index) {
            if (this.mode !== 'preview') this.locate(heading);
            const preview = this.$refs.preview?.contentDocument;
            preview?.querySelectorAll('h1,h2,h3,h4,h5,h6')[index]?.scrollIntoView({ block: 'start' });
        },
        findNext() {
            if (!this.findText) return;
            if (this.mode === 'preview' || this.mode === 'diff') this.mode = 'source';
            this.$nextTick(() => {
                const editor = this.$refs.source;
                const value = this.matchCase ? editor.value : editor.value.toLowerCase();
                const needle = this.matchCase ? this.findText : this.findText.toLowerCase();
                let start = value.indexOf(needle, editor.selectionEnd);
                if (start < 0) start = value.indexOf(needle);
                if (start < 0) { this.findNotice = 'No match found.'; return; }
                editor.focus(); editor.setSelectionRange(start, start + this.findText.length);
                editor.scrollTop = Math.max(0, (editor.value.slice(0, start).split('\n').length - 3) * (parseFloat(getComputedStyle(editor).lineHeight) || 24));
                this.findNotice = '';
            });
        },
        replaceMatch() {
            const editor = this.$refs.source;
            if (!editor || !this.findText) return;
            const value = editor.value.slice(editor.selectionStart, editor.selectionEnd);
            const matches = this.matchCase ? value === this.findText : value.toLowerCase() === this.findText.toLowerCase();
            if (!matches) { this.findNext(); return; }
            editor.setRangeText(this.replacement, editor.selectionStart, editor.selectionEnd, 'end');
            this.onInput(editor.value);
            this.findNext();
        },
        async acknowledgeBaseline() {
            if (this.dirty) { this.error = 'Save or discard your edits before acknowledging a new published version.'; return; }
            try {
                const data = await this.api(this.path('/baseline/'), this.json('POST', { revision: this.revision, published_revision: this.publishedRevision }));
                this.applyDocument(data); this.notice = 'Published baseline acknowledged. Review the draft before submitting it.';
            } catch (error) { this.error = error.message; }
        },
        async prepareRelease() {
            if (!this.canPublish || this.preparingRelease) return;
            this.preparingRelease = true; this.error = '';
            try {
                await this.loadList();
                const changed = this.documents.filter(doc => doc.changed || doc.request_outdated);
                this.releaseDocuments = await Promise.all(changed.map(doc => this.api(`${this.number}/documents/${doc.id}`)));
                if (this.dirty) throw new Error('Save your current edits before reviewing a publication request.');
                this.releaseSelection = this.releaseDocuments.filter(doc => doc.validation.valid && !doc.published_changed).map(doc => doc.id);
                this.$refs.releaseDialog.showModal();
            } catch (error) { this.error = error.message; }
            finally { this.preparingRelease = false; }
        },
        async submitRelease() {
            if (!this.releaseSelection.length || this.preparingRelease) return;
            this.preparingRelease = true; this.error = '';
            this.statusVersion += 1;
            try {
                const documents = this.releaseDocuments.filter(doc => this.releaseSelection.includes(doc.id)).map(doc => ({
                    id: doc.id, revision: doc.revision, published_revision: doc.published_revision,
                }));
                const result = await this.api(`${this.number}/publish/`, this.json('POST', { documents }));
                this.sync = result.sync; this.publish = result.publish;
                this.$refs.releaseDialog.close();
                this.notice = 'Publication request queued. The published content changes only after review and merge.';
            } catch (error) { this.error = error.message; }
            finally { this.preparingRelease = false; }
        },
        async retry(operation) {
            this.statusVersion += 1;
            try {
                const result = await this.api(`${this.number}/retry/${operation}/`, { method: 'POST' });
                this.sync = result.sync; this.publish = result.publish; this.error = '';
            } catch (error) { this.error = error.message; }
        },
        async poll() {
            clearTimeout(this.pollTimer);
            if (this.destroyed) return;
            const statusVersion = this.statusVersion;
            try {
                const result = await this.api(`${this.number}/status/`);
                if (!this.destroyed && statusVersion === this.statusVersion) {
                    this.sync = result.sync; this.publish = result.publish;
                    for (const doc of this.documents) {
                        const status = result.documents?.[doc.id];
                        if (status) Object.assign(doc, status);
                    }
                }
            } catch (error) { if (!this.destroyed) this.error = `Unable to refresh operation status: ${error.message}`; }
            if (!this.destroyed) this.pollTimer = setTimeout(() => this.poll(), 5000);
        },
        destroy() {
            this.destroyed = true;
            this.stopSplitResize();
            this._splitObserver?.disconnect();
            if (this.splitLayoutFrame !== null) cancelAnimationFrame(this.splitLayoutFrame);
            this.splitLayoutFrame = null;
            for (const timer of [this.pollTimer, this.previewTimer, this.validationTimer]) clearTimeout(timer);
            window.removeEventListener('beforeunload', this._beforeUnload);
            window.removeEventListener('popstate', this._popstate);
        },
    };
}
