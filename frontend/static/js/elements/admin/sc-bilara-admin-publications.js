import { ScBilaraPublications } from '../publications/sc-bilara-publications.js';

export class ScBilaraAdminPublications extends ScBilaraPublications {
    get adminPage() { return true; }
}

customElements.define('sc-bilara-admin-publications', ScBilaraAdminPublications);
