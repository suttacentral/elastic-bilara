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
