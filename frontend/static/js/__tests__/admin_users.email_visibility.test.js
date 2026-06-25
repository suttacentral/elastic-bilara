const fs = require('fs');
const path = require('path');

const ROLES = {
    admin: 'administrator',
    superuser: 'superuser',
};
const adminUsersSource = fs.readFileSync(path.resolve(__dirname, '../adminUsers.js'), 'utf8');
const adminUsersElementSource = fs.readFileSync(
    path.resolve(__dirname, '../elements/admin/sc-bilara-admin-users.js'),
    'utf8'
);

eval(adminUsersSource);

describe('admin user email visibility', () => {
    test('only administrators can view managed user email', () => {
        const component = users();

        component.currentUserRole = ROLES.superuser;
        expect(component.canViewUserEmail()).toBe(false);

        component.currentUserRole = ROLES.admin;
        expect(component.canViewUserEmail()).toBe(true);
    });

    test('loads the current role before loading users', async () => {
        const component = users();
        component.getUsers = jest.fn().mockResolvedValue();
        global.getUserInfo = jest.fn(() => ({
            role: ROLES.superuser,
            getRole: jest.fn().mockResolvedValue(),
        }));

        await component.init();

        expect(component.currentUserRole).toBe(ROLES.superuser);
        expect(component.getUsers).toHaveBeenCalledTimes(1);
    });

    test('conditionally renders only the managed-user email card', () => {
        expect(adminUsersElementSource).toContain('<template x-if="canViewUserEmail()">');
        expect(adminUsersElementSource).toContain('id="email"');
    });
});
