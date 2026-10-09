function publicationDefaults() {
    return {
        publication_number: '',
        root_lang_iso: 'pli',
        root_lang_name: 'Pali',
        translation_lang_iso: '',
        translation_lang_name: '',
        source_url: '',
        creator_uid: '',
        creator_name: '',
        creator_github_handle: '',
        text_uid: '',
        translation_title: '',
        translation_subtitle: '',
        root_title: '',
        creation_process: '',
        text_description: '',
        is_published: false,
        publication_status: '',
        license_type: 'Creative Commons Zero',
        license_abbreviation: 'CC0',
        license_url: 'https://creativecommons.org/publicdomain/zero/1.0/',
        license_statement: '',
        first_published: '',
        editions_url: '',
    };
}

function publicationsManager(adminPage = false) {
    return {
        publications: [],
        isAdmin: false,
        authorized: false,
        loadError: '',
        formError: '',
        conflict: false,
        originalForm: null,
        editingAuthors: false,
        authorMode: 'single',
        authorRows: [],
        singleAuthorIndex: '',
        revision: '',
        publishTaskId: '',
        publishStatus: '',
        loadingDetail: false,
        formTrigger: null,
        loading: false,
        view: 'list', // 'list' | 'form'
        editingPub: null,
        searchQuery: '',
        filterLang: '',
        filterPublished: '',
        sortField: 'publication_number',
        sortAsc: true,
        publishing: false,

        form: publicationDefaults(),
        formErrors: {},
        saving: false,
        toast: { show: false, message: '', type: 'success' },

        async init() {
            try {
                const user = await getCurrentUser();
                const privileged = ['administrator', 'superuser'].includes(user.role);
                this.authorized = user.is_active && (privileged || user.role === 'writer');
                this.isAdmin = adminPage && privileged;
                if (!this.authorized) {
                    this.loadError = 'An active writer or administrator account is required.';
                    return;
                }
                await this.loadPublications();
            } catch (error) {
                this.loadError = error.message;
            }
        },

        errorMessage(data) {
            if (Array.isArray(data.detail)) {
                return data.detail.map(error => `${error.loc.slice(1).join('.')}: ${error.msg}`).join('; ');
            }
            return data.detail || 'Request failed';
        },

        async loadPublications() {
            this.loading = true;
            this.loadError = '';
            try {
                const res = await requestWithTokenRetry('publications/');
                const data = await res.json();
                if (!res.ok) throw new Error(this.errorMessage(data));
                this.publications = data;
            } catch (e) {
                this.loadError = 'Failed to load publications: ' + e.message;
            } finally {
                this.loading = false;
            }
        },

        get filteredPublications() {
            let list = [...this.publications];

            if (this.searchQuery) {
                const q = this.searchQuery.toLowerCase();
                list = list.filter(p =>
                    String(p.publication_number).toLowerCase().includes(q) ||
                    String(p.creator_name).toLowerCase().includes(q) ||
                    String(p.creator_uid).toLowerCase().includes(q) ||
                    String(p.translation_title).toLowerCase().includes(q) ||
                    String(p.translation_lang_name).toLowerCase().includes(q) ||
                    String(p.text_uid).toLowerCase().includes(q)
                );
            }

            if (this.filterLang) {
                list = list.filter(p => p.translation_lang_iso === this.filterLang);
            }

            if (this.filterPublished === 'true') {
                list = list.filter(p => p.is_published);
            } else if (this.filterPublished === 'false') {
                list = list.filter(p => !p.is_published);
            }

            list.sort((a, b) => {
                let va = a[this.sortField] ?? '';
                let vb = b[this.sortField] ?? '';
                // publication_number sorts by the number after scpub
                if (this.sortField === 'publication_number') {
                    const na = parseInt(String(va).substring(5), 10) || 0;
                    const nb = parseInt(String(vb).substring(5), 10) || 0;
                    return this.sortAsc ? na - nb : nb - na;
                }
                if (typeof va === 'string') va = va.toLowerCase();
                if (typeof vb === 'string') vb = vb.toLowerCase();
                if (va < vb) return this.sortAsc ? -1 : 1;
                if (va > vb) return this.sortAsc ? 1 : -1;
                return 0;
            });

            return list;
        },

        get uniqueLanguages() {
            const langs = new Set();
            this.publications.forEach(p => {
                if (p.translation_lang_iso) langs.add(p.translation_lang_iso);
            });
            return [...langs].sort();
        },

        toggleSort(field) {
            if (this.sortField === field) {
                this.sortAsc = !this.sortAsc;
            } else {
                this.sortField = field;
                this.sortAsc = true;
            }
        },

        sortIcon(field) {
            if (this.sortField !== field) return 'bi-arrow-down-up';
            return this.sortAsc ? 'bi-sort-up' : 'bi-sort-down';
        },

        async showCreateForm() {
            if (!this.isAdmin) return;
            this.resetForm();
            try {
                const res = await requestWithTokenRetry('publications/next-number/');
                const data = await res.json();
                if (!res.ok) throw new Error(this.errorMessage(data));
                this.form.publication_number = data.next_number;
                this.formTrigger = document.activeElement;
                this.view = 'form';
            } catch (error) {
                this.showToast(error.message, 'error');
            }
        },

        async showEditForm(pub) {
            if (this.loadingDetail || this.saving) return;
            this.loadingDetail = true;
            try {
                const res = await requestWithTokenRetry(`publications/${encodeURIComponent(pub.publication_number)}`);
                const data = await res.json();
                if (!res.ok) throw new Error(this.errorMessage(data));
                this.resetForm();
                this.editingPub = data.publication_number;
                this.revision = data._revision;
                for (const key of Object.keys(this.form)) {
                    if (Object.hasOwn(data, key)) {
                        this.form[key] = data[key] === false && key !== 'is_published'
                            ? '' : JSON.parse(JSON.stringify(data[key]));
                    }
                }
                this.form.first_published = data.first_published ?? data.publication_date ?? '';
                this.originalForm = JSON.parse(JSON.stringify(this.form));
                this.formTrigger = document.activeElement;
                this.view = 'form';
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                this.loadingDetail = false;
            }
        },

        resetForm() {
            this.form = publicationDefaults();
            this.editingAuthors = false;
            this.authorMode = 'single';
            this.authorRows = [];
            this.singleAuthorIndex = '';
            this.editingPub = null;
            this.originalForm = null;
            this.revision = '';
            this.formErrors = {};
            this.formError = '';
            this.conflict = false;
        },

        beginAuthorEdit() {
            if (!this.isAdmin) return;
            const uids = Array.isArray(this.form.creator_uid) ? this.form.creator_uid : [this.form.creator_uid];
            const names = Array.isArray(this.form.creator_name) ? this.form.creator_name : [this.form.creator_name];
            if (uids.length !== names.length) {
                this.formError = 'Creator UIDs and names must have matching lengths.';
                return;
            }
            this.authorRows = uids.map((uid, i) => ({ uid, name: names[i] }));
            this.authorMode = Array.isArray(this.form.creator_uid) ? 'team' : 'single';
            this.singleAuthorIndex = this.authorMode === 'single' ? '0' : '';
            this.editingAuthors = true;
            if (!this.conflict) this.formError = '';
        },

        setAuthorMode(mode) {
            if (!this.isAdmin || !this.editingAuthors) return;
            this.authorMode = mode;
            this.singleAuthorIndex = mode === 'single' && this.authorRows.length === 1 ? '0' : '';
        },

        addAuthor() {
            if (this.isAdmin && this.editingAuthors && this.authorMode === 'team') {
                this.authorRows.push({ uid: '', name: '' });
            }
        },

        removeAuthor(index) {
            if (this.isAdmin && this.editingAuthors && this.authorMode === 'team' && this.authorRows.length > 1) {
                this.authorRows.splice(index, 1);
            }
        },

        get visibleAuthorRows() {
            if (this.authorMode === 'team') return this.authorRows;
            return this.singleAuthorIndex === '' ? [] : [this.authorRows[Number(this.singleAuthorIndex)]];
        },

        authorMetadata() {
            const rows = this.visibleAuthorRows;
            if (!rows.length) throw new Error('Choose the author to retain.');
            const value = key => this.authorMode === 'single' ? rows[0][key] : rows.map(row => row[key]);
            return { creator_uid: value('uid'), creator_name: value('name') };
        },

        addEditorHandle() {
            if (!this.isAdmin) return;
            if (!Array.isArray(this.form.creator_github_handle)) this.form.creator_github_handle = [this.form.creator_github_handle];
            this.form.creator_github_handle.push('');
        },

        removeEditorHandle(index) {
            if (!this.isAdmin || !Array.isArray(this.form.creator_github_handle)) return;
            this.form.creator_github_handle.splice(index, 1);
        },

        buildCreate() {
            const authors = this.isAdmin && this.editingAuthors ? this.authorMetadata() : {};
            return { ...this.form, ...authors };
        },

        buildUpdate() {
            const writerFields = ['creator_name', 'translation_title', 'translation_subtitle', 'root_title',
                'creation_process', 'text_description', 'publication_status', 'license_type',
                'license_abbreviation', 'license_url', 'license_statement', 'first_published', 'editions_url'];
            const changes = {};
            for (const [key, value] of Object.entries(this.form)) {
                if (!this.isAdmin && !writerFields.includes(key)) continue;
                if (JSON.stringify(value) !== JSON.stringify(this.originalForm[key])) changes[key] = value;
            }
            if (this.isAdmin && this.editingAuthors) Object.assign(changes, this.authorMetadata());
            return { revision: this.revision, changes };
        },

        validateForm() {
            this.formErrors = {};
            if (!this.form.publication_number.trim()) {
                this.formErrors.publication_number = 'Publication number is required';
            }
            if (this.isAdmin && this.editingAuthors) {
                const rows = this.visibleAuthorRows;
                if (!rows.length) this.formErrors.authors = 'Choose the author to retain.';
                else if (rows.some(row => !row.uid.trim())) this.formErrors.authors = 'Every author needs a Creator UID.';
                else if (new Set(rows.map(row => row.uid)).size !== rows.length) this.formErrors.authors = 'Creator UIDs must be unique.';
            } else if (this.isAdmin && !this.editingPub) {
                const uids = Array.isArray(this.form.creator_uid) ? this.form.creator_uid : [this.form.creator_uid];
                if (!uids.length || uids.some(uid => typeof uid !== 'string' || !uid.trim())) {
                    this.formErrors.creator_uid = 'Creator UID is required for a new publication.';
                }
            }
            return Object.keys(this.formErrors).length === 0;
        },

        async submitForm() {
            if (!this.validateForm()) return;
            if (this.saving || this.conflict) return;
            this.saving = true;
            this.formError = '';
            try {
                const isEdit = !!this.editingPub;
                const url = isEdit
                    ? `publications/${encodeURIComponent(this.editingPub)}`
                    : 'publications/';
                const method = isEdit ? 'PATCH' : 'POST';

                const res = await requestWithTokenRetry(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(isEdit ? this.buildUpdate() : this.buildCreate()),
                });
                const data = await res.json();
                if (!res.ok) {
                    this.conflict = isEdit && res.status === 409;
                    throw new Error(this.errorMessage(data));
                }

                this.showToast(
                    isEdit ? 'Publication saved in both metadata files' : 'Publication created in both metadata files',
                    'success'
                );
                await this.loadPublications();
                this.view = 'list';
                this.formTrigger?.focus();
            } catch (e) {
                this.formError = e.message;
            } finally {
                this.saving = false;
            }
        },

        async deletePub(pubNumber) {
            if (!this.isAdmin) return;
            if (!confirm(`Delete ${pubNumber}? This cannot be undone.`)) return;
            try {
                const res = await requestWithTokenRetry(`publications/${encodeURIComponent(pubNumber)}`, {
                    method: 'DELETE',
                    headers: { 'If-Match': this.publications.find(pub => pub.publication_number === pubNumber)._revision },
                    credentials: 'include',
                });
                const data = await res.json();
                if (!res.ok) throw new Error(this.errorMessage(data));
                this.showToast(`${pubNumber} deleted`, 'success');
                await this.loadPublications();
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            }
        },

        cancelForm() {
            if (this.saving) return;
            this.view = 'list';
            this.editingPub = null;
            this.formTrigger?.focus();
        },

        trapFormFocus(event) {
            const controls = [...event.currentTarget.querySelectorAll('button, input, textarea, select, [tabindex]')]
                .filter(element => !element.disabled && element.tabIndex >= 0 && element.getClientRects().length);
            if (!controls.length) return;
            const first = controls[0];
            const last = controls[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        },

        showToast(message, type = 'success') {
            this.toast = { show: true, message, type };
            setTimeout(() => { this.toast.show = false; }, 4000);
        },

        autoGenerateSourceUrl() {
            const uid = this.isAdmin && this.editingAuthors
                ? (this.authorMode === 'single' ? this.visibleAuthorRows[0]?.uid : null) : this.form.creator_uid;
            const lang = this.form.translation_lang_iso;
            if (!this.editingPub && this.isAdmin && typeof uid === 'string' && uid && lang) {
                this.form.source_url = `https://github.com/suttacentral/bilara-data/tree/published/translation/${lang}/${uid}/sutta`;
            }
        },

        async publishToGitHub() {
            if (!this.isAdmin || this.publishing) return;
            if (!confirm('Commit and push publication metadata to GitHub?')) return;
            this.publishing = true;
            try {
                const res = await requestWithTokenRetry('publications/publish/', {
                    method: 'POST',
                    credentials: 'include',
                });
                const data = await res.json();
                if (!res.ok) throw new Error(this.errorMessage(data));
                this.publishTaskId = data.task_id;
                this.publishStatus = 'GitHub submission queued. Check its status below.';
            } catch (e) {
                this.showToast('Publish error: ' + e.message, 'error');
            } finally {
                this.publishing = false;
            }
        },

        async checkPublishStatus() {
            if (!this.publishTaskId) return;
            try {
                const res = await requestWithTokenRetry(`tasks/${encodeURIComponent(this.publishTaskId)}/`);
                const data = await res.json();
                if (!res.ok) throw new Error(this.errorMessage(data));
                if (data.status === 'SUCCESS' && data.result === true) {
                    this.publishStatus = 'Both metadata files were submitted to the unpublished branch on GitHub.';
                    return;
                }
                if (data.status === 'FAILURE' || data.status === 'SUCCESS') {
                    this.publishStatus = 'GitHub submission failed: ' + (data.error || 'No files were submitted.');
                    return;
                }
                this.publishStatus = 'GitHub submission: ' + data.status;
            } catch (error) {
                this.publishStatus = error.message;
            }
        },
    };
}
