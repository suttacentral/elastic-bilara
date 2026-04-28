function publicationsManager() {
    return {
        publications: [],
        loading: false,
        view: 'list', // 'list' | 'form'
        editingPub: null,
        searchQuery: '',
        filterLang: '',
        filterPublished: '',
        sortField: 'publication_number',
        sortAsc: true,
        publishing: false,

        form: {
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
        },
        formErrors: {},
        saving: false,
        toast: { show: false, message: '', type: 'success' },

        async init() {
            await this.loadPublications();
        },

        async loadPublications() {
            this.loading = true;
            try {
                const res = await requestWithTokenRetry('publications/');
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Failed to load');
                this.publications = data;
            } catch (e) {
                this.showToast('Failed to load publications: ' + e.message, 'error');
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
            this.editingPub = null;
            this.formErrors = {};
            // Get next publication number
            try {
                const res = await requestWithTokenRetry('publications/next-number/');
                const data = await res.json();
                this.resetForm();
                this.form.publication_number = data.next_number || '';
            } catch {
                this.resetForm();
            }
            this.view = 'form';
        },

        showEditForm(pub) {
            this.editingPub = pub.publication_number;
            this.formErrors = {};
            this.form = {
                publication_number: pub.publication_number,
                root_lang_iso: pub.root_lang_iso || 'pli',
                root_lang_name: pub.root_lang_name || 'Pali',
                translation_lang_iso: pub.translation_lang_iso || '',
                translation_lang_name: pub.translation_lang_name || '',
                source_url: pub.source_url || '',
                creator_uid: pub.creator_uid || '',
                creator_name: pub.creator_name || '',
                creator_github_handle: pub.creator_github_handle || '',
                text_uid: pub.text_uid || '',
                translation_title: pub.translation_title || '',
                translation_subtitle: pub.translation_subtitle || '',
                root_title: pub.root_title || '',
                creation_process: pub.creation_process || '',
                text_description: pub.text_description || '',
                is_published: pub.is_published || false,
                publication_status: pub.publication_status || '',
                license_type: pub.license_type || 'Creative Commons Zero',
                license_abbreviation: pub.license_abbreviation || 'CC0',
                license_url: pub.license_url || 'https://creativecommons.org/publicdomain/zero/1.0/',
                license_statement: pub.license_statement || '',
                first_published: pub.first_published || '',
                editions_url: pub.editions_url || '',
            };
            this.view = 'form';
        },

        resetForm() {
            this.form = {
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
        },

        validateForm() {
            this.formErrors = {};
            if (!this.form.publication_number.trim()) {
                this.formErrors.publication_number = 'Publication number is required';
            }
            return Object.keys(this.formErrors).length === 0;
        },

        async submitForm() {
            if (!this.validateForm()) return;
            this.saving = true;
            try {
                const isEdit = !!this.editingPub;
                const url = isEdit
                    ? `publications/${this.editingPub}`
                    : 'publications/';
                const method = isEdit ? 'PUT' : 'POST';

                const res = await requestWithTokenRetry(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(this.form),
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Save failed');

                this.showToast(
                    isEdit ? 'Publication updated successfully' : 'Publication created successfully',
                    'success'
                );
                await this.loadPublications();
                this.view = 'list';
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            } finally {
                this.saving = false;
            }
        },

        async deletePub(pubNumber) {
            if (!confirm(`Delete ${pubNumber}? This cannot be undone.`)) return;
            try {
                const res = await requestWithTokenRetry(`publications/${pubNumber}`, {
                    method: 'DELETE',
                    credentials: 'include',
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Delete failed');
                this.showToast(`${pubNumber} deleted`, 'success');
                await this.loadPublications();
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            }
        },

        cancelForm() {
            this.view = 'list';
            this.editingPub = null;
        },

        showToast(message, type = 'success') {
            this.toast = { show: true, message, type };
            setTimeout(() => { this.toast.show = false; }, 4000);
        },

        autoGenerateSourceUrl() {
            const uid = this.form.creator_uid;
            const lang = this.form.translation_lang_iso;
            if (uid && lang) {
                this.form.source_url = `https://github.com/suttacentral/bilara-data/tree/published/translation/${lang}/${uid}/sutta`;
            }
        },

        async publishToGitHub() {
            if (!confirm('Commit and push publication metadata to GitHub?')) return;
            this.publishing = true;
            try {
                const res = await requestWithTokenRetry('publications/publish/', {
                    method: 'POST',
                    credentials: 'include',
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Publish failed');
                this.showToast('Published to GitHub (task: ' + data.task_id + ')', 'success');
            } catch (e) {
                this.showToast('Publish error: ' + e.message, 'error');
            } finally {
                this.publishing = false;
            }
        },
    };
}
