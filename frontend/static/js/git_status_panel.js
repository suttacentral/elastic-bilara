function gitStatusPanel() {
    return {
        files: [],
        selectedFile: null,
        selectedFileData: null,
        loading: true,
        publishing: false,
        loadingDiff: false,
        diffContent: '',
        diffError: null,
        stats: {
            modified: 0,
            untracked: 0,
            deleted: 0,
            staged: 0
        },
        // Discard related state
        showConfirmModal: false,
        fileToDiscard: null,
        discarding: false,
        skipDiscardConfirm: false,
        // Edit related state
        showEditModal: false,
        fileToEdit: null,
        skipEditConfirm: false,
        // Publish related state
        showPublishModal: false,
        fileToPublish: null,
        publishingFile: null,
        skipPublishConfirm: false,
        toast: {
            show: false,
            message: '',
            type: 'success'
        },
        // Filter, Sort and Pagination state
        filterText: '',
        sortMode: 'default', // 'default' or 'date'
        currentPage: 1,
        pageSize: 20,
        // User role state
        userInfo: null,
        isAdmin: false,
        username: '',
        // Multi-selection state
        selectedFiles: [],
        batchPublishing: false,
        // Performance optimization: diff cache
        diffCache: new Map(),

        async init() {
            // Parse URL parameters
            const urlParams = new URLSearchParams(window.location.search);
            const filterParam = urlParams.get('filter');

            // Set initial filter text from URL parameter if present
            if (filterParam) {
                this.filterText = decodeURIComponent(filterParam);
            }

            await this.loadUserInfo();
            await this.fetchStatus();
        },

        async loadUserInfo() {
            try {
                const userInfo = getUserInfo();
                await userInfo.getRole();
                this.isAdmin = userInfo.isAdmin;
                this.username = userInfo.username;
            } catch (error) {
                console.error('Error loading user info:', error);
                this.isAdmin = false;
                this.username = '';
            }
        },

        get filteredFiles() {
            let filtered = [...this.files];

            if (!this.isAdmin && this.username) {
                // For non-admin users, only show files that contain their username in the path
                filtered = filtered.filter(file =>
                    file.path.toLowerCase().includes(this.username.toLowerCase())
                );
            }

            if (this.filterText.trim()) {
                const searchText = this.filterText.toLowerCase();
                filtered = filtered.filter(file =>
                    file.path.toLowerCase().includes(searchText)
                );
            }

            if (this.sortMode === 'date') {
                filtered.sort((a, b) => {
                    const dateA = new Date(a.modified_time || 0);
                    const dateB = new Date(b.modified_time || 0);
                    return dateB - dateA; // newest first
                });
            } else {
                const statusOrder = {
                    'staged_new': 1,
                    'staged_modified': 2,
                    'staged_deleted': 3,
                    'modified': 4,
                    'untracked': 5,
                    'deleted': 6
                };
                filtered.sort((a, b) => {
                    const orderA = statusOrder[a.status] || 99;
                    const orderB = statusOrder[b.status] || 99;
                    if (orderA !== orderB) return orderA - orderB;
                    return a.path.localeCompare(b.path);
                });
            }

            return filtered;
        },

        get totalPages() {
            return Math.ceil(this.filteredFiles.length / this.pageSize);
        },

        get paginatedFiles() {
            const start = (this.currentPage - 1) * this.pageSize;
            const end = start + this.pageSize;
            return this.filteredFiles.slice(start, end);
        },

        get startItem() {
            if (this.filteredFiles.length === 0) return 0;
            return (this.currentPage - 1) * this.pageSize + 1;
        },

        get endItem() {
            const end = this.currentPage * this.pageSize;
            return Math.min(end, this.filteredFiles.length);
        },

        setSortMode(mode) {
            if (this.sortMode !== mode) {
                this.sortMode = mode;
                this.currentPage = 1; // Reset to first page when sorting changes
            }
        },

        async refresh() {
            this.selectedFile = null;
            this.diffContent = '';
            this.diffError = null;
            this.selectedFiles = []; // Clear selection on refresh
            this.diffCache.clear(); // Clear diff cache on refresh
            await this.fetchStatus();
        },

        async fetchStatus() {
            this.loading = true;
            try {
                const response = await fetch('/api/v1/git/status', {
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                this.files = data.files;
                this.calculateStats();
            } catch (error) {
                console.error('Error fetching git status:', error);
                this.files = [];
            } finally {
                this.loading = false;
            }
        },

        calculateStats() {
            this.stats = {
                modified: 0,
                untracked: 0,
                deleted: 0,
                staged: 0
            };

            for (const file of this.files) {
                if (file.status === 'modified') this.stats.modified++;
                else if (file.status === 'untracked') this.stats.untracked++;
                else if (file.status === 'deleted') this.stats.deleted++;
                else if (file.status.startsWith('staged')) this.stats.staged++;
            }
        },

        async selectFile(file) {
            if (this.selectedFile === file.path) return;

            this.selectedFile = file.path;
            this.selectedFileData = file;

            // Check cache first (performance optimization)
            if (this.diffCache.has(file.path)) {
                this.diffContent = this.diffCache.get(file.path);
                this.diffError = null;
                return;
            }

            this.loadingDiff = true;
            this.diffContent = '';
            this.diffError = null;

            try {
                const response = await fetch(`/api/v1/git/diff/${encodeURIComponent(file.path)}`, {
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                    }
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                // Cache the diff for future use
                this.diffCache.set(file.path, data.diff);
                this.diffContent = data.diff;
            } catch (error) {
                console.error('Error fetching diff:', error);
                this.diffError = error.message;
            } finally {
                this.loadingDiff = false;
            }
        },

        getStatusIcon(status) {
            const icons = {
                'modified': 'bi-pencil-fill',
                'untracked': 'bi-plus-circle-fill',
                'deleted': 'bi-trash-fill',
                'staged_new': 'bi-check-circle-fill',
                'staged_modified': 'bi-check-circle-fill',
                'staged_deleted': 'bi-check-circle-fill'
            };
            return icons[status] || 'bi-question-circle';
        },

        getStatusClass(status) {
            if (status.startsWith('staged')) return 'staged';
            return status;
        },

        formatStatus(status) {
            const labels = {
                'modified': 'M',
                'untracked': 'U',
                'deleted': 'D',
                'staged_new': 'A',
                'staged_modified': 'SM',
                'staged_deleted': 'SD'
            };
            return labels[status] || status;
        },

        parseDiff(diff) {
            if (!diff) return [];

            const lines = diff.split('\n');
            return lines.map(line => {
                let type = 'context';

                if (line.startsWith('+++') || line.startsWith('---') ||
                    line.startsWith('@@') || line.startsWith('diff ') ||
                    line.startsWith('index ')) {
                    return { text: '', type: '' };
                } else if (line.startsWith('+')) {
                    type = 'addition';
                } else if (line.startsWith('-')) {
                    type = 'deletion';
                }

                return { text: line, type };
            });
        },

        showDiscardConfirm(file) {
            this.fileToDiscard = file;
            if (localStorage.getItem('skipDiscardConfirm') === 'true') {
                this.confirmDiscard();
                return;
            }
            this.showConfirmModal = true;
        },

        closeConfirmModal() {
            this.showConfirmModal = false;
            this.fileToDiscard = null;
            this.skipDiscardConfirm = false;
        },

        async confirmDiscard() {
            if (!this.fileToDiscard || this.discarding) return;

            if (this.skipDiscardConfirm) {
                localStorage.setItem('skipDiscardConfirm', 'true');
            }

            this.discarding = true;
            try {
                const response = await fetch('/api/v1/git/discard', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ file_path: this.fileToDiscard.path })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                }

                const data = await response.json();

                this.showToast(data.message, 'success');

                // Clear cache for the discarded file
                this.diffCache.delete(this.fileToDiscard.path);

                // Clear selection if discarded file was selected
                if (this.selectedFile === this.fileToDiscard.path) {
                    this.selectedFile = null;
                    this.diffContent = '';
                    this.diffError = null;
                }

                // Refresh file list
                await this.fetchStatus();
            } catch (error) {
                console.error('Error discarding changes:', error);
                this.showToast(error.message, 'error');
            } finally {
                this.discarding = false;
                this.closeConfirmModal();
            }
        },

        showToast(message, type = 'success') {
            this.toast = { show: true, message, type };
            setTimeout(() => {
                this.toast.show = false;
            }, 3000);
        },

        showEditConfirm(file) {
            this.fileToEdit = file;
            if (localStorage.getItem('skipEditConfirm') === 'true') {
                this.confirmEdit();
                return;
            }
            this.showEditModal = true;
        },

        closeEditModal() {
            this.showEditModal = false;
            this.fileToEdit = null;
            this.skipEditConfirm = false;
        },

        async confirmEdit() {
            if (this.skipEditConfirm) {
                localStorage.setItem('skipEditConfirm', 'true');
            }

            // if (!this.fileToEdit || !this.fileToEdit.path) return;
            // console.log(`Navigating to edit file: ${this.fileToEdit.path}`);
            // window.location.href = `/translation?path=${encodeURIComponent(this.fileToEdit.path)}`;

            //this.fileToEdit.pathd的样例：translation/en/sujato/sutta/an/an1/an1.616-627_translation-en-sujato.json
            // let elementFullName = this.fileToEdit.path || "";
            // let elementMuid = elementFullName.split('/').pop().split('_')[1].split('.')[0] || "";
            // let elementPrefix = elementFullName.split('/').pop().split('_')[0] || "";
            // console.log(`Calculated values: ${elementFullName}, ${elementMuid}, ${elementPrefix}`);

            // const response = await requestWithTokenRetry(`projects/${elementFullName}/source/`);
            // const { muid: source } = await response.json();
            // const muid = elementMuid === source ? "" : elementMuid;
            // window.open(`/translation?prefix=${elementPrefix}&muid=${muid}&source=${source}`, '_blank');
            // this.closeEditModal();

            if (!this.fileToEdit || !this.fileToEdit.path) return;

            try {
                const elementFullName = this.fileToEdit.path;
                const fileName = elementFullName.split('/').filter(Boolean).pop();

                if (!fileName) {
                    console.error('Invalid file path: unable to extract filename');
                    this.showToast('Invalid file path', 'error');
                    return;
                }

                const elementMuid = getMuid(elementFullName);
                const elementPrefix = getPrefix(fileName);

                if (!elementPrefix) {
                    console.error('Invalid file name format: unable to extract prefix');
                    this.showToast('Invalid file name format', 'error');
                    return;
                }

                const response = await requestWithTokenRetry(`projects/${elementFullName}/source/`);

                if (!response.ok) {
                    throw new Error(`Failed to fetch source: ${response.status}`);
                }

                const { muid: source } = await response.json();
                const muid = elementMuid === source ? "" : elementMuid;

                window.open(`/translation?prefix=${elementPrefix}&muid=${muid}&source=${source}`, '_blank');
                this.closeEditModal();
            } catch (error) {
                console.error('Error opening file for edit:', error);
                this.showToast(`Failed to open file: ${error.message}`, 'error');
            }
        },

        showPublishConfirm(file) {
            this.fileToPublish = file;
            if (localStorage.getItem('skipPublishConfirm') === 'true') {
                this.confirmPublish();
                return;
            }
            this.showPublishModal = true;
        },

        closePublishModal() {
            this.showPublishModal = false;
            this.fileToPublish = null;
            this.skipPublishConfirm = false;
        },

        async confirmPublish() {
            if (this.skipPublishConfirm) {
                localStorage.setItem('skipPublishConfirm', 'true');
            }

            if (!this.fileToPublish) return;
            await this.publishFile(this.fileToPublish);
            this.closePublishModal();
        },

        async publishFile(file) {
            if (this.publishing || this.publishingFile) return;
            this.publishing = true;
            this.publishingFile = file.path;

            try {
                const response = await requestWithTokenRetry('pr/', {
                    credentials: 'include',
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ paths: [file.path] })
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail?.error || errorData.detail || `HTTP error! status: ${response.status}`);
                }
                const { task_id: taskID } = await response.json();

                if (!taskID) {
                    throw new Error('Failed to schedule pull request');
                }
                this.showToast(`Pull Request scheduled for: ${file.path}`, 'success');
                setTimeout(async () => {
                    await this.fetchStatus();
                }, 1000);
            } catch (error) {
                console.error('Error publishing file:', error);
                this.showToast(error.message, 'error');
            } finally {
                this.publishingFile = null;
                this.publishing = false;
            }
        },

        // Multi-selection computed properties
        get isAllSelected() {
            return this.filteredFiles.length > 0 &&
                   this.filteredFiles.every(file => this.selectedFiles.includes(file.path));
        },

        get isPartiallySelected() {
            const selectedCount = this.filteredFiles.filter(file =>
                this.selectedFiles.includes(file.path)
            ).length;
            return selectedCount > 0 && selectedCount < this.filteredFiles.length;
        },

        // Multi-selection methods
        isFileSelected(filePath) {
            return this.selectedFiles.includes(filePath);
        },

        toggleFileSelection(filePath) {
            const index = this.selectedFiles.indexOf(filePath);
            if (index === -1) {
                this.selectedFiles.push(filePath);
            } else {
                this.selectedFiles.splice(index, 1);
            }
        },

        toggleSelectAll() {
            if (this.isAllSelected) {
                // Deselect all filtered files
                this.selectedFiles = this.selectedFiles.filter(
                    path => !this.filteredFiles.some(file => file.path === path)
                );
            } else {
                // Select all filtered files
                const filteredPaths = this.filteredFiles.map(file => file.path);
                const newSelection = [...this.selectedFiles];
                filteredPaths.forEach(path => {
                    if (!newSelection.includes(path)) {
                        newSelection.push(path);
                    }
                });
                this.selectedFiles = newSelection;
            }
        },

        clearSelection() {
            this.selectedFiles = [];
        },

        async batchPublish() {
            if (this.selectedFiles.length === 0) {
                this.showToast('Please select at least one file to publish', 'error');
                return;
            }

            // Group files by project head (same logic as backend get_project_head)
            // so that each /pr/ call only contains files from the same project.
            const groupByProject = (paths) => {
                const groups = {};
                for (const path of paths) {
                    const parts = path.split('/').filter(Boolean);
                    const dirParts = parts.slice(0, -1);
                    let head;
                    if (dirParts.length === 6 && !dirParts[dirParts.length - 2].includes(dirParts[dirParts.length - 3])) {
                        head = dirParts.slice(0, -1).join('_');
                    } else if (dirParts.length > 6 && dirParts[dirParts.length - 3] && dirParts[dirParts.length - 2].includes(dirParts[dirParts.length - 3])) {
                        head = dirParts.slice(0, -2).join('_');
                    } else {
                        head = dirParts.join('_');
                    }
                    if (!groups[head]) groups[head] = [];
                    groups[head].push(path);
                }
                return Object.values(groups);
            };

            const fileGroups = groupByProject([...this.selectedFiles]);
            const totalGroups = fileGroups.length;

            this.batchPublishing = true;
            let successCount = 0;
            let errorMessages = [];

            try {
                for (const groupPaths of fileGroups) {
                    try {
                        const response = await requestWithTokenRetry('pr/', {
                            credentials: 'include',
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ paths: groupPaths })
                        });
                        if (!response.ok) {
                            const errorData = await response.json();
                            errorMessages.push(errorData.detail?.error || errorData.detail || `HTTP ${response.status}`);
                        } else {
                            successCount++;
                        }
                    } catch (err) {
                        errorMessages.push(err.message);
                    }
                }

                if (errorMessages.length === 0) {
                    this.showToast(
                        `Pull Request${totalGroups > 1 ? 's' : ''} scheduled for ${this.selectedFiles.length} file(s) across ${totalGroups} project${totalGroups > 1 ? 's' : ''}.`,
                        'success'
                    );
                    this.clearSelection();
                    setTimeout(async () => { await this.fetchStatus(); }, 2000);
                } else {
                    const succeeded = successCount > 0 ? `${successCount}/${totalGroups} succeeded. ` : '';
                    this.showToast(`${succeeded}Errors: ${errorMessages.join('; ')}`, 'error');
                }
            } finally {
                this.batchPublishing = false;
            }
        },
        showToast(message, type = 'success') {
            this.toast = { show: true, message, type };
            setTimeout(() => {
                this.toast.show = false;
            }, 3000);
        }
    };
}