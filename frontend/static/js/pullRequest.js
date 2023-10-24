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
                <div class="rounded border-neutral-500" x-on:click.stop>
                    <div class="flex justify-between align-middle my-2 gap-2">
                        <div class="relative">
                            <span 
                                class="absolute inset-y-0 left-0 pl-3 flex items-center cursor-pointer"
                                x-on:click="$event.target.nextElementSibling.focus()">🔍</span>
                            <input 
                                class="border rounded border-slate-600 pl-10 pr-10 w-full px-2 py-1" 
                                type="text"
                                placeholder="Search..."
                                x-model="searchTerm"
                                x-on:input="filterPaths"/>
                            <span
                                x-cloak
                                x-show="searchTerm.length" 
                                class="absolute inset-y-0 right-0 pr-3 flex items-center cursor-pointer"
                                x-on:click="clearSearch">❌</span>
                        </div>
                        <button 
                            class="border rounded px-2 py-1 hover:bg-red-200 bg-red-50 border-neutral-500 hover:cursor-pointer" 
                            x-on:click="destroyModal">Close</button>
                    </div>
                    <ul class="flex-col flex-wrap max-h-[75vh] overflow-y-auto gap-2 text-lg">
                        <template x-for="path in filteredPaths">
                            <li class="hover:bg-green-50 px-1 py-0.5 flex gap-2 rounded text-white hover:text-black">
                                <input 
                                    type="checkbox" 
                                    x-model="selectedPaths[path]"
                                    x-bind:id="path" 
                                    x-bind:value="path" 
                                    x-bind:name="path"/>
                                <label
                                    class="flex-grow hover:cursor-pointer"
                                    x-text="path.split('/').pop()" 
                                    x-bind:for="path" 
                                    ></label>
                            </li>
                        </template>
                    </ul>
                    <div class="flex justify-center my-2 gap-2">
                        <button 
                            class="rounded my-2 py-2 px-1 bg-zinc-100 hover:bg-green-50 border border-neutral-500 hover:cursor-pointer" 
                            x-on:click="selectAll">Select All</button>
                        <button 
                            class="rounded my-2 py-2 px-1 bg-zinc-100 hover:bg-green-50 border border-neutral-500 hover:cursor-pointer" 
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
