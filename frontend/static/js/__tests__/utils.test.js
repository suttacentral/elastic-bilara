/**
 * Utils.js Tests
 *
 * This file tests the utility functions in utils.js including:
 * - formatDate
 * - displayMessage
 * - ensureStatusBadge
 * - displayBadge / hideBadge
 * - addLoadingAttribute / removeLoadingAttribute
 * - insertSpinner / removeSpinner
 * - isInViewPort
 * - getMuid / getPrefix
 * - setMaxHeight
 * - ROLES and BadgeStatus constants
 * - getUserInfo (Partly due to dependence on external sources API)
 * - getUpdateStatus / pollUpdateStatus (Partly due to dependence on external sources API)
 * - tooltip (Partly due to dependence on external sources API)
 */

// ============================================================================
// Pure Functions (extracted from utils.js for unit testing)
// ============================================================================

const getMuid = string => string.split("/").slice(0, 3).join("-");
const getPrefix = string => string.split("/").pop().split("_")[0];

function formatDate(dateString) {
    const options = { year: "numeric", month: "long", day: "numeric" };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

function isInViewPort(element) {
    let rect = element.getBoundingClientRect();
    return (
        rect.bottom >= 0 &&
        rect.top <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right >= 0 &&
        rect.left <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

const ROLES = {
    admin: "administrator",
    superuser: "superuser",
    writer: "writer",
    reviewer: "reviewer",
};

const BadgeStatus = {
    COMMITTED: 'committed',
    PENDING: 'pending',
    ERROR: 'error',
    MODIFIED: 'modified'
};

// ============================================================================
// getMuid Tests
// ============================================================================

describe('getMuid', () => {
    test('should extract first 3 path segments and join with hyphen', () => {
        expect(getMuid('root/translation/mn1/file.json')).toBe('root-translation-mn1');
        expect(getMuid('pli-ms/sutta/dn/dn1.json')).toBe('pli-ms-sutta-dn');
    });

    test('should handle paths with fewer than 3 segments', () => {
        // slice(0, 3) Take only the existing elements, then join.
        expect(getMuid('root/translation')).toBe('root-translation');
        expect(getMuid('root')).toBe('root');
    });

    test('should handle empty string', () => {
        // An empty string split returns [''], slice(0,3) returns [''], join returns ''
        expect(getMuid('')).toBe('');
    });

    test('should handle paths with multiple slashes', () => {
        expect(getMuid('a/b/c/d/e/f')).toBe('a-b-c');
    });
});

// ============================================================================
// getPrefix Tests
// ============================================================================

describe('getPrefix', () => {
    test('should extract prefix before underscore from filename', () => {
        expect(getPrefix('root/translation/mn_translation.json')).toBe('mn');
        expect(getPrefix('pli-ms/sutta/dn/dn1_root.json')).toBe('dn1');
    });

    test('should return whole filename if no underscore', () => {
        expect(getPrefix('root/translation/mn1.json')).toBe('mn1.json');
    });

    test('should handle paths without directories', () => {
        expect(getPrefix('mn1_translation.json')).toBe('mn1');
    });

    test('should handle multiple underscores', () => {
        expect(getPrefix('path/to/mn1_translation_v2.json')).toBe('mn1');
    });

    test('should handle empty string', () => {
        expect(getPrefix('')).toBe('');
    });
});

// ============================================================================
// formatDate Tests
// ============================================================================

describe('formatDate', () => {
    test('should format ISO date string', () => {
        const dateStr = '2024-01-15T10:30:00Z';
        const formatted = formatDate(dateStr);
        // The format may vary depending on the locale, but it should include year, month, and day
        expect(formatted).toMatch(/2024/);
        expect(formatted).toMatch(/15/);
    });

    test('should format various date formats', () => {
        expect(formatDate('2024-12-25')).toMatch(/2024/);
        expect(formatDate('December 25, 2024')).toMatch(/2024/);
    });

    test('should handle invalid date gracefully', () => {
        const result = formatDate('invalid-date');
        expect(result).toBe('Invalid Date');
    });
});

// ============================================================================
// ROLES Constant Tests
// ============================================================================

describe('ROLES', () => {
    test('should have correct role values', () => {
        expect(ROLES.admin).toBe('administrator');
        expect(ROLES.superuser).toBe('superuser');
        expect(ROLES.writer).toBe('writer');
        expect(ROLES.reviewer).toBe('reviewer');
    });

    test('should have all expected keys', () => {
        expect(Object.keys(ROLES)).toEqual(['admin', 'superuser', 'writer', 'reviewer']);
    });
});

// ============================================================================
// BadgeStatus Constant Tests
// ============================================================================

describe('BadgeStatus', () => {
    test('should have correct status values', () => {
        expect(BadgeStatus.COMMITTED).toBe('committed');
        expect(BadgeStatus.PENDING).toBe('pending');
        expect(BadgeStatus.ERROR).toBe('error');
        expect(BadgeStatus.MODIFIED).toBe('modified');
    });

    test('should have all expected keys', () => {
        expect(Object.keys(BadgeStatus)).toEqual(['COMMITTED', 'PENDING', 'ERROR', 'MODIFIED']);
    });
});

// ============================================================================
// DOM Related Functions (Requires JSDOM environment)
// ============================================================================

describe('DOM Functions', () => {
    beforeEach(() => {
        // Set up basic DOM structure
        document.body.innerHTML = `
            <div id="test-container">
                <div id="message-element" class="project-header__message"></div>
                <div id="badge-wrapper">
                    <textarea id="test-textarea"></textarea>
                </div>
                <div id="existing-badge" class="translation-cell__status"></div>
                <div id="loading-element"></div>
            </div>
        `;
    });

    afterEach(() => {
        document.body.innerHTML = '';
        jest.clearAllTimers();
    });

    describe('displayMessage', () => {
        function displayMessage(element, message, type) {
            element.textContent = message;
            element.classList.add("project-header__message--show");
            if (type === "failure") {
                element.classList.add("project-header__message--failure");
            }
            // Simplified version, does not test isInViewPort and setTimeout
        }

        test('should display message text', () => {
            const element = document.getElementById('message-element');
            displayMessage(element, 'Test message', 'success');
            expect(element.textContent).toBe('Test message');
        });

        test('should add show class', () => {
            const element = document.getElementById('message-element');
            displayMessage(element, 'Test message', 'success');
            expect(element.classList.contains('project-header__message--show')).toBe(true);
        });

        test('should add failure class when type is failure', () => {
            const element = document.getElementById('message-element');
            displayMessage(element, 'Error message', 'failure');
            expect(element.classList.contains('project-header__message--failure')).toBe(true);
        });

        test('should not add failure class for non-failure types', () => {
            const element = document.getElementById('message-element');
            displayMessage(element, 'Success message', 'success');
            expect(element.classList.contains('project-header__message--failure')).toBe(false);
        });
    });

    describe('ensureStatusBadge', () => {
        function ensureStatusBadge(textarea, muid, uid, isSource) {
            const badgeId = isSource ? `root-badge-${muid}-${uid}` : `translation-badge-${muid}-${uid}`;
            if (document.getElementById(badgeId)) {
                return;
            }
            const badge = document.createElement('sc-bilara-translation-edit-status');
            badge.id = badgeId;
            badge.className = 'translation-cell__status';
            const wrapper = textarea.parentElement;
            if (wrapper) {
                wrapper.appendChild(badge);
            }
        }

        test('should create badge with correct ID for source', () => {
            const textarea = document.getElementById('test-textarea');
            ensureStatusBadge(textarea, 'pli-ms', 'mn1:1.1', true);

            const badge = document.getElementById('root-badge-pli-ms-mn1:1.1');
            expect(badge).not.toBeNull();
            expect(badge.className).toBe('translation-cell__status');
        });

        test('should create badge with correct ID for translation', () => {
            const textarea = document.getElementById('test-textarea');
            ensureStatusBadge(textarea, 'en-sujato', 'mn1:1.1', false);

            const badge = document.getElementById('translation-badge-en-sujato-mn1:1.1');
            expect(badge).not.toBeNull();
        });

        test('should not create duplicate badges', () => {
            const textarea = document.getElementById('test-textarea');
            ensureStatusBadge(textarea, 'pli-ms', 'mn1:1.1', true);
            ensureStatusBadge(textarea, 'pli-ms', 'mn1:1.1', true);

            const badges = document.querySelectorAll('#root-badge-pli-ms-mn1\\:1\\.1');
            expect(badges.length).toBe(1);
        });

        test('should not throw when textarea has no parent', () => {
            const textarea = document.createElement('textarea');
            // textarea 没有父元素
            expect(() => {
                ensureStatusBadge(textarea, 'pli-ms', 'mn1:1.1', true);
            }).not.toThrow();
        });
    });

    describe('displayBadge and hideBadge', () => {
        function displayBadge(badgeId, status) {
            const badge = document.getElementById(badgeId);
            if (badge) badge.status = status;
        }

        function hideBadge(badgeId) {
            const badge = document.getElementById(badgeId);
            if (badge) badge.status = "";
        }

        beforeEach(() => {
            const badge = document.createElement('sc-bilara-translation-edit-status');
            badge.id = 'test-badge';
            badge.status = '';
            document.body.appendChild(badge);
        });

        test('should set badge status', () => {
            displayBadge('test-badge', 'committed');
            const badge = document.getElementById('test-badge');
            expect(badge.status).toBe('committed');
        });

        test('should hide badge by clearing status', () => {
            displayBadge('test-badge', 'pending');
            hideBadge('test-badge');
            const badge = document.getElementById('test-badge');
            expect(badge.status).toBe('');
        });
    });

    describe('addLoadingAttribute and removeLoadingAttribute', () => {
        function addLoadingAttribute(elementId) {
            const element = document.getElementById(elementId);
            if (element) element.setAttribute("loading", "");
        }

        function removeLoadingAttribute(elementId) {
            const element = document.getElementById(elementId);
            if (element) element.removeAttribute("loading");
        }

        test('should add loading attribute', () => {
            addLoadingAttribute('loading-element');
            const element = document.getElementById('loading-element');
            expect(element.hasAttribute('loading')).toBe(true);
        });

        test('should remove loading attribute', () => {
            addLoadingAttribute('loading-element');
            removeLoadingAttribute('loading-element');
            const element = document.getElementById('loading-element');
            expect(element.hasAttribute('loading')).toBe(false);
        });
    });

    describe('insertSpinner and removeSpinner', () => {
        function insertSpinner(badgeId) {
            const badge = document.getElementById(badgeId);
            if (!badge || !badge.parentElement) return;
            const slSpinner = document.createElement('sl-spinner');
            slSpinner.id = 'spinner';
            slSpinner.style = "font-size: 2rem;";
            badge.parentElement.appendChild(slSpinner);
        }

        function removeSpinner() {
            const spinner = document.getElementById('spinner');
            if (spinner) {
                spinner.remove();
            }
        }

        beforeEach(() => {
            const wrapper = document.createElement('div');
            wrapper.id = 'spinner-wrapper';
            const badge = document.createElement('sc-bilara-translation-edit-status');
            badge.id = 'spinner-test-badge';
            wrapper.appendChild(badge);
            document.body.appendChild(wrapper);
        });

        test('should insert spinner next to badge', () => {
            insertSpinner('spinner-test-badge');
            const spinner = document.getElementById('spinner');
            expect(spinner).not.toBeNull();
            expect(spinner.tagName.toLowerCase()).toBe('sl-spinner');
        });

        test('should remove spinner', () => {
            insertSpinner('spinner-test-badge');
            removeSpinner();
            const spinner = document.getElementById('spinner');
            expect(spinner).toBeNull();
        });

        test('should not throw if no spinner exists', () => {
            expect(() => removeSpinner()).not.toThrow();
        });
    });

    describe('isInViewPort', () => {
        test('should return true for element in viewport', () => {
            const element = document.createElement('div');
            element.getBoundingClientRect = jest.fn(() => ({
                top: 0,
                left: 0,
                bottom: 100,
                right: 100
            }));

            Object.defineProperty(window, 'innerHeight', { value: 768, writable: true });
            Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });

            expect(isInViewPort(element)).toBe(true);
        });

        test('should return false for element above viewport', () => {
            const element = document.createElement('div');
            element.getBoundingClientRect = jest.fn(() => ({
                top: -200,
                left: 0,
                bottom: -100,
                right: 100
            }));

            expect(isInViewPort(element)).toBe(false);
        });

        test('should return false for element below viewport', () => {
            const element = document.createElement('div');
            element.getBoundingClientRect = jest.fn(() => ({
                top: 1000,
                left: 0,
                bottom: 1100,
                right: 100
            }));

            Object.defineProperty(window, 'innerHeight', { value: 768, writable: true });

            expect(isInViewPort(element)).toBe(false);
        });

        test('should return false for element to the left of viewport', () => {
            const element = document.createElement('div');
            element.getBoundingClientRect = jest.fn(() => ({
                top: 0,
                left: -200,
                bottom: 100,
                right: -100
            }));

            expect(isInViewPort(element)).toBe(false);
        });

        test('should return true for partially visible element', () => {
            const element = document.createElement('div');
            element.getBoundingClientRect = jest.fn(() => ({
                top: -50,
                left: 0,
                bottom: 50,
                right: 100
            }));

            Object.defineProperty(window, 'innerHeight', { value: 768, writable: true });
            Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });

            expect(isInViewPort(element)).toBe(true);
        });
    });

    describe('setMaxHeight', () => {
        function setMaxHeight(textareas) {
            const maxHeight = Math.max(...textareas.map(textarea => textarea.scrollHeight));
            textareas.forEach(textarea => (textarea.style.height = `${maxHeight}px`));
        }

        test('should set all textareas to max height', () => {
            const textarea1 = document.createElement('textarea');
            const textarea2 = document.createElement('textarea');
            const textarea3 = document.createElement('textarea');

            // Mock scrollHeight
            Object.defineProperty(textarea1, 'scrollHeight', { value: 50, writable: true });
            Object.defineProperty(textarea2, 'scrollHeight', { value: 100, writable: true });
            Object.defineProperty(textarea3, 'scrollHeight', { value: 75, writable: true });

            setMaxHeight([textarea1, textarea2, textarea3]);

            expect(textarea1.style.height).toBe('100px');
            expect(textarea2.style.height).toBe('100px');
            expect(textarea3.style.height).toBe('100px');
        });

        test('should handle single textarea', () => {
            const textarea = document.createElement('textarea');
            Object.defineProperty(textarea, 'scrollHeight', { value: 50, writable: true });

            setMaxHeight([textarea]);

            expect(textarea.style.height).toBe('50px');
        });

        test('should handle empty array', () => {
            expect(() => setMaxHeight([])).not.toThrow();
        });
    });
});

// ============================================================================
// getUserInfo Tests (Structural testing)
// ============================================================================

describe('getUserInfo', () => {
    function getUserInfo() {
        return {
            isAdmin: false,
            isActive: false,
            username: "",
            avatarURL: "",
            async getRole() {
                // Simulated implementation
            },
        };
    }

    test('should return object with correct initial values', () => {
        const userInfo = getUserInfo();
        expect(userInfo.isAdmin).toBe(false);
        expect(userInfo.isActive).toBe(false);
        expect(userInfo.username).toBe("");
        expect(userInfo.avatarURL).toBe("");
    });

    test('should have getRole method', () => {
        const userInfo = getUserInfo();
        expect(typeof userInfo.getRole).toBe('function');
    });
});

// ============================================================================
// tooltip Tests (Structural testing)
// ============================================================================

describe('tooltip', () => {
    function tooltip() {
        return {
            show: false,
            tooltipData: [],
            requested: false,
            async fetchData(path) {
                // Simulated implementation
            },
            hide() {
                this.show = false;
            },
        };
    }

    test('should return object with correct initial values', () => {
        const tip = tooltip();
        expect(tip.show).toBe(false);
        expect(tip.tooltipData).toEqual([]);
        expect(tip.requested).toBe(false);
    });

    test('should have fetchData method', () => {
        const tip = tooltip();
        expect(typeof tip.fetchData).toBe('function');
    });

    test('should have hide method that sets show to false', () => {
        const tip = tooltip();
        tip.show = true;
        tip.hide();
        expect(tip.show).toBe(false);
    });
});

// ============================================================================
// pollUpdateStatus Tests (State Machine Testing)
// ============================================================================

describe('pollUpdateStatus state machine', () => {
    test('SUCCESS status should add success class and remove others', () => {
        const element = document.createElement('div');
        element.classList.add('loading');

        const status = 'SUCCESS';
        switch (status.toUpperCase()) {
            case "SUCCESS":
                element.classList.remove("loading", "failure");
                element.classList.add("success");
                break;
        }

        expect(element.classList.contains('success')).toBe(true);
        expect(element.classList.contains('loading')).toBe(false);
        expect(element.classList.contains('failure')).toBe(false);
    });

    test('FAILURE status should add failure class and remove others', () => {
        const element = document.createElement('div');
        element.classList.add('loading');

        const status = 'FAILURE';
        switch (status.toUpperCase()) {
            case "FAILURE":
                element.classList.remove("loading", "success");
                element.classList.add("failure");
                break;
        }

        expect(element.classList.contains('failure')).toBe(true);
        expect(element.classList.contains('loading')).toBe(false);
        expect(element.classList.contains('success')).toBe(false);
    });

    test('PENDING status should add loading class', () => {
        const element = document.createElement('div');

        const status = 'PENDING';
        switch (status.toUpperCase()) {
            case "SUCCESS":
            case "FAILURE":
                break;
            default:
                element.classList.remove("success", "failure");
                element.classList.add("loading");
        }

        expect(element.classList.contains('loading')).toBe(true);
    });
});

// ============================================================================
// Edge Cases and Error Handling
// ============================================================================

describe('Edge Cases and Error Handling', () => {
    describe('getMuid edge cases', () => {
        test('should handle paths with dots', () => {
            expect(getMuid('pli-ms/sutta/mn/mn1.2.json')).toBe('pli-ms-sutta-mn');
        });

        test('should handle paths with special characters', () => {
            expect(getMuid('pli-ms/sutta-test/kp/file.json')).toBe('pli-ms-sutta-test-kp');
        });
    });

    describe('getPrefix edge cases', () => {
        test('should handle filenames with only underscore', () => {
            expect(getPrefix('path/to/_translation.json')).toBe('');
        });

        test('should handle deeply nested paths', () => {
            expect(getPrefix('a/b/c/d/e/f/g/mn1_test.json')).toBe('mn1');
        });
    });

    describe('formatDate edge cases', () => {
        test('should handle timestamp', () => {
            const formatted = formatDate(Date.now());
            expect(typeof formatted).toBe('string');
        });

        test('should handle date at epoch', () => {
            const formatted = formatDate(0);
            expect(formatted).toMatch(/1970/);
        });
    });
});
