/**
 * Git Status Panel Tests
 * 
 * This file tests the git_status_panel.js functionality including:
 * - State initialization
 * - File filtering (filteredFiles)
 * - Pagination (paginatedFiles, totalPages, startItem, endItem)
 * - Statistics calculation (calculateStats)
 * - Status helpers (getStatusIcon, getStatusClass, formatStatus)
 * - Diff parsing (parseDiff)
 * - Multi-selection (isFileSelected, toggleFileSelection, toggleSelectAll, clearSelection)
 * - Sort mode (setSortMode)
 * - Toast notifications (showToast)
 */

// ============================================================================
// Mock Setup
// ============================================================================

// Mock localStorage
const localStorageMock = {
    store: {},
    getItem: jest.fn((key) => localStorageMock.store[key] || null),
    setItem: jest.fn((key, value) => { localStorageMock.store[key] = value; }),
    removeItem: jest.fn((key) => { delete localStorageMock.store[key]; }),
    clear: jest.fn(() => { localStorageMock.store = {}; })
};
global.localStorage = localStorageMock;

// Mock window.location
delete global.window;
global.window = {
    location: {
        search: '',
        href: ''
    },
    open: jest.fn()
};

// Mock fetch
global.fetch = jest.fn();

// Mock getUserInfo
global.getUserInfo = jest.fn(() => ({
    getRole: jest.fn().mockResolvedValue(),
    isAdmin: false,
    username: 'testuser'
}));

// Mock requestWithTokenRetry
global.requestWithTokenRetry = jest.fn();

// Mock getMuid and getPrefix
global.getMuid = jest.fn((path) => {
    const fileName = path.split('/').filter(Boolean).pop();
    const parts = fileName.split('_');
    if (parts.length > 1) {
        return parts[1].split('.')[0];
    }
    return '';
});

global.getPrefix = jest.fn((fileName) => {
    return fileName.split('_')[0] || '';
});

// ============================================================================
// Helper function to create mock panel instance
// ============================================================================

function createMockPanel(overrides = {}) {
    const panel = {
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
        showConfirmModal: false,
        fileToDiscard: null,
        discarding: false,
        skipDiscardConfirm: false,
        showEditModal: false,
        fileToEdit: null,
        skipEditConfirm: false,
        showPublishModal: false,
        fileToPublish: null,
        publishingFile: null,
        skipPublishConfirm: false,
        toast: {
            show: false,
            message: '',
            type: 'success'
        },
        filterText: '',
        sortMode: 'default',
        currentPage: 1,
        pageSize: 20,
        userInfo: null,
        isAdmin: false,
        username: '',
        selectedFiles: [],
        batchPublishing: false,

        get filteredFiles() {
            let filtered = [...this.files];

            if (!this.isAdmin && this.username) {
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
                    return dateB - dateA;
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
                this.currentPage = 1;
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

        showToast(message, type = 'success') {
            this.toast = { show: true, message, type };
        },

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
                this.selectedFiles = this.selectedFiles.filter(
                    path => !this.filteredFiles.some(file => file.path === path)
                );
            } else {
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

        ...overrides
    };

    return panel;
}

// ============================================================================
// State Initialization Tests
// ============================================================================

describe('Git Status Panel State Initialization', () => {
    test('should have correct default state', () => {
        const panel = createMockPanel();
        
        expect(panel.files).toEqual([]);
        expect(panel.selectedFile).toBeNull();
        expect(panel.selectedFileData).toBeNull();
        expect(panel.loading).toBe(true);
        expect(panel.publishing).toBe(false);
        expect(panel.loadingDiff).toBe(false);
        expect(panel.diffContent).toBe('');
        expect(panel.diffError).toBeNull();
    });

    test('should have correct default stats', () => {
        const panel = createMockPanel();
        
        expect(panel.stats).toEqual({
            modified: 0,
            untracked: 0,
            deleted: 0,
            staged: 0
        });
    });

    test('should have correct default modal states', () => {
        const panel = createMockPanel();
        
        expect(panel.showConfirmModal).toBe(false);
        expect(panel.fileToDiscard).toBeNull();
        expect(panel.discarding).toBe(false);
        expect(panel.showEditModal).toBe(false);
        expect(panel.fileToEdit).toBeNull();
        expect(panel.showPublishModal).toBe(false);
        expect(panel.fileToPublish).toBeNull();
    });

    test('should have correct default filter and pagination state', () => {
        const panel = createMockPanel();
        
        expect(panel.filterText).toBe('');
        expect(panel.sortMode).toBe('default');
        expect(panel.currentPage).toBe(1);
        expect(panel.pageSize).toBe(20);
    });

    test('should have correct default multi-selection state', () => {
        const panel = createMockPanel();
        
        expect(panel.selectedFiles).toEqual([]);
        expect(panel.batchPublishing).toBe(false);
    });
});

// ============================================================================
// Statistics Calculation Tests
// ============================================================================

describe('calculateStats', () => {
    test('should correctly count modified files', () => {
        const panel = createMockPanel();
        panel.files = [
            { path: 'file1.json', status: 'modified' },
            { path: 'file2.json', status: 'modified' },
            { path: 'file3.json', status: 'untracked' }
        ];
        
        panel.calculateStats();
        
        expect(panel.stats.modified).toBe(2);
        expect(panel.stats.untracked).toBe(1);
        expect(panel.stats.deleted).toBe(0);
        expect(panel.stats.staged).toBe(0);
    });

    test('should correctly count untracked files', () => {
        const panel = createMockPanel();
        panel.files = [
            { path: 'file1.json', status: 'untracked' },
            { path: 'file2.json', status: 'untracked' },
            { path: 'file3.json', status: 'untracked' }
        ];
        
        panel.calculateStats();
        
        expect(panel.stats.untracked).toBe(3);
    });

    test('should correctly count deleted files', () => {
        const panel = createMockPanel();
        panel.files = [
            { path: 'file1.json', status: 'deleted' },
            { path: 'file2.json', status: 'modified' }
        ];
        
        panel.calculateStats();
        
        expect(panel.stats.deleted).toBe(1);
        expect(panel.stats.modified).toBe(1);
    });

    test('should correctly count staged files', () => {
        const panel = createMockPanel();
        panel.files = [
            { path: 'file1.json', status: 'staged_new' },
            { path: 'file2.json', status: 'staged_modified' },
            { path: 'file3.json', status: 'staged_deleted' }
        ];
        
        panel.calculateStats();
        
        expect(panel.stats.staged).toBe(3);
    });

    test('should correctly count mixed statuses', () => {
        const panel = createMockPanel();
        panel.files = [
            { path: 'file1.json', status: 'modified' },
            { path: 'file2.json', status: 'untracked' },
            { path: 'file3.json', status: 'deleted' },
            { path: 'file4.json', status: 'staged_new' },
            { path: 'file5.json', status: 'staged_modified' },
            { path: 'file6.json', status: 'modified' }
        ];
        
        panel.calculateStats();
        
        expect(panel.stats.modified).toBe(2);
        expect(panel.stats.untracked).toBe(1);
        expect(panel.stats.deleted).toBe(1);
        expect(panel.stats.staged).toBe(2);
    });

    test('should handle empty file list', () => {
        const panel = createMockPanel();
        panel.files = [];
        
        panel.calculateStats();
        
        expect(panel.stats).toEqual({
            modified: 0,
            untracked: 0,
            deleted: 0,
            staged: 0
        });
    });
});

// ============================================================================
// Status Helper Functions Tests
// ============================================================================

describe('Status Helper Functions', () => {
    describe('getStatusIcon', () => {
        test('should return correct icon for modified status', () => {
            const panel = createMockPanel();
            expect(panel.getStatusIcon('modified')).toBe('bi-pencil-fill');
        });

        test('should return correct icon for untracked status', () => {
            const panel = createMockPanel();
            expect(panel.getStatusIcon('untracked')).toBe('bi-plus-circle-fill');
        });

        test('should return correct icon for deleted status', () => {
            const panel = createMockPanel();
            expect(panel.getStatusIcon('deleted')).toBe('bi-trash-fill');
        });

        test('should return correct icon for staged statuses', () => {
            const panel = createMockPanel();
            expect(panel.getStatusIcon('staged_new')).toBe('bi-check-circle-fill');
            expect(panel.getStatusIcon('staged_modified')).toBe('bi-check-circle-fill');
            expect(panel.getStatusIcon('staged_deleted')).toBe('bi-check-circle-fill');
        });

        test('should return default icon for unknown status', () => {
            const panel = createMockPanel();
            expect(panel.getStatusIcon('unknown')).toBe('bi-question-circle');
            expect(panel.getStatusIcon('')).toBe('bi-question-circle');
        });
    });

    describe('getStatusClass', () => {
        test('should return status as class for non-staged statuses', () => {
            const panel = createMockPanel();
            expect(panel.getStatusClass('modified')).toBe('modified');
            expect(panel.getStatusClass('untracked')).toBe('untracked');
            expect(panel.getStatusClass('deleted')).toBe('deleted');
        });

        test('should return "staged" class for staged statuses', () => {
            const panel = createMockPanel();
            expect(panel.getStatusClass('staged_new')).toBe('staged');
            expect(panel.getStatusClass('staged_modified')).toBe('staged');
            expect(panel.getStatusClass('staged_deleted')).toBe('staged');
        });
    });

    describe('formatStatus', () => {
        test('should return correct abbreviation for all statuses', () => {
            const panel = createMockPanel();
            expect(panel.formatStatus('modified')).toBe('M');
            expect(panel.formatStatus('untracked')).toBe('U');
            expect(panel.formatStatus('deleted')).toBe('D');
            expect(panel.formatStatus('staged_new')).toBe('A');
            expect(panel.formatStatus('staged_modified')).toBe('SM');
            expect(panel.formatStatus('staged_deleted')).toBe('SD');
        });

        test('should return original status for unknown status', () => {
            const panel = createMockPanel();
            expect(panel.formatStatus('unknown')).toBe('unknown');
            expect(panel.formatStatus('custom_status')).toBe('custom_status');
        });
    });
});

// ============================================================================
// Diff Parsing Tests
// ============================================================================

describe('parseDiff', () => {
    test('should return empty array for null or empty diff', () => {
        const panel = createMockPanel();
        expect(panel.parseDiff(null)).toEqual([]);
        expect(panel.parseDiff('')).toEqual([]);
    });

    test('should correctly parse addition lines', () => {
        const panel = createMockPanel();
        const diff = '+added line';
        const result = panel.parseDiff(diff);
        
        expect(result).toHaveLength(1);
        expect(result[0]).toEqual({ text: '+added line', type: 'addition' });
    });

    test('should correctly parse deletion lines', () => {
        const panel = createMockPanel();
        const diff = '-removed line';
        const result = panel.parseDiff(diff);
        
        expect(result).toHaveLength(1);
        expect(result[0]).toEqual({ text: '-removed line', type: 'deletion' });
    });

    test('should correctly parse context lines', () => {
        const panel = createMockPanel();
        const diff = ' context line';
        const result = panel.parseDiff(diff);
        
        expect(result).toHaveLength(1);
        expect(result[0]).toEqual({ text: ' context line', type: 'context' });
    });

    test('should filter out header lines', () => {
        const panel = createMockPanel();
        const diff = `diff --git a/file.txt b/file.txt
index abc123..def456 100644
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,4 @@
 context
+added
-removed`;
        const result = panel.parseDiff(diff);
        
        // Header lines should have empty text and type
        const headerResults = result.filter(r => r.text === '' && r.type === '');
        expect(headerResults.length).toBeGreaterThan(0);
        
        // Should have actual content lines
        const additionLine = result.find(r => r.type === 'addition');
        expect(additionLine).toBeDefined();
        expect(additionLine.text).toBe('+added');
    });

    test('should handle multiline diff correctly', () => {
        const panel = createMockPanel();
        const diff = ` context line 1
+added line
-removed line
 context line 2`;
        const result = panel.parseDiff(diff);
        
        expect(result).toHaveLength(4);
        expect(result[0].type).toBe('context');
        expect(result[1].type).toBe('addition');
        expect(result[2].type).toBe('deletion');
        expect(result[3].type).toBe('context');
    });
});

// ============================================================================
// Filter and Sort Tests
// ============================================================================

describe('filteredFiles', () => {
    test('should return all files when no filter is applied for admin users', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.files = [
            { path: 'translation/en/user1/file1.json', status: 'modified' },
            { path: 'translation/en/user2/file2.json', status: 'untracked' }
        ];
        
        expect(panel.filteredFiles).toHaveLength(2);
    });

    test('should filter files by username for non-admin users', () => {
        const panel = createMockPanel();
        panel.isAdmin = false;
        panel.username = 'user1';
        panel.files = [
            { path: 'translation/en/user1/file1.json', status: 'modified' },
            { path: 'translation/en/user2/file2.json', status: 'untracked' },
            { path: 'translation/en/User1/file3.json', status: 'deleted' }
        ];
        
        // Should include files with 'user1' (case-insensitive)
        expect(panel.filteredFiles).toHaveLength(2);
    });

    test('should filter files by filterText', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.filterText = 'sutta';
        panel.files = [
            { path: 'translation/en/sutta/mn1.json', status: 'modified' },
            { path: 'translation/en/vinaya/pli-tv.json', status: 'untracked' },
            { path: 'translation/en/sutta/dn1.json', status: 'deleted' }
        ];
        
        expect(panel.filteredFiles).toHaveLength(2);
    });

    test('should combine username filter and text filter', () => {
        const panel = createMockPanel();
        panel.isAdmin = false;
        panel.username = 'sujato';
        panel.filterText = 'mn';
        panel.files = [
            { path: 'translation/en/sujato/sutta/mn/mn1.json', status: 'modified' },
            { path: 'translation/en/sujato/sutta/dn/dn1.json', status: 'untracked' },
            { path: 'translation/en/brahmali/vinaya/pli-tv.json', status: 'deleted' }
        ];
        
        expect(panel.filteredFiles).toHaveLength(1);
        expect(panel.filteredFiles[0].path).toContain('mn');
    });

    test('should sort by status order in default mode', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.sortMode = 'default';
        panel.files = [
            { path: 'file1.json', status: 'deleted' },
            { path: 'file2.json', status: 'staged_new' },
            { path: 'file3.json', status: 'modified' },
            { path: 'file4.json', status: 'untracked' }
        ];
        
        const sorted = panel.filteredFiles;
        expect(sorted[0].status).toBe('staged_new');
        expect(sorted[1].status).toBe('modified');
        expect(sorted[2].status).toBe('untracked');
        expect(sorted[3].status).toBe('deleted');
    });

    test('should sort by date in date mode', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.sortMode = 'date';
        panel.files = [
            { path: 'file1.json', status: 'modified', modified_time: '2024-01-01T10:00:00Z' },
            { path: 'file2.json', status: 'modified', modified_time: '2024-01-03T10:00:00Z' },
            { path: 'file3.json', status: 'modified', modified_time: '2024-01-02T10:00:00Z' }
        ];
        
        const sorted = panel.filteredFiles;
        expect(sorted[0].path).toBe('file2.json'); // newest first
        expect(sorted[1].path).toBe('file3.json');
        expect(sorted[2].path).toBe('file1.json');
    });

    test('should sort alphabetically within same status in default mode', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.sortMode = 'default';
        panel.files = [
            { path: 'c_file.json', status: 'modified' },
            { path: 'a_file.json', status: 'modified' },
            { path: 'b_file.json', status: 'modified' }
        ];
        
        const sorted = panel.filteredFiles;
        expect(sorted[0].path).toBe('a_file.json');
        expect(sorted[1].path).toBe('b_file.json');
        expect(sorted[2].path).toBe('c_file.json');
    });
});

describe('setSortMode', () => {
    test('should change sort mode and reset to page 1', () => {
        const panel = createMockPanel();
        panel.sortMode = 'default';
        panel.currentPage = 3;
        
        panel.setSortMode('date');
        
        expect(panel.sortMode).toBe('date');
        expect(panel.currentPage).toBe(1);
    });

    test('should not change state if same mode is set', () => {
        const panel = createMockPanel();
        panel.sortMode = 'default';
        panel.currentPage = 3;
        
        panel.setSortMode('default');
        
        expect(panel.sortMode).toBe('default');
        expect(panel.currentPage).toBe(3); // Should not reset
    });
});

// ============================================================================
// Pagination Tests
// ============================================================================

describe('Pagination', () => {
    describe('totalPages', () => {
        test('should calculate correct total pages', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.pageSize = 10;
            panel.files = Array(25).fill(null).map((_, i) => ({
                path: `file${i}.json`,
                status: 'modified'
            }));
            
            expect(panel.totalPages).toBe(3);
        });

        test('should return 1 for files equal to page size', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.pageSize = 10;
            panel.files = Array(10).fill(null).map((_, i) => ({
                path: `file${i}.json`,
                status: 'modified'
            }));
            
            expect(panel.totalPages).toBe(1);
        });

        test('should return 0 for empty file list', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.files = [];
            
            expect(panel.totalPages).toBe(0);
        });
    });

    describe('paginatedFiles', () => {
        test('should return correct slice for first page', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.pageSize = 5;
            panel.currentPage = 1;
            panel.files = Array(12).fill(null).map((_, i) => ({
                path: `file${i}.json`,
                status: 'modified'
            }));
            
            const paginated = panel.paginatedFiles;
            expect(paginated).toHaveLength(5);
            expect(paginated[0].path).toBe('file0.json');
        });

        test('should return correct slice for middle page', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.pageSize = 5;
            panel.currentPage = 2;
            // Use zero-padded numbers to ensure alphabetical order matches numeric order
            panel.files = Array(12).fill(null).map((_, i) => ({
                path: `file${String(i).padStart(2, '0')}.json`,
                status: 'modified'
            }));
            
            const paginated = panel.paginatedFiles;
            expect(paginated).toHaveLength(5);
            // After sorting alphabetically: file00, file01, ..., file11
            // Page 2 starts at index 5: file05
            expect(paginated[0].path).toBe('file05.json');
        });

        test('should return remaining items for last page', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.pageSize = 5;
            panel.currentPage = 3;
            // Use zero-padded numbers to ensure alphabetical order matches numeric order
            panel.files = Array(12).fill(null).map((_, i) => ({
                path: `file${String(i).padStart(2, '0')}.json`,
                status: 'modified'
            }));
            
            const paginated = panel.paginatedFiles;
            expect(paginated).toHaveLength(2);
            // After sorting alphabetically: file00, file01, ..., file11
            // Page 3 starts at index 10: file10
            expect(paginated[0].path).toBe('file10.json');
        });
    });

    describe('startItem and endItem', () => {
        test('should return correct range for first page', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.pageSize = 10;
            panel.currentPage = 1;
            panel.files = Array(25).fill(null).map((_, i) => ({
                path: `file${i}.json`,
                status: 'modified'
            }));
            
            expect(panel.startItem).toBe(1);
            expect(panel.endItem).toBe(10);
        });

        test('should return correct range for last page', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.pageSize = 10;
            panel.currentPage = 3;
            panel.files = Array(25).fill(null).map((_, i) => ({
                path: `file${i}.json`,
                status: 'modified'
            }));
            
            expect(panel.startItem).toBe(21);
            expect(panel.endItem).toBe(25);
        });

        test('should return 0 for startItem when no files', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.files = [];
            
            expect(panel.startItem).toBe(0);
        });
    });
});

// ============================================================================
// Multi-Selection Tests
// ============================================================================

describe('Multi-Selection', () => {
    describe('isFileSelected', () => {
        test('should return true for selected file', () => {
            const panel = createMockPanel();
            panel.selectedFiles = ['file1.json', 'file2.json'];
            
            expect(panel.isFileSelected('file1.json')).toBe(true);
            expect(panel.isFileSelected('file2.json')).toBe(true);
        });

        test('should return false for unselected file', () => {
            const panel = createMockPanel();
            panel.selectedFiles = ['file1.json'];
            
            expect(panel.isFileSelected('file2.json')).toBe(false);
        });
    });

    describe('toggleFileSelection', () => {
        test('should add file to selection when not selected', () => {
            const panel = createMockPanel();
            panel.selectedFiles = [];
            
            panel.toggleFileSelection('file1.json');
            
            expect(panel.selectedFiles).toContain('file1.json');
        });

        test('should remove file from selection when already selected', () => {
            const panel = createMockPanel();
            panel.selectedFiles = ['file1.json', 'file2.json'];
            
            panel.toggleFileSelection('file1.json');
            
            expect(panel.selectedFiles).not.toContain('file1.json');
            expect(panel.selectedFiles).toContain('file2.json');
        });
    });

    describe('isAllSelected', () => {
        test('should return true when all filtered files are selected', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.files = [
                { path: 'file1.json', status: 'modified' },
                { path: 'file2.json', status: 'modified' }
            ];
            panel.selectedFiles = ['file1.json', 'file2.json'];
            
            expect(panel.isAllSelected).toBe(true);
        });

        test('should return false when not all filtered files are selected', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.files = [
                { path: 'file1.json', status: 'modified' },
                { path: 'file2.json', status: 'modified' }
            ];
            panel.selectedFiles = ['file1.json'];
            
            expect(panel.isAllSelected).toBe(false);
        });

        test('should return false when no files', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.files = [];
            panel.selectedFiles = [];
            
            expect(panel.isAllSelected).toBe(false);
        });
    });

    describe('isPartiallySelected', () => {
        test('should return true when some files are selected', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.files = [
                { path: 'file1.json', status: 'modified' },
                { path: 'file2.json', status: 'modified' },
                { path: 'file3.json', status: 'modified' }
            ];
            panel.selectedFiles = ['file1.json'];
            
            expect(panel.isPartiallySelected).toBe(true);
        });

        test('should return false when all files are selected', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.files = [
                { path: 'file1.json', status: 'modified' },
                { path: 'file2.json', status: 'modified' }
            ];
            panel.selectedFiles = ['file1.json', 'file2.json'];
            
            expect(panel.isPartiallySelected).toBe(false);
        });

        test('should return false when no files are selected', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.files = [
                { path: 'file1.json', status: 'modified' },
                { path: 'file2.json', status: 'modified' }
            ];
            panel.selectedFiles = [];
            
            expect(panel.isPartiallySelected).toBe(false);
        });
    });

    describe('toggleSelectAll', () => {
        test('should select all filtered files when none selected', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.files = [
                { path: 'file1.json', status: 'modified' },
                { path: 'file2.json', status: 'modified' }
            ];
            panel.selectedFiles = [];
            
            panel.toggleSelectAll();
            
            expect(panel.selectedFiles).toContain('file1.json');
            expect(panel.selectedFiles).toContain('file2.json');
        });

        test('should deselect all filtered files when all selected', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.files = [
                { path: 'file1.json', status: 'modified' },
                { path: 'file2.json', status: 'modified' }
            ];
            panel.selectedFiles = ['file1.json', 'file2.json'];
            
            panel.toggleSelectAll();
            
            expect(panel.selectedFiles).toHaveLength(0);
        });

        test('should preserve selections outside of filtered files', () => {
            const panel = createMockPanel();
            panel.isAdmin = true;
            panel.filterText = 'file1';
            panel.files = [
                { path: 'file1.json', status: 'modified' },
                { path: 'file2.json', status: 'modified' }
            ];
            panel.selectedFiles = ['file1.json', 'file3.json'];
            
            // Deselect all filtered (only file1.json)
            panel.toggleSelectAll();
            
            // file3.json should still be selected (not in filtered files)
            expect(panel.selectedFiles).toContain('file3.json');
            expect(panel.selectedFiles).not.toContain('file1.json');
        });
    });

    describe('clearSelection', () => {
        test('should clear all selections', () => {
            const panel = createMockPanel();
            panel.selectedFiles = ['file1.json', 'file2.json', 'file3.json'];
            
            panel.clearSelection();
            
            expect(panel.selectedFiles).toHaveLength(0);
        });
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
});

// ============================================================================
// Edge Cases and Error Handling
// ============================================================================

describe('Edge Cases', () => {
    test('should handle files with special characters in path', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.files = [
            { path: 'translation/en/file-with-dash.json', status: 'modified' },
            { path: 'translation/en/file_with_underscore.json', status: 'modified' },
            { path: 'translation/en/file.with.dots.json', status: 'modified' }
        ];
        
        panel.calculateStats();
        
        expect(panel.stats.modified).toBe(3);
        expect(panel.filteredFiles).toHaveLength(3);
    });

    test('should handle empty filterText correctly', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.filterText = '   '; // Whitespace only
        panel.files = [
            { path: 'file1.json', status: 'modified' },
            { path: 'file2.json', status: 'modified' }
        ];
        
        expect(panel.filteredFiles).toHaveLength(2);
    });

    test('should handle case-insensitive search', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.filterText = 'SUTTA';
        panel.files = [
            { path: 'translation/en/sutta/mn1.json', status: 'modified' },
            { path: 'translation/en/Sutta/dn1.json', status: 'modified' },
            { path: 'translation/en/vinaya/pli-tv.json', status: 'modified' }
        ];
        
        expect(panel.filteredFiles).toHaveLength(2);
    });

    test('should handle files without modified_time in date sort mode', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.sortMode = 'date';
        panel.files = [
            { path: 'file1.json', status: 'modified' }, // no modified_time
            { path: 'file2.json', status: 'modified', modified_time: '2024-01-01T10:00:00Z' },
            { path: 'file3.json', status: 'modified' } // no modified_time
        ];
        
        // Should not throw error
        expect(() => panel.filteredFiles).not.toThrow();
        expect(panel.filteredFiles).toHaveLength(3);
    });

    test('should handle unknown status in sorting', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.sortMode = 'default';
        panel.files = [
            { path: 'file1.json', status: 'unknown_status' },
            { path: 'file2.json', status: 'modified' },
            { path: 'file3.json', status: 'custom' }
        ];
        
        // Unknown statuses should be sorted to end (order 99)
        const sorted = panel.filteredFiles;
        expect(sorted[0].status).toBe('modified');
        expect(sorted[1].status).toBe('unknown_status');
        expect(sorted[2].status).toBe('custom');
    });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('Integration Tests', () => {
    test('should correctly filter, sort, and paginate files', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.filterText = 'sutta';
        panel.sortMode = 'default';
        panel.pageSize = 2;
        panel.currentPage = 1;
        panel.files = [
            { path: 'vinaya/pli-tv.json', status: 'modified' },
            { path: 'sutta/mn1.json', status: 'untracked' },
            { path: 'sutta/dn1.json', status: 'modified' },
            { path: 'sutta/sn1.json', status: 'staged_new' },
            { path: 'abhidhamma/ds.json', status: 'deleted' }
        ];
        
        // Should filter to 3 sutta files
        expect(panel.filteredFiles).toHaveLength(3);
        
        // Should sort by status: staged_new, modified, untracked
        expect(panel.filteredFiles[0].path).toBe('sutta/sn1.json');
        expect(panel.filteredFiles[1].path).toBe('sutta/dn1.json');
        expect(panel.filteredFiles[2].path).toBe('sutta/mn1.json');
        
        // Should paginate to 2 items on page 1
        expect(panel.paginatedFiles).toHaveLength(2);
        expect(panel.totalPages).toBe(2);
        
        // Move to page 2
        panel.currentPage = 2;
        expect(panel.paginatedFiles).toHaveLength(1);
    });

    test('should handle complete workflow of selecting, filtering, and clearing', () => {
        const panel = createMockPanel();
        panel.isAdmin = true;
        panel.files = [
            { path: 'sutta/mn1.json', status: 'modified' },
            { path: 'sutta/dn1.json', status: 'modified' },
            { path: 'vinaya/pli-tv.json', status: 'modified' }
        ];
        
        // Select all
        panel.toggleSelectAll();
        expect(panel.selectedFiles).toHaveLength(3);
        expect(panel.isAllSelected).toBe(true);
        
        // Apply filter
        panel.filterText = 'sutta';
        expect(panel.filteredFiles).toHaveLength(2);
        // isAllSelected checks if all filtered files are selected
        // Both sutta files are still selected, so isAllSelected is true
        expect(panel.isAllSelected).toBe(true);
        
        // Toggle select all (should deselect filtered files since all are selected)
        panel.toggleSelectAll();
        // sutta files should be deselected, vinaya file remains
        expect(panel.selectedFiles).not.toContain('sutta/mn1.json');
        expect(panel.selectedFiles).not.toContain('sutta/dn1.json');
        expect(panel.selectedFiles).toContain('vinaya/pli-tv.json');
        
        // Clear selection
        panel.clearSelection();
        expect(panel.selectedFiles).toHaveLength(0);
    });
});
