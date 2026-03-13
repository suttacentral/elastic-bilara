/**
 * Navigation (nav.js) Tests
 * 
 * This file tests the nav.js functionality including:
 * - tree() function state and methods
 * - Element class construction and methods
 * - Directory tree navigation
 * - Publish modal state management
 * - Progress display logic
 * - Element search functionality
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
global.getUserInfo = jest.fn(() => ({
    getRole: jest.fn().mockResolvedValue(),
    username: 'testuser',
    isAdmin: false
}));

// Mock getMuid and getPrefix
global.getMuid = jest.fn((fullName) => {
    const parts = fullName.split('/').filter(p => p);
    if (parts.length > 3) {
        const fileName = parts[parts.length - 1];
        const match = fileName.match(/_([^_]+)\./);
        return match ? match[1] : null;
    }
    return null;
});

global.getPrefix = jest.fn((name) => {
    return name.split('_')[0] || null;
});

// Mock document
global.document = {
    querySelector: jest.fn(),
    querySelectorAll: jest.fn(() => [])
};

// Mock window.open
const mockWindowOpen = jest.fn();
Object.defineProperty(window, 'open', {
    value: mockWindowOpen,
    writable: true
});

// ============================================================================
// Element Class
// ============================================================================

class Element {
    constructor(name, base, isOpen, isFile) {
        this.name = name;
        this.base = base;
        this.fullName = this.base === null ? this.name : this.base + this.name;
        this.isOpen = isOpen;
        this.isFile = isFile;
        this.muid = this.fullName.split("/").length > 3 ? getMuid(this.fullName) : null;
        this.prefix = this.isFile ? getPrefix(this.name) : null;
        this.children = [];
        this.progress = null;
        this.totalKeys = 0;
        this.translatedKeys = 0;
        this.loading = false;
    }

    add(child) {
        this.children.push(child);
    }
}

// ============================================================================
// Helper function to create mock tree instance
// ============================================================================

function createMockTree(overrides = {}) {
    const tree = {
        loading: false,
        showAllContent: false,
        filterUsername: "",
        data: [],
        showPublishModal: false,
        publishingFile: null,
        isPublishing: false,

        toggleShowAll() {
            this.showAllContent = !this.showAllContent;
            this.data = [];
        },

        openPublishModal(name) {
            this.publishingFile = name;
            this.showPublishModal = true;
        },

        closePublishModal() {
            this.showPublishModal = false;
            this.publishingFile = null;
        },

        reviewPublish() {
            if (this.publishingFile) {
                mockWindowOpen(`git_status_panel.html?filter=${encodeURIComponent(this.publishingFile)}`, '_blank');
                this.closePublishModal();
            }
        },

        getElementByName(name) {
            let result = null;

            function search(query, collection) {
                collection.forEach(item => {
                    if (item.fullName === query) {
                        result = item;
                    } else if (item.children.length && result === null) {
                        search(query, item.children);
                    }
                });
            }

            search(name, this.data);
            return result;
        },

        close(element) {
            element.isOpen = false;
        },

        renderNode(element) {
            if (!element) return "";

            let result = `
                <a href="#"
                    class="navigation-list__item-link ${element.isOpen ? 'navigation-list--open' : ''}"
                    onclick="event.preventDefault();"
                    x-on:click.prevent="itemClicked('${element.fullName}')">
                    <i class="mdi ${element.isFile ? 'mdi-file-outline' : (element.isOpen ? 'mdi-folder-open-outline' : 'mdi-folder-outline')}"></i>
                    ${element.name.split("/").join("")}
                </a>`;

            const isTranslationFile = element.fullName && element.fullName.startsWith('translation/');
            if (element.isFile && isTranslationFile && element.progress !== null && element.progress >= 0) {
                const progressClass = element.progress >= 90 ? 'high' : (element.progress >= 50 ? 'medium' : 'low');
                result += `<span class="translation-progress ${progressClass}" title="${element.progress}% translated (${element.translatedKeys}/${element.totalKeys})">
                    <span class="progress-bar" style="width: ${element.progress}%"></span>
                    <span class="progress-text">${element.progress}%</span>
                </span>`;
            }

            if (element.muid && (element.fullName.split('/').length >= 5 || element.isFile)) {
                result += `<button class="btn btn--publish" x-on:click="openPublishModal('${element.fullName}')">Publish</button>`;
            }

            if (element.loading) {
                result += `<div class="node-loading"><div class="spinner-small"></div></div>`;
            }

            if (element.isOpen && !element.isFile && element.children.length) {
                result += `<ul class="navigation-list">`;
                for (const child of element.children) {
                    result += `<li class="navigation-list__item">${this.renderNode(child)}</li>`;
                }
                result += `</ul>`;
            }

            return result;
        },

        itemClicked(name) {
            const element = this.getElementByName(name);
            if (element) {
                if (element.isFile) {
                    return 'redirect';
                }
                if (element.isOpen) {
                    this.close(element);
                } else {
                    element.isOpen = true;
                }
            }
        },

        ...overrides
    };

    return tree;
}

// ============================================================================
// Element Class Tests
// ============================================================================

describe('Element Class', () => {
    beforeEach(() => {
        getMuid.mockClear();
        getPrefix.mockClear();
    });

    describe('Constructor', () => {
        test('should create element with correct properties', () => {
            const element = new Element('folder/', null, false, false);
            
            expect(element.name).toBe('folder/');
            expect(element.base).toBeNull();
            expect(element.fullName).toBe('folder/');
            expect(element.isOpen).toBe(false);
            expect(element.isFile).toBe(false);
            expect(element.children).toEqual([]);
            expect(element.progress).toBeNull();
            expect(element.totalKeys).toBe(0);
            expect(element.translatedKeys).toBe(0);
            expect(element.loading).toBe(false);
        });

        test('should calculate fullName with base', () => {
            const element = new Element('subfolder/', 'parent/', false, false);
            
            expect(element.fullName).toBe('parent/subfolder/');
        });

        test('should set fullName as name when base is null', () => {
            const element = new Element('root/', null, false, false);
            
            expect(element.fullName).toBe('root/');
        });

        test('should call getMuid for deep paths', () => {
            getMuid.mockReturnValue('en-sujato');
            const element = new Element('file.json', 'translation/en/sujato/sutta/', false, true);
            
            expect(getMuid).toHaveBeenCalled();
            expect(element.muid).toBe('en-sujato');
        });

        test('should not set muid for shallow paths', () => {
            const element = new Element('folder/', 'parent/', false, false);
            
            expect(element.muid).toBeNull();
        });

        test('should set prefix for files', () => {
            getPrefix.mockReturnValue('mn1');
            const element = new Element('mn1_translation-en-sujato.json', 'path/', false, true);
            
            expect(getPrefix).toHaveBeenCalledWith('mn1_translation-en-sujato.json');
            expect(element.prefix).toBe('mn1');
        });

        test('should not set prefix for directories', () => {
            const element = new Element('folder/', 'path/', false, false);
            
            expect(element.prefix).toBeNull();
        });
    });

    describe('add method', () => {
        test('should add child element', () => {
            const parent = new Element('parent/', null, false, false);
            const child = new Element('child/', 'parent/', false, false);
            
            parent.add(child);
            
            expect(parent.children).toHaveLength(1);
            expect(parent.children[0]).toBe(child);
        });

        test('should add multiple children', () => {
            const parent = new Element('parent/', null, false, false);
            const child1 = new Element('child1/', 'parent/', false, false);
            const child2 = new Element('child2/', 'parent/', false, false);
            
            parent.add(child1);
            parent.add(child2);
            
            expect(parent.children).toHaveLength(2);
        });
    });
});

// ============================================================================
// Tree State Tests
// ============================================================================

describe('Tree State Initialization', () => {
    test('should have correct default state', () => {
        const tree = createMockTree();
        
        expect(tree.loading).toBe(false);
        expect(tree.showAllContent).toBe(false);
        expect(tree.filterUsername).toBe('');
        expect(tree.data).toEqual([]);
    });

    test('should have correct default publish modal state', () => {
        const tree = createMockTree();
        
        expect(tree.showPublishModal).toBe(false);
        expect(tree.publishingFile).toBeNull();
        expect(tree.isPublishing).toBe(false);
    });
});

// ============================================================================
// Toggle Show All Tests
// ============================================================================

describe('toggleShowAll', () => {
    test('should toggle showAllContent from false to true', () => {
        const tree = createMockTree();
        tree.showAllContent = false;
        
        tree.toggleShowAll();
        
        expect(tree.showAllContent).toBe(true);
    });

    test('should toggle showAllContent from true to false', () => {
        const tree = createMockTree();
        tree.showAllContent = true;
        
        tree.toggleShowAll();
        
        expect(tree.showAllContent).toBe(false);
    });

    test('should reset data array', () => {
        const tree = createMockTree();
        tree.data = [new Element('folder/', null, false, false)];
        
        tree.toggleShowAll();
        
        expect(tree.data).toEqual([]);
    });
});

// ============================================================================
// Publish Modal Tests
// ============================================================================

describe('Publish Modal', () => {
    beforeEach(() => {
        mockWindowOpen.mockClear();
    });

    describe('openPublishModal', () => {
        test('should set publishingFile and show modal', () => {
            const tree = createMockTree();
            
            tree.openPublishModal('translation/en/sujato/file.json');
            
            expect(tree.publishingFile).toBe('translation/en/sujato/file.json');
            expect(tree.showPublishModal).toBe(true);
        });
    });

    describe('closePublishModal', () => {
        test('should reset modal state', () => {
            const tree = createMockTree();
            tree.showPublishModal = true;
            tree.publishingFile = 'some/file.json';
            
            tree.closePublishModal();
            
            expect(tree.showPublishModal).toBe(false);
            expect(tree.publishingFile).toBeNull();
        });
    });

    describe('reviewPublish', () => {
        test('should open git status panel with filter', () => {
            const tree = createMockTree();
            tree.publishingFile = 'translation/en/sujato/';
            tree.showPublishModal = true;
            
            tree.reviewPublish();
            
            expect(mockWindowOpen).toHaveBeenCalledWith(
                'git_status_panel.html?filter=translation%2Fen%2Fsujato%2F',
                '_blank'
            );
            expect(tree.showPublishModal).toBe(false);
            expect(tree.publishingFile).toBeNull();
        });

        test('should not open if no publishingFile', () => {
            const tree = createMockTree();
            tree.publishingFile = null;
            
            tree.reviewPublish();
            
            expect(mockWindowOpen).not.toHaveBeenCalled();
        });
    });
});

// ============================================================================
// Element Search Tests
// ============================================================================

describe('getElementByName', () => {
    test('should find element at root level', () => {
        const tree = createMockTree();
        const element = new Element('folder/', null, false, false);
        tree.data = [element];
        
        const found = tree.getElementByName('folder/');
        
        expect(found).toBe(element);
    });

    test('should find nested element', () => {
        const tree = createMockTree();
        const parent = new Element('parent/', null, false, false);
        const child = new Element('child/', 'parent/', false, false);
        parent.add(child);
        tree.data = [parent];
        
        const found = tree.getElementByName('parent/child/');
        
        expect(found).toBe(child);
    });

    test('should find deeply nested element', () => {
        const tree = createMockTree();
        const level1 = new Element('level1/', null, false, false);
        const level2 = new Element('level2/', 'level1/', false, false);
        const level3 = new Element('level3/', 'level1/level2/', false, false);
        level1.add(level2);
        level2.add(level3);
        tree.data = [level1];
        
        const found = tree.getElementByName('level1/level2/level3/');
        
        expect(found).toBe(level3);
    });

    test('should return null for non-existent element', () => {
        const tree = createMockTree();
        const element = new Element('folder/', null, false, false);
        tree.data = [element];
        
        const found = tree.getElementByName('nonexistent/');
        
        expect(found).toBeNull();
    });

    test('should return null for empty data', () => {
        const tree = createMockTree();
        tree.data = [];
        
        const found = tree.getElementByName('anything/');
        
        expect(found).toBeNull();
    });

    test('should find correct element among siblings', () => {
        const tree = createMockTree();
        const parent = new Element('parent/', null, false, false);
        const child1 = new Element('child1/', 'parent/', false, false);
        const child2 = new Element('child2/', 'parent/', false, false);
        parent.add(child1);
        parent.add(child2);
        tree.data = [parent];
        
        const found = tree.getElementByName('parent/child2/');
        
        expect(found).toBe(child2);
    });
});

// ============================================================================
// Close Element Tests
// ============================================================================

describe('close', () => {
    test('should set isOpen to false', () => {
        const tree = createMockTree();
        const element = new Element('folder/', null, true, false);
        
        tree.close(element);
        
        expect(element.isOpen).toBe(false);
    });
});

// ============================================================================
// Item Click Tests
// ============================================================================

describe('itemClicked', () => {
    test('should return redirect for file element', () => {
        const tree = createMockTree();
        const fileElement = new Element('file.json', 'path/', false, true);
        tree.data = [fileElement];
        
        const result = tree.itemClicked('path/file.json');
        
        expect(result).toBe('redirect');
    });

    test('should open closed folder element', () => {
        const tree = createMockTree();
        const folderElement = new Element('folder/', null, false, false);
        tree.data = [folderElement];
        
        tree.itemClicked('folder/');
        
        expect(folderElement.isOpen).toBe(true);
    });

    test('should close open folder element', () => {
        const tree = createMockTree();
        const folderElement = new Element('folder/', null, true, false);
        tree.data = [folderElement];
        
        tree.itemClicked('folder/');
        
        expect(folderElement.isOpen).toBe(false);
    });

    test('should do nothing for non-existent element', () => {
        const tree = createMockTree();
        tree.data = [];
        
        // Should not throw
        expect(() => tree.itemClicked('nonexistent/')).not.toThrow();
    });
});

// ============================================================================
// Render Node Tests
// ============================================================================

describe('renderNode', () => {
    test('should return empty string for null element', () => {
        const tree = createMockTree();
        
        const result = tree.renderNode(null);
        
        expect(result).toBe('');
    });

    test('should render folder icon for directory', () => {
        const tree = createMockTree();
        const element = new Element('folder/', null, false, false);
        
        const result = tree.renderNode(element);
        
        expect(result).toContain('mdi-folder-outline');
        expect(result).not.toContain('mdi-folder-open-outline');
    });

    test('should render open folder icon for open directory', () => {
        const tree = createMockTree();
        const element = new Element('folder/', null, true, false);
        
        const result = tree.renderNode(element);
        
        expect(result).toContain('mdi-folder-open-outline');
    });

    test('should render file icon for file', () => {
        const tree = createMockTree();
        const element = new Element('file.json', 'path/', false, true);
        
        const result = tree.renderNode(element);
        
        expect(result).toContain('mdi-file-outline');
    });

    test('should render progress bar for translation file with progress', () => {
        const tree = createMockTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 75;
        element.translatedKeys = 75;
        element.totalKeys = 100;
        
        const result = tree.renderNode(element);
        
        expect(result).toContain('translation-progress');
        expect(result).toContain('75%');
    });

    test('should use high progress class for >= 90%', () => {
        const tree = createMockTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 95;
        
        const result = tree.renderNode(element);
        
        expect(result).toContain('class="translation-progress high"');
    });

    test('should use medium progress class for >= 50%', () => {
        const tree = createMockTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 60;
        
        const result = tree.renderNode(element);
        
        expect(result).toContain('class="translation-progress medium"');
    });

    test('should use low progress class for < 50%', () => {
        const tree = createMockTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 30;
        
        const result = tree.renderNode(element);
        
        expect(result).toContain('class="translation-progress low"');
    });

    test('should not render progress for non-translation files', () => {
        const tree = createMockTree();
        const element = new Element('file.json', 'other/', false, true);
        element.progress = 50;
        
        const result = tree.renderNode(element);
        
        expect(result).not.toContain('translation-progress');
    });

    test('should render loading spinner when loading', () => {
        const tree = createMockTree();
        const element = new Element('folder/', null, false, false);
        element.loading = true;
        
        const result = tree.renderNode(element);
        
        expect(result).toContain('node-loading');
        expect(result).toContain('spinner-small');
    });

    test('should render children for open directory', () => {
        const tree = createMockTree();
        const parent = new Element('parent/', null, true, false);
        const child = new Element('child/', 'parent/', false, false);
        parent.add(child);
        
        const result = tree.renderNode(parent);
        
        expect(result).toContain('navigation-list');
        expect(result).toContain('navigation-list__item');
    });

    test('should not render children for file', () => {
        const tree = createMockTree();
        const element = new Element('file.json', 'path/', true, true);
        
        const result = tree.renderNode(element);
        
        expect(result).not.toContain('<ul class="navigation-list">');
    });

    test('should render publish button for deep paths with muid', () => {
        const tree = createMockTree();
        getMuid.mockReturnValue('en-sujato');
        const element = new Element('file.json', 'translation/en/sujato/sutta/', false, true);
        element.muid = 'en-sujato';
        
        const result = tree.renderNode(element);
        
        expect(result).toContain('btn--publish');
        expect(result).toContain('Publish');
    });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('Edge Cases', () => {
    test('should handle element with special characters in name', () => {
        const tree = createMockTree();
        const element = new Element('file-with-dash_and_underscore.json', 'path/', false, true);
        tree.data = [element];
        
        const found = tree.getElementByName('path/file-with-dash_and_underscore.json');
        
        expect(found).toBe(element);
    });

    test('should handle very deep nesting', () => {
        const tree = createMockTree();
        let current = new Element('level0/', null, false, false);
        tree.data = [current];
        
        for (let i = 1; i <= 10; i++) {
            const child = new Element(`level${i}/`, current.fullName, false, false);
            current.add(child);
            current = child;
        }
        
        const found = tree.getElementByName('level0/level1/level2/level3/level4/level5/level6/level7/level8/level9/level10/');
        
        expect(found).not.toBeNull();
        expect(found.name).toBe('level10/');
    });

    test('should handle element with empty children array', () => {
        const tree = createMockTree();
        const element = new Element('folder/', null, true, false);
        
        const result = tree.renderNode(element);
        
        // Should not render child list if no children
        expect(result).not.toContain('<ul class="navigation-list">');
    });

    test('should handle progress value of 0', () => {
        const tree = createMockTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 0;
        element.translatedKeys = 0;
        element.totalKeys = 100;
        
        const result = tree.renderNode(element);
        
        expect(result).toContain('translation-progress');
        expect(result).toContain('0%');
    });

    test('should handle progress value of 100', () => {
        const tree = createMockTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 100;
        element.translatedKeys = 100;
        element.totalKeys = 100;
        
        const result = tree.renderNode(element);
        
        expect(result).toContain('translation-progress high');
        expect(result).toContain('100%');
    });

    test('should not render progress for null progress', () => {
        const tree = createMockTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = null;
        
        const result = tree.renderNode(element);
        
        expect(result).not.toContain('translation-progress');
    });

    test('should not render progress for negative progress', () => {
        const tree = createMockTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = -1;
        
        const result = tree.renderNode(element);
        
        expect(result).not.toContain('translation-progress');
    });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('Integration Tests', () => {
    beforeEach(() => {
        mockWindowOpen.mockClear();
    });

    test('should handle complete folder open/close workflow', () => {
        const tree = createMockTree();
        const folder = new Element('folder/', null, false, false);
        const child = new Element('child/', 'folder/', false, false);
        folder.add(child);
        tree.data = [folder];
        
        // Initially closed
        expect(folder.isOpen).toBe(false);
        
        // Open folder
        tree.itemClicked('folder/');
        expect(folder.isOpen).toBe(true);
        
        // Close folder
        tree.itemClicked('folder/');
        expect(folder.isOpen).toBe(false);
    });

    test('should handle publish modal workflow', () => {
        const tree = createMockTree();
        const filePath = 'translation/en/sujato/file.json';
        
        // Open modal
        tree.openPublishModal(filePath);
        expect(tree.showPublishModal).toBe(true);
        expect(tree.publishingFile).toBe(filePath);
        
        // Review publish
        tree.reviewPublish();
        expect(mockWindowOpen).toHaveBeenCalled();
        expect(tree.showPublishModal).toBe(false);
        expect(tree.publishingFile).toBeNull();
    });

    test('should build correct element hierarchy', () => {
        const root = new Element('translation/', null, false, false);
        const lang = new Element('en/', 'translation/', false, false);
        const author = new Element('sujato/', 'translation/en/', false, false);
        const file = new Element('mn1.json', 'translation/en/sujato/', false, true);
        
        root.add(lang);
        lang.add(author);
        author.add(file);
        
        expect(root.children).toContain(lang);
        expect(lang.children).toContain(author);
        expect(author.children).toContain(file);
        expect(file.fullName).toBe('translation/en/sujato/mn1.json');
    });

    test('should correctly search in complex tree structure', () => {
        const tree = createMockTree();
        
        // Build a tree with multiple branches
        const root1 = new Element('translation/', null, false, false);
        const root2 = new Element('root/', null, false, false);
        
        const branch1 = new Element('en/', 'translation/', false, false);
        const branch2 = new Element('de/', 'translation/', false, false);
        
        const leaf1 = new Element('file1.json', 'translation/en/', false, true);
        const leaf2 = new Element('file2.json', 'translation/de/', false, true);
        
        root1.add(branch1);
        root1.add(branch2);
        branch1.add(leaf1);
        branch2.add(leaf2);
        
        tree.data = [root1, root2];
        
        // Search for specific file
        const found = tree.getElementByName('translation/de/file2.json');
        expect(found).toBe(leaf2);
        
        // Search for branch
        const foundBranch = tree.getElementByName('translation/en/');
        expect(foundBranch).toBe(branch1);
    });
});
