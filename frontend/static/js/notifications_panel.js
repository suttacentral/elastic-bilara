function notificationsPanel() {
    return {
        notifications: [],
        selectedNotification: null,
        selectedNotificationData: null,
        loading: true,
        loadingDetail: false,
        detailError: null,
        // Filter, Sort and Pagination state
        filterText: '',
        sortMode: 'date', // 'date' or 'author'
        currentPage: 1,
        pageSize: 10,
        // Action state
        markingDone: null,
        // Toast state
        toast: {
            show: false,
            message: '',
            type: 'success'
        },
        // Settings state
        showSettingsModal: false,
        allAuthors: [],
        selectedAuthors: [],
        selectedDays: 360,
        authorSearchText: '',

        getNotificationKey(notification) {
            return notification.notification_ref || notification.commit;
        },

        getNotificationType(notification) {
            return notification.notification_type || 'commit';
        },

        isNotificationRead(notification) {
            return Boolean(notification.isRead);
        },

        getNotificationBadgeText(notification) {
            if (this.getNotificationType(notification) === 'remark') {
                return `remark ${notification.action || 'updated'}`;
            }
            return `${notification.effected_files?.length || 0} file(s)`;
        },

        getNotificationIconClass(notification) {
            return this.getNotificationType(notification) === 'remark'
                ? 'bi-chat-square-text'
                : 'bi-git';
        },

        getNotificationTitle(notification) {
            if (this.getNotificationType(notification) === 'remark') {
                return `${notification.author} changed a remark`;
            }
            return notification.author;
        },

        isCommitNotification(notification) {
            return this.getNotificationType(notification) === 'commit';
        },

        async init() {
            await this.loadPreferences();
            await this.fetchNotifications();
        },

        get filteredAuthors() {
            if (!this.authorSearchText.trim()) {
                return this.allAuthors;
            }
            const searchText = this.authorSearchText.toLowerCase();
            return this.allAuthors.filter(author =>
                author.toLowerCase().includes(searchText)
            );
        },

        get filteredNotifications() {
            let filtered = [...this.notifications];

            if (this.filterText.trim()) {
                const searchText = this.filterText.toLowerCase();
                filtered = filtered.filter(notification =>
                    notification.author?.toLowerCase().includes(searchText) ||
                    notification.commit?.toLowerCase().includes(searchText) ||
                    notification.date?.toLowerCase().includes(searchText) ||
                    notification.uid?.toLowerCase().includes(searchText) ||
                    notification.segment_id?.toLowerCase().includes(searchText)
                );
            }

            if (this.sortMode === 'author') {
                filtered.sort((a, b) => {
                    return (a.author || '').localeCompare(b.author || '');
                });
            } else {
                // Sort by date (newest first)
                filtered.sort((a, b) => {
                    const dateA = new Date(a.date || 0);
                    const dateB = new Date(b.date || 0);
                    return dateB - dateA;
                });
            }

            return filtered;
        },

        get totalPages() {
            return Math.ceil(this.filteredNotifications.length / this.pageSize);
        },

        get paginatedNotifications() {
            const start = (this.currentPage - 1) * this.pageSize;
            const end = start + this.pageSize;
            return this.filteredNotifications.slice(start, end);
        },

        get startItem() {
            if (this.filteredNotifications.length === 0) return 0;
            return (this.currentPage - 1) * this.pageSize + 1;
        },

        get endItem() {
            const end = this.currentPage * this.pageSize;
            return Math.min(end, this.filteredNotifications.length);
        },

        get uniqueAuthors() {
            const authors = new Set(this.notifications.map(n => n.author));
            return authors.size;
        },

        get totalFiles() {
            return this.notifications.reduce((sum, n) => sum + (n.effected_files?.length || 0), 0);
        },

        toggleSortMode() {
            this.sortMode = this.sortMode === 'date' ? 'author' : 'date';
            this.currentPage = 1;
        },

        async refresh() {
            this.selectedNotification = null;
            this.selectedNotificationData = null;
            this.detailError = null;
            await this.fetchNotifications();
        },

        notifyNotificationCountChanged() {
            window.dispatchEvent(new CustomEvent('notifications-updated'));
        },

        async fetchNotifications() {
            this.loading = true;
            try {
                const response = await requestWithTokenRetry(
                    'notifications/feed?include_read=true'
                );
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                if (!data.notifications) {
                    throw new Error("Invalid data format from the API");
                }
                this.notifications = data.notifications.map(notification => ({
                    ...notification,
                    isRead: Boolean(notification.is_done || notification.isRead)
                }));
            } catch (error) {
                console.error('Error fetching notifications:', error);
                this.notifications = [];
                this.showToast('Failed to load notifications', 'error');
            } finally {
                this.loading = false;
            }
        },

        async selectNotification(notification) {
            const notificationKey = this.getNotificationKey(notification);
            if (this.selectedNotification === notificationKey) return;

            this.selectedNotification = notificationKey;
            this.selectedNotificationData = notification;
            this.loadingDetail = false;
            this.detailError = null;

            if (!this.isNotificationRead(notification)) {
                await this.markAsDone(notification, {
                    silent: true,
                    preserveSelection: true,
                    skipIfAlreadyProcessing: true,
                    refreshList: false
                });
            }
        },

        formatDate(dateStr) {
            if (!dateStr) return '';
            try {
                const date = new Date(dateStr);
                return date.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } catch {
                return dateStr;
            }
        },

        async markAsDone(notification, options = {}) {
            const {
                silent = false,
                preserveSelection = false,
                skipIfAlreadyProcessing = false,
                refreshList = true
            } = options;

            if (this.markingDone && skipIfAlreadyProcessing) return;
            if (this.markingDone) return;

            const notificationKey = this.getNotificationKey(notification);
            this.markingDone = notificationKey;
            try {
                const response = await requestWithTokenRetry('notifications/done', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        notification_type: this.getNotificationType(notification),
                        notification_ref: notificationKey
                    })
                });
                const data = await response.json();

                if (data.success) {
                    notification.isRead = true;

                    if (!silent) {
                        this.showToast('Notification marked as done', 'success');
                    }

                    // Clear selection if this was the selected notification
                    if (!preserveSelection && this.selectedNotification === notificationKey) {
                        this.selectedNotification = null;
                        this.selectedNotificationData = null;
                    }

                    if (refreshList) {
                        await this.fetchNotifications();
                    }

                    this.notifyNotificationCountChanged();
                } else {
                    throw new Error(data.message || 'Failed to mark as done');
                }
            } catch (error) {
                console.error('Error marking notification as done:', error);
                if (!silent) {
                    this.showToast(error.message || 'Failed to mark as done', 'error');
                }
            } finally {
                this.markingDone = null;
            }
        },

        showToast(message, type = 'success') {
            this.toast = { show: true, message, type };
            setTimeout(() => {
                this.toast.show = false;
            }, 3000);
        },

        async loadPreferences() {
            try {
                const response = await requestWithTokenRetry('notifications/preferences');
                const data = await response.json();

                this.selectedAuthors = data.notification_authors || ['sujato'];
                this.selectedDays = data.notification_days || 360;
            } catch (error) {
                console.error('Error loading preferences:', error);
                // Use default values
                this.selectedAuthors = ['sujato'];
                this.selectedDays = 360;
            }
        },

        async loadAuthors() {
            const CACHE_KEY = 'git-authors-cache';
            const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

            try {
                // Check cache first
                const cached = localStorage.getItem(CACHE_KEY);
                if (cached) {
                    const { authors, timestamp } = JSON.parse(cached);
                    const now = Date.now();

                    // Use cached data if not expired
                    if (now - timestamp < CACHE_DURATION) {
                        this.allAuthors = authors;
                        return;
                    }
                }

                // Fetch from API
                const response = await requestWithTokenRetry('notifications/authors');
                const data = await response.json();

                this.allAuthors = data.authors || [];

                // Update cache
                localStorage.setItem(CACHE_KEY, JSON.stringify({
                    authors: this.allAuthors,
                    timestamp: Date.now()
                }));
            } catch (error) {
                console.error('Error loading authors:', error);
                this.allAuthors = [];
            }
        },

        async openSettings() {
            this.showSettingsModal = true;
            await this.loadAuthors();
        },

        toggleAllAuthors(select) {
            if (select) {
                this.selectedAuthors = [...this.allAuthors];
            } else {
                this.selectedAuthors = [];
            }
        },

        async savePreferences() {
            if (this.selectedAuthors.length === 0) {
                this.showToast('Please select at least one author', 'error');
                return;
            }

            try {
                const response = await fetch('/api/v1/notifications/preferences', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                    },
                    body: JSON.stringify({
                        notification_authors: this.selectedAuthors,
                        notification_days: this.selectedDays
                    })
                });

                if (!response.ok) {
                    throw new Error('Failed to save preferences');
                }

                this.showToast('Settings saved successfully', 'success');
                this.showSettingsModal = false;

                // Refresh notifications with new preferences
                await this.refresh();
            } catch (error) {
                console.error('Error saving preferences:', error);
                this.showToast('Failed to save settings', 'error');
                // Keep modal open on error
            }
        }
    };
}
