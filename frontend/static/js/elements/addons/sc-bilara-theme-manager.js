import { themes, defaultTheme, getThemeNames, validateTheme } from './sc-bilara-theme.js';

class ThemeManager {
    constructor() {
        this.currentTheme = this.loadTheme();
        this.init();
    }

    init() {
        this.applyTheme(this.currentTheme);
        this.setupThemeToggle();
    }

    loadTheme() {
        const saved = localStorage.getItem('bilara-theme');
        return validateTheme(saved) || defaultTheme;
    }

    saveTheme(themeName) {
        localStorage.setItem('bilara-theme', themeName);
    }

    applyTheme(themeName) {
        const validTheme = validateTheme(themeName);
        document.body.classList.remove(...getThemeNames().map(name => `theme-${name}`));
        document.body.classList.add(`theme-${validTheme}`);
        this.applyCSSVariables(validTheme);
        this.currentTheme = validTheme;
        this.saveTheme(validTheme);

        document.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme: validTheme }
        }));
    }

    applyCSSVariables(themeName) {
        const theme = themes[themeName];
        if (!theme) return;

        const tempStyle = document.createElement('style');
        tempStyle.textContent = `:root { ${theme.cssText} }`;
        document.head.appendChild(tempStyle);

        const existingThemeStyle = document.getElementById('bilara-theme-style');
        if (existingThemeStyle) {
            existingThemeStyle.remove();
        }

        tempStyle.id = 'bilara-theme-style';
    }

    setupThemeToggle() {
        this.createThemeSelector();
    }

    createThemeSelector() {
        const selector = document.createElement('select');
        selector.id = 'theme-selector';
        selector.className = 'theme-selector';

        getThemeNames().forEach(themeName => {
            const option = document.createElement('option');
            option.value = themeName;
            option.textContent = this.getThemeDisplayName(themeName);
            option.selected = themeName === this.currentTheme;
            selector.appendChild(option);
        });

        selector.addEventListener('change', (e) => {
            this.applyTheme(e.target.value);
        });

        if (!document.getElementById('theme-selector')) {
            const nav = document.querySelector('#theme-selector-container') || document.body;
            nav.appendChild(selector);
        }
    }

    getThemeDisplayName(themeName) {
        const displayNames = {
          'suriya': 'suriya',
          'candima': 'candima',
          'manussa': 'manussa',
          'yakkha': 'yakkha',
          'deva': 'deva',
          'asura': 'asura',
          'gandhabba': 'gandhabba',
          'mara': 'mara',
          'niraya': 'niraya',
          'suññatā': 'suññatā'
        };
        return displayNames[themeName] || themeName;
    }

    getCurrentTheme() {
        return this.currentTheme;
    }

    getAvailableThemes() {
        return getThemeNames();
    }
}

export const themeManager = new ThemeManager();

document.addEventListener('DOMContentLoaded', () => {
  themeManager.init();
});