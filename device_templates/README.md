# Device templates

Jinja2 templates for SR Linux config, used by the Deploy page. Every `.j2` file here shows up in the template list.

## How a template becomes a form

Every variable the template uses becomes a text field on the Deploy page, except these, which are filled in automatically:

| Variable | Value |
|---|---|
| `hostname` | device name |
| `ip` | device management IP |
| `role` | `spine` or `leaf` |
| `timestamp` | render time, `YYYY-MM-DD HH:MM:SS` |

A field left empty counts as not given:

- `{{ x | default('value') }}` uses the default.
- `{% if x is defined %}` skips the block.
- A plain `{{ x }}` fails the preview with `'x' is undefined`, so nothing is sent.

Use `is defined`, not `{% if x %}`: a missing variable is an error, even inside `if`.

## SR Linux rules

Each line is sent to the device on its own, then committed once.

- Write flat `set / ...` lines, the same format as `info flat` and the backups. Indented blocks with `{ }` are not supported.
- Comments start with `#`. SR Linux rejects `!` lines with a parsing error.
- Empty lines are skipped.

## Example

```jinja
# NTP for {{ hostname }}
set / system ntp admin-state enable
set / system ntp server {{ ntp_server }} prefer true
{% if ntp_backup is defined %}
set / system ntp server {{ ntp_backup }}
{% endif %}
```

The form asks for `ntp_server` (required) and `ntp_backup` (optional).
