export const defaultBackground = 'random';

export const illustrationBackgrounds = [
    'bodhi-leaf',
    'bamboo-finches',
    'tripitaka-koreana',
    'palm-leaf',
    'ink-bamboo'
];

export function getRandomBackground() {
    const idx = Math.floor(Math.random() * illustrationBackgrounds.length);
    return illustrationBackgrounds[idx];
}

export const backgrounds = {
    'random': {
        label: 'Random',
        src: '',
        className: 'bodhi-leaf-bg--random'
    },
    'bodhi-leaf': {
        label: 'Bodhi Leaf',
        src: './static/img/bodhi-leaf.png',
        className: 'bodhi-leaf-bg--bodhi-leaf'
    },
    'bamboo-finches': {
        label: 'Finches & Bamboo',
        src: './static/img/bamboo-finches.png',
        className: 'bodhi-leaf-bg--bamboo-finches'
    },
    'tripitaka-koreana': {
        label: 'Tripitaka Koreana',
        src: './static/img/tripitaka-koreana.png',
        className: 'bodhi-leaf-bg--tripitaka-koreana'
    },
    'palm-leaf': {
        label: 'Palm-leaf Manuscript',
        src: './static/img/palm-leaf-manuscript.png',
        className: 'bodhi-leaf-bg--palm-leaf'
    },
    'ink-bamboo': {
        label: 'Ink Bamboo',
        src: './static/img/ink-bamboo.png',
        className: 'bodhi-leaf-bg--ink-bamboo'
    },
    'none': {
        label: 'No Background',
        src: '',
        className: 'bodhi-leaf-bg--none'
    }
};

export function getBackgroundNames() {
    return Object.keys(backgrounds);
}

export function validateBackground(bgName) {
    return bgName && Object.prototype.hasOwnProperty.call(backgrounds, bgName)
        ? bgName
        : defaultBackground;
}

class BackgroundManager {
    constructor() {
        this.storageKey = 'bilara-index-bg';
        this.currentBackground = this.loadBackground();
        this.activeBackground = null;
        this.init();
    }

    init() {
        this.applyBackground(this.currentBackground);
        this.setupBackgroundSelector();
    }

    loadBackground() {
        const saved = localStorage.getItem(this.storageKey);
        return validateBackground(saved);
    }

    saveBackground(bgName) {
        localStorage.setItem(this.storageKey, bgName);
    }

    resolveBackground(bgName, forceNewRandom = false) {
        if (bgName === 'random') {
            if (!forceNewRandom) {
                const container = document.querySelector('.bodhi-leaf-bg');
                if (container && container.dataset && container.dataset.activeBg && illustrationBackgrounds.includes(container.dataset.activeBg)) {
                    return container.dataset.activeBg;
                }
            }
            return getRandomBackground();
        }
        return bgName;
    }

    applyBackground(bgName, forceNewRandom = false) {
        const validBg = validateBackground(bgName);
        const resolvedBg = this.resolveBackground(validBg, forceNewRandom);
        const resolvedConfig = backgrounds[resolvedBg];
        const container = document.querySelector('.bodhi-leaf-bg');

        if (container) {
            const allModifierClasses = getBackgroundNames().map(name => backgrounds[name].className);
            container.classList.remove(...allModifierClasses);

            if (validBg === 'random') {
                container.classList.add(backgrounds['random'].className);
            }

            if (resolvedBg === 'none') {
                container.classList.add(backgrounds['none'].className);
                container.hidden = true;
                if (container.dataset) delete container.dataset.activeBg;
            } else {
                container.hidden = false;
                container.classList.add(resolvedConfig.className);
                if (container.dataset) container.dataset.activeBg = resolvedBg;

                const img = container.querySelector('img');
                if (img && img.getAttribute('src') !== resolvedConfig.src) {
                    img.setAttribute('src', resolvedConfig.src);
                }
            }
        }

        this.currentBackground = validBg;
        this.activeBackground = resolvedBg;
        this.saveBackground(validBg);

        const selector = document.getElementById('bg-selector');
        if (selector && selector.value !== validBg) {
            selector.value = validBg;
        }

        document.dispatchEvent(new CustomEvent('backgroundChanged', {
            detail: { background: validBg, resolvedBackground: resolvedBg }
        }));
    }

    setupBackgroundSelector() {
        this.createBackgroundSelector();
    }

    createBackgroundSelector() {
        let selector = document.getElementById('bg-selector');
        if (!selector) {
            selector = document.createElement('select');
            selector.id = 'bg-selector';
            selector.className = 'theme-selector bg-selector';
            selector.setAttribute('aria-label', 'Select background illustration');
            selector.title = 'Select background illustration';

            getBackgroundNames().forEach(bgName => {
                const option = document.createElement('option');
                option.value = bgName;
                option.textContent = this.getBackgroundDisplayName(bgName);
                option.selected = bgName === this.currentBackground;
                selector.appendChild(option);
            });

            selector.addEventListener('change', (e) => {
                this.applyBackground(e.target.value, e.target.value === 'random');
            });
        }

        const nav = document.querySelector('#theme-selector-container') || document.body;
        if (nav && selector.parentElement !== nav) {
            nav.appendChild(selector);
        }
    }

    getBackgroundDisplayName(bgName) {
        return backgrounds[bgName]?.label || bgName;
    }

    getCurrentBackground() {
        return this.currentBackground;
    }

    getActiveBackground() {
        return this.activeBackground;
    }

    getAvailableBackgrounds() {
        return getBackgroundNames();
    }
}

export const backgroundManager = new BackgroundManager();

document.addEventListener('DOMContentLoaded', () => {
    backgroundManager.init();
});
