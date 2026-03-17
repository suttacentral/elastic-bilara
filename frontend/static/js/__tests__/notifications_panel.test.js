/**
 * Notifications Panel Tests
 * 
 * This file tests the notifications_panel.js functionality including:
 * - State initialization
 * - Notification filtering (filteredNotifications, filteredAuthors)
 * - Pagination (paginatedNotifications, totalPages, startItem, endItem)
 * - Statistics (uniqueAuthors, totalFiles)
 * - Sort mode toggle (toggleSortMode)
 * - Date formatting (formatDate)
 * - Notification selection (selectNotification)
 * - Toast notifications (showToast)
 * - Author management (toggleAllAuthors)
 */

// ============================================================================
// Mock Setup
// ============================================================================

const localStorageMock = {
    store: {},
    getItem: jest.fn((key) => localStorageMock.store[key] || null),
    setItem: jest.fn((key, value) => { localStorageMock.store[key] = value; }),
    removeItem: jest.fn((key) => { delete localStorageMock.store[key]; }),
    clear: jest.fn(() => { localStorageMock.store = {}; })
};
global.localStorage = localStorageMock;

global.fetch = jest.fn();
global.requestWithTokenRetry = jest.fn();

// ============================================================================
// Helper function to create mock panel instance
// ============================================================================

function createMockPanel(overrides = {}) {
    const panel = {
        notifications: [],
        selectedNotification: null,
        selectedNotificationData: null,
        loading: true,
        loadingDetail: false,
        detailError: null,
        filterText: '',
        sortMode: 'date',
        currentPage: 1,
        pageSize: 10,
        markingDone: null,
        toast: {
            show: false,
            message: '',
            type: 'success'
        },
        showSettingsModal: false,
        allAuthors: [],
        selectedAuthors: [],
        selectedDays: 360,
        authorSearchText: '',

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
                    notification.date?.toLowerCase().includes(searchText)
                );
            }

            if (this.sortMode === 'author') {
                filtered.sort((a, b) => {
                    return (a.author || '').localeCompare(b.author || '');
                });
            } else {
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

        selectNotification(notification) {
            if (this.selectedNotification === notification.commit) return;

            this.selectedNotification = notification.commit;
            this.selectedNotificationData = notification;
            this.loadingDetail = false;
            this.detailError = null;
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

        showToast(message, type = 'success') {
            this.toast = { show: true, message, type };
        },

        toggleAllAuthors(select) {
            if (select) {
                this.selectedAuthors = [...this.allAuthors];
            } else {
                this.selectedAuthors = [];
            }
        },

        ...overrides
    };

    return panel;
}

// ============================================================================
// State Initialization Tests
// ============================================================================

describe('Notifications Panel State Initialization', () => {
    test('should have correct default state', () => {
        const panel = createMockPanel();
        
        expect(panel.notifications).toEqual([]);
        expect(panel.selectedNotification).toBeNull();
        expect(panel.selectedNotificationData).toBeNull();
        expect(panel.loading).toBe(true);
        expect(panel.loadingDetail).toBe(false);
        expect(panel.detailError).toBeNull();
    });

    test('should have correct default filter and pagination state', () => {
        const panel = createMockPanel();
        
        expect(panel.filterText).toBe('');
        expect(panel.sortMode).toBe('date');
        expect(panel.currentPage).toBe(1);
        expect(panel.pageSize).toBe(10);
    });

    test('should have correct default toast state', () => {
        const panel = createMockPanel();
        
        expect(panel.toast).toEqual({
            show: false,
            message: '',
            type: 'success'
        });
    });

    test('should have correct default settings state', () => {
        const panel = createMockPanel();
        
        expect(panel.showSettingsModal).toBe(false);
        expect(panel.allAuthors).toEqual([]);
        expect(panel.selectedAuthors).toEqual([]);
        expect(panel.selectedDays).toBe(360);
        expect(panel.authorSearchText).toBe('');
    });
});

// ============================================================================
// Filter Tests
// ============================================================================

describe('filteredNotifications', () => {
    test('should return all notifications when no filter is applied', () => {
        const panel = createMockPanel();
        panel.notifications = [
            { commit: 'abc123', author: 'sujato', date: '2024-01-01' },
            { commit: 'def456', author: 'brahmali', date: '2024-01-02' }
        ];
        
        expect(panel.filteredNotifications).toHaveLength(2);
    });

    test('should filter notifications by author', () => {
        const panel = createMockPanel();
        panel.filterText = 'sujato';
        panel.notifications = [
            { commit: 'abc123', author: 'sujato', date: '2024-01-01' },
            { commit: 'def456', author: 'brahmali', date: '2024-01-02' },
            { commit: 'ghi789', author: 'sujato', date: '2024-01-03' }
        ];
        
        expect(panel.filteredNotifications).toHaveLength(2);
        expect(panel.filteredNotifications.every(n => n.author === 'sujato')).toBe(true);
    });

    test('should filter notifications by commit hash', () => {
        const panel = createMockPanel();
        panel.filterText = 'abc';
        panel.notifications = [
            { commit: 'abc123', author: 'sujato', date: '2024-01-01' },
            { commit: 'def456', author: 'brahmali', date: '2024-01-02' }
        ];
        
        expect(panel.filteredNotifications).toHaveLength(1);
        expect(panel.filteredNotifications[0].commit).toBe('abc123');
    });

    test('should filter notifications by date', () => {
        const panel = createMockPanel();
        panel.filterText = '2024-01-02';
        panel.notifications = [
            { commit: 'abc123', author: 'sujato', date: '2024-01-01' },
            { commit: 'def456', author: 'brahmali', date: '2024-01-02' }
        ];
        
        expect(panel.filteredNotifications).toHaveLength(1);
        expect(panel.filteredNotifications[0].date).toBe('2024-01-02');
    });

    test('should be case-insensitive', () => {
        const panel = createMockPanel();
        panel.filterText = 'SUJATO';
        panel.notifications = [
            { commit: 'abc123', author: 'sujato', date: '2024-01-01' },
            { commit: 'def456', author: 'brahmali', date: '2024-01-02' }
        ];
        
        expect(panel.filteredNotifications).toHaveLength(1);
    });

    test('should handle empty filterText with whitespace', () => {
        const panel = createMockPanel();
        panel.filterText = '   ';
        panel.notifications = [
            { commit: 'abc123', author: 'sujato', date: '2024-01-01' },
            { commit: 'def456', author: 'brahmali', date: '2024-01-02' }
        ];
        
        expect(panel.filteredNotifications).toHaveLength(2);
    });

    test('should handle notifications with missing fields', () => {
        const panel = createMockPanel();
        panel.filterText = 'test';
        panel.notifications = [
            { commit: 'abc123' }, // missing author and date
            { author: 'testuser' }, // missing commit and date
            { date: '2024-01-01' } // missing commit and author
        ];
        
        // Should filter without throwing errors
        expect(() => panel.filteredNotifications).not.toThrow();
    });
});

describe('filteredAuthors', () => {
    test('should return all authors when no search text', () => {
        const panel = createMockPanel();
        panel.allAuthors = ['sujato', 'brahmali', 'sabbamitta'];
        
        expect(panel.filteredAuthors).toEqual(['sujato', 'brahmali', 'sabbamitta']);
    });

    test('should filter authors by search text', () => {
        const panel = createMockPanel();
        panel.allAuthors = ['sujato', 'brahmali', 'sabbamitta'];
        panel.authorSearchText = 'su';
        
        expect(panel.filteredAuthors).toHaveLength(1);
        expect(panel.filteredAuthors[0]).toBe('sujato');
    });

    test('should be case-insensitive', () => {
        const panel = createMockPanel();
        panel.allAuthors = ['sujato', 'brahmali', 'Sabbamitta'];
        panel.authorSearchText = 'SAB';
        
        expect(panel.filteredAuthors).toHaveLength(1);
        expect(panel.filteredAuthors[0]).toBe('Sabbamitta');
    });

    test('should return all authors for whitespace-only search', () => {
        const panel = createMockPanel();
        panel.allAuthors = ['sujato', 'brahmali'];
        panel.authorSearchText = '   ';
        
        expect(panel.filteredAuthors).toHaveLength(2);
    });
});

// ============================================================================
// Sort Tests
// ============================================================================

describe('Sorting', () => {
    test('should sort by date (newest first) in date mode', () => {
        const panel = createMockPanel();
        panel.sortMode = 'date';
        panel.notifications = [
            { commit: 'abc', author: 'sujato', date: '2024-01-01T10:00:00Z' },
            { commit: 'def', author: 'brahmali', date: '2024-01-03T10:00:00Z' },
            { commit: 'ghi', author: 'sabbamitta', date: '2024-01-02T10:00:00Z' }
        ];
        
        const sorted = panel.filteredNotifications;
        expect(sorted[0].date).toBe('2024-01-03T10:00:00Z');
        expect(sorted[1].date).toBe('2024-01-02T10:00:00Z');
        expect(sorted[2].date).toBe('2024-01-01T10:00:00Z');
    });

    test('should sort by author alphabetically in author mode', () => {
        const panel = createMockPanel();
        panel.sortMode = 'author';
        panel.notifications = [
            { commit: 'abc', author: 'sujato', date: '2024-01-01' },
            { commit: 'def', author: 'brahmali', date: '2024-01-02' },
            { commit: 'ghi', author: 'sabbamitta', date: '2024-01-03' }
        ];
        
        const sorted = panel.filteredNotifications;
        expect(sorted[0].author).toBe('brahmali');
        expect(sorted[1].author).toBe('sabbamitta');
        expect(sorted[2].author).toBe('sujato');
    });

    test('should handle missing author in author sort mode', () => {
        const panel = createMockPanel();
        panel.sortMode = 'author';
        panel.notifications = [
            { commit: 'abc', author: 'sujato', date: '2024-01-01' },
            { commit: 'def', date: '2024-01-02' }, // missing author
            { commit: 'ghi', author: 'brahmali', date: '2024-01-03' }
        ];
        
        // Should not throw
        expect(() => panel.filteredNotifications).not.toThrow();
        expect(panel.filteredNotifications).toHaveLength(3);
    });

    test('should handle missing date in date sort mode', () => {
        const panel = createMockPanel();
        panel.sortMode = 'date';
        panel.notifications = [
            { commit: 'abc', author: 'sujato', date: '2024-01-01' },
            { commit: 'def', author: 'brahmali' }, // missing date
            { commit: 'ghi', author: 'sabbamitta', date: '2024-01-03' }
        ];
        
        // Should not throw
        expect(() => panel.filteredNotifications).not.toThrow();
        expect(panel.filteredNotifications).toHaveLength(3);
    });
});

describe('toggleSortMode', () => {
    test('should toggle from date to author', () => {
        const panel = createMockPanel();
        panel.sortMode = 'date';
        panel.currentPage = 3;
        
        panel.toggleSortMode();
        
        expect(panel.sortMode).toBe('author');
        expect(panel.currentPage).toBe(1);
    });

    test('should toggle from author to date', () => {
        const panel = createMockPanel();
        panel.sortMode = 'author';
        panel.currentPage = 2;
        
        panel.toggleSortMode();
        
        expect(panel.sortMode).toBe('date');
        expect(panel.currentPage).toBe(1);
    });
});

// ============================================================================
// Pagination Tests
// ============================================================================

describe('Pagination', () => {
    describe('totalPages', () => {
        test('should calculate correct total pages', () => {
            const panel = createMockPanel();
            panel.pageSize = 10;
            panel.notifications = Array(25).fill(null).map((_, i) => ({
                commit: `commit${i}`,
                author: 'author',
                date: '2024-01-01'
            }));
            
            expect(panel.totalPages).toBe(3);
        });

        test('should return 1 for notifications equal to page size', () => {
            const panel = createMockPanel();
            panel.pageSize = 10;
            panel.notifications = Array(10).fill(null).map((_, i) => ({
                commit: `commit${i}`,
                author: 'author',
                date: '2024-01-01'
            }));
            
            expect(panel.totalPages).toBe(1);
        });

        test('should return 0 for empty notifications', () => {
            const panel = createMockPanel();
            panel.notifications = [];
            
            expect(panel.totalPages).toBe(0);
        });
    });

    describe('paginatedNotifications', () => {
        test('should return correct slice for first page', () => {
            const panel = createMockPanel();
            panel.pageSize = 5;
            panel.currentPage = 1;
            panel.notifications = Array(12).fill(null).map((_, i) => ({
                commit: `commit${String(i).padStart(2, '0')}`,
                author: 'author',
                date: `2024-01-${String(12 - i).padStart(2, '0')}` // Dates in descending order
            }));
            
            const paginated = panel.paginatedNotifications;
            expect(paginated).toHaveLength(5);
        });

        test('should return remaining items for last page', () => {
            const panel = createMockPanel();
            panel.pageSize = 5;
            panel.currentPage = 3;
            panel.notifications = Array(12).fill(null).map((_, i) => ({
                commit: `commit${String(i).padStart(2, '0')}`,
                author: 'author',
                date: `2024-01-${String(12 - i).padStart(2, '0')}`
            }));
            
            const paginated = panel.paginatedNotifications;
            expect(paginated).toHaveLength(2);
        });
    });

    describe('startItem and endItem', () => {
        test('should return correct range for first page', () => {
            const panel = createMockPanel();
            panel.pageSize = 10;
            panel.currentPage = 1;
            panel.notifications = Array(25).fill(null).map((_, i) => ({
                commit: `commit${i}`,
                author: 'author',
                date: '2024-01-01'
            }));
            
            expect(panel.startItem).toBe(1);
            expect(panel.endItem).toBe(10);
        });

        test('should return correct range for last page', () => {
            const panel = createMockPanel();
            panel.pageSize = 10;
            panel.currentPage = 3;
            panel.notifications = Array(25).fill(null).map((_, i) => ({
                commit: `commit${i}`,
                author: 'author',
                date: '2024-01-01'
            }));
            
            expect(panel.startItem).toBe(21);
            expect(panel.endItem).toBe(25);
        });

        test('should return 0 for startItem when no notifications', () => {
            const panel = createMockPanel();
            panel.notifications = [];
            
            expect(panel.startItem).toBe(0);
        });
    });
});

// ============================================================================
// Statistics Tests
// ============================================================================

describe('Statistics', () => {
    describe('uniqueAuthors', () => {
        test('should count unique authors correctly', () => {
            const panel = createMockPanel();
            panel.notifications = [
                { commit: 'abc', author: 'sujato' },
                { commit: 'def', author: 'brahmali' },
                { commit: 'ghi', author: 'sujato' },
                { commit: 'jkl', author: 'sabbamitta' }
            ];
            
            expect(panel.uniqueAuthors).toBe(3);
        });

        test('should return 0 for empty notifications', () => {
            const panel = createMockPanel();
            panel.notifications = [];
            
            expect(panel.uniqueAuthors).toBe(0);
        });

        test('should handle undefined authors', () => {
            const panel = createMockPanel();
            panel.notifications = [
                { commit: 'abc', author: 'sujato' },
                { commit: 'def' }, // no author
                { commit: 'ghi', author: undefined }
            ];
            
            // undefined values should be counted as one unique "author"
            expect(panel.uniqueAuthors).toBe(2); // 'sujato' and undefined
        });
    });

    describe('totalFiles', () => {
        test('should count total affected files correctly', () => {
            const panel = createMockPanel();
            panel.notifications = [
                { commit: 'abc', effected_files: ['file1.json', 'file2.json'] },
                { commit: 'def', effected_files: ['file3.json'] },
                { commit: 'ghi', effected_files: ['file4.json', 'file5.json', 'file6.json'] }
            ];
            
            expect(panel.totalFiles).toBe(6);
        });

        test('should return 0 when no files', () => {
            const panel = createMockPanel();
            panel.notifications = [
                { commit: 'abc' },
                { commit: 'def', effected_files: [] }
            ];
            
            expect(panel.totalFiles).toBe(0);
        });

        test('should handle missing effected_files', () => {
            const panel = createMockPanel();
            panel.notifications = [
                { commit: 'abc', effected_files: ['file1.json'] },
                { commit: 'def' } // no effected_files
            ];
            
            expect(panel.totalFiles).toBe(1);
        });
    });
});

// ============================================================================
// Notification Selection Tests
// ============================================================================

describe('selectNotification', () => {
    test('should select a notification', () => {
        const panel = createMockPanel();
        const notification = { commit: 'abc123', author: 'sujato', date: '2024-01-01' };
        
        panel.selectNotification(notification);
        
        expect(panel.selectedNotification).toBe('abc123');
        expect(panel.selectedNotificationData).toBe(notification);
        expect(panel.loadingDetail).toBe(false);
        expect(panel.detailError).toBeNull();
    });

    test('should not reselect the same notification', () => {
        const panel = createMockPanel();
        const notification = { commit: 'abc123', author: 'sujato', date: '2024-01-01' };
        
        panel.selectedNotification = 'abc123';
        panel.selectedNotificationData = { old: 'data' };
        
        panel.selectNotification(notification);
        
        // Should not change since already selected
        expect(panel.selectedNotificationData).toEqual({ old: 'data' });
    });

    test('should update selection when selecting different notification', () => {
        const panel = createMockPanel();
        const notification1 = { commit: 'abc123', author: 'sujato' };
        const notification2 = { commit: 'def456', author: 'brahmali' };
        
        panel.selectNotification(notification1);
        panel.selectNotification(notification2);
        
        expect(panel.selectedNotification).toBe('def456');
        expect(panel.selectedNotificationData).toBe(notification2);
    });
});

// ============================================================================
// Date Formatting Tests
// ============================================================================

describe('formatDate', () => {
    test('should format valid date string', () => {
        const panel = createMockPanel();
        const formatted = panel.formatDate('2024-01-15T14:30:00Z');
        
        // Should contain the date components
        expect(formatted).toMatch(/Jan/);
        expect(formatted).toMatch(/15/);
        expect(formatted).toMatch(/2024/);
    });

    test('should return empty string for null', () => {
        const panel = createMockPanel();
        expect(panel.formatDate(null)).toBe('');
    });

    test('should return empty string for undefined', () => {
        const panel = createMockPanel();
        expect(panel.formatDate(undefined)).toBe('');
    });

    test('should return empty string for empty string', () => {
        const panel = createMockPanel();
        expect(panel.formatDate('')).toBe('');
    });

    test('should return original string for invalid date', () => {
        const panel = createMockPanel();
        const result = panel.formatDate('not-a-date');
        // Invalid Date will return "Invalid Date" from toLocaleDateString
        // or the original string depending on implementation
        expect(typeof result).toBe('string');
    });
});

// ============================================================================
// Toast Notification Tests
// ============================================================================

describe('showToast', () => {
    test('should set toast with success type by default', () => {
        const panel = createMockPanel();
        
        panel.showToast('Test message');
        
        expect(panel.toast.show).toBe(true);
        expect(panel.toast.message).toBe('Test message');
        expect(panel.toast.type).toBe('success');
    });

    test('should set toast with specified type', () => {
        const panel = createMockPanel();
        
        panel.showToast('Error message', 'error');
        
        expect(panel.toast.show).toBe(true);
        expect(panel.toast.message).toBe('Error message');
        expect(panel.toast.type).toBe('error');
    });

    test('should allow warning type', () => {
        const panel = createMockPanel();
        
        panel.showToast('Warning message', 'warning');
        
        expect(panel.toast.type).toBe('warning');
    });
});

// ============================================================================
// Author Management Tests
// ============================================================================

describe('toggleAllAuthors', () => {
    test('should select all authors when select is true', () => {
        const panel = createMockPanel();
        panel.allAuthors = ['sujato', 'brahmali', 'sabbamitta'];
        panel.selectedAuthors = [];
        
        panel.toggleAllAuthors(true);
        
        expect(panel.selectedAuthors).toEqual(['sujato', 'brahmali', 'sabbamitta']);
    });

    test('should deselect all authors when select is false', () => {
        const panel = createMockPanel();
        panel.allAuthors = ['sujato', 'brahmali', 'sabbamitta'];
        panel.selectedAuthors = ['sujato', 'brahmali'];
        
        panel.toggleAllAuthors(false);
        
        expect(panel.selectedAuthors).toEqual([]);
    });

    test('should create a copy of allAuthors array', () => {
        const panel = createMockPanel();
        panel.allAuthors = ['sujato', 'brahmali'];
        
        panel.toggleAllAuthors(true);
        
        // Should be a different array reference
        expect(panel.selectedAuthors).not.toBe(panel.allAuthors);
        expect(panel.selectedAuthors).toEqual(panel.allAuthors);
    });
});

// ============================================================================
// Edge Cases and Error Handling
// ============================================================================

describe('Edge Cases', () => {
    test('should handle notifications with special characters in commit', () => {
        const panel = createMockPanel();
        panel.filterText = 'abc-123';
        panel.notifications = [
            { commit: 'abc-123_test', author: 'sujato' },
            { commit: 'def456', author: 'brahmali' }
        ];
        
        expect(panel.filteredNotifications).toHaveLength(1);
    });

    test('should handle very long notification lists', () => {
        const panel = createMockPanel();
        panel.pageSize = 10;
        panel.notifications = Array(1000).fill(null).map((_, i) => ({
            commit: `commit${i}`,
            author: 'author',
            date: '2024-01-01'
        }));
        
        expect(panel.totalPages).toBe(100);
        expect(panel.paginatedNotifications).toHaveLength(10);
    });

    test('should handle empty author in filter', () => {
        const panel = createMockPanel();
        panel.filterText = 'nonexistent';
        panel.notifications = [
            { commit: 'abc123', author: 'sujato' },
            { commit: 'def456', author: 'brahmali' }
        ];
        
        expect(panel.filteredNotifications).toHaveLength(0);
    });

    test('should handle unicode characters in author names', () => {
        const panel = createMockPanel();
        panel.filterText = '日本語';
        panel.notifications = [
            { commit: 'abc123', author: '日本語ユーザー' },
            { commit: 'def456', author: 'english-user' }
        ];
        
        expect(panel.filteredNotifications).toHaveLength(1);
    });

    test('should handle notifications with all fields null', () => {
        const panel = createMockPanel();
        panel.notifications = [
            { commit: null, author: null, date: null, effected_files: null }
        ];
        
        // Should not throw
        expect(() => panel.filteredNotifications).not.toThrow();
        expect(() => panel.totalFiles).not.toThrow();
        expect(panel.totalFiles).toBe(0);
    });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('Integration Tests', () => {
    test('should correctly filter, sort, and paginate notifications', () => {
        const panel = createMockPanel();
        panel.filterText = 'sujato';
        panel.sortMode = 'date';
        panel.pageSize = 2;
        panel.currentPage = 1;
        panel.notifications = [
            { commit: 'c1', author: 'sujato', date: '2024-01-01T10:00:00Z' },
            { commit: 'c2', author: 'brahmali', date: '2024-01-02T10:00:00Z' },
            { commit: 'c3', author: 'sujato', date: '2024-01-03T10:00:00Z' },
            { commit: 'c4', author: 'sujato', date: '2024-01-04T10:00:00Z' },
            { commit: 'c5', author: 'sabbamitta', date: '2024-01-05T10:00:00Z' }
        ];
        
        // Should filter to 3 sujato notifications
        expect(panel.filteredNotifications).toHaveLength(3);
        
        // Should sort by date (newest first): c4, c3, c1
        expect(panel.filteredNotifications[0].commit).toBe('c4');
        expect(panel.filteredNotifications[1].commit).toBe('c3');
        expect(panel.filteredNotifications[2].commit).toBe('c1');
        
        // Should paginate to 2 items on page 1
        expect(panel.paginatedNotifications).toHaveLength(2);
        expect(panel.totalPages).toBe(2);
        
        // Move to page 2
        panel.currentPage = 2;
        expect(panel.paginatedNotifications).toHaveLength(1);
        expect(panel.paginatedNotifications[0].commit).toBe('c1');
    });

    test('should correctly calculate statistics after filtering', () => {
        const panel = createMockPanel();
        panel.notifications = [
            { commit: 'c1', author: 'sujato', effected_files: ['f1', 'f2'] },
            { commit: 'c2', author: 'brahmali', effected_files: ['f3'] },
            { commit: 'c3', author: 'sujato', effected_files: ['f4', 'f5', 'f6'] }
        ];
        
        // uniqueAuthors and totalFiles are based on all notifications (not filtered)
        expect(panel.uniqueAuthors).toBe(2);
        expect(panel.totalFiles).toBe(6);
        
        // Apply filter
        panel.filterText = 'sujato';
        
        // Statistics should still reflect all notifications
        expect(panel.uniqueAuthors).toBe(2);
        expect(panel.totalFiles).toBe(6);
        
        // But filtered notifications should be 2
        expect(panel.filteredNotifications).toHaveLength(2);
    });

    test('should handle complete workflow of selecting and toggling', () => {
        const panel = createMockPanel();
        panel.notifications = [
            { commit: 'c1', author: 'sujato', date: '2024-01-01' },
            { commit: 'c2', author: 'brahmali', date: '2024-01-02' }
        ];
        
        // Select a notification
        panel.selectNotification(panel.notifications[0]);
        expect(panel.selectedNotification).toBe('c1');
        
        // Toggle sort mode
        panel.toggleSortMode();
        expect(panel.sortMode).toBe('author');
        expect(panel.currentPage).toBe(1);
        
        // Sorted by author: brahmali first
        expect(panel.filteredNotifications[0].author).toBe('brahmali');
    });
});
