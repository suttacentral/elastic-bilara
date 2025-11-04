// 模拟浏览器环境的全局对象
global.localStorage = {
    getItem: jest.fn(),
    setItem: jest.fn(),
    removeItem: jest.fn(),
    clear: jest.fn()
};

global.requestWithTokenRetry = jest.fn();

// 模拟 DOM 方法
global.document.querySelector = jest.fn();