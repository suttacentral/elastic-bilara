import { css } from 'https://cdn.jsdelivr.net/npm/lit@3.3.2/+esm';

export const defaultTheme = 'aruna';

const commonVariables = css`
    --bilara-footer-height: 108px;
    --scrollbar-size: 8px;
    --scrollbar-minlength: 1.5rem;
    --transition: all 0.2s ease;
`;

export const themes = {
  'aruna': css`
      --color-primary: #ee7612;
      --color-secondary: #ae445a;
      --color-background: #242936;
      --color-background-secondary: #451a52;
      --color-background-tertiary: #672549;
      --color-text: #f2d8d7;
      --color-text-emphasized: #fcf5f5;
      --color-text-secondary: #e8bcb9;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(255, 255, 255, 0.1);
      --color-warning: #ee7612;
      --color-error: #ee121c;
      --color-success: #0ebf5e;
      --color-info: #5960f3;
      --color-unread-bg: #3d2a1a;
      --color-progress-low: #ff6b6b;
      --color-progress-medium: #ffd166;
      --color-progress-high: #2de59e;
  `,
  'suriya': css`
      --color-primary: #d33682;
      --color-secondary: #6c71c4;
      --color-background: #fdf6e3;
      --color-background-secondary: #fbeecb;
      --color-background-tertiary: #f8df9c;
      --color-text: #657b83;
      --color-text-emphasized: #586e75;
      --color-text-secondary: #93a1a1;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(255, 194, 2, 0.3);
      --color-warning: #cb4b16;
      --color-error: #dc322f;
      --color-success: #859900;
      --color-info: #268bd2;
      --color-unread-bg: #fde8f2;
      --color-progress-low: #c0392b;
      --color-progress-medium: #8a6800;
      --color-progress-high: #1e6e00;
  `,
  'candima': css`
      --color-primary: #dc322f;
      --color-secondary: #6c71c4;
      --color-background: #002b36;
      --color-background-secondary: #073642;
      --color-background-tertiary: #094959;
      --color-text: #a1adad;
      --color-text-emphasized: #bcc5c5;
      --color-text-secondary: #788989;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(255, 255, 255, 0.1);
      --color-warning: #cb4b16;
      --color-error: #dc322f;
      --color-success: #859900;
      --color-info: #268bd2;
      --color-unread-bg: #1a0f0f;
      --color-progress-low: #ff6b6b;
      --color-progress-medium: #ffd166;
      --color-progress-high: #2de59e;
  `,
  'manussa': css`
      --color-primary: black;
      --color-secondary: #757575;
      --color-background: white;
      --color-background-secondary: #efefef;
      --color-background-tertiary: #DDDDDD;
      --color-text: black;
      --color-text-emphasized: black;
      --color-text-secondary: #757575;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(0, 0, 0, 0.1);
      --color-warning: #FF851B;
      --color-error: #FF4136;
      --color-success: #2ECC40;
      --color-info: #0074D9;
      --color-unread-bg: #e8f0fe;
      --color-progress-low: #c62828;
      --color-progress-medium: #c76b00;
      --color-progress-high: #2e7d32;
  `,
  'yakkha': css`
      --color-primary: crimson;
      --color-secondary: #85144b;
      --color-background: #111111;
      --color-background-secondary: #001f3f;
      --color-background-tertiary: #3D9970;
      --color-text: #dedede;
      --color-text-emphasized: #ffffff;
      --color-text-secondary: #cccccc;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(255, 255, 255, 0.1);
      --color-warning: #FF851B;
      --color-error: #FF4136;
      --color-success: #2ECC40;
      --color-info: #0074D9;
      --color-unread-bg: #2a0a0f;
      --color-progress-low: #ff5050;
      --color-progress-medium: #ffcc00;
      --color-progress-high: #00e676;
  `,
  'deva': css`
      --color-primary: #92a8d1;
      --color-secondary: #d192a8;
      --color-background: #f4f6fa;
      --color-background-secondary: #e9edf5;
      --color-background-tertiary: #dee4f1;
      --color-text: rgba(0,0,0,0.5);
      --color-text-emphasized: rgba(0,0,0,0.7);
      --color-text-secondary: rgba(0,0,0,0.3);
      --color-text-on-strong: #ffffff;
      --color-border: rgba(0, 0, 0, 0.1);
      --color-warning: #FF851B;
      --color-error: #e34843;
      --color-success: #5abb5c;
      --color-info: #0074D9;
      --color-unread-bg: #dce6f4;
      --color-progress-low: #c62828;
      --color-progress-medium: #c75f00;
      --color-progress-high: #276749;
  `,
  'asura': css`
      --color-primary: #92a8d1;
      --color-secondary: #c5a1a0;
      --color-background: #7f7f7f;
      --color-background-secondary: #727272;
      --color-background-tertiary: #666666;
      --color-text: #e9edf5;
      --color-text-emphasized:  #ffffff;
      --color-text-secondary: #dee4f1;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(255, 255, 255, 0.1);
      --color-warning: #FF851B;
      --color-error: #ed8986;
      --color-success: #2ECC40;
      --color-info: #0074D9;
      --color-unread-bg: #5a6a7d;
      --color-progress-low: #ff5252;
      --color-progress-medium: #ffca28;
      --color-progress-high: #00e676;
  `,
  'gandhabba': css`
      --color-primary: #92a8d1;
      --color-secondary: #F661B1;
      --color-background: #1C1C1C;
      --color-background-secondary:  #272727;
      --color-background-tertiary: #25313E;
      --color-text: rgba(255,255,255,0.8);
      --color-text-emphasized:  white;
      --color-text-secondary: #D4D4D4;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(255, 255, 255, 0.1);
      --color-warning: #F39B35;
      --color-error: #FC4384;
      --color-success: #5c8c25;
      --color-info: #00A7AA;
      --color-unread-bg: #1e2a38;
      --color-progress-low: #ff6b6b;
      --color-progress-medium: #ffd166;
      --color-progress-high: #6fcf97;
  `,
  'mara': css`
      --color-primary: #6272a4;
      --color-secondary: #a46293;
      --color-background: #282a36;
      --color-background-secondary:  #44475a;
      --color-background-tertiary: #4f5269;
      --color-text: #f8f8f2;
      --color-text-emphasized:  white;
      --color-text-secondary: #e8e8e2;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(0, 0, 0, 0.1);
      --color-warning: #be884e;
      --color-error: #ff5555;
      --color-success: #06c436;
      --color-info: #7b90ce;
      --color-unread-bg: #353747;
      --color-progress-low: #ff5555;
      --color-progress-medium: #ffb86c;
      --color-progress-high: #50fa7b;
  `,
  'niraya': css`
      --color-primary: #666;
      --color-secondary: firebrick;
      --color-background: darkred;
      --color-background-secondary: red;
      --color-background-tertiary: #666;
      --color-text: crimson;
      --color-text-emphasized: maroon;
      --color-text-secondary: maroon;
      --color-text-on-strong: #ffffff;
      --color-border: orange;
      --color-warning: orange;
      --color-error: red;
      --color-success: tomato;
      --color-info: blue;
      --color-unread-bg: #7a1010;
      --color-progress-low: #ff8c00;
      --color-progress-medium: #ffd700;
      --color-progress-high: #39ff14;
  `,
  'suññatā': css`
      --color-primary: initial;
      --color-secondary: initial;
      --color-background: initial;
      --color-background-secondary: initial;
      --color-background-tertiary: initial;
      --color-text: initial;
      --color-text-emphasized: initial;
      --color-text-secondary: initial;
      --color-text-on-strong: #ffffff;
      --color-border: initial;
      --color-warning: initial;
      --color-error: initial;
      --color-success: initial;
      --color-info: initial;
      --color-unread-bg: #e8f0fe;
      --color-progress-low: #ef4444;
      --color-progress-medium: #f59e0b;
      --color-progress-high: #22c55e;
  `,
  /* Calm, Precise, Introspective — Light mode */
  'pañña': css`
      --color-primary: #4a7c9e;
      --color-secondary: #7a9e8a;
      --color-background: #f7f5f0;
      --color-background-secondary: #edeae3;
      --color-background-tertiary: #e0dbd1;
      --color-text: #2e2e2e;
      --color-text-emphasized: #1a1a1a;
      --color-text-secondary: #6b6b6b;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(0, 0, 0, 0.12);
      --color-warning: #b85c00;
      --color-error: #c0392b;
      --color-success: #2d7a4f;
      --color-info: #2c6b8a;
      --color-unread-bg: #ddeaf4;
      --color-progress-low: #b91c1c;
      --color-progress-medium: #925000;
      --color-progress-high: #1a6b38;
  `,
  /* Calm, Precise, Introspective — Dark mode */
  'samādhi': css`
      --color-primary: #c8a96e;
      --color-secondary: #7a9e8a;
      --color-background: #1a1e1c;
      --color-background-secondary: #242924;
      --color-background-tertiary: #2e352e;
      --color-text: #cfd5cb;
      --color-text-emphasized: #eaede7;
      --color-text-secondary: #8a9685;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(255, 255, 255, 0.08);
      --color-warning: #e0933a;
      --color-error: #e05c5c;
      --color-success: #5dab6d;
      --color-info: #5b9fbf;
      --color-unread-bg: #2e2918;
      --color-progress-low: #f08080;
      --color-progress-medium: #f4c464;
      --color-progress-high: #6fcb82;
  `,
  /* High contrast — Low vision accessibility (WCAG AAA) */
  'dīpā': css`
      --color-primary: #005fcc;
      --color-secondary: #7a3800;
      --color-background: #ffffff;
      --color-background-secondary: #f0f0f0;
      --color-background-tertiary: #dcdcdc;
      --color-text: #000000;
      --color-text-emphasized: #000000;
      --color-text-secondary: #333333;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(0, 0, 0, 0.5);
      --color-warning: #7a3800;
      --color-error: #cc0000;
      --color-success: #006600;
      --color-info: #005fcc;
      --color-unread-bg: #cce0ff;
      --color-progress-low: #b50000;
      --color-progress-medium: #7a3800;
      --color-progress-high: #005500;
  `,
  /* Zhongguose - Palace Vermilion */
  'gongque-danqing': css`
      --color-primary: #c93a12;
      --color-secondary: #8b2f1a;
      --color-background: #fff1d6;
      --color-background-secondary: #ffe3b0;
      --color-background-tertiary: #f7c77a;
      --color-text: #3b1f0f;
      --color-text-emphasized: #221007;
      --color-text-secondary: #744a2f;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(95, 49, 24, 0.28);
      --color-warning: #d79b00;
      --color-error: #b91f00;
      --color-success: #3f7d1e;
      --color-info: #1f5f9c;
      --color-unread-bg: #fde5d0;
      --color-progress-low: #b71c1c;
      --color-progress-medium: #7a4800;
      --color-progress-high: #2e5e18;
  `,
  /* Zhongguose - Misty Jiangnan */
  'jiangnan-yanyu': css`
      --color-primary: #0b4f9f;
      --color-secondary: #008ea8;
      --color-background: #eef7f6;
      --color-background-secondary: #d6eced;
      --color-background-tertiary: #b8d8db;
      --color-text: #132734;
      --color-text-emphasized: #071620;
      --color-text-secondary: #3e5a69;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(7, 22, 32, 0.24);
      --color-warning: #b88600;
      --color-error: #ad3a31;
      --color-success: #1e7a52;
      --color-info: #1670c5;
      --color-unread-bg: #cde3f5;
      --color-progress-low: #ad3a31;
      --color-progress-medium: #9a6200;
      --color-progress-high: #1e7a52;
  `,
  /* Zhongguose - Spring Bamboo */
  'chunshan-xincha': css`
      --color-primary: #008f5a;
      --color-secondary: #7fcf72;
      --color-background: #f0fae4;
      --color-background-secondary: #dbf2c6;
      --color-background-tertiary: #c2e7a5;
      --color-text: #11301f;
      --color-text-emphasized: #061a10;
      --color-text-secondary: #3f624d;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(6, 26, 16, 0.22);
      --color-warning: #a97a00;
      --color-error: #c94a2a;
      --color-success: #067a4b;
      --color-info: #1f6f96;
      --color-unread-bg: #c8ebd6;
      --color-progress-low: #c94a2a;
      --color-progress-medium: #9a6000;
      --color-progress-high: #076840;
  `,
  /* Zhongguose - Academy Ink */
  'shuyuan-yamo': css`
      --color-primary: #d4a24c;
      --color-secondary: #7f8ea3;
      --color-background: #1f252d;
      --color-background-secondary: #2a323d;
      --color-background-tertiary: #36414f;
      --color-text: #dfe5eb;
      --color-text-emphasized: #f7fafc;
      --color-text-secondary: #afbcc9;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(255, 255, 255, 0.18);
      --color-warning: #d08f2f;
      --color-error: #c65b4a;
      --color-success: #4c8b62;
      --color-info: #4f88c6;
      --color-unread-bg: #2e2418;
      --color-progress-low: #e57373;
      --color-progress-medium: #ffb74d;
      --color-progress-high: #81c784;
  `,
  /* Zhongguose - Celadon Ru Ware */
  'tianqing-ruci': css`
      --color-primary: #3a7d8c;
      --color-secondary: #6fa3a3;
      --color-background: #eef4f4;
      --color-background-secondary: #dae9e9;
      --color-background-tertiary: #c3d9d9;
      --color-text: #1a2e2e;
      --color-text-emphasized: #0d1f1f;
      --color-text-secondary: #436060;
      --color-text-on-strong: #ffffff;
      --color-border: rgba(26, 46, 46, 0.22);
      --color-warning: #a07020;
      --color-error: #b53030;
      --color-success: #266b4a;
      --color-info: #1f5d9c;
      --color-unread-bg: #c8e2e8;
      --color-progress-low: #b53030;
      --color-progress-medium: #904800;
      --color-progress-high: #266b4a;
    `,
    /* Buddhist Kasaya - Huai Se */
    'kasaya': css`
            --color-primary: #8c5a2b;
            --color-secondary: #6f6a60;
            --color-background: #1f2a3a;
            --color-background-secondary: #2c3848;
            --color-background-tertiary: #3f2f24;
            --color-text: #e7dfd2;
            --color-text-emphasized: #f6efe3;
            --color-text-secondary: #b9b1a5;
            --color-text-on-strong: #ffffff;
            --color-border: rgba(231, 223, 210, 0.22);
            --color-warning: #9b6b2f;
            --color-error: #8b3a2a;
            --color-success: #5f6f3a;
            --color-info: #2f4f79;
            --color-unread-bg: #2e1f12;
            --color-progress-low: #ef7070;
            --color-progress-medium: #dba840;
            --color-progress-high: #7cc07c;
    `,
    /* Buddhist Five-Color Flag - Pancavanna */
    'pancavanna': css`
        --color-primary: #a55b2a;
        --color-secondary: #1f5aa6;
        --color-background: #f3f1ea;
        --color-background-secondary: #e8e2d4;
        --color-background-tertiary: #f0df9d;
        --color-text: #2f251e;
        --color-text-emphasized: #1a130f;
        --color-text-secondary: #5c4e42;
        --color-text-on-strong: #ffffff;
        --color-border: rgba(47, 37, 30, 0.2);
        --color-warning: #d4a017;
        --color-error: #b8322a;
        --color-success: #4f7a5c;
        --color-info: #1f5aa6;
        --color-unread-bg: #ecdcc8;
        --color-progress-low: #b8322a;
        --color-progress-medium: #906200;
        --color-progress-high: #3d6b4a;
    `,
    /* Zhongguose - Zen Forest */
    'chanlin': css`
        --color-primary: #78846c;
        --color-secondary: #ddba9a;
        --color-background: #f8f7f4;
        --color-background-secondary: #eeeadd;
        --color-background-tertiary: #e3dcc8;
        --color-text: #2a3024;
        --color-text-emphasized: #131710;
        --color-text-secondary: #4a5441;
        --color-text-on-strong: #ffffff;
        --color-border: rgba(120, 132, 108, 0.25);
        --color-warning: #c0843c;
        --color-error: #bf4545;
        --color-success: #4e874e;
        --color-info: #3b7b9c;
        --color-unread-bg: #d8e0ce;
        --color-progress-low: #bf4545;
        --color-progress-medium: #945500;
        --color-progress-high: #3d7a3d;
    `,
    /* Zhongguose - Ruihe */
    'ruihe': css`
        --color-primary: #5c6d5a;
        --color-secondary: #7f6345;
        --color-background: #fdfbf5;
        --color-background-secondary: #f1ebd8;
        --color-background-tertiary: #decd99;
        --color-text: #45493b;
        --color-text-emphasized: #23251e;
        --color-text-secondary: #696f5a;
        --color-text-on-strong: #ffffff;
        --color-border: #af9261;
        --color-warning: #7f6345;
        --color-error: #a84242;
        --color-success: #5c6d5a;
        --color-info: #4c82a3;
        --color-unread-bg: #e4dcc4;
        --color-progress-low: #a84242;
        --color-progress-medium: #7a5500;
        --color-progress-high: #336633;
    `
}

export function getThemeNames() {
    return Object.keys(themes);
}

export function validateTheme(themeName) {
    return themes.hasOwnProperty(themeName) ? themeName : defaultTheme;
}

export function getThemeCSS(themeName) {
    const validTheme = validateTheme(themeName);
    return themes[validTheme];
}