/**
 * Navigation (nav.js) Tests
 *
 * This file tests the real nav.js functionality including:
 * - tree() function state and methods loaded from nav.js runtime
 * - Element class construction and methods
 * - Directory tree navigation
 * - Publish modal state management
 * - Progress display logic
 * - Element search functionality
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

// ============================================================================
// Runtime Loader Setup
// ============================================================================

function loadNavRuntime(overrides = {}) {
    const navPath = path.resolve(__dirname, '../nav.js');
    const code = fs.readFileSync(navPath, 'utf8');

    const mockWindowOpen = overrides.mockWindowOpen || jest.fn();
    const sandbox = {
        console,
        setTimeout,
        clearTimeout,
        window: {
            location: { href: '' },
            open: mockWindowOpen,
            scrollTo: jest.fn(),
            scrollY: 0,
            history: {
                state: null,
                replaceState: jest.fn(),
            },
            ...(overrides.window || {}),
        },
        document: {
            querySelector: jest.fn(),
            querySelectorAll: jest.fn(() => []),
            ...(overrides.document || {}),
        },
        localStorage: {
            store: {},
            getItem: jest.fn((key) => sandbox.localStorage.store[key] || null),
            setItem: jest.fn((key, value) => { sandbox.localStorage.store[key] = value; }),
            removeItem: jest.fn((key) => { delete sandbox.localStorage.store[key]; }),
            clear: jest.fn(() => { sandbox.localStorage.store = {}; }),
            ...(overrides.localStorage || {}),
        },
        fetch: jest.fn(),
        requestWithTokenRetry: overrides.requestWithTokenRetry || jest.fn(async () => ({
            ok: true,
            json: async () => ({ directories: [], base: null }),
        })),
        getUserInfo: overrides.getUserInfo || jest.fn(() => ({
            getRole: jest.fn().mockResolvedValue(),
            username: 'testuser',
            isAdmin: false,
            role: 'writer',
        })),
        getMuid: overrides.getMuid || jest.fn((fullName) => {
            const parts = fullName.split('/').filter(p => p);
            if (parts.length > 3) {
                const fileName = parts[parts.length - 1];
                const match = fileName.match(/_([^_]+)\./);
                return match ? match[1] : null;
            }
            return null;
        }),
        getPrefix: overrides.getPrefix || jest.fn((name) => {
            return name.split('_')[0] || null;
        }),
        ROLES: {
            admin: 'administrator',
            superuser: 'superuser',
            writer: 'writer',
            reviewer: 'reviewer',
        },
        ...overrides.globals,
    };

    vm.createContext(sandbox);
    vm.runInContext(`${code}\nthis.__tree = tree; this.__Element = Element;`, sandbox);

    return {
        treeFactory: sandbox.__tree,
        Element: sandbox.__Element,
        sandbox,
        mockWindowOpen,
    };
}

let treeFactory;
let Element;
let mockWindowOpen;
let defaultSandbox;

function createTestTree(overrides = {}) {
    const tree = treeFactory();
    Object.assign(tree, overrides);
    return tree;
}

beforeEach(() => {
    const runtime = loadNavRuntime();
    treeFactory = runtime.treeFactory;
    Element = runtime.Element;
    mockWindowOpen = runtime.mockWindowOpen;
    defaultSandbox = runtime.sandbox;
});

// ============================================================================
// Element Class Tests
// ============================================================================

describe('Element Class', () => {
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
            expect(element.canPublish).toBe(false);
            expect(element.isVirtual).toBe(false);
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
            defaultSandbox.getMuid.mockReturnValue('en-sujato');
            const element = new Element('file.json', 'translation/en/sujato/sutta/', false, true);

            expect(defaultSandbox.getMuid).toHaveBeenCalled();
            expect(element.muid).toBe('en-sujato');
        });

        test('should not set muid for shallow paths', () => {
            const element = new Element('folder/', 'parent/', false, false);

            expect(element.muid).toBeNull();
        });

        test('should set prefix for files', () => {
            defaultSandbox.getPrefix.mockReturnValue('mn1');
            const element = new Element('mn1_translation-en-sujato.json', 'path/', false, true);

            expect(defaultSandbox.getPrefix).toHaveBeenCalledWith('mn1_translation-en-sujato.json');
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
        const tree = createTestTree();

        expect(tree.loading).toBe(false);
        expect(tree.showAllContent).toBe(false);
        expect(tree.filterUsername).toBe('');
        expect(tree.data).toEqual([]);
    });

    test('should have correct default publish modal state', () => {
        const tree = createTestTree();

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
        const tree = createTestTree();
        tree.showAllContent = false;
        tree.init = jest.fn();

        tree.toggleShowAll();

        expect(tree.showAllContent).toBe(true);
        expect(tree.init).toHaveBeenCalled();
    });

    test('should toggle showAllContent from true to false', () => {
        const tree = createTestTree();
        tree.showAllContent = true;
        tree.init = jest.fn();

        tree.toggleShowAll();

        expect(tree.showAllContent).toBe(false);
        expect(tree.init).toHaveBeenCalled();
    });

    test('should reset data array', () => {
        const tree = createTestTree();
        tree.data = [new Element('folder/', null, false, false)];
        tree.init = jest.fn();

        tree.toggleShowAll();

        expect(tree.data).toEqual([]);
    });
});

// ============================================================================
// Publish Modal Tests
// ============================================================================

describe('Publish Modal', () => {
    describe('openPublishModal', () => {
        test('should set publishingFile and show modal', () => {
            const tree = createTestTree();

            tree.openPublishModal('translation/en/sujato/file.json');

            expect(tree.publishingFile).toBe('translation/en/sujato/file.json');
            expect(tree.showPublishModal).toBe(true);
        });
    });

    describe('closePublishModal', () => {
        test('should reset modal state', () => {
            const tree = createTestTree();
            tree.showPublishModal = true;
            tree.publishingFile = 'some/file.json';

            tree.closePublishModal();

            expect(tree.showPublishModal).toBe(false);
            expect(tree.publishingFile).toBeNull();
        });
    });

    describe('reviewPublish', () => {
        test('should open git status panel with filter', () => {
            const tree = createTestTree();
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
            const tree = createTestTree();
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
        const tree = createTestTree();
        const element = new Element('folder/', null, false, false);
        tree.data = [element];

        const found = tree.getElementByName('folder/');

        expect(found).toBe(element);
    });

    test('should find nested element', () => {
        const tree = createTestTree();
        const parent = new Element('parent/', null, false, false);
        const child = new Element('child/', 'parent/', false, false);
        parent.add(child);
        tree.data = [parent];

        const found = tree.getElementByName('parent/child/');

        expect(found).toBe(child);
    });

    test('should find deeply nested element', () => {
        const tree = createTestTree();
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
        const tree = createTestTree();
        const element = new Element('folder/', null, false, false);
        tree.data = [element];

        const found = tree.getElementByName('nonexistent/');

        expect(found).toBeNull();
    });

    test('should return null for empty data', () => {
        const tree = createTestTree();
        tree.data = [];

        const found = tree.getElementByName('anything/');

        expect(found).toBeNull();
    });

    test('should find correct element among siblings', () => {
        const tree = createTestTree();
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
        const tree = createTestTree();
        const element = new Element('folder/', null, true, false);

        tree.close(element);

        expect(element.isOpen).toBe(false);
    });
});

// ============================================================================
// Item Click Tests
// ============================================================================

describe('itemClicked', () => {
    test('should redirect for file element', () => {
        const tree = createTestTree();
        const fileElement = new Element('file.json', 'path/', false, true);
        tree.data = [fileElement];
        tree.redirectToFile = jest.fn();

        tree.itemClicked('path/file.json');

        expect(tree.redirectToFile).toHaveBeenCalledWith(fileElement);
    });

    test('should open closed folder element', () => {
        const tree = createTestTree();
        const folderElement = new Element('folder/', null, false, false);
        tree.data = [folderElement];
        tree.open = jest.fn();

        tree.itemClicked('folder/');

        expect(tree.open).toHaveBeenCalledWith(folderElement);
    });

    test('should close open folder element', () => {
        const tree = createTestTree();
        const folderElement = new Element('folder/', null, true, false);
        tree.data = [folderElement];

        tree.itemClicked('folder/');

        expect(folderElement.isOpen).toBe(false);
    });

    test('should do nothing for non-existent element', () => {
        const tree = createTestTree();
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
        const tree = createTestTree();

        const result = tree.renderNode(null);

        expect(result).toBe('');
    });

    test('should render folder icon for directory', () => {
        const tree = createTestTree();
        const element = new Element('folder/', null, false, false);

        const result = tree.renderNode(element);

        expect(result).toContain('mdi-folder-outline');
        expect(result).not.toContain('mdi-folder-open-outline');
    });

    test('should render open folder icon for open directory', () => {
        const tree = createTestTree();
        const element = new Element('folder/', null, true, false);

        const result = tree.renderNode(element);

        expect(result).toContain('mdi-folder-open-outline');
    });

    test('should render file icon for file', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'path/', false, true);

        const result = tree.renderNode(element);

        expect(result).toContain('mdi-file-outline');
    });

    test('should render progress bar for translation file with progress', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 75;
        element.translatedKeys = 75;
        element.totalKeys = 100;

        const result = tree.renderNode(element);

        expect(result).toContain('translation-progress');
        expect(result).toContain('75%');
    });

    test('should use high progress class for >= 90%', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 95;

        const result = tree.renderNode(element);

        expect(result).toContain('class="translation-progress high"');
    });

    test('should use medium progress class for >= 50%', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 60;

        const result = tree.renderNode(element);

        expect(result).toContain('class="translation-progress medium"');
    });

    test('should use low progress class for < 50%', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 30;

        const result = tree.renderNode(element);

        expect(result).toContain('class="translation-progress low"');
    });

    test('should not render progress for non-translation files', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'other/', false, true);
        element.progress = 50;

        const result = tree.renderNode(element);

        expect(result).not.toContain('translation-progress');
    });

    test('should render loading spinner when loading', () => {
        const tree = createTestTree();
        const element = new Element('folder/', null, false, false);
        element.loading = true;

        const result = tree.renderNode(element);

        expect(result).toContain('node-loading');
        expect(result).toContain('spinner-small');
    });

    test('should render children for open directory', () => {
        const tree = createTestTree();
        const parent = new Element('parent/', null, true, false);
        const child = new Element('child/', 'parent/', false, false);
        parent.add(child);

        const result = tree.renderNode(parent);

        expect(result).toContain('navigation-list');
        expect(result).toContain('navigation-list__item');
    });

    test('should not render children for file', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'path/', true, true);

        const result = tree.renderNode(element);

        expect(result).not.toContain('<ul class="navigation-list">');
    });

    test('should render publish button when element has muid and canPublish is true', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/en/sujato/sutta/', false, true);
        element.muid = 'en-sujato';
        element.canPublish = true;
        element.isVirtual = false;

        const result = tree.renderNode(element);

        expect(result).toContain('btn--publish');
        expect(result).toContain('Publish');
    });

    test('should not render publish button when canPublish is false', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/en/sujato/sutta/', false, true);
        element.muid = 'en-sujato';
        element.canPublish = false;
        element.isVirtual = false;

        const result = tree.renderNode(element);

        expect(result).not.toContain('btn--publish');
    });

    test('should not render publish button for virtual files even if canPublish is true', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/en/sujato/sutta/', false, true);
        element.muid = 'en-sujato';
        element.canPublish = true;
        element.isVirtual = true;

        const result = tree.renderNode(element);

        expect(result).not.toContain('btn--publish');
    });

    test('should not render publish button for shallow paths without deep segments', () => {
        const tree = createTestTree();
        const element = new Element('sn/', 'translation/en/', false, false);
        element.muid = 'en';
        element.canPublish = true;
        element.isVirtual = false;

        const result = tree.renderNode(element);

        expect(result).not.toContain('btn--publish');
    });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('Edge Cases', () => {
    test('should handle element with special characters in name', () => {
        const tree = createTestTree();
        const element = new Element('file-with-dash_and_underscore.json', 'path/', false, true);
        tree.data = [element];

        const found = tree.getElementByName('path/file-with-dash_and_underscore.json');

        expect(found).toBe(element);
    });

    test('should handle very deep nesting', () => {
        const tree = createTestTree();
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
        const tree = createTestTree();
        const element = new Element('folder/', null, true, false);

        const result = tree.renderNode(element);

        // Should not render child list if no children
        expect(result).not.toContain('<ul class="navigation-list">');
    });

    test('should handle progress value of 0', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 0;
        element.translatedKeys = 0;
        element.totalKeys = 100;

        const result = tree.renderNode(element);

        expect(result).toContain('translation-progress');
        expect(result).toContain('0%');
    });

    test('should handle progress value of 100', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 100;
        element.translatedKeys = 100;
        element.totalKeys = 100;

        const result = tree.renderNode(element);

        expect(result).toContain('translation-progress high');
        expect(result).toContain('100%');
    });

    test('should not render progress for null progress', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = null;

        const result = tree.renderNode(element);

        expect(result).not.toContain('translation-progress');
    });

    test('should not render progress for negative progress', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = -1;

        const result = tree.renderNode(element);

        expect(result).not.toContain('translation-progress');
    });

    test('should render guide line and row wrapper when node has actions', () => {
        const tree = createTestTree();
        const element = new Element('file.json', 'translation/', false, true);
        element.progress = 50;
        element.translatedKeys = 50;
        element.totalKeys = 100;

        const result = tree.renderNode(element);

        expect(result).toContain('navigation-list__row');
        expect(result).toContain('navigation-list__row--has-actions');
        expect(result).toContain('navigation-list__guide-line');
        expect(result).toContain('navigation-list__actions');
    });

    test('should not render guide line when node has no actions', () => {
        const tree = createTestTree();
        const element = new Element('folder/', null, false, false);

        const result = tree.renderNode(element);

        expect(result).toContain('navigation-list__row');
        expect(result).not.toContain('navigation-list__row--has-actions');
        expect(result).not.toContain('navigation-list__guide-line');
        expect(result).not.toContain('navigation-list__actions');
    });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('Integration Tests', () => {
    test('should handle complete folder open/close workflow', () => {
        const tree = createTestTree();
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
        const tree = createTestTree();
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
        const tree = createTestTree();

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
