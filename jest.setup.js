global.localStorage = {
    getItem: jest.fn(),
    setItem: jest.fn(),
    removeItem: jest.fn(),
    clear: jest.fn()
};

global.requestWithTokenRetry = jest.fn();

global.document.querySelector = jest.fn();