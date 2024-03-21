const getUpdateStatus = async taskID => {
    try {
        const response = await requestWithTokenRetry(`tasks/${taskID}/`);
        const data = await response.json();
        if (!data.status) {
            throw new Error("Invalid data format from the API");
        }
        return data.status;
    } catch (error) {
        throw new Error(error);
    }
};

const pollUpdateStatus = async (taskID, element) => {
    let status = await getUpdateStatus(taskID);
    switch (status.toUpperCase()) {
        case "SUCCESS":
            element.classList.remove("loading", "failure");
            element.classList.add("success");
            setTimeout(() => element.classList.remove("success"), 30000);
            break;
        case "FAILURE":
            element.classList.remove("loading", "success");
            element.classList.add("failure");
            break;
        default:
            element.classList.remove("success", "failure");
            element.classList.add("loading");
            setTimeout(() => pollUpdateStatus(taskID, element), 750);
    }
};

function getUserInfo() {
    return {
        isAdmin: false,
        isActive: false,
        username: "",
        avatarURL: "",
        async getRole() {
            try {
                const response = await requestWithTokenRetry("users/me");
                const data = await response.json();
                if (data.role === ROLES.admin || data.role === ROLES.superuser) {
                    this.isAdmin = true;
                }
                this.isActive = data.is_active;
                this.username = data.username;
                this.avatarURL = data.avatar_url;
            } catch (error) {
                throw new Error(error);
            }
        },
    };
}

const ROLES = {
    admin: "administrator",
    superuser: "superuser",
    writer: "writer",
    reviewer: "reviewer",
};

function formatDate(dateString) {
    const options = { year: "numeric", month: "long", day: "numeric" };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

function displayMessage(element, message, type) {
    element.textContent = message;
    element.classList.add("project-header__message--show");
    if (type === "failure") element.classList.add("project-header__message--failure");
    if (!isInViewPort(element)) {
        element.classList.add("project-header__message--fixed");
    }

    setTimeout(() => {
        element.textContent = "";
        element.classList.remove("project-header__message--show");
        element.classList.remove("project-header__message--failure");
        element.classList.remove("project-header__message--fixed");
    }, 15000);
}

function isInViewPort(element) {
    let rect = element.getBoundingClientRect();
    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

function tooltip() {
    return {
        show: false,
        tooltipData: [],
        requested: false,
        async fetchData(path) {
            if (path.endsWith(".json")) return;
            if (path.startsWith("/")) {
                path = path.slice(1);
            }
            if (this.requested) return this.show = true;
            const response = await requestWithTokenRetry(`directories/${path}/`);
            if (response.ok) this.requested = true;
            const {directories, files} = await response.json();
            this.tooltipData = [...directories, ...files];
            if (this.requested) this.show = true;
        },
        hide() {
            this.show = false;
        },
    };
}

const getMuid = string => string.split("/").slice(0, 3).join("-");
const getPrefix = string => string.split("/").pop().split("_")[0];
