import difflib
import re

# A token is a quoted string, a bracketed leaf-list value, or a bare word
_CONFIG_TOKEN_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\[[^\]]*\]|\S+')


def split_config_commands(config_text):
    """Split flat config text into single-line commands.

    Blank lines and '#' comments are dropped. Statements whose quoted value
    spans several lines (login banner, TLS keys) cannot be sent line by line,
    so they are skipped. Returns (commands, skipped_statements).
    """
    commands = []
    skipped = []
    # Lines of a multi-line statement collected so far; empty when not inside one
    pending = []

    for raw in config_text.splitlines():
        line = raw.strip()

        # Inside a multi-line statement: collect lines until the quote closes
        if pending:
            pending.append(line)
            if line.count('"') % 2 == 1:
                skipped.append('\n'.join(pending))
                pending = []
            continue

        if not line or line.startswith('#'):
            continue

        # An odd number of quotes means a quote opens here and closes on a later line
        if line.count('"') % 2 == 1:
            pending = [line]
            continue

        commands.append(line)

    # Text ended before the quote closed; still report the statement as skipped
    if pending:
        skipped.append('\n'.join(pending))

    return commands, skipped


def _set_path_tokens(line):
    """Tokenize the part after 'set / ' of a flat config line, or None."""
    if not line.startswith('set / '):
        return None
    return tuple(_CONFIG_TOKEN_RE.findall(line[len('set / '):]))


def _multiline_statement_paths(config_text):
    """Paths of the multi-line statements that split_config_commands skips."""
    _, skipped = split_config_commands(config_text)
    paths = []
    for statement in skipped:
        # The path is on the first line, up to where the quoted value starts
        first_line = statement.split('\n', 1)[0]
        path = []
        for token in _set_path_tokens(first_line) or ():
            if token.startswith('"'):
                break
            path.append(token)
        if path:
            paths.append(tuple(path))
    return paths


def config_delete_commands(current_config, target_config):
    """Compute the 'delete' commands that turn current_config into target_config.

    Sending these deletes, then target_config's set commands, in one commit
    yields the target config. Deletes that would remove a multi-line statement
    are withheld, since such statements cannot be sent back.
    Returns (delete_commands, withheld_commands).
    """
    target_commands, _ = split_config_commands(target_config)
    current_commands, _ = split_config_commands(current_config)
    target_multiline = _multiline_statement_paths(target_config)

    # Every path the target contains, including all prefixes of each line
    target_lines = set()
    target_prefixes = set()
    for command in target_commands:
        tokens = _set_path_tokens(command)
        if tokens is None:
            continue
        target_lines.add(tokens)
        for i in range(1, len(tokens) + 1):
            target_prefixes.add(tokens[:i])
    # Skipped statements still exist in the target; without this a delete
    # next to them would widen and remove them (e.g. 'delete / system banner')
    for path in target_multiline:
        for i in range(1, len(path) + 1):
            target_prefixes.add(path[:i])

    # For each extra line, delete at the first token the target does not have
    candidates = []
    for command in current_commands:
        tokens = _set_path_tokens(command)
        if tokens is None or tokens in target_lines:
            continue
        diverge = next(
            (i for i in range(1, len(tokens) + 1) if tokens[:i] not in target_prefixes),
            None,
        )
        if diverge is None:
            continue  # Current line is a prefix of a target line
        # Only the value differs (changed leaf): delete the leaf, not its value
        path = tokens[:diverge] if diverge < len(tokens) else tokens[:-1]
        if path and path not in candidates:
            candidates.append(path)

    # Drop paths already covered by deleting one of their ancestors
    paths = [
        path for path in candidates
        if not any(other != path and path[:len(other)] == other for other in candidates)
    ]

    # Never delete a multi-line statement; report it instead
    protected = _multiline_statement_paths(current_config) + target_multiline
    deletes = []
    withheld = []
    for path in paths:
        command = 'delete / ' + ' '.join(path)
        if any(p[:len(path)] == path for p in protected):
            withheld.append(command)
        else:
            deletes.append(command)

    return deletes, withheld


def needed_set_commands(current_config, target_commands, delete_commands):
    """The target commands to send after delete_commands, in the same commit.

    A command already on the device is left out, unless one of the deletes
    removes it as well (a delete can be wider than the line it was made for).
    """
    current_commands, _ = split_config_commands(current_config)
    current = set(current_commands)
    deleted_paths = [
        tuple(_CONFIG_TOKEN_RE.findall(command[len('delete / '):]))
        for command in delete_commands
    ]

    needed = []
    for command in target_commands:
        # Not on the device: a new or changed line, must be sent
        if command not in current:
            needed.append(command)
            continue
        # On the device, but inside a path that is about to be deleted
        tokens = _set_path_tokens(command) or ()
        if any(tokens[:len(path)] == path for path in deleted_paths):
            needed.append(command)
    return needed


def unified_diff(old_text, new_text, old_label, new_label):
    """Unified diff of two configs as a list of lines; empty if they are equal."""
    return list(difflib.unified_diff(
        old_text.splitlines(), new_text.splitlines(),
        fromfile=old_label, tofile=new_label,
        # splitlines() already removed the newlines; don't add them back
        lineterm='',
    ))
