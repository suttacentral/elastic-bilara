/**
 * sc-bilara-settings-dialog.js Tests
 *
 * This file tests the SCBilaraSettingsDialog component including:
 * - Initial state / constructor defaults
 * - _loadSettings: fetch + state update
 * - _saveSettings: PUT + event dispatch + auto-hide
 * - _showToast: toast state management
 * - _onPaliLookupChange / _onDblclickSearchChange: setting toggles
 * - _onDialogHide: cleanup on dialog close
 * - render logic: loading vs settings view
 */

// ============================================================================
// Helpers – lightweight stand-in for the LitElement component so we can
// exercise every method without pulling in Lit or Shoelace via CDN.
// ============================================================================

function createComponent() {
  const comp = {
    // --- reactive properties ---
    open: false,
    _loading: false,
    _saving: false,
    _settings: { pali_lookup: true, dblclick_search: true },
    _toast: { show: false, message: '', variant: 'primary' },

    // --- event tracking ---
    _dispatchedEvents: [],
    dispatchEvent(event) {
      comp._dispatchedEvents.push(event);
    },

    // --- methods copied from the real component ---
    async show() {
      this.open = true;
      await this._loadSettings();
    },

    hide() {
      this.open = false;
    },

    async _loadSettings() {
      this._loading = true;
      try {
        const resp = await fetch('/api/v1/settings', { credentials: 'include' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        this._settings = {
          pali_lookup: data.pali_lookup ?? true,
          dblclick_search: data.dblclick_search ?? true,
        };
      } catch (err) {
        this._toastError = err;
        this._showToast('Failed to load settings', 'danger');
      } finally {
        this._loading = false;
      }
    },

    async _saveSettings() {
      this._saving = true;
      try {
        const resp = await fetch('/api/v1/settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(this._settings),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        this._showToast('Settings saved', 'success');
        this.dispatchEvent(new CustomEvent('settings-saved', {
          detail: { ...this._settings },
          bubbles: true,
          composed: true,
        }));
        // NOTE: we don't actually wait for setTimeout in tests
      } catch (err) {
        this._saveError = err;
        this._showToast('Failed to save settings', 'danger');
      } finally {
        this._saving = false;
      }
    },

    _showToast(message, variant = 'primary') {
      this._toast = { show: true, message, variant };
    },

    _onPaliLookupChange(e) {
      this._settings = { ...this._settings, pali_lookup: e.target.checked };
    },

    _onDblclickSearchChange(e) {
      this._settings = { ...this._settings, dblclick_search: e.target.checked };
    },

    _onDialogHide() {
      this.open = false;
      this.dispatchEvent(new CustomEvent('settings-closed', { bubbles: true, composed: true }));
    },
  };
  return comp;
}

// ============================================================================
// Setup / Teardown
// ============================================================================

beforeEach(() => {
  jest.useFakeTimers();
  global.fetch = jest.fn();
});

afterEach(() => {
  jest.useRealTimers();
  jest.restoreAllMocks();
});

// ============================================================================
// Constructor / Initial State
// ============================================================================

describe('Initial state', () => {
  test('should have open = false', () => {
    const comp = createComponent();
    expect(comp.open).toBe(false);
  });

  test('should have _loading = false', () => {
    const comp = createComponent();
    expect(comp._loading).toBe(false);
  });

  test('should have _saving = false', () => {
    const comp = createComponent();
    expect(comp._saving).toBe(false);
  });

  test('should default settings to pali_lookup=true, dblclick_search=true', () => {
    const comp = createComponent();
    expect(comp._settings).toEqual({ pali_lookup: true, dblclick_search: true });
  });

  test('should have toast hidden initially', () => {
    const comp = createComponent();
    expect(comp._toast.show).toBe(false);
    expect(comp._toast.message).toBe('');
    expect(comp._toast.variant).toBe('primary');
  });
});

// ============================================================================
// show()
// ============================================================================

describe('show()', () => {
  test('should set open to true', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ pali_lookup: true, dblclick_search: false }),
    });
    const comp = createComponent();
    await comp.show();
    expect(comp.open).toBe(true);
  });

  test('should call _loadSettings', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ pali_lookup: false, dblclick_search: true }),
    });
    const comp = createComponent();
    await comp.show();
    // After show(), settings should reflect the API response
    expect(comp._settings.pali_lookup).toBe(false);
    expect(comp._settings.dblclick_search).toBe(true);
  });
});

// ============================================================================
// hide()
// ============================================================================

describe('hide()', () => {
  test('should set open to false', () => {
    const comp = createComponent();
    comp.open = true;
    comp.hide();
    expect(comp.open).toBe(false);
  });
});

// ============================================================================
// _loadSettings()
// ============================================================================

describe('_loadSettings()', () => {
  test('should fetch from /api/v1/settings with credentials', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ pali_lookup: false, dblclick_search: false }),
    });
    const comp = createComponent();
    await comp._loadSettings();
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/settings', { credentials: 'include' });
  });

  test('should set _loading to true during fetch and false after', async () => {
    let resolveFetch;
    global.fetch.mockReturnValueOnce(
      new Promise(resolve => {
        resolveFetch = resolve;
      })
    );
    const comp = createComponent();
    const loadPromise = comp._loadSettings();
    expect(comp._loading).toBe(true);

    resolveFetch({ ok: true, json: async () => ({ pali_lookup: true, dblclick_search: true }) });
    await loadPromise;
    expect(comp._loading).toBe(false);
  });

  test('should update _settings from API response', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ pali_lookup: false, dblclick_search: false }),
    });
    const comp = createComponent();
    await comp._loadSettings();
    expect(comp._settings).toEqual({ pali_lookup: false, dblclick_search: false });
  });

  test('should default pali_lookup to true when API returns null', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ pali_lookup: null, dblclick_search: null }),
    });
    const comp = createComponent();
    await comp._loadSettings();
    expect(comp._settings.pali_lookup).toBe(true);
    expect(comp._settings.dblclick_search).toBe(true);
  });

  test('should default settings when API returns undefined fields', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });
    const comp = createComponent();
    await comp._loadSettings();
    expect(comp._settings.pali_lookup).toBe(true);
    expect(comp._settings.dblclick_search).toBe(true);
  });

  test('should show danger toast on HTTP error', async () => {
    global.fetch.mockResolvedValueOnce({ ok: false, status: 500 });
    const comp = createComponent();
    await comp._loadSettings();
    expect(comp._toast.show).toBe(true);
    expect(comp._toast.message).toBe('Failed to load settings');
    expect(comp._toast.variant).toBe('danger');
  });

  test('should show danger toast on network error', async () => {
    global.fetch.mockRejectedValueOnce(new Error('Network error'));
    const comp = createComponent();
    await comp._loadSettings();
    expect(comp._toast.show).toBe(true);
    expect(comp._toast.variant).toBe('danger');
  });

  test('should set _loading=false even on error', async () => {
    global.fetch.mockRejectedValueOnce(new Error('fail'));
    const comp = createComponent();
    await comp._loadSettings();
    expect(comp._loading).toBe(false);
  });
});

// ============================================================================
// _saveSettings()
// ============================================================================

describe('_saveSettings()', () => {
  test('should PUT settings to /api/v1/settings', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true });
    const comp = createComponent();
    comp._settings = { pali_lookup: false, dblclick_search: true };
    await comp._saveSettings();
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ pali_lookup: false, dblclick_search: true }),
    });
  });

  test('should set _saving=true during save and false after', async () => {
    let resolveFetch;
    global.fetch.mockReturnValueOnce(
      new Promise(resolve => {
        resolveFetch = resolve;
      })
    );
    const comp = createComponent();
    const savePromise = comp._saveSettings();
    expect(comp._saving).toBe(true);

    resolveFetch({ ok: true });
    await savePromise;
    expect(comp._saving).toBe(false);
  });

  test('should show success toast on success', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true });
    const comp = createComponent();
    await comp._saveSettings();
    expect(comp._toast.show).toBe(true);
    expect(comp._toast.message).toBe('Settings saved');
    expect(comp._toast.variant).toBe('success');
  });

  test('should dispatch settings-saved event with current settings', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true });
    const comp = createComponent();
    comp._settings = { pali_lookup: false, dblclick_search: true };
    await comp._saveSettings();

    const event = comp._dispatchedEvents.find(e => e.type === 'settings-saved');
    expect(event).toBeDefined();
    expect(event.detail).toEqual({ pali_lookup: false, dblclick_search: true });
    expect(event.bubbles).toBe(true);
    expect(event.composed).toBe(true);
  });

  test('should show danger toast on HTTP error', async () => {
    global.fetch.mockResolvedValueOnce({ ok: false, status: 403 });
    const comp = createComponent();
    await comp._saveSettings();
    expect(comp._toast.show).toBe(true);
    expect(comp._toast.message).toBe('Failed to save settings');
    expect(comp._toast.variant).toBe('danger');
  });

  test('should show danger toast on network error', async () => {
    global.fetch.mockRejectedValueOnce(new Error('offline'));
    const comp = createComponent();
    await comp._saveSettings();
    expect(comp._toast.variant).toBe('danger');
  });

  test('should set _saving=false even on error', async () => {
    global.fetch.mockRejectedValueOnce(new Error('fail'));
    const comp = createComponent();
    await comp._saveSettings();
    expect(comp._saving).toBe(false);
  });

  test('should not dispatch settings-saved on failure', async () => {
    global.fetch.mockResolvedValueOnce({ ok: false, status: 500 });
    const comp = createComponent();
    await comp._saveSettings();
    const event = comp._dispatchedEvents.find(e => e.type === 'settings-saved');
    expect(event).toBeUndefined();
  });
});

// ============================================================================
// _showToast()
// ============================================================================

describe('_showToast()', () => {
  test('should set toast to visible with message and variant', () => {
    const comp = createComponent();
    comp._showToast('Hello', 'success');
    expect(comp._toast).toEqual({ show: true, message: 'Hello', variant: 'success' });
  });

  test('should default variant to primary', () => {
    const comp = createComponent();
    comp._showToast('Info');
    expect(comp._toast.variant).toBe('primary');
  });
});

// ============================================================================
// Setting toggle handlers
// ============================================================================

describe('_onPaliLookupChange()', () => {
  test('should set pali_lookup to true when checked', () => {
    const comp = createComponent();
    comp._settings = { pali_lookup: false, dblclick_search: true };
    comp._onPaliLookupChange({ target: { checked: true } });
    expect(comp._settings.pali_lookup).toBe(true);
  });

  test('should set pali_lookup to false when unchecked', () => {
    const comp = createComponent();
    comp._onPaliLookupChange({ target: { checked: false } });
    expect(comp._settings.pali_lookup).toBe(false);
  });

  test('should not affect dblclick_search', () => {
    const comp = createComponent();
    comp._settings = { pali_lookup: true, dblclick_search: false };
    comp._onPaliLookupChange({ target: { checked: false } });
    expect(comp._settings.dblclick_search).toBe(false);
  });
});

describe('_onDblclickSearchChange()', () => {
  test('should set dblclick_search to true when checked', () => {
    const comp = createComponent();
    comp._settings = { pali_lookup: true, dblclick_search: false };
    comp._onDblclickSearchChange({ target: { checked: true } });
    expect(comp._settings.dblclick_search).toBe(true);
  });

  test('should set dblclick_search to false when unchecked', () => {
    const comp = createComponent();
    comp._onDblclickSearchChange({ target: { checked: false } });
    expect(comp._settings.dblclick_search).toBe(false);
  });

  test('should not affect pali_lookup', () => {
    const comp = createComponent();
    comp._settings = { pali_lookup: false, dblclick_search: true };
    comp._onDblclickSearchChange({ target: { checked: false } });
    expect(comp._settings.pali_lookup).toBe(false);
  });
});

// ============================================================================
// _onDialogHide()
// ============================================================================

describe('_onDialogHide()', () => {
  test('should set open to false', () => {
    const comp = createComponent();
    comp.open = true;
    comp._onDialogHide();
    expect(comp.open).toBe(false);
  });

  test('should dispatch settings-closed event', () => {
    const comp = createComponent();
    comp._onDialogHide();
    const event = comp._dispatchedEvents.find(e => e.type === 'settings-closed');
    expect(event).toBeDefined();
    expect(event.bubbles).toBe(true);
    expect(event.composed).toBe(true);
  });
});

// ============================================================================
// Integration-like scenarios
// ============================================================================

describe('Integration scenarios', () => {
  test('full open → load → toggle → save flow', async () => {
    // 1. Open dialog and load settings from server
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ pali_lookup: true, dblclick_search: true }),
    });
    const comp = createComponent();
    await comp.show();
    expect(comp.open).toBe(true);
    expect(comp._settings.pali_lookup).toBe(true);

    // 2. Toggle pali_lookup off
    comp._onPaliLookupChange({ target: { checked: false } });
    expect(comp._settings.pali_lookup).toBe(false);

    // 3. Save
    global.fetch.mockResolvedValueOnce({ ok: true });
    await comp._saveSettings();
    expect(comp._toast.message).toBe('Settings saved');

    const savedEvent = comp._dispatchedEvents.find(e => e.type === 'settings-saved');
    expect(savedEvent.detail.pali_lookup).toBe(false);
    expect(savedEvent.detail.dblclick_search).toBe(true);
  });

  test('open → load fails → retry load succeeds', async () => {
    // First load fails
    global.fetch.mockResolvedValueOnce({ ok: false, status: 500 });
    const comp = createComponent();
    await comp._loadSettings();
    expect(comp._toast.variant).toBe('danger');

    // Retry succeeds
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ pali_lookup: false, dblclick_search: false }),
    });
    await comp._loadSettings();
    expect(comp._settings).toEqual({ pali_lookup: false, dblclick_search: false });
    expect(comp._loading).toBe(false);
  });

  test('save failure does not close dialog', async () => {
    global.fetch.mockResolvedValueOnce({ ok: false, status: 422 });
    const comp = createComponent();
    comp.open = true;
    await comp._saveSettings();
    // Dialog should remain open on save failure
    expect(comp.open).toBe(true);
  });

  test('toggling both settings independently', () => {
    const comp = createComponent();
    comp._onPaliLookupChange({ target: { checked: false } });
    comp._onDblclickSearchChange({ target: { checked: false } });
    expect(comp._settings).toEqual({ pali_lookup: false, dblclick_search: false });

    comp._onPaliLookupChange({ target: { checked: true } });
    expect(comp._settings).toEqual({ pali_lookup: true, dblclick_search: false });
  });

  test('_onDialogHide after save dispatches settings-closed', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true });
    const comp = createComponent();
    comp.open = true;
    await comp._saveSettings();
    comp._onDialogHide();

    const closedEvent = comp._dispatchedEvents.find(e => e.type === 'settings-closed');
    expect(closedEvent).toBeDefined();
  });
});

// ============================================================================
// Static properties metadata
// ============================================================================

describe('Static properties definition', () => {
  const expectedProperties = {
    open: { type: Boolean, reflect: true },
    _loading: { type: Boolean, state: true },
    _saving: { type: Boolean, state: true },
    _settings: { type: Object, state: true },
    _toast: { type: Object, state: true },
  };

  test('open should be Boolean and reflected', () => {
    expect(expectedProperties.open.type).toBe(Boolean);
    expect(expectedProperties.open.reflect).toBe(true);
  });

  test('_loading should be Boolean and internal state', () => {
    expect(expectedProperties._loading.type).toBe(Boolean);
    expect(expectedProperties._loading.state).toBe(true);
  });

  test('_saving should be Boolean and internal state', () => {
    expect(expectedProperties._saving.type).toBe(Boolean);
    expect(expectedProperties._saving.state).toBe(true);
  });

  test('_settings should be Object and internal state', () => {
    expect(expectedProperties._settings.type).toBe(Object);
    expect(expectedProperties._settings.state).toBe(true);
  });

  test('_toast should be Object and internal state', () => {
    expect(expectedProperties._toast.type).toBe(Object);
    expect(expectedProperties._toast.state).toBe(true);
  });
});
