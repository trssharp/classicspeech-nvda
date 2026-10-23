"""Bounded, declarative single-preset transfer; no GUI or configuration writes."""
import copy
import json
import os
import tempfile
import uuid

from . import model

FORMAT = 'ClassicSpeech presentation preset'
VERSION = 1
MAX_FILE_BYTES = model.MAX_BYTES


def validate(record):
    if not isinstance(record, dict):
        raise ValueError('Invalid preset record.')
    name = record.get('name')
    if not model._text(name, 80) or not name.strip():
        raise ValueError('Invalid preset name.')
    model.from_domains(record.get('domains'))
    return copy.deepcopy(record)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field: ' + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Non-finite JSON numbers are not supported.')


def decode(data):
    try:
        if not isinstance(data, bytes) or len(data) > MAX_FILE_BYTES:
            raise ValueError('Preset file is too large (maximum 600000 bytes).')
        payload = json.loads(data.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
        if (not isinstance(payload, dict) or payload.get('format') != FORMAT
                or type(payload.get('version')) is not int or payload['version'] != VERSION):
            raise ValueError('Unsupported presentation preset file format or version.')
        record = validate(payload.get('preset'))
        # Also reject overflowed JSON exponents (e.g. 1e999), including opaque
        # fields, without interpreting or applying any unknown content.
        json.dumps(record, allow_nan=False)
        return record
    except (UnicodeError, RecursionError, TypeError, OverflowError) as error:
        raise ValueError('Invalid presentation preset file.') from error


def encode(record):
    try:
        data = json.dumps({'format': FORMAT, 'version': VERSION, 'preset': validate(record)},
                          ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8')
        if len(data) > MAX_FILE_BYTES:
            raise ValueError('Preset file is too large (maximum 600000 bytes).')
        return data
    except (UnicodeError, RecursionError, TypeError, OverflowError) as error:
        raise ValueError('Invalid presentation preset data.') from error


def read(path):
    with open(path, 'rb') as stream:
        return decode(stream.read(MAX_FILE_BYTES + 1))


def write(path, record):
    """Validate before opening; replace atomically from a closed same-folder file."""
    data = encode(record)
    path = os.path.abspath(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=os.path.dirname(path),
                                         prefix='.classicspeech-preset-', suffix='.tmp', delete=False) as stream:
            temporary = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def selected_record(library, key):
    # Built-in defaults are generated from this installation, not a saved record.
    if key == model.DEFAULT_ID or key not in library.records:
        raise ValueError('Select a saved preset to export. ClassicSpeech defaults cannot be exported.')
    return validate(library.records[key])


def stage(library, record, name):
    """Preflight a complete candidate library before mutating the working copy.

    Import never loads the record or changes the loaded/reference metadata.
    """
    library._require_writable()
    record = validate(record)
    record['name'] = library.validate_name(name)
    if len(library.records) >= model.MAX_RECORDS:
        raise ValueError('The preset library is full (100 presets).')
    candidate = copy.deepcopy(library)
    key = uuid.uuid4().hex
    candidate.records[key] = record
    candidate.serialize()
    library.records[key] = record
    return key
