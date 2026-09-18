"""Pure split/merge planning. Root order is authoritative for every data type."""
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path


def load_rules(operation):
    if operation not in ('split', 'merge'):
        raise ValueError('Unknown structure operation')
    rules = json.loads(Path(__file__).with_name(f'{operation}.json').read_text())
    if not isinstance(rules, dict) or not all(isinstance(v, str) for v in rules.values()):
        raise ValueError(f'Invalid {operation}.json')
    return rules


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def uid_parts(uid):
    match = re.fullmatch(r'([^:]+:(?:[0-9]+\.)*)([0-9]+)', uid)
    if not match:
        raise ValueError(f'Unsupported segment UID: {uid}')
    # Include the separator: single-level segments use ':', nested ones use '.'.
    return match[1], int(match[2])


def build_preview(files, root, operation, uid, rules):
    if root.split('/')[0] != 'root':
        raise ValueError('Split/merge must operate on a root project')
    root_data = files[root]
    keys = list(root_data)
    if uid not in root_data:
        raise ValueError('Segment does not exist in the root')
    parent, number = uid_parts(uid)
    index = keys.index(uid)
    next_uid = None
    new_uid = None
    merge_crosses_section = False
    mapping = dict(zip(keys, keys))
    if operation == 'split':
        new_uid = f'{parent}{number + 1}'
        for key in keys[index + 1:]:
            last = key.removeprefix(parent)
            if key.startswith(parent) and re.fullmatch(r'[0-9]+', last) and int(last) > number:
                mapping[key] = f'{parent}{int(last) + 1}'
        target_keys = [mapping[key] for key in keys]
        target_keys.insert(index + 1, new_uid)
    elif operation == 'merge':
        if index + 1 == len(keys):
            raise ValueError('There is no next root segment to merge')
        next_uid = keys[index + 1]
        next_parent, next_number = uid_parts(next_uid)
        # Adjacency follows root order, including across sections/subsections.
        merge_crosses_section = parent != next_parent
        del mapping[next_uid]
        for key in keys[index + 2:]:
            last = key.removeprefix(next_parent)
            if key.startswith(next_parent) and re.fullmatch(r'[0-9]+', last) and int(last) > next_number:
                mapping[key] = f'{next_parent}{int(last) - 1}'
        target_keys = [mapping[key] for key in keys if key != next_uid]
    else:
        raise ValueError('Unknown structure operation')
    if len(set(target_keys)) != len(target_keys):
        raise ValueError('Operation would produce duplicate UIDs')

    projects = []
    for path, before in files.items():
        kind = path.split('/')[0]
        if kind not in rules:
            raise ValueError(f'Data type `{kind}` is not found in `{operation}.json`. Please add it before proceeding.')
        if not isinstance(before, dict) or not all(isinstance(v, str) for v in before.values()):
            raise ValueError(f'Invalid segment data: {path}')
        if set(before) - set(keys):
            raise ValueError(f'Segments not found in root: {path}')
        # Sparse files follow the same root mapping; absent values are empty segments.
        after = {mapping[key]: before.get(key, '') for key in keys if key in mapping}
        if operation == 'split':
            after[new_uid] = ''
        elif rules[kind] != 'manual':
            after[uid] = before.get(uid, '') + rules[kind] + before.get(next_uid, '')
        after = {key: after[key] for key in target_keys}
        projects.append({'path': path, 'muid': '-'.join(Path(path).parts[:3]),
                         'data': after, 'before': before, 'manual': rules[kind] == 'manual'})
    if len({project['muid'] for project in projects}) != len(projects):
        raise ValueError('The text contains duplicate project IDs')
    return {'operation': operation, 'uid': uid, 'root': root, 'uid_mapping': mapping,
            'splitter_uid': new_uid, 'merger_uid': uid if operation == 'merge' else None,
            'mergee_uid': next_uid, 'projects': projects,
            'merge_crosses_section': merge_crosses_section,
            'manual_projects': [p['muid'] for p in projects if p['manual']],
            'revision': digest([root, operation, uid, rules, sorted(files.items())])}


def apply_edits(preview, edits, reviewed):
    if set(preview['manual_projects']) - set(reviewed):
        raise ValueError('Review every manual project before confirming')
    projects = {p['muid']: p for p in preview['projects']}
    if set(edits) - set(projects):
        raise ValueError('Edits contain an unrelated project')
    result = {}
    for muid, project in projects.items():
        data = deepcopy(project['data'])
        changes = edits.get(muid, {})
        if set(changes) - set(data) or not all(isinstance(v, str) for v in changes.values()):
            raise ValueError(f'Invalid edited segments: {muid}')
        data.update(changes)
        if muid.startswith('html-'):
            required = [preview['uid']]
            if preview['splitter_uid']:
                required.append(preview['splitter_uid'])
            for key in required:
                if not data[key].strip():
                    raise ValueError(f'{muid}: {key}: HTML must not be empty. Add the appropriate markup with one {{}} placeholder.')
        result[muid] = data
    return result
