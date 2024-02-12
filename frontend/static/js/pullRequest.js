const publishChangesHandler = async (paths, element) => {
    let data = Array.isArray(paths) ? [...paths] : [];
    if (Object.keys(paths).includes("paths")) {
        data = paths["paths"];
    }
    if (!data.length) return;
    try {
        const response = await requestWithTokenRetry(`pr/`, {
            credentials: "include",
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                paths: data,
            }),
        });
        const { task_id: taskID, detail: detail } = await response.json();
        if (!taskID) {
            throw new Error("Invalid data format from the API");
        }
        if (element !== null && element !== undefined) {
            await pollUpdateStatus(taskID, element);
        }
        return detail;
    } catch (error) {
        throw new Error(error);
    }
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
            const message = await publishChangesHandler(selected, null);
            this.destroyModal();
            renderPullRequestMessage(message);
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

const renderPullRequestMessage = message => {
    const element = document.createElement("p");
    element.textContent = message;
    element.setAttribute("id", "pr-message");
    element.classList.add("bg-green-100", "my-2", "px-1", "py-3", "text-2xl", "font-bold", "text-center", "rounded");
    document.querySelector("main").prepend(element);
    setTimeout(() => {
        const element = document.querySelector("#pr-message");
        if (element) {
            element.remove();
        }
    }, 5000);
};
