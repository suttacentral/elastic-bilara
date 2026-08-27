const PULL_REQUEST_TASK_POLL_INTERVAL = 750;
const PULL_REQUEST_TASK_MAX_POLL_INTERVAL = 10000;
const PULL_REQUEST_TASK_MONITOR_TIMEOUT = 65 * 60 * 1000;
const ACTIVE_PULL_REQUEST_TASK_STATES = new Set([
    'PENDING',
    'RECEIVED',
    'STARTED',
    'RETRY',
    'PROGRESS',
]);

class PullRequestMonitoringTimeoutError extends Error {
    constructor() {
        super('Pull request monitoring timed out');
        this.name = 'PullRequestMonitoringTimeoutError';
    }
}

function parsePullRequestUrl(value) {
    if (typeof value !== 'string') {
        throw new Error('Pull request task returned an invalid URL');
    }

    let url;
    try {
        url = new URL(value);
    } catch {
        throw new Error('Pull request task returned an invalid URL');
    }
    if (url.protocol !== 'https:' && url.protocol !== 'http:') {
        throw new Error('Pull request task returned an invalid URL');
    }
    return url.href;
}

async function waitForPullRequestTask(task) {
    const deadline = Date.now() + PULL_REQUEST_TASK_MONITOR_TIMEOUT;
    let pollInterval = PULL_REQUEST_TASK_POLL_INTERVAL;
    while (true) {
        if (Date.now() >= deadline) {
            throw new PullRequestMonitoringTimeoutError();
        }
        const response = await requestWithTokenRetry(`tasks/${task.taskId}/`);
        if (!response.ok) {
            throw new Error(`Failed to retrieve pull request task (${response.status})`);
        }

        const data = await response.json();
        if (typeof data.status !== 'string') {
            throw new Error('Pull request task returned an invalid status');
        }

        const status = data.status.toUpperCase();
        if (status === 'SUCCESS') {
            return { ...task, url: parsePullRequestUrl(data.result) };
        }
        if (status === 'FAILURE' || status === 'REVOKED') {
            throw new Error(data.error || 'Pull request creation failed');
        }
        if (!ACTIVE_PULL_REQUEST_TASK_STATES.has(status)) {
            throw new Error(`Pull request task returned an unknown status: ${data.status}`);
        }

        const remainingTime = deadline - Date.now();
        if (remainingTime <= 0) {
            throw new PullRequestMonitoringTimeoutError();
        }

        await new Promise(resolve => setTimeout(
            resolve,
            Math.min(pollInterval, remainingTime),
        ));
        pollInterval = Math.min(
            pollInterval * 2,
            PULL_REQUEST_TASK_MAX_POLL_INTERVAL,
        );
    }
}

async function monitorPullRequestTasks(tasks) {
    const results = await Promise.allSettled(tasks.map(waitForPullRequestTask));
    return results.reduce(
        (summary, result, index) => {
            if (result.status === 'fulfilled') {
                summary.succeeded.push(result.value);
            } else {
                summary.failed.push({
                    ...tasks[index],
                    error: result.reason instanceof Error
                        ? result.reason.message
                        : String(result.reason),
                    timedOut: result.reason instanceof PullRequestMonitoringTimeoutError,
                });
            }
            return summary;
        },
        { succeeded: [], failed: [] },
    );
}

async function showPullRequestTaskResults(tasks, showToast, initialFailures = []) {
    const summary = await monitorPullRequestTasks(tasks);
    summary.failed.push(...initialFailures);
    const pullRequestCount = summary.succeeded.length;
    const timedOutCount = summary.failed.filter(task => task.timedOut).length;
    const failedTasks = summary.failed.filter(task => !task.timedOut);
    const failedCount = failedTasks.length;
    const actions = summary.succeeded.map((pullRequest, index) => ({
        label: pullRequestCount === 1
            ? 'View Pull Request ↗'
            : `View Pull Request ${index + 1} ↗`,
        href: pullRequest.url,
    }));

    let message = pullRequestCount === 1
        ? 'Pull Request created.'
        : `${pullRequestCount} Pull Requests created.`;
    let type = 'success';
    if (failedCount > 0) {
        type = 'error';
        message = pullRequestCount > 0
            ? `${message} ${failedCount} failed.`
            : `Pull request creation failed: ${failedTasks.map(task => task.error).join('; ')}`;
    }
    if (timedOutCount > 0) {
        if (failedCount === 0) {
            type = 'warning';
        }
        if (pullRequestCount === 0 && failedCount === 0 && timedOutCount === 1) {
            message = 'Stopped checking Pull Request status. The task may still be running in the background.';
        } else {
            message += ` Stopped checking ${timedOutCount} task${timedOutCount === 1 ? '' : 's'}; ` +
                `${timedOutCount === 1 ? 'it may' : 'they may'} still be running in the background.`;
        }
    }

    showToast(message, type, pullRequestCount > 1 || timedOutCount > 0 ? 12000 : 8000, actions);
    return summary;
}

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

        const toast = document.querySelector('sc-bilara-toast');
        if (toast) {
            void showPullRequestTaskResults(
                [{
                    taskId: taskID,
                    label: data.length === 1 ? data[0] : `${data.length} files`,
                }],
                toast.show.bind(toast),
            );
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
