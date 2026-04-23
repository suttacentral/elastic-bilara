let dataTypes = {
    users: users(),
    projects: projects(),
    publications: { isVisible: false },
    roots: roots(),
    shift: shift(),
}

function admin() {
    return {
        activeComponent: null,
        dataTypes,
        setActiveComponent(component) {
            if (this.activeComponent) {
                this.dataTypes[this.activeComponent].isVisible = false;
            }
            this.activeComponent = component;
            this.dataTypes[this.activeComponent].isVisible = true;
        }
    }
}
