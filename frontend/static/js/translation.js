function fetchTranslation() {
    return {
        translations: [],
        relatedProjects: [],
        async init() {
            const params = new URLSearchParams(window.location.search);
            this.prefix = params.get("prefix");
            const muid = params.get("muid");
            const source = params.get("source");

            await this.findOrCreateObject(source, this.prefix, true);
            if (muid) await this.findOrCreateObject(muid, this.prefix);

            const projects = await this.fetchRelatedProjects(this.prefix);
            this.relatedProjects = projects.filter(project => project !== muid && project !== source);
            dragHandler();
            resizeHandler();
        },
        getValue(translation, uid) {
            return translation.data[uid] || "";
        },
        setValue(translation, uid, value) {
            if (!translation.data) {
                translation.data = {};
            }
            translation.data[uid] = value;
        },
        async findOrCreateObject(key, prefix, source = false) {
            let obj = this.translations.find(item => key in item);
            if (!obj) {
                try {
                    const data = await this.fetchData(key, prefix);
                    obj = { canEdit: false, muid: key, prefix: prefix };
                    obj["data"] = data.data;
                    obj["canEdit"] = data["can_edit"];
                } catch (error) {
                    throw new Error(error);
                }
                if (source) {
                    obj.isSource = true;
                }
                this.translations.push(obj);
            }
            return obj;
        },
        async fetchData(key, prefix) {
            try {
                const response = await requestWithTokenRetry(`projects/${key}/${prefix}/`);
                const data = await response.json();
                if (!data.data) {
                    throw new Error("Invalid data format from the API");
                }
                return data;
            } catch (error) {
                throw new Error(error);
            }
        },
        async handleEnter(event, uid, segment, translation) {
            if (translation.canEdit) {
                if (event.shiftKey) {
                    event.target.value += "\n";
                    return;
                }
                const nextSection = event.target.parentElement.nextElementSibling;
                if (nextSection) {
                    const nextTextarea = nextSection.querySelector("textarea");
                    if (nextTextarea) {
                        nextTextarea.focus();
                    }
                }
                try {
                    const muid = translation.muid;
                    await this.updateHandler(
                        muid,
                        { [uid]: segment },
                        document.querySelector("p.project-header__message"),
                    );
                } catch (error) {
                    throw new Error(error);
                }
            }
        },
        async updateHandler(muid, data, element) {
            try {
                const response = await requestWithTokenRetry(`projects/${muid}/${this.prefix}/`, {
                    credentials: "include",
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(data),
                });
                const { task_id: taskID } = await response.json();
                if (!taskID) {
                    displayMessage(
                        element,
                        "There has been an error. Please retry in a few moments. If the issue persists, please contact the administrator.",
                        "failure",
                    );
                }
                displayMessage(
                    element,
                    "Your changes have reached the server. They are being processed at the moment. This may take some time. Please continue your work as normal.",
                );
            } catch (error) {
                throw new Error(error);
            }
        },
        async fetchRelatedProjects(prefix) {
            try {
                const response = await requestWithTokenRetry(`projects/?prefix=${prefix}`);
                const data = await response.json();
                if (!data.projects) {
                    throw new Error("Invalid data format from the API");
                }
                return data.projects;
            } catch (error) {
                throw new Error(error);
            }
        },
        async toggleRelatedProject(project) {
            const index = this.translations.findIndex(t => t.muid === project);
            if (index > -1) {
                this.translations.splice(index, 1);
            } else {
                try {
                    await this.findOrCreateObject(project, this.prefix);
                } catch (error) {
                    throw new Error(error);
                }
            }
        },
    };
}

function textareaAdjuster() {
    return {
        observer: null,
        init() {
            const options = { threshold: [0.1] };
            const callback = entries => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const index = entry.target.getAttribute("data-index");
                        const sections = Array.from(
                            document.querySelectorAll(
                                `.project-container__content-body__section[data-index="${index}"]`,
                            ),
                        );
                        setMaxHeight(sections.map(section => section.querySelector("textarea")));
                    }
                });
            };
            this.observer = new IntersectionObserver(callback, options);
            this.observeSections();
        },
        observeSections() {
            const sections = document.querySelectorAll(".project-container__content-body__section");

            sections.forEach(section => {
                if (!this.observer) return;
                this.observer.unobserve(section);
                this.observer.observe(section);
            });
        },
    };
}

function adjustTextareas(element) {
    const parent = element.parentElement;
    const index = parent.getAttribute("data-index");
    const sections = Array.from(
        document.querySelectorAll(`.project-container__content-body__section[data-index="${index}"]`),
    );
    setMaxHeight(sections.map(section => section.querySelector("textarea")));
}

function* generateUniqueVisibleElements() {
    const body = document.querySelector(".project-container__content-body");
    const elements = body.querySelectorAll(".project-container__content-body__section");
    for (const el of elements) {
        if (isInViewPort(el)) {
            yield el;
        } else {
            break;
        }
    }
}

function adjustVisibleTextareas() {
    const uniqueVisibleElements = generateUniqueVisibleElements();
    for (const el of uniqueVisibleElements) {
        adjustTextareas(el.querySelector("textarea"));
    }
}

function dragHandler() {
    const container = document.querySelector(".project-container__content");
    const dragElems = document.querySelectorAll(".draggable-container");

    dragElems.forEach(elem => {
        elem.addEventListener("dragstart", event => {
            const draggable = elem.closest(".project-container__content-details");
            draggable.classList.add("dragging");
            event.dataTransfer.setDragImage(draggable, event.clientX, event.clientY);
        });

        elem.addEventListener("dragend", e => {
            const afterElement = document
                .elementFromPoint(e.clientX, e.clientY)
                .closest(".project-container__content-details");
            if (!afterElement) return;
            const dragging = document.querySelector(".dragging");
            const orderTarget = afterElement.style.order;
            afterElement.style.order = dragging.style.order;
            dragging.style.order = orderTarget;
            dragging.classList.remove("dragging");
        });
    });

    container.addEventListener("dragover", e => {
        e.preventDefault();
    });
}

function resizeHandler() {
    const resizables = document.querySelectorAll(".resize");
    resizables.forEach(resize => {
        const container = resize.parentElement.parentElement;
        let x, w;

        resize.addEventListener("mousedown", e => {
            x = e.clientX;
            w = container.clientWidth;
            document.addEventListener("mousemove", move);
            document.addEventListener("mouseup", up);
        });

        function move(e) {
            const mx = e.clientX;
            const cx = mx - x;
            const detailPanel = container.parentElement;
            if (detailPanel.classList.contains("project-container__detail-panel")) {
                detailPanel.style.maxWidth = "100%";
            }
            container.style.width = `${w + cx}px`;
        }

        function up(e) {
            document.removeEventListener("mousemove", move);
            document.removeEventListener("mouseup", up);
            adjustVisibleTextareas();
        }
    });
}
