from network.configdiff import (
    config_delete_commands,
    needed_set_commands,
    split_config_commands,
    unified_diff,
)


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


def test_new_list_under_existing_entry_deleted_with_key():
    # Lab: 'delete / interface ethernet-1/1 subinterface' -> "Missing value for 'index'"
    current = BASE + (
        'set / interface ethernet-1/1 subinterface 0 admin-state enable\n'
        'set / interface ethernet-1/1 subinterface 0 ipv4 address 10.1.1.2/30\n'
    )
    assert config_delete_commands(current, BASE) == (
        ['delete / interface ethernet-1/1 subinterface 0'], []
    )


def test_new_list_with_two_keys_deleted_with_both_keys():
    current = BASE + 'set / acl acl-filter cpm type ipv4 entry 10 action accept\n'
    target = BASE + 'set / acl policers system-cpu-policer icmp peak-packet-rate 1000\n'
    assert config_delete_commands(current, target) == (
        ['delete / acl acl-filter cpm type ipv4'], []
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


def test_needed_sets_leave_out_lines_already_on_device():
    current = 'set / system name host-name spine1\nset / system ntp admin-state enable\n'
    target = ['set / system name host-name spine1', 'set / system ntp admin-state disable']
    deletes = ['delete / system ntp admin-state']
    assert needed_set_commands(current, target, deletes) == [
        'set / system ntp admin-state disable'
    ]


def test_needed_sets_resend_lines_under_a_wide_delete():
    current = (
        'set / network-instance mgmt type ip-vrf\n'
        'set / network-instance mgmt protocols bgp\n'
        'set / network-instance mgmt protocols ospf\n'
    )
    target = ['set / network-instance mgmt type ip-vrf', 'set / network-instance mgmt protocols bgp']
    # 'ospf' ends its line, so the delete is made one level up and also removes bgp
    deletes, _ = config_delete_commands(current, '\n'.join(target))
    assert deletes == ['delete / network-instance mgmt protocols']
    assert needed_set_commands(current, target, deletes) == [
        'set / network-instance mgmt protocols bgp'
    ]


def test_unified_diff_marks_removed_and_added_lines():
    old = 'set / system name host-name spine1\nset / system ntp admin-state disable\n'
    new = 'set / system name host-name spine1\nset / system ntp admin-state enable\n'
    assert unified_diff(old, new, 'old', 'new') == [
        '--- old',
        '+++ new',
        '@@ -1,2 +1,2 @@',
        ' set / system name host-name spine1',
        '-set / system ntp admin-state disable',
        '+set / system ntp admin-state enable',
    ]


def test_unified_diff_of_equal_configs_is_empty():
    assert unified_diff(BASE, BASE, 'old', 'new') == []
