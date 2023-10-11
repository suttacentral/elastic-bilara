function search() {
	return {
		closed: true,
		projects: [],
		suggestions: [],
		projectQuery: "",
		selectedProjects: {},
		size: 10,
		page: 0,
		currentPage: 0,
		isNextPage: false,
		fields: {
			uid: "",
		},
		results: {},
		async init() {
			try {
				const response = await requestWithTokenRetry(`projects/`);
				const { projects } = await response.json();
				if (!projects) {
					throw new Error("Invalid data format from the API");
				}
				this.projects = projects;
			} catch (error) {
				throw new Error(error);
			}
		},
		updateSuggestions() {
			if (!this.projectQuery) {
				this.suggestions = [];
				return;
			}
			this.suggestions = this.projects.filter((project) =>
				project.toLowerCase().startsWith(this.projectQuery.toLowerCase()),
			);
		},
		toggleSelectedProjects(project) {
			this.selectedProjects[project] = !this.selectedProjects[project];
			if (project in this.fields) {
				return delete this.fields[project];
			}
			this.fields[project] = "";
		},
		async searchHandler(event = null) {
			if (event !== null) {
				this.currentPage = 0;
				this.page = this.currentPage;
				this.isNextPage = false;
				this.results = {};
			}
			this.page = this.currentPage;
			this.prefetchedData = null;
			try {
				const params = this.constructQueryParams();
				const response = await requestWithTokenRetry(
					`search/?${params.toString()}`,
				);
				const { results } = await response.json();
				if (!results) {
					throw new Error("Invalid data format from the API");
				}
				this.results = results;
				this.renderResults();
				this.currentPage = this.page;
				this.page++;
				await this.prefetchNextPage();
			} catch (error) {
				throw new Error(error);
			}
		},
		async prefetchNextPage() {
			const nextPageParams = new URLSearchParams(this.constructQueryParams());
			nextPageParams.set("page", this.page);
			const response = await requestWithTokenRetry(
				`search/?${nextPageParams.toString()}`,
			);
			const { results } = await response.json();
			if (!results) {
				throw new Error("Invalid data format from the API");
			}
			this.prefetchedData = results;
			this.isNextPage = Object.keys(this.prefetchedData).length !== 0;
		},
		async nextHandler() {
			if (this.prefetchedData) {
				this.results = this.prefetchedData;
				this.prefetchedData = null;
				this.currentPage = this.page;
				this.page++;
				this.renderResults();
				if (this.isNextPage) {
					await this.prefetchNextPage();
				}
			} else {
				await this.searchHandler();
			}
		},
		async previousHandler() {
			if (this.currentPage > 0) {
				this.page = --this.currentPage;
				await this.searchHandler();
			}
		},
		constructQueryParams() {
			const params = new URLSearchParams();
			this.size = this.size <= 100 ? this.size : 10
			params.set("size", this.size);
			params.set("page", this.currentPage);
			for (const [key, value] of Object.entries(this.fields)) {
				params.set(key, value);
			}
			return params;
		},
		renderResults() {
			let html = "";
			for (const [resultKey, resultValue] of Object.entries(this.results)) {
				html += `
					<div class="px-2 py-1 border rounded">
						<h3 class="inline-block font-italic text-xs mb-2 border rounded-full py-1 px-2">${resultKey}</h3>
						<ul>
							${Object.entries(resultValue)
								.map(
									([key, value]) => `
								<li class="flex justify-around items-center flex-wrap text-lg"><span class="font-bold flex-shrink text-sm my-1 min-w-1/3">${key}:</span> ${value}</li>
							`,
								)
								.join("")}
						</ul>
					</div>
				`;
			}
			return html;
		},
		scrollTop(selector) {
			document.querySelector(selector).scrollTop = 0;
		},
	};
}
