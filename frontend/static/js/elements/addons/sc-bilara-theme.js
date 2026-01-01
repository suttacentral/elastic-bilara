import { css } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';

export const defaultTheme = 'aruna';

const commonVariables = css`
    --bilara-footer-height: 108px;
    --scrollbar-size: 8px;
    --scrollbar-minlength: 1.5rem;
    --border: 1px solid var(--color-primary-color);
`;

export const themes = {
  'aruna': css`
      --color-primary: #D9B26F;
      --color-secondary: #FFC10A;
      --color-background: #fdf6e3;
      --color-background-secondary: #fbeecb;
      --color-background-tertiary: #f8df9c;
      --color-text: #657b83;
      --color-text-emphasized: #586e75;
      --color-text-secondary: #93a1a1;
      --color-accent: rgba(255, 194, 2, 0.3);
      --color-warning: #cb4b16;
      --color-error: #dc322f;
      --color-success: #859900;
      --color-info: #268bd2;
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
      --color-accent: rgba(255, 194, 2, 0.3);
      --color-warning: #cb4b16;
      --color-error: #dc322f;
      --color-success: #859900;
      --color-info: #268bd2;
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
      --color-accent: rgba(255, 194, 2, 0.1);
      --color-warning: #cb4b16;
      --color-error: #dc322f;
      --color-success: #859900;
      --color-info: #268bd2;
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
      --color-accent: rgba(255, 194, 2, 0.3);
      --color-warning: #FF851B;
      --color-error: #FF4136;
      --color-success: #2ECC40;
      --color-info: #0074D9;
  `,
  'yakkha': css`
      --color-primary: white;
      --color-secondary: #85144b;
      --color-background: #111111;
      --color-background-secondary: #001f3f;
      --color-background-tertiary: #3D9970;
      --color-text: white;
      --color-text-emphasized: white;
      --color-text-secondary: #AAAAAA;
      --color-accent: rgba(255, 194, 2, 0.1);
      --color-warning: #FF851B;
      --color-error: #FF4136;
      --color-success: #2ECC40;
      --color-info: #0074D9;
  `,
  'deva': css`
      --color-primary: #92a8d1;
      --color-secondary: #c5a1a0;
      --color-background: #f4f6fa;
      --color-background-secondary: #e9edf5;
      --color-background-tertiary: #dee4f1;
      --color-text: rgba(0,0,0,0.5);
      --color-text-emphasized: rgba(0,0,0,0.7);
      --color-text-secondary: rgba(0,0,0,0.3);
      --color-accent: #e4f1de;
      --color-warning: #FF851B;
      --color-error: #ed8986;
      --color-success:#70ea73;
      --color-info: #0074D9;
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
      --color-accent: rgba(228, 241, 222,0.1);
      --color-warning: #FF851B;
      --color-error: #ed8986;
      --color-success: #2ECC40;
      --color-info: #0074D9;
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
      --color-accent: rgba(230, 219, 116,0.1);
      --color-warning: #F39B35;
      --color-error: #FC4384;
      --color-success: #98E342;
      --color-info: #00A7AA;
  `,
  'mara': css`
      --color-primary: #6272a4;
      --color-secondary: #6272a4;
      --color-background: #282a36;
      --color-background-secondary:  #44475a;
      --color-background-tertiary: #4f5269;
      --color-text: #f8f8f2;
      --color-text-emphasized:  white;
      --color-text-secondary: #e8e8e2;
      --color-accent: #d36d00;
      --color-warning: #ffb86c;
      --color-error: #ff5555;
      --color-success: #06c436;
      --color-info: #8be9fd;
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
      --color-accent: orange;
      --color-warning: orange;
      --color-error: red;
      --color-success: tomato;
      --color-info: blue;
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
      --color-accent: initial;
      --color-warning: initial;
      --color-error: initial;
      --color-success: initial;
      --color-info: initial;
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