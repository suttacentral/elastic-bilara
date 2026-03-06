import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.3.2/+esm';

export class ScBilaraHowTo extends LitElement {
  static styles = [
    css`
      :host {
        display: block;
      }
    `
  ];

  createRenderRoot() {
    return this;
  }

  render() {
    return html`
      <details id="how-to-details">
        <summary>get started</summary>
        <div>
          <p>
            Bilara is a Computer Assisted Translation (CAT) webapp built by
            SuttaCentral to help human beings translate Buddhist scripture.
          </p>
          <p>
            Before you begin, read the
            <a
              href="https://github.com/suttacentral/bilara-data/wiki/SuttaCentral-translation-style-guide"
              >Translation Style Guide</a
            >.
          </p>
          <p>
            <b>Basic usage</b>. For more details see the
            <a
              href="https://github.com/suttacentral/bilara-data/wiki/Guide-for-translators"
              >Guide For Translators</a
            >.
          </p>
          <ol>
            <li>
              Navigate to a text. (<b>Bold</b> items are the ones you can edit.)
            </li>
            <li>Click on the translation column.</li>
            <li>Write the translation for that segment.</li>
            <li>
              If the Translation Memory (TM) shows a match, you can click it and
              modify as needed.
            </li>
            <li>Press <kbd>Enter</kbd>.</li>
            <li>Repeat until finished!</li>
          </ol>
          <p><b>Some tips</b></p>
          <ul>
            <li>Write plain text. Don’t input anything other than plain text.</li>
            <li>
              Your translations are securely saved at Github using git version
              control, which keeps a full record of every change made. In
              emergency, contact admins, and they will restore your text if
              possible.
            </li>
            <li>
              Github has a
              <a
                href="https://github.com/suttacentral/bilara-data/pulse"
                target="_blank"
                >range of fancy stats</a
              >.
            </li>
            <li>
              You can use a limited range of markdown:
              <ul>
                <li>
                  <code>_underscore_</code> for quoting foreign words (esp.
                  Pali) (= <code>&lt;i&gt;</code>).
                </li>
                <li>
                  <code>*asterisks*</code> to emphasize words (=
                  <code>&lt;em&gt;</code>).
                </li>
                <li>
                  <code>**double asterisks**</code> for things that stand out,
                  like numbers or headwords. You probably don't want to use this
                  (= <code>&lt;b&gt;</code>).
                </li>
              </ul>
            </li>
            <li>
              The little icons on the right indicate whether a string is
              properly committed or not.
            </li>
            <li>
              You can drag and drop the columns in any order you like.
            </li>
            <li>
              You can add more columns by clicking the ⊕ icon.
            </li>
          </ul>
          <p>
            Finally, <b>DO NOT USE AI</b>. All content produced by AI is
            forbidden on SuttaCentral.
          </p>
          <ul>
            <li>Do not use AI for suggestions.</li>
            <li>Do not use AI for drafting.</li>
            <li>Do not use AI for research.</li>
            <li>Do not use AI for anything at all.</li>
          </ul>
        </div>
      </details>
    `;
  }
}
customElements.define('sc-bilara-how-to', ScBilaraHowTo);
