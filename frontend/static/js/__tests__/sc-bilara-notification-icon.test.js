const fs = require('fs');
const path = require('path');

const componentSource = fs.readFileSync(
  path.resolve(
    __dirname,
    '../elements/notification/sc-bilara-notification-icon.js',
  ),
  'utf8',
);

class LitElementStub extends HTMLElement {
  connectedCallback() {}
  disconnectedCallback() {}
}

const templateTagStub = () => '';

function loadComponent() {
  if (!customElements.get('sc-bilara-notification-icon')) {
    const executableSource = componentSource.replace(/^import .*;\n/gm, '');
    const evaluate = new Function(
      'LitElement',
      'html',
      'css',
      executableSource,
    );
    evaluate(LitElementStub, templateTagStub, templateTagStub);
  }

  return customElements.get('sc-bilara-notification-icon');
}

class EventSourceMock {
  constructor(url) {
    this.url = url;
    this.listeners = new Map();
    this.close = jest.fn();
    EventSourceMock.instances.push(this);
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }

  removeEventListener(name) {
    this.listeners.delete(name);
  }
}

EventSourceMock.instances = [];

describe('notification count icon', () => {
  const NotificationIcon = loadComponent();

  beforeEach(() => {
    jest.useFakeTimers();
    EventSourceMock.instances = [];
    global.EventSource = EventSourceMock;
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  test('uses the stream for initial count without downloading the feed', () => {
    const icon = new NotificationIcon();

    icon.connectedCallback();

    expect(EventSourceMock.instances).toHaveLength(1);
    expect(EventSourceMock.instances[0].url).toBe('/api/v1/notifications/stream');
    expect(fetch).not.toHaveBeenCalled();
    expect(componentSource).not.toContain("fetch('/api/v1/notifications/feed')");

    icon.disconnectedCallback();
  });

  test('updates the badge from an unread_count stream event', () => {
    const icon = new NotificationIcon();

    icon._handleUnreadCountEvent({ data: '{"unread_count": 5}' });

    expect(icon.count).toBe(5);
  });

  test('uses the lightweight count endpoint after a local update', async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ unread_count: 3 }),
    });
    const icon = new NotificationIcon();

    await icon._handleNotificationsUpdated();

    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/notifications/count',
      { credentials: 'include' },
    );
    expect(icon.count).toBe(3);
  });

  test('deduplicates concurrent count refreshes', async () => {
    let resolveResponse;
    fetch.mockReturnValue(new Promise(resolve => {
      resolveResponse = resolve;
    }));
    const icon = new NotificationIcon();

    const firstRefresh = icon._refreshNotificationCount();
    const secondRefresh = icon._refreshNotificationCount();
    resolveResponse({
      ok: true,
      json: async () => ({ unread_count: 2 }),
    });
    await Promise.all([firstRefresh, secondRefresh]);

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(icon.count).toBe(2);
  });
});
