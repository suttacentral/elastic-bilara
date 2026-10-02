function isCommentReadOnly(muid, uid) {
    if (!muid.startsWith('comment-')) return false;
    const colon = uid.indexOf(':');
    return colon !== -1 && uid.slice(colon + 1).split('.').some(part => /^0+$/.test(part));
}

function assertCommentSegmentsEditable(muid, uids) {
    const blocked = uids.filter(uid => isCommentReadOnly(muid, uid));
    if (blocked.length) {
        throw new Error(`Comment is read-only for segments with a zero UID component: ${blocked.join(', ')}`);
    }
}
