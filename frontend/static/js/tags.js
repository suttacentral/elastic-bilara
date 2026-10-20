function tagsManager() {
    return {
        tags: [],
        loading: true,
        editingTag: null,
        newTag: { tag: '', expansion: '', definition: '' },
        showAddForm: false,
        saving: false,
        deletingTag: null,
        loadError: '',
        syncStatus: '',
        syncState: 'idle',
        canRetrySync: false,
        retryingSync: false,
        syncTimer: null,
        syncVersion: 0,
        destroyed: false,

        async init() {
            await this.fetchTags();
            await this.checkSyncStatus();
        },

        async fetchTags() {
            this.loading = true;
            this.loadError = '';
            try {
                const response = await requestWithTokenRetry('tags/');
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || 'Failed to load tags');
                this.tags = Array.isArray(data) ? data : [];
            } catch (error) {
                console.error('Failed to fetch tags:', error);
                this.loadError = error.message;
            }
            this.loading = false;
        },

        async addTag() {
            if (this.saving || this.retryingSync) return;
            const name = this.newTag.tag.trim();
            if (!name) return;
            if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(name)) {
                alert('Tag name must be lowercase alphanumeric with hyphens only.');
                return;
            }
            if (this.tags.some(t => t.tag === name)) {
                alert(`Tag "${name}" already exists.`);
                return;
            }
            this.beginSave();
            try {
                const response = await requestWithTokenRetry('tags/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.newTag),
                });
                if (response.ok) {
                    const { _sync, ...created } = await response.json();
                    this.setSyncStatus(_sync);
                    this.tags.push(created);
                    this.newTag = { tag: '', expansion: '', definition: '' };
                    this.showAddForm = false;
                } else {
                    const err = await response.json();
                    alert(err.detail || 'Failed to add tag');
                }
            } catch (error) {
                alert('Failed to add tag: ' + error.message);
            } finally {
                this.finishSave();
            }
        },

        startEdit(tag) {
            if (this.saving) return;
            this.editingTag = { ...tag, _original: tag.tag };
        },

        cancelEdit() {
            if (this.saving) return;
            this.editingTag = null;
        },

        async saveEdit() {
            if (!this.editingTag || this.saving || this.retryingSync) return;
            const originalName = this.editingTag._original;
            this.beginSave();
            try {
                const response = await requestWithTokenRetry(`tags/${encodeURIComponent(originalName)}/`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tag: this.editingTag.tag,
                        expansion: this.editingTag.expansion,
                        definition: this.editingTag.definition,
                    }),
                });
                if (response.ok) {
                    const { _sync, ...updated } = await response.json();
                    this.setSyncStatus(_sync);
                    const idx = this.tags.findIndex(t => t.tag === originalName);
                    if (idx !== -1) this.tags[idx] = updated;
                    this.editingTag = null;
                } else {
                    const err = await response.json();
                    alert(err.detail || 'Failed to update tag');
                }
            } catch (error) {
                alert('Failed to update tag: ' + error.message);
            } finally {
                this.finishSave();
            }
        },

        async deleteTag(tagName) {
            if (this.saving || this.retryingSync) return;
            if (!confirm(`Delete tag "${tagName}"? This cannot be undone.`)) return;
            this.beginSave();
            this.deletingTag = tagName;
            try {
                const response = await requestWithTokenRetry(`tags/${encodeURIComponent(tagName)}/`, {
                    method: 'DELETE',
                });
                if (response.ok) {
                    const result = await response.json();
                    this.setSyncStatus(result._sync);
                    this.tags = this.tags.filter(t => t.tag !== tagName);
                } else {
                    const err = await response.json();
                    alert(err.detail || 'Failed to delete tag');
                }
            } catch (error) {
                alert('Failed to delete tag: ' + error.message);
            } finally {
                this.deletingTag = null;
                this.finishSave();
            }
        },
        beginSave() {
            this.saving = true;
            this.canRetrySync = false;
            this.syncVersion++;
            clearTimeout(this.syncTimer);
        },

        finishSave() {
            this.saving = false;
            // Also recover visible status after a lost response or storage error.
            void this.checkSyncStatus();
        },

        destroy() {
            this.destroyed = true;
            clearTimeout(this.syncTimer);
        },

        setSyncStatus(data) {
            if (this.destroyed) return;
            this.syncVersion++;
            clearTimeout(this.syncTimer);
            this.syncState = data?.status || 'pending';
            this.canRetrySync = Boolean(data?.can_retry);
            const messages = {
                idle: '',
                pending: 'Saved. Waiting to sync to GitHub.',
                queued: 'Saved. GitHub sync queued.',
                syncing: 'Saved. Syncing to GitHub.',
                retrying: 'Saved. GitHub sync interrupted; retrying automatically.',
                synced: 'Saved and synced to the unpublished branch on GitHub.',
                failed: 'Saved, but GitHub sync failed.',
            };
            this.syncStatus = messages[this.syncState] || 'Saved. Waiting for GitHub sync status.';
            if (data?.error && ['pending', 'retrying', 'failed'].includes(this.syncState)) {
                this.syncStatus += ' ' + data.error;
            }
            if (!['idle', 'synced', 'failed'].includes(this.syncState)) this.scheduleSyncCheck();
        },

        scheduleSyncCheck() {
            clearTimeout(this.syncTimer);
            if (!this.destroyed) this.syncTimer = setTimeout(() => this.checkSyncStatus(), 3000);
        },

        async checkSyncStatus() {
            const version = this.syncVersion;
            try {
                const res = await requestWithTokenRetry('tags/sync/');
                const data = await res.json();
                if (this.destroyed || this.saving || version !== this.syncVersion) return;
                if (!res.ok) {
                    if ([401, 403].includes(res.status)) {
                        clearTimeout(this.syncTimer);
                        this.syncStatus = 'Sign in with an active account to view GitHub sync status.';
                        this.canRetrySync = false;
                        return;
                    }
                    throw new Error(data.detail || 'Unable to check sync status');
                }
                this.setSyncStatus(data);
            } catch (error) {
                if (this.destroyed || this.saving || version !== this.syncVersion) return;
                this.syncStatus = 'Unable to check GitHub sync status. ' + error.message;
                this.scheduleSyncCheck();
            }
        },

        async retrySync() {
            if (!this.canRetrySync || this.retryingSync || this.saving) return;
            this.retryingSync = true;
            this.syncVersion++;
            clearTimeout(this.syncTimer);
            try {
                const res = await requestWithTokenRetry('tags/sync/retry/', {
                    method: 'POST', credentials: 'include',
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Unable to check sync status');
                this.setSyncStatus(data);
            } catch (error) {
                alert('Sync retry failed: ' + error.message);
            } finally {
                this.retryingSync = false;
                void this.checkSyncStatus();
            }
        },
    };
}
