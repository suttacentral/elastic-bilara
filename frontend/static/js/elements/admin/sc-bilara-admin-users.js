import { LitElement, html } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class ScBilaraAdminUsers extends LitElement {

    createRenderRoot() {
        return this;
    }

    render() {
        return html`
          <div x-data="dataTypes.users" x-init="await getUsers()">
              <div class="admin-section-header">
                  <h1 class="admin-section-title">User Management</h1>
              </div>


              <ul class="admin-user-list">
                  <template x-for="(user, key) in users" :key="user.id">
                      <li class="admin-user-item">
                          <!-- User Header (Clickable) -->
                          <div class="admin-user-header" @click="user.showDetails = !user.showDetails">
                              <div class="admin-user-info">
                                  <img :src="user.avatar_url" :alt="${'`${user.username}\'s profile`'}"
                                       class="admin-user-avatar"/>
                                  <div>
                                      <p class="admin-user-name" x-text="user.username"></p>
                                      <p class="admin-user-meta" x-text="${'`Last seen: ${formatDate(user.last_login)}`'}"></p>
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
                                      <label :for="${'`${key}-role`'}" class="admin-label">Change Role</label>
                                      <select :name="${'`${key}-role`'}" :id="${'`${key}-role`'}" x-model="user.role"
                                              x-on:change="await setUsersRole(user.github_id, user.role); await redirectNonPrivilegedUserFromAdminToNav(); user=await getUser(user.github_id); user.showDetails = !user.showDetails"
                                              class="admin-select">
                                          <template x-for="role in ROLES">
                                              <option x-text="role" :value="role" :selected="role === user.role"></option>
                                          </template>
                                      </select>
                                  </div>
                                  <div class="admin-form-group">
                                      <label :for="${'`${key}-state`'}" class="admin-label">Account Status</label>
                                      <select :name="${'`${key}-state`'}" :id="${'`${key}-state`'}" x-model="user.is_active"
                                              x-on:change="await activateUser(user.github_id, user.is_active); await redirectNonPrivilegedUserFromAdminToNav(); user=await getUser(user.github_id); user.showDetails = !user.showDetails"
                                              class="admin-select">
                                          <template x-for="state in ['true', 'false']">
                                              <option x-text="state === 'true' ? 'Active' : 'Inactive'" :value="state"
                                                      :selected="user.is_active === (state === 'true')"></option>
                                          </template>
                                      </select>
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
                                  <div class="admin-info-card">
                                      <span class="admin-info-label">Email</span>
                                      <span class="admin-info-value" x-text="user.email"></span>
                                  </div>
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
                                                      x-text="selectedUser ? ${"'`Delete ${selectedUser.username}?`'"} : ''"></h2>
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
