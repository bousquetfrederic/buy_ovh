from m.autobuy import is_auto_buy, add_auto_buy


def plan(fqn='24sk40.ram-32g-ecc.softraid-2x480ssd.gra',
         model='KS-4',
         price=10.0):
    return {'fqn': fqn, 'model': model, 'price': price}


def rule(regex, num=1, max_price=0):
    return {'regex': regex, 'num': num, 'max_price': max_price,
            'invoice': False, 'unknown': False}


# ---------------- is_auto_buy ----------------

class TestIsAutoBuy:

    def test_regex_matches_fqn(self):
        assert is_auto_buy(plan(fqn='24sk40.foo.gra'), rule(r'24sk40'))

    def test_regex_matches_model(self):
        assert is_auto_buy(plan(fqn='x.y.z', model='KS-LE-B'), rule(r'KS-LE-B'))

    def test_regex_no_match(self):
        assert not is_auto_buy(plan(fqn='x.y.z', model='OTHER'),
                               rule(r'KS-LE-B'))

    def test_num_zero_never_matches(self):
        assert not is_auto_buy(plan(), rule(r'24sk40', num=0))

    def test_num_negative_never_matches(self):
        assert not is_auto_buy(plan(), rule(r'24sk40', num=-1))

    def test_max_price_zero_means_no_cap(self):
        assert is_auto_buy(plan(price=999.0), rule(r'24sk40', max_price=0))

    def test_price_at_cap_matches(self):
        assert is_auto_buy(plan(price=20.0), rule(r'24sk40', max_price=20))

    def test_price_above_cap_rejects(self):
        assert not is_auto_buy(plan(price=21.0), rule(r'24sk40', max_price=20))

    def test_price_below_cap_matches(self):
        assert is_auto_buy(plan(price=5.0), rule(r'24sk40', max_price=20))

    def test_all_conditions_required(self):
        # regex would match but num is 0 -> no
        r = rule(r'24sk40', num=0, max_price=100)
        assert not is_auto_buy(plan(price=5.0), r)
        # regex does not match, all else fine -> no
        assert not is_auto_buy(plan(fqn='nomatch.gra', model='nomatch'),
                               rule(r'KS-4', num=1, max_price=100))

    def test_regex_anchors(self):
        # regex uses re.search, not fullmatch, so partial matches count
        assert is_auto_buy(plan(fqn='prefix-24sk40-suffix.gra'),
                           rule(r'24sk40'))


# ---------------- add_auto_buy ----------------

class TestAddAutoBuy:

    def test_tags_matching_plan(self):
        plans = [plan(fqn='24sk40.foo.gra')]
        add_auto_buy(plans, [rule(r'24sk40')])
        assert plans[0]['autobuy'] is True

    def test_untagged_when_no_match(self):
        plans = [plan(fqn='other.foo.gra', model='OTHER')]
        add_auto_buy(plans, [rule(r'24sk40')])
        assert plans[0]['autobuy'] is False

    def test_empty_rules_all_false(self):
        plans = [plan(), plan(fqn='other.bar.rbx')]
        add_auto_buy(plans, [])
        assert all(p['autobuy'] is False for p in plans)

    def test_first_match_wins_short_circuit(self):
        # Two rules both match; is_auto_buy should stop at the first.
        # We verify by decrementing-style: make first rule's num=0 so it
        # won't match; then only the second should match.
        rules = [rule(r'24sk40', num=0), rule(r'KS-4')]
        p = plan()
        add_auto_buy([p], rules)
        assert p['autobuy'] is True

    def test_overwrites_previous_autobuy_flag(self):
        # add_auto_buy resets the flag to False then re-evaluates.
        p = plan(fqn='other.bar.rbx', model='OTHER')
        p['autobuy'] = True  # stale value
        add_auto_buy([p], [rule(r'24sk40')])
        assert p['autobuy'] is False

    def test_handles_empty_plans(self):
        # Should not error on empty input.
        add_auto_buy([], [rule(r'24sk40')])

    def test_multiple_plans_independent(self):
        plans = [
            plan(fqn='24sk40.foo.gra'),
            plan(fqn='other.bar.rbx', model='OTHER'),
            plan(fqn='KS-LE.foo.gra', model='KS-LE-B'),
        ]
        add_auto_buy(plans, [rule(r'24sk40'), rule(r'KS-LE-B')])
        assert [p['autobuy'] for p in plans] == [True, False, True]

    def test_price_filter_applied(self):
        plans = [plan(price=10.0), plan(price=100.0)]
        add_auto_buy(plans, [rule(r'24sk40', max_price=50)])
        assert plans[0]['autobuy'] is True
        assert plans[1]['autobuy'] is False
