/**
 * Generic handler for publishing changes via pull request
 * @param {Array|Object} paths - File paths to publish
 * @param {HTMLElement} element - Element to display messages
 * @param {string} options.endpoint - API endpoint (default: 'pr/')
 * @param {string} options.buttonId - Loading button ID (default: 'btn-publish-changes')
 * @returns {Promise<string|undefined>} Response detail or undefined
 */
const publishChangesHandler = async (
    paths, 
    element, 
    options = {}
) => {
    const {
        endpoint = 'pr/',
        buttonId = 'btn-publish-changes'
    } = options;

    let data = Array.isArray(paths) ? [...paths] : [];
    if (Object.keys(paths).includes("paths")) {
        data = paths["paths"];
    }

    if (!data.length) {
        return;
    }

    const errorMessage = "There has been an error. Please retry in a few moments. " +
                        "If the issue persists, please contact the administrator.";

    try {
        addLoadingAttribute(buttonId);

        const response = await requestWithTokenRetry(endpoint, {
            credentials: "include",
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ paths: data }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            return displayMessage(
                element,
                `${errorData.detail?.error || 'Unknown error'}.`,
                "failure",
            );
        }

        const { task_id: taskID, detail } = await response.json();

        if (!taskID) {
            displayMessage(element, errorMessage, "failure");
            return;
        }

        if (element) {
            displayMessage(element, "Pull Request has been scheduled.");
        }

        return detail;
    } catch (error) {
        console.error('Pull request error:', error);
        displayMessage(element, errorMessage, "failure");
    } finally {
        removeLoadingAttribute(buttonId);
    }
};

/**
 * Handler for standard pull request publishing
 * @param {Array|Object} paths - File paths to publish
 * @param {HTMLElement} element - Element to display messages
 * @returns {Promise<string|undefined>}
 */
const publishChanges = (paths, element) => {
    return publishChangesHandler(paths, element, {
        endpoint: 'pr/',
        buttonId: 'btn-publish-changes'
    });
};

/**
 * Handler for split/merge pull request publishing
 * @param {Array|Object} paths - File paths to publish
 * @param {HTMLElement} element - Element to display messages
 * @returns {Promise<string|undefined>}
 */
const publishChangesForSplitOrMerge = (paths, element) => {
    return publishChangesHandler(paths, element, {
        endpoint: 'pr/split-merge/',
        buttonId: 'btn-publish-changes-split-merge'
    });
};

function pullRequestModal(paths) {
    return {
        showModal: true,
        searchTerm: "",
        allPaths: paths,
        filteredPaths: paths,
        selectedPaths: {},
        filterPaths() {
            this.filteredPaths = this.allPaths.filter(path => path.includes(this.searchTerm));
        },
        async submitPaths() {
            const selected = Object.keys(this.selectedPaths).filter(key => this.selectedPaths[key]);
            await publishChangesHandler(selected, document.getElementById("pull-request-message"));
            this.destroyModal();
        },
        selectAll() {
            if (
                Object.keys(this.selectedPaths).filter(key => this.selectedPaths[key] === true).length ===
                this.allPaths.length
            ) {
                this.selectedPaths = {};
            } else {
                this.filteredPaths.forEach(path => (this.selectedPaths[path] = true));
            }
        },
        destroyModal() {
            this.showModal = false;
            document.getElementById("modal-component").remove();
        },
        clearSearch() {
            this.searchTerm = "";
            this.filteredPaths = this.allPaths;
        },
    };
}

function getPullRequestModalHTML(dataString) {
    return `
            <div
                id="modal-component"
                class="modal" 
                x-data="pullRequestModal(${dataString})" 
                x-show="showModal" 
                x-on:click="destroyModal">
                <div class="pull-request-container" x-on:click.stop>
                    <div class="pull-request-container__search">
                        <div class="pull-request-container__search__search-box">
                            <span 
                                class="pull-request-container__search__search-box__icon"
                                x-on:click="$event.target.nextElementSibling.focus()">🔍</span>
                            <input 
                                class="pull-request-container__search__search-box__input" 
                                type="text"
                                placeholder="Search..."
                                x-model="searchTerm"
                                x-on:input="filterPaths"/>
                            <span
                                x-cloak
                                x-show="searchTerm.length" 
                                class="pull-request-container__search__search-box__clear-icon"
                                x-on:click="clearSearch">❌</span>
                        </div>
                        <button 
                            class="pull-request-container__search__close-button" 
                            x-on:click="destroyModal">Close</button>
                    </div>
                    <ul class="pull-request-container__paths-list">
                        <template x-for="path in filteredPaths">
                            <li class="pull-request-container__paths-list__item">
                                <input 
                                class="pull-request-container__paths-list__item__checkbox"
                                    type="checkbox" 
                                    x-model="selectedPaths[path]"
                                    x-bind:id="path" 
                                    x-bind:value="path" 
                                    x-bind:name="path"/>
                                <label
                                    class="pull-request-container__paths-list__item__label"
                                    x-text="path.split('/').pop()" 
                                    x-bind:for="path" 
                                    ></label>
                            </li>
                        </template>
                    </ul>
                    <div class="pull-request-container__actions">
                        <button 
                            class="pull-request-container__actions__select-all-button" 
                            x-on:click="selectAll">Select All</button>
                        <button 
                            class="pull-request-container__actions__publish-button" 
                            x-on:click="submitPaths">Publish</button>
                    </div>
                </div>
            </div>`;
}
