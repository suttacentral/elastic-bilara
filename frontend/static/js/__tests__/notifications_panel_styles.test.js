const fs = require('fs');
const path = require('path');

const notificationsCss = fs.readFileSync(
  path.resolve(__dirname, '../../css/pages/notifications_panel.css'),
  'utf8'
);

function ruleBlock(selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = notificationsCss.match(new RegExp(`${escapedSelector}\\s*\\{([\\s\\S]*?)\\}`));
  return match ? match[1] : '';
}

describe('notifications panel dark theme styles', () => {
  test('HTML diff pre blocks use a themed surface and readable text color', () => {
    const changePre = ruleBlock('.change-pre');

    expect(changePre).toContain('background-color: var(--notification-change-surface)');
    expect(changePre).toContain('color: var(--notification-change-text)');
    expect(changePre).not.toContain('background-color: var(--color-text-on-strong)');
  });

  test('notification diff colors define page-level themed backgrounds', () => {
    expect(notificationsCss).toContain('--notification-change-surface: color-mix');
    expect(notificationsCss).toContain('--notification-change-add-bg: color-mix');
    expect(notificationsCss).toContain('--notification-change-delete-bg: color-mix');
  });
});
