from network.configdiff import config_delete_commands, split_config_commands


def test_split_drops_blank_lines_and_comments():
    text = (
        '# Device: spine1\n'
        '\n'
        'set / system name host-name spine1\n'
        '   \n'
        'set / system ntp admin-state enable\n'
    )
    assert split_config_commands(text) == (
        ['set / system name host-name spine1', 'set / system ntp admin-state enable'],
        [],
    )


def test_split_skips_multiline_statement_and_keeps_following_lines():
    text = (
        'set / system name host-name spine1\n'
        'set / system banner login-banner "Welcome\n'
        'to spine1"\n'
        'set / system ntp admin-state enable\n'
    )
    assert split_config_commands(text) == (
        ['set / system name host-name spine1', 'set / system ntp admin-state enable'],
        ['set / system banner login-banner "Welcome\nto spine1"'],
    )


def test_split_reports_unterminated_statement_as_skipped():
    text = (
        'set / system name host-name spine1\n'
        'set / system banner login-banner "Welcome\n'
        'to spine1\n'
    )
    assert split_config_commands(text) == (
        ['set / system name host-name spine1'],
        ['set / system banner login-banner "Welcome\nto spine1'],
    )


BASE = (
    'set / interface ethernet-1/1 description to_leaf1\n'
    'set / interface ethernet-1/1 admin-state enable\n'
    'set / system name host-name spine1\n'
)


def test_identical_configs_need_no_deletes():
    assert config_delete_commands(BASE, BASE) == ([], [])


def test_added_container_deleted_at_shortest_path():
    current = BASE + (
        'set / system ntp admin-state enable\n'
        'set / system ntp server 10.0.0.1 iburst true\n'
    )
    assert config_delete_commands(current, BASE) == (['delete / system ntp'], [])


def test_extra_list_entry_deleted_by_key():
    target = BASE + 'set / system ntp server 10.0.0.1 iburst true\n'
    current = target + 'set / system ntp server 10.0.0.2 iburst true\n'
    assert config_delete_commands(current, target) == (
        ['delete / system ntp server 10.0.0.2'], []
    )


def test_changed_leaf_value_deletes_leaf():
    current = BASE.replace('to_leaf1', '"changed by deploy"')
    assert config_delete_commands(current, BASE) == (
        ['delete / interface ethernet-1/1 description'], []
    )


def test_changed_leaf_list_deletes_leaf():
    target = BASE + 'set / system grpc-server mgmt services [ gnmi ]\n'
    current = BASE + 'set / system grpc-server mgmt services [ gnmi gnoi ]\n'
    assert config_delete_commands(current, target) == (
        ['delete / system grpc-server mgmt services'], []
    )


def test_removed_config_needs_no_delete():
    current = 'set / system name host-name spine1\n'
    assert config_delete_commands(current, BASE) == ([], [])


def test_ignores_header_comments():
    target = '# Configuration Backup\n# Device: spine1\n\n' + BASE
    assert config_delete_commands(BASE, target) == ([], [])


def test_delete_next_to_multiline_statement_stays_narrow():
    target = BASE + (
        'set / system banner login-banner "line one\n'
        'line two"\n'
    )
    current = target + 'set / system banner motd-banner hello\n'
    assert config_delete_commands(current, target) == (
        ['delete / system banner motd-banner'], []
    )


def test_withholds_delete_covering_multiline_statement():
    current = BASE + (
        'set / system tls server-profile lab cipher-list [ aes ]\n'
        'set / system tls server-profile lab key "-----BEGIN KEY-----\n'
        '-----END KEY-----"\n'
    )
    assert config_delete_commands(current, BASE) == (
        [], ['delete / system tls']
    )
