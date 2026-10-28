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

function response(status = 200, unread_count = 3) {
  return { status, ok: status >= 200 && status < 300, json: async () => ({ unread_count }) };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function latestStream() {
  return EventSourceMock.instances.at(-1);
}

function emit(name, data = {}) {
  latestStream().listeners.get(name)({ data: JSON.stringify(data) });
}

function urls() {
  return fetch.mock.calls.map(([url]) => url);
}

describe('notification count icon', () => {
  const NotificationIcon = loadComponent();
  let icon;

  beforeEach(() => {
    jest.useFakeTimers();
    jest.spyOn(Math, 'random').mockReturnValue(0);
    jest.spyOn(console, 'error').mockImplementation(() => {});
    EventSourceMock.instances = [];
    global.EventSource = EventSourceMock;
    global.fetch = jest.fn().mockResolvedValue(response());
    icon = new NotificationIcon();
    document.body.appendChild(icon);
  });

  afterEach(() => {
    icon.remove();
    jest.clearAllTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  test('uses the stream for initial count without downloading the feed', () => {
    expect(EventSourceMock.instances).toHaveLength(1);
    expect(latestStream().url).toBe('/api/v1/notifications/stream');
    expect(fetch).not.toHaveBeenCalled();
  });

  test('updates the badge from an unread_count stream event', () => {
    emit('unread_count', { unread_count: 5 });
    expect(icon.count).toBe(5);
  });

  test('uses the count endpoint after a local update', async () => {
    window.dispatchEvent(new Event('notifications-updated'));
    await jest.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledWith('/api/v1/notifications/count', {
      credentials: 'include', signal: expect.any(AbortSignal),
    });
    expect(icon.count).toBe(3);
  });

  test('deduplicates concurrent count refreshes', async () => {
    const pending = deferred();
    fetch.mockReturnValueOnce(pending.promise);
    const first = icon._handleNotificationsUpdated();
    const second = icon._handleNotificationsUpdated();
    pending.resolve(response(200, 2));
    await Promise.all([first, second]);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(icon.count).toBe(2);
  });

  test('query errors retry only SSE with growing, capped delays', async () => {
    for (const delay of [5000, 10000, 20000, 40000, 60000, 60000]) {
      const count = EventSourceMock.instances.length;
      const oldStream = latestStream();
      emit('stream_error', { error: 'Busy' });
      expect(oldStream.close).toHaveBeenCalledTimes(1);
      // Local events during recovery must not create a second counting path.
      window.dispatchEvent(new Event('notifications-updated'));
      await jest.advanceTimersByTimeAsync(delay - 1);
      expect(EventSourceMock.instances).toHaveLength(count);
      await jest.advanceTimersByTimeAsync(1);
      expect(EventSourceMock.instances).toHaveLength(count + 1);
      expect(fetch).not.toHaveBeenCalled();
    }
  });

  test.each([0, 0.5, 0.999])('applies jitter to each retry (random=%s)', async random => {
    Math.random.mockReturnValue(random);
    const delay = Math.floor(10000 * (0.5 + random * 0.5));
    emit('stream_error');
    await jest.advanceTimersByTimeAsync(delay - 1);
    expect(EventSourceMock.instances).toHaveLength(1);
    await jest.advanceTimersByTimeAsync(1);
    expect(EventSourceMock.instances).toHaveLength(2);
  });

  test('resets backoff only after a valid count event', async () => {
    emit('stream_error');
    await jest.advanceTimersByTimeAsync(5000);
    emit('unread_count', { unread_count: -1 });
    emit('stream_error');
    await jest.advanceTimersByTimeAsync(9999);
    expect(EventSourceMock.instances).toHaveLength(2);
    await jest.advanceTimersByTimeAsync(1);
    emit('unread_count', { unread_count: 0 });
    emit('stream_error');
    await jest.advanceTimersByTimeAsync(5000);
    expect(EventSourceMock.instances).toHaveLength(4);
  });

  test('checks auth after transport backoff without querying count', async () => {
    latestStream().onerror();
    expect(fetch).not.toHaveBeenCalled();
    await jest.advanceTimersByTimeAsync(5000);
    expect(urls()).toEqual(['/api/v1/users/me']);
    expect(EventSourceMock.instances).toHaveLength(2);
  });

  test('refreshes expired access once, verifies it, then reconnects', async () => {
    fetch.mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200))
      .mockResolvedValueOnce(response(200));
    latestStream().onerror();
    await jest.advanceTimersByTimeAsync(5000);
    expect(urls()).toEqual(['/api/v1/users/me', '/api/v1/refresh/', '/api/v1/users/me']);
    expect(fetch.mock.calls[1][1]).toEqual(expect.objectContaining({ method: 'POST', credentials: 'include' }));
    expect(EventSourceMock.instances).toHaveLength(2);
  });

  test.each([401, 403])('stops retries when refresh confirms auth failure (%s)', async status => {
    fetch.mockResolvedValueOnce(response(401)).mockResolvedValueOnce(response(status));
    latestStream().onerror();
    await jest.advanceTimersByTimeAsync(5000);
    window.dispatchEvent(new Event('notifications-updated'));
    await jest.advanceTimersByTimeAsync(600000);
    expect(urls()).toEqual(['/api/v1/users/me', '/api/v1/refresh/']);
    expect(EventSourceMock.instances).toHaveLength(1);
    expect(jest.getTimerCount()).toBe(0);
    icon.remove();
    document.body.appendChild(icon);
    expect(EventSourceMock.instances).toHaveLength(2);
  });

  test('stops if refreshed access is still unauthorized', async () => {
    fetch.mockResolvedValueOnce(response(401)).mockResolvedValueOnce(response())
      .mockResolvedValueOnce(response(401));
    latestStream().onerror();
    await jest.advanceTimersByTimeAsync(600000);
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(EventSourceMock.instances).toHaveLength(1);
    expect(jest.getTimerCount()).toBe(0);
  });

  test('does not refresh forbidden credentials', async () => {
    fetch.mockResolvedValueOnce(response(403));
    latestStream().onerror();
    await jest.advanceTimersByTimeAsync(600000);
    expect(urls()).toEqual(['/api/v1/users/me']);
    expect(EventSourceMock.instances).toHaveLength(1);
  });

  test.each(['network', 'server', 'refresh'])('keeps transient %s failures recoverable', async failure => {
    if (failure === 'network') fetch.mockRejectedValueOnce(new TypeError('offline'));
    if (failure === 'server') fetch.mockResolvedValueOnce(response(503));
    if (failure === 'refresh') {
      fetch.mockResolvedValueOnce(response(401)).mockResolvedValueOnce(response(503));
    }
    latestStream().onerror();
    await jest.advanceTimersByTimeAsync(5000);
    expect(EventSourceMock.instances).toHaveLength(1);
    await jest.advanceTimersByTimeAsync(9999);
    expect(EventSourceMock.instances).toHaveLength(1);
    await jest.advanceTimersByTimeAsync(1);
    expect(EventSourceMock.instances).toHaveLength(2);
    expect(urls()).not.toContain('/api/v1/logout/');
    expect(urls()).not.toContain('/api/v1/notifications/count');
  });

  test('waits for an existing count before probing auth and opening another stream', async () => {
    const pending = deferred();
    fetch.mockReturnValueOnce(pending.promise);
    const refresh = icon._handleNotificationsUpdated();
    latestStream().onerror();
    await jest.advanceTimersByTimeAsync(5000);
    window.dispatchEvent(new Event('notifications-updated'));
    expect(urls()).toEqual(['/api/v1/notifications/count']);
    expect(EventSourceMock.instances).toHaveLength(1);
    pending.resolve(response(401));
    await refresh;
    await jest.advanceTimersByTimeAsync(0);
    expect(urls()).toEqual(['/api/v1/notifications/count', '/api/v1/users/me']);
    expect(EventSourceMock.instances).toHaveLength(2);
    expect(jest.getTimerCount()).toBe(0);
  });

  test('routes a count 401 through delayed auth recovery without retrying count', async () => {
    fetch.mockResolvedValueOnce(response(401)).mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(401));
    await icon._handleNotificationsUpdated();
    await jest.advanceTimersByTimeAsync(600000);
    expect(urls()).toEqual(['/api/v1/notifications/count', '/api/v1/users/me', '/api/v1/refresh/']);
    expect(EventSourceMock.instances).toHaveLength(1);
  });

  test('a count 403 stops streaming and local refreshes', async () => {
    fetch.mockResolvedValueOnce(response(403));
    const stream = latestStream();
    await icon._handleNotificationsUpdated();
    window.dispatchEvent(new Event('notifications-updated'));
    await jest.advanceTimersByTimeAsync(600000);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(stream.close).toHaveBeenCalledTimes(1);
    expect(EventSourceMock.instances).toHaveLength(1);
  });

  test('aborts pending counts on unmount and ignores late results across remount', async () => {
    const old = deferred();
    const current = deferred();
    fetch.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const oldRefresh = icon._handleNotificationsUpdated();
    const signal = fetch.mock.calls[0][1].signal;
    icon.remove();
    expect(signal.aborted).toBe(true);
    document.body.appendChild(icon);
    const newRefresh = icon._handleNotificationsUpdated();
    old.resolve(response(200, 99));
    await oldRefresh;
    expect(icon.count).toBe(0);
    // The old finally block must not erase the new request's deduplication state.
    const duplicate = icon._handleNotificationsUpdated();
    expect(fetch).toHaveBeenCalledTimes(2);
    current.resolve(response(200, 7));
    await Promise.all([newRefresh, duplicate]);
    expect(icon.count).toBe(7);
  });

  test('ignores queued events from a closed stream and cancels reconnection on unmount', async () => {
    const stream = latestStream();
    const oldError = stream.onerror;
    const oldCount = stream.listeners.get('unread_count');
    const oldQueryError = stream.listeners.get('stream_error');
    oldError();
    icon.remove();
    expect(stream.onerror).toBeNull();
    document.body.appendChild(icon);
    oldError();
    oldQueryError();
    oldCount({ data: '{"unread_count":99}' });
    await jest.advanceTimersByTimeAsync(600000);
    expect(EventSourceMock.instances).toHaveLength(2);
    expect(icon.count).toBe(0);
    expect(fetch).not.toHaveBeenCalled();
  });

  test('aborts auth probes on unmount and never refreshes from their late result', async () => {
    const pending = deferred();
    fetch.mockReturnValueOnce(pending.promise);
    latestStream().onerror();
    await jest.advanceTimersByTimeAsync(5000);
    const signal = fetch.mock.calls[0][1].signal;
    icon.remove();
    document.body.appendChild(icon);
    pending.resolve(response(401));
    await jest.advanceTimersByTimeAsync(600000);
    expect(signal.aborted).toBe(true);
    expect(urls()).toEqual(['/api/v1/users/me']);
    expect(EventSourceMock.instances).toHaveLength(2);
  });

  test.each(['count', 'auth'])('times out a stalled %s request and permits recovery', async kind => {
    fetch.mockImplementationOnce((url, { signal }) => new Promise((resolve, reject) => {
      signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    }));
    if (kind === 'count') {
      void icon._handleNotificationsUpdated();
      emit('stream_error');
    } else {
      latestStream().onerror();
      await jest.advanceTimersByTimeAsync(5000);
    }
    const signal = fetch.mock.calls[0][1].signal;
    await jest.advanceTimersByTimeAsync(29999);
    expect(signal.aborted).toBe(false);
    expect(EventSourceMock.instances).toHaveLength(1);
    await jest.advanceTimersByTimeAsync(1);
    expect(signal.aborted).toBe(true);
    if (kind === 'auth') await jest.advanceTimersByTimeAsync(10000);
    expect(EventSourceMock.instances).toHaveLength(2);
  });

  test('does not overwrite a newer SSE count with an older fetch result', async () => {
    const pending = deferred();
    fetch.mockReturnValueOnce(pending.promise);
    const refresh = icon._handleNotificationsUpdated();
    emit('unread_count', { unread_count: 8 });
    pending.resolve(response(200, 2));
    await refresh;
    expect(icon.count).toBe(8);
  });
});
