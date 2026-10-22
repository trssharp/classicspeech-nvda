"""Versioned named-domain snapshots; no config or GUI side effects.

Version 1 carries explicit named domains. Future payloads are preserved but
never applied. Missing later domains leave current settings unchanged.
"""
import copy
import json
import uuid
from . import domains as extended

VERSION = 1
MAX_RECORDS = 100
MAX_BYTES = 600000
DEFAULT_ID = 'defaults'
DEFAULT_NAME = 'ClassicSpeech defaults'
TOKEN_FIELDS = ('order', 'renames', 'mutedLabels')
TIMING_FIELDS = ('pauseMode', 'globalPause', 'pauses', 'pausePlacement', 'pauseAfterFinalToken')
FIELDS = TOKEN_FIELDS + TIMING_FIELDS
SHAPE_DOMAINS = {'tokens': TOKEN_FIELDS, 'timing': TIMING_FIELDS}
DOMAINS = {**SHAPE_DOMAINS, **extended.FIELDS}
TOKENS = ('name', 'role', 'value', 'state', 'position', 'description', 'hotkey')


def defaults():
    # Import lazily: verbosity imports the settings package during startup.
    from ...verbosity import VerbosityManager
    return copy.deepcopy(VerbosityManager.DEFAULT_SHAPE)


def _text(value, limit=500):
    return isinstance(value, str) and len(value) <= limit and not any(ord(c) < 32 for c in value)


def capture(shape):
    """Strict full v1 snapshot, with unrelated keys deliberately excluded."""
    if not isinstance(shape, dict) or not all(k in shape for k in FIELDS):
        raise ValueError('Incomplete presentation settings')
    order = shape['order']
    renames = shape['renames']
    muted = shape['mutedLabels']
    pauses = shape['pauses']
    if (not isinstance(order, list) or len(order) != len(TOKENS)
            or any(not isinstance(t, str) for t in order) or set(order) != set(TOKENS)):
        raise ValueError('Invalid token order')
    if (not isinstance(renames, dict) or len(renames) > 1000
            or any(not _text(k) or not k or not _text(v) for k, v in renames.items())):
        raise ValueError('Invalid renames')
    if (not isinstance(muted, list) or len(muted) > 1000
            or any(not _text(t) or not t for t in muted)):
        raise ValueError('Invalid muted labels')
    if (not isinstance(pauses, dict) or set(pauses) != set(TOKENS)
            or any(type(v) is not int or not -1 <= v <= 2000 for v in pauses.values())):
        raise ValueError('Invalid pauses')
    if type(shape['globalPause']) is not int or not 0 <= shape['globalPause'] <= 2000:
        raise ValueError('Invalid global pause')
    if shape['pauseMode'] not in ('global', 'perToken'):
        raise ValueError('Invalid pause mode')
    if shape['pausePlacement'] not in ('before', 'after'):
        raise ValueError('Invalid pause placement')
    if type(shape['pauseAfterFinalToken']) is not bool:
        raise ValueError('Invalid final pause')
    result = {key: copy.deepcopy(shape[key]) for key in FIELDS}
    result['mutedLabels'] = sorted(set(muted), key=str.casefold)
    for name in extended.FIELDS:
        if name in shape:
            result[name] = extended.validate(name, shape[name])
    return result


def merge(current, snapshot):
    result = copy.deepcopy(current)
    result.update(capture(snapshot))
    return result


def to_domains(shape):
    shape = capture(shape)
    result = {domain: {field: shape[field] for field in fields} for domain, fields in SHAPE_DOMAINS.items()}
    result.update({name: shape[name] for name in extended.FIELDS if name in shape})
    return result


def from_domains(domains):
    if not isinstance(domains, dict) or any(not isinstance(domains.get(k), dict) for k in SHAPE_DOMAINS):
        raise ValueError('Incomplete presentation domains')
    shape = {}
    for domain, fields in SHAPE_DOMAINS.items():
        shape.update({field: domains[domain][field] for field in fields if field in domains[domain]})
    for name in extended.FIELDS:
        if name in domains:
            data = domains[name]
            # A future domain version stays opaque and cannot change live state.
            if isinstance(data, dict) and type(data.get('version')) is int and data['version'] != 1:
                continue
            shape[name] = extended.validate(name, data)
    return capture(shape)


class Library:
    def __init__(self, raw, current):
        self.extended = any(name in current for name in extended.FIELDS)
        self.records = {}
        self.loaded = None
        try:
            self.reference = capture(current)
        except ValueError:
            # Existing native/current settings can exceed this format's bounds.
            # Keep them live, allow explicit Load, and never force a default.
            self.reference = None
        self.invalid = False
        self.read_only = False
        self._raw = raw
        if raw:
            try:
                if not isinstance(raw, str) or len(raw) > MAX_BYTES:
                    raise ValueError('Library too large')
                data = json.loads(raw)
                if (isinstance(data, dict) and type(data.get('version')) is int
                        and data['version'] != VERSION):
                    self.read_only = True
                    raise ValueError('Unsupported library version')
                if (not isinstance(data, dict) or type(data.get('version')) is not int
                        or data['version'] != VERSION or not isinstance(data.get('records'), dict)
                        or len(data['records']) > MAX_RECORDS):
                    raise ValueError('Unsupported library')
                for key, record in data['records'].items():
                    try:
                        if not _text(key, 64) or not key or key == DEFAULT_ID or not isinstance(record, dict):
                            raise ValueError('Invalid record')
                        name = self.validate_name(record.get('name'))
                        domains = record.get('domains')
                        from_domains(domains)
                        self.records[key] = {'name': name, 'domains': copy.deepcopy(domains)}
                    except (ValueError, TypeError):
                        self.invalid = True
                loaded = data.get('loaded')
                if loaded == DEFAULT_ID or loaded in self.records:
                    self.loaded = loaded
                    self.reference = self.snapshot(loaded)
            except (ValueError, TypeError, RecursionError):
                self.invalid = True
        if self.loaded is None and self.reference == self.snapshot(DEFAULT_ID):
            self.loaded = DEFAULT_ID

    def validate_name(self, name, excluding=None):
        if not _text(name, 80) or not name.strip():
            raise ValueError('Enter a name of 1 to 80 characters, without control characters.')
        name = name.strip()
        names = [DEFAULT_NAME] + [v['name'] for k, v in self.records.items() if k != excluding]
        if name.casefold() in {n.casefold() for n in names}:
            raise ValueError('That preset name already exists. Choose another name.')
        return name

    def snapshot(self, key):
        if key == DEFAULT_ID:
            result = defaults()
            if self.extended:
                result.update(extended.defaults())
            return result
        return from_domains(self.records[key]['domains'])

    def modified(self, current):
        try:
            scoped = current if self.reference is None else {k: current[k] for k in self.reference if k in current}
            captured = capture(scoped)
            # A partial older record owns only its supported, present domains.
            return self.reference is None or any(captured.get(k) != v for k, v in self.reference.items())
        except ValueError:
            return True

    def load(self, key):
        snapshot = self.snapshot(key)
        self.loaded = key
        self.reference = copy.deepcopy(snapshot)
        return snapshot

    def _require_writable(self):
        if self.read_only:
            raise ValueError('This preset library uses an unsupported version and is read-only. '
                             'Its data will be kept unchanged. Use a compatible ClassicSpeech version '
                             'to edit it, or explicitly replace the library.')

    def _editable(self, key):
        self._require_writable()
        if key == DEFAULT_ID or key not in self.records:
            raise ValueError('ClassicSpeech defaults cannot be changed.')

    def save_as(self, name, current):
        self._require_writable()
        name = self.validate_name(name)
        if len(self.records) >= MAX_RECORDS:
            raise ValueError('The preset library is full (100 presets).')
        shape = capture(current)
        key = uuid.uuid4().hex
        self.records[key] = {'name': name, 'domains': to_domains(shape)}
        self.load(key)
        return key

    def update(self, key, current):
        self._editable(key)
        # Replace only audited fields, retaining opaque fields and sibling domains.
        for domain, fields in to_domains(current).items():
            target = self.records[key]['domains'].setdefault(domain, {})
            if domain in extended.FIELDS:
                # Never overwrite a domain owned by a newer implementation.
                if type(target.get('version')) is int and target['version'] != 1:
                    continue
                extended.merge_owned(target, fields, domain)
            else:
                target.update(fields)
        self.load(key)

    def rename(self, key, name):
        self._editable(key)
        self.records[key]['name'] = self.validate_name(name, excluding=key)

    def delete(self, key):
        self._editable(key)
        del self.records[key]
        if self.loaded == key:
            self.loaded = None

    def serialize(self):
        if self.read_only:
            return self._raw
        result = json.dumps({'version': VERSION, 'records': self.records, 'loaded': self.loaded},
                            ensure_ascii=True, sort_keys=True).replace('%', r'\u0025')
        # ConfigObj interpolation must never interpret user names or labels.
        if len(result) > MAX_BYTES:
            raise ValueError('The preset library is too large.')
        return result
