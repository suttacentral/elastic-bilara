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


function  getUserInfo() {
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
        }
    }
}

const ROLES = {
    admin: "administrator",
    superuser: "superuser",
    writer: "writer",
    reviewer: "reviewer",
}
// TODO: there is an endpoint /users/roles -> that returns a list of roles

function formatDate(dateString) {
  const options = { year: 'numeric', month: 'long', day: 'numeric' };
  return new Date(dateString).toLocaleDateString(undefined, options);
}
