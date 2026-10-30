import { LitElement, html } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class ScBilaraAdminUsers extends LitElement {

    createRenderRoot() {
        return this;
    }

    render() {
        return html`
          <div x-data="dataTypes.users">
              <div class="admin-section-header">
                  <h1 class="admin-section-title">User Management</h1>
                  <p class="admin-text-muted">Inactive accounts are listed first.</p>
              </div>


              <div class="admin-user-filters" role="group" aria-label="Filter users">
                  <div class="admin-form-group">
                      <label for="user-search" class="admin-label">Search users</label>
                      <input id="user-search" type="search" class="admin-input" x-model="searchQuery"
                             :placeholder="canViewUserEmail() ? 'Username, GitHub ID or email' : 'Username or GitHub ID'">
                  </div>
                  <div class="admin-form-group">
                      <label for="user-status-filter" class="admin-label">Account status</label>
                      <select id="user-status-filter" class="admin-select" x-model="filterStatus">
                          <option value="">All statuses</option>
                          <option value="false">Inactive</option>
                          <option value="true">Active</option>
                      </select>
                  </div>
                  <div class="admin-form-group">
                      <label for="user-role-filter" class="admin-label">Role</label>
                      <select id="user-role-filter" class="admin-select" x-model="filterRole">
                          <option value="">All roles</option>
                          <template x-for="role in ROLES" :key="role">
                              <option :value="role" x-text="role"></option>
                          </template>
                      </select>
                  </div>
                  <button type="button" class="btn admin-btn admin-btn-secondary" @click="clearFilters()"
                          :disabled="!hasFilters">Clear filters</button>
              </div>
              <p class="admin-text-muted" role="status" aria-live="polite" aria-atomic="true"
                 x-text="'Showing ' + filteredUsers.length + ' / ' + users.length + ' users'"></p>
              <p x-cloak x-show="operationMessage" x-text="operationMessage"
                 class="admin-alert admin-alert-success" role="status"></p>
              <p x-cloak x-show="operationError" x-text="operationError"
                 class="admin-alert admin-alert-danger" role="alert"></p>
              <div x-cloak x-show="usersLoaded && filteredUsers.length === 0" class="admin-card admin-mb-3">
                  <div class="admin-card-body">
                      <p x-text="hasFilters ? 'No users match the current filters.' : 'No users yet.'"></p>
                      <button x-show="hasFilters" type="button" class="btn admin-btn admin-btn-secondary"
                              @click="clearFilters()">Clear filters</button>
                  </div>
              </div>
              <ul class="admin-user-list">
                  <template x-for="user in filteredUsers" :key="user.id">
                      <li class="admin-user-item">
                          <!-- User Header (Clickable) -->
                          <div class="admin-user-header" @click="user.showDetails = !user.showDetails">
                              <div class="admin-user-info">
                                  <img :src="user.avatar_url" :alt="'Profile image for ' + user.username"
                                       class="admin-user-avatar"/>
                                  <div>
                                      <p class="admin-user-name" x-text="user.username"></p>
                                      <p class="admin-user-meta" x-text="'Last seen: ' + formatDate(user.last_login)"></p>
                                  </div>
                              </div>
                              <div class="admin-user-badges">
                                  <span class="admin-badge"
                                        :class="user.is_active ? 'admin-badge-active' : 'admin-badge-inactive'"
                                        x-text="user.is_active ? 'Active' : 'Inactive'"></span>
                                  <span class="admin-badge admin-badge-role" x-text="user.role"></span>
                                  <i class="bi-chevron-down admin-user-chevron" :class="{'open': user.showDetails}"></i>
                              </div>
                          </div>
                          <!-- User Details (Expandable) -->
                          <div x-cloak x-show="user.showDetails" class="admin-user-details">
                              <div class="admin-user-controls">
                                  <div class="admin-form-group">
                                      <label :for="'user-' + user.id + '-role'" class="admin-label">Change Role</label>
                                      <select :name="'user-' + user.id + '-role'" :id="'user-' + user.id + '-role'" x-model="user.selectedRole"
                                              :disabled="user.isUpdatingStatus || user.isUpdatingRole" :aria-busy="user.isUpdatingRole"
                                              x-on:change="await changeUserRole(user)"
                                              class="admin-select">
                                          <template x-for="role in ROLES">
                                              <option x-text="role" :value="role" :selected="role === user.selectedRole"></option>
                                          </template>
                                      </select>
                                      <p x-cloak x-show="user.isUpdatingRole" class="admin-text-muted" role="status">Saving user role…</p>
                                      <p x-cloak x-show="user.roleError" x-text="user.roleError"
                                         class="admin-alert admin-alert-danger" role="alert"></p>
                                  </div>
                                  <div class="admin-form-group">
                                      <label :for="'user-' + user.id + '-state'" class="admin-label">Account Status</label>
                                      <select :name="'user-' + user.id + '-state'" :id="'user-' + user.id + '-state'" x-model="user.selectedStatus"
                                              :disabled="user.isUpdatingStatus || user.isUpdatingRole" :aria-busy="user.isUpdatingStatus"
                                              x-on:change="await changeUserStatus(user)"
                                              class="admin-select">
                                          <template x-for="state in ['true', 'false']">
                                              <option x-text="state === 'true' ? 'Active' : 'Inactive'" :value="state"
                                                      :selected="user.selectedStatus === state"></option>
                                          </template>
                                      </select>
                                      <p x-cloak x-show="user.isUpdatingStatus" class="admin-text-muted" role="status">Saving account status…</p>
                                      <p x-cloak x-show="user.statusError" x-text="user.statusError"
                                         class="admin-alert admin-alert-danger" role="alert"></p>
                                  </div>
                              </div>
                              <!-- Info Grid -->
                              <div class="admin-info-grid">
                                  <div class="admin-info-card">
                                      <span class="admin-info-label">Github ID</span>
                                      <span class="admin-info-value" x-text="user.github_id"></span>
                                  </div>
                                  <div class="admin-info-card">
                                      <span class="admin-info-label">Username</span>
                                      <span class="admin-info-value" x-text="user.username"></span>
                                  </div>
                                  <template x-if="canViewUserEmail()">
                                      <div class="admin-info-card">
                                          <span class="admin-info-label">Email</span>
                                          <span class="admin-info-value" x-text="user.email"></span>
                                      </div>
                                  </template>
                                  <div class="admin-info-card">
                                      <span class="admin-info-label">Joined</span>
                                      <span class="admin-info-value" x-text="formatDate(user.created_on)"></span>
                                  </div>
                                  <div class="admin-info-card">
                                      <span class="admin-info-label">Last Seen</span>
                                      <span class="admin-info-value" x-text="formatDate(user.last_login)"></span>
                                  </div>
                              </div>
                              <!-- Delete Action -->
                              <div class="admin-user-actions" x-data="{ modalShown: false, selectedUser: null }">
                                  <button class="btn admin-btn admin-btn-danger"
                                          :disabled="user.isUpdatingStatus || user.isUpdatingRole"
                                          @click.prevent="selectedUser = user; modalShown = true">
                                      <i class="bi-trash"></i>
                                      Delete User
                                  </button>
                                  <!-- Delete Modal -->
                                  <div x-cloak x-show="modalShown" class="admin-modal-overlay"
                                       @click="modalShown = false" aria-modal="true">
                                      <div class="admin-modal" @click.stop>
                                          <div class="admin-modal-header">
                                              <div class="admin-modal-icon admin-modal-icon-danger">
                                                  <i class="bi-exclamation-triangle"></i>
                                              </div>
                                              <div>
                                                  <h2 class="admin-modal-title"
                                                      x-text="selectedUser ? 'Delete ' + selectedUser.username + '?' : ''"></h2>
                                                  <p class="admin-modal-subtitle">This action cannot be undone.</p>
                                              </div>
                                          </div>
                                          <div class="admin-modal-footer">
                                              <button @click="modalShown = false" class="btn admin-btn admin-btn-secondary">
                                                  Cancel
                                              </button>
                                              <button @click.prevent="await deleteUser(selectedUser.github_id); await getUsers(); modalShown = false; selectedUser = null"
                                                      class="btn admin-btn admin-btn-danger">
                                                  Delete
                                              </button>
                                          </div>
                                      </div>
                                  </div>
                              </div>
                          </div>
                      </li>
                  </template>
              </ul>
              <!-- Add User Form -->
              <div x-data="{open: false, newUser: {githubId: '', username: '', email: '', avatarUrl: '', role: 'writer'}}">
                  <!-- Toggle Button -->
                  <div class="admin-toolbar">
                      <div></div>
                      <button class="btn admin-btn admin-btn-secondary" @click="open = !open">
                          <i :class="open ? 'bi-dash-circle' : 'bi-plus-circle'"></i>
                          <span x-text="open ? 'Cancel' : 'Add User'"></span>
                      </button>
                  </div>
                  <!-- Add User Form Card -->
                  <div x-cloak x-show="open" class="admin-card admin-mb-3">
                      <div class="admin-card-header">
                          <h3 class="admin-card-title">Add New User</h3>
                      </div>
                      <div class="admin-card-body">
                          <form @submit.prevent="await createUser(newUser); await getUsers(); open=!open; newUser = {githubId: '', username: '', email: '', avatarUrl: '', role: 'writer'}">
                              <div class="admin-form-row">
                                  <div class="admin-form-group">
                                      <label for="githubId" class="admin-label">Github ID</label>
                                      <input type="text" id="githubId" x-model="newUser.githubId"
                                             class="admin-input" placeholder="Enter GitHub ID">
                                  </div>
                                  <div class="admin-form-group">
                                      <label for="role" class="admin-label">Role</label>
                                      <select name="role" id="role" x-model="newUser.role" class="admin-select">
                                          <template x-for="role in ROLES">
                                              <option x-text="role" :value="role" :selected="role === 'writer'"></option>
                                          </template>
                                      </select>
                                  </div>
                              </div>
                              <div class="admin-form-row">
                                  <div class="admin-form-group">
                                      <label for="username" class="admin-label">Username</label>
                                      <input type="text" id="username" x-model="newUser.username"
                                             class="admin-input" placeholder="Enter username">
                                  </div>
                                  <div class="admin-form-group">
                                      <label for="email" class="admin-label">Email</label>
                                      <input type="email" id="email" x-model="newUser.email"
                                             class="admin-input" placeholder="Enter email">
                                  </div>
                              </div>
                              <div class="admin-form-row">
                                  <div class="admin-form-group">
                                      <label for="avatarUrl" class="admin-label">Avatar URL</label>
                                      <input type="text" id="avatarUrl" x-model="newUser.avatarUrl"
                                             class="admin-input" placeholder="Enter avatar URL">
                                  </div>
                                  <div class="admin-form-group admin-form-actions">
                                      <button type="submit" class="btn admin-btn admin-btn-primary">
                                          <i class="bi-plus-circle"></i>
                                          Create User
                                      </button>
                                  </div>
                              </div>
                          </form>
                      </div>
                  </div>
              </div>
          </div>
        `;
    }
}

customElements.define('sc-bilara-admin-users', ScBilaraAdminUsers);
