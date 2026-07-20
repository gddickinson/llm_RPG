"""data_loader: merging + defensive skip of file-sync conflict copies."""

import json
import os
import tempfile
import unittest

from items.data_loader import load_data_dir, DataError, _SYNC_DUP


class TestSyncDuplicateSkip(unittest.TestCase):
    def _dir(self, files):
        d = tempfile.mkdtemp(prefix="llmrpg_dl_")
        sub = os.path.join(d, "npcs")
        os.makedirs(sub)
        for name, obj in files.items():
            with open(os.path.join(sub, name), "w") as f:
                json.dump(obj, f)
        return d

    def test_sync_conflict_copies_are_skipped(self):
        # a real file + iCloud/Dropbox conflict copies with the SAME id
        root = self._dir({
            "cast.json": {"king": {"name": "K"}},
            "cast 2.json": {"king": {"name": "dup"}},        # " 2"
            "cast copy.json": {"king": {"name": "dup"}},     # " copy"
            "cast copy 3.json": {"king": {"name": "dup"}},   # " copy 3"
        })
        merged = load_data_dir("npcs", root=root)   # must NOT raise a dup error
        self.assertEqual(list(merged.keys()), ["king"])
        self.assertEqual(merged["king"]["name"], "K", "the REAL file wins")

    def test_a_genuine_duplicate_still_errors(self):
        # two non-copy files sharing an id is a real authoring bug — still caught
        root = self._dir({
            "a.json": {"king": {}},
            "b.json": {"king": {}},
        })
        with self.assertRaises(DataError):
            load_data_dir("npcs", root=root)

    def test_pattern_matches_copies_not_real_names(self):
        for stem in ("monsters 2", "quests copy", "cast Copy 4", "npcs 10"):
            self.assertRegex(stem, _SYNC_DUP)
        for stem in ("monsters", "bloodstone_castle", "idle2", "spells"):
            self.assertNotRegex(stem, _SYNC_DUP)


if __name__ == "__main__":
    unittest.main()
