function tagsManager() {
    return {
        tags: [],
        loading: true,
        editingTag: null,
        newTag: { tag: '', expansion: '', definition: '' },
        showAddForm: false,

        async init() {
            await this.fetchTags();
        },

        async fetchTags() {
            this.loading = true;
            try {
                const response = await requestWithTokenRetry('tags/');
                const data = await response.json();
                this.tags = Array.isArray(data) ? data : [];
            } catch (error) {
                console.error('Failed to fetch tags:', error);
                this.tags = [];
            }
            this.loading = false;
        },

        async addTag() {
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
            try {
                const response = await requestWithTokenRetry('tags/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.newTag),
                });
                if (response.ok) {
                    const created = await response.json();
                    this.tags.push(created);
                    this.newTag = { tag: '', expansion: '', definition: '' };
                    this.showAddForm = false;
                } else {
                    const err = await response.json();
                    alert(err.detail || 'Failed to add tag');
                }
            } catch (error) {
                alert('Failed to add tag: ' + error.message);
            }
        },

        startEdit(tag) {
            this.editingTag = { ...tag, _original: tag.tag };
        },

        cancelEdit() {
            this.editingTag = null;
        },

        async saveEdit() {
            if (!this.editingTag) return;
            const originalName = this.editingTag._original;
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
                    const updated = await response.json();
                    const idx = this.tags.findIndex(t => t.tag === originalName);
                    if (idx !== -1) this.tags[idx] = updated;
                    this.editingTag = null;
                } else {
                    const err = await response.json();
                    alert(err.detail || 'Failed to update tag');
                }
            } catch (error) {
                alert('Failed to update tag: ' + error.message);
            }
        },

        async deleteTag(tagName) {
            if (!confirm(`Delete tag "${tagName}"? This cannot be undone.`)) return;
            try {
                const response = await requestWithTokenRetry(`tags/${encodeURIComponent(tagName)}/`, {
                    method: 'DELETE',
                });
                if (response.ok) {
                    this.tags = this.tags.filter(t => t.tag !== tagName);
                } else {
                    const err = await response.json();
                    alert(err.detail || 'Failed to delete tag');
                }
            } catch (error) {
                alert('Failed to delete tag: ' + error.message);
            }
        },
    };
}
