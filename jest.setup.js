global.localStorage = {
    getItem: jest.fn(),
    setItem: jest.fn(),
    removeItem: jest.fn(),
    clear: jest.fn()
};

global.requestWithTokenRetry = jest.fn();

global.document.querySelector = jest.fn();

// Load the same shared segment policy that translation.html loads before its controllers.
Object.assign(global, new Function(
    require('fs').readFileSync(require('path').join(__dirname, 'frontend/static/js/segment-permissions.js'), 'utf8') +
    '\nreturn { isCommentReadOnly, assertCommentSegmentsEditable };'
)());
