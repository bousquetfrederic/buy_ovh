import m.monitor as mon


# ---------------- compress_fnq_list ----------------

class TestCompressFqnList:

    def test_single_fqn_is_unchanged(self):
        assert mon.compress_fnq_list(['a.b.c.d']) == ['a.b.c.d']

    def test_two_fqns_same_prefix_merge(self):
        out = mon.compress_fnq_list(['a.b.c.d', 'a.b.c.e'])
        assert out == ['a.b.c.(d|e)']

    def test_merged_last_parts_are_sorted(self):
        out = mon.compress_fnq_list(['a.b.c.z', 'a.b.c.a', 'a.b.c.m'])
        assert out == ['a.b.c.(a|m|z)']

    def test_different_prefixes_stay_separate(self):
        out = mon.compress_fnq_list(['a.b.c.d', 'a.b.c.e', 'x.y.z.q'])
        assert set(out) == {'a.b.c.(d|e)', 'x.y.z.q'}

    def test_empty_input_empty_output(self):
        assert mon.compress_fnq_list([]) == []


# ---------------- avail_added_removed_Str ----------------

class TestAvailAddedRemovedStr:

    def test_empty_previous_returns_empty(self):
        # with no history, the function refuses to emit (bootstrap case)
        out = mon.avail_added_removed_Str({}, {'a.b.c.d': 'available'})
        assert out == ''

    def test_empty_new_returns_empty(self):
        out = mon.avail_added_removed_Str({'a.b.c.d': 'available'}, {})
        assert out == ''

    def test_added_fqn(self):
        prev = {'a.b.c.d': 'available'}
        new = {'a.b.c.d': 'available', 'a.b.c.e': 'low'}
        out = mon.avail_added_removed_Str(prev, new)
        assert out == '+ a.b.c.e\n'

    def test_removed_fqn(self):
        prev = {'a.b.c.d': 'available', 'a.b.c.e': 'low'}
        new = {'a.b.c.d': 'available'}
        out = mon.avail_added_removed_Str(prev, new)
        assert out == '- a.b.c.e\n'

    def test_added_and_removed_both_present(self):
        prev = {'a.b.c.d': 'available'}
        new = {'a.b.c.e': 'available'}
        out = mon.avail_added_removed_Str(prev, new)
        # added is emitted before removed
        assert '+ a.b.c.e\n' in out
        assert '- a.b.c.d\n' in out
        assert out.index('+') < out.index('-')

    def test_pre_and_post_str_wrap_each_line(self):
        prev = {'a.b.c.d': 'available'}
        new = {'a.b.c.d': 'available', 'a.b.c.e': 'low'}
        out = mon.avail_added_removed_Str(prev, new, preStr='[', postStr=']')
        assert out == '[+ a.b.c.e]\n'

    def test_compression_groups_added_fqns(self):
        prev = {'a.b.c.d': 'available'}
        new = {'a.b.c.d': 'available',
               'a.b.c.e': 'low', 'a.b.c.f': 'low'}
        out = mon.avail_added_removed_Str(prev, new)
        assert out == '+ a.b.c.(e|f)\n'

    def test_no_changes_returns_empty(self):
        d = {'a.b.c.d': 'available'}
        assert mon.avail_added_removed_Str(d, dict(d)) == ''


# ---------------- avail_changed_Str ----------------

class TestAvailChangedStr:

    def test_empty_previous_returns_empty(self):
        out = mon.avail_changed_Str({}, {'a.b.c.gra': 'available'},
                                    r'a\.b\.c')
        assert out == ''

    def test_new_available_matching_regex_emits_O(self):
        # fqn newly appears and is available
        out = mon.avail_changed_Str({'other.x.rbx': 'unavailable'},
                                    {'other.x.rbx': 'unavailable',
                                     '24sk40.foo.gra': 'low'},
                                    r'24sk40')
        assert out == 'O 24sk40.foo.gra\n'

    def test_became_available_emits_O(self):
        # fqn existed, was unavailable, now available
        out = mon.avail_changed_Str({'24sk40.foo.gra': 'unavailable'},
                                    {'24sk40.foo.gra': 'low'},
                                    r'24sk40')
        assert out == 'O 24sk40.foo.gra\n'

    def test_regex_filter_excludes_non_matching(self):
        # same transition but regex doesn't match
        out = mon.avail_changed_Str({'24sk40.foo.gra': 'unavailable'},
                                    {'24sk40.foo.gra': 'low'},
                                    r'does-not-match')
        assert out == ''

    def test_still_available_no_output(self):
        out = mon.avail_changed_Str({'24sk40.foo.gra': 'low'},
                                    {'24sk40.foo.gra': 'high'},
                                    r'24sk40')
        assert out == ''

    def test_pre_and_post_str(self):
        out = mon.avail_changed_Str({'24sk40.foo.gra': 'unavailable'},
                                    {'24sk40.foo.gra': 'low'},
                                    r'24sk40', preStr='[', postStr=']')
        assert out == '[O 24sk40.foo.gra]\n'


# ---------------- catalog_added_removed_Str ----------------

class TestCatalogAddedRemovedStr:

    def _p(self, fqn):
        return {'fqn': fqn}

    def test_no_previous_returns_empty(self):
        out = mon.catalog_added_removed_Str([], [self._p('a.b.c.d')])
        assert out == ''

    def test_added_plan(self):
        prev = [self._p('a.b.c.d')]
        new = [self._p('a.b.c.d'), self._p('a.b.c.e')]
        out = mon.catalog_added_removed_Str(prev, new)
        assert out == '+ a.b.c.e\n'

    def test_removed_plan(self):
        prev = [self._p('a.b.c.d'), self._p('a.b.c.e')]
        new = [self._p('a.b.c.d')]
        out = mon.catalog_added_removed_Str(prev, new)
        assert out == '- a.b.c.e\n'

    def test_compression_of_added(self):
        prev = [self._p('a.b.c.d')]
        new = [self._p('a.b.c.d'), self._p('a.b.c.e'), self._p('a.b.c.f')]
        out = mon.catalog_added_removed_Str(prev, new)
        assert out == '+ a.b.c.(e|f)\n'

    def test_pre_post_str(self):
        prev = [self._p('a.b.c.d')]
        new = [self._p('a.b.c.d'), self._p('a.b.c.e')]
        out = mon.catalog_added_removed_Str(prev, new, '<li>', '</li>')
        assert out == '<li>+ a.b.c.e</li>\n'

    def test_no_changes_returns_empty(self):
        prev = [self._p('a.b.c.d')]
        new = [self._p('a.b.c.d')]
        assert mon.catalog_added_removed_Str(prev, new) == ''
