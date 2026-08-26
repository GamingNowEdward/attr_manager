"""channel_box tests: setAttr echo parsing plus real MCommandMessage hook
behaviour inside the Maya kernel.
"""

from __future__ import annotations

import unittest

import maya.cmds as cmds
import maya.mel as mel

import support
from core import channel_box


class ParseSetAttrLine(unittest.TestCase):
    CASES = [
        ('setAttr -type double3 "pCube1.color" 1 2 3;', ("pCube1", "color")),
        ('setAttr "-l" 1 {"pCube1.visibility"};', ("pCube1", "visibility")),
        ('setAttr "pCube1.translateX" 5;', ("pCube1", "translateX")),
        ('setAttr -type doubleLinear "pCube1.dist" 2.0;',
         ("pCube1", "dist")),
        ('setAttr "|grp|pCube1.rotateY" 90;', ("|grp|pCube1", "rotateY")),
        ('select -r pCube1;', None),
        ('setAttr ".v" 0;', None),
        ('setAttr "pCube1" 5;', None),
        ('setAttr -l 1;', None),
        ('', None),
    ]

    def test_parse_matrix(self):
        for line, expected in self.CASES:
            with self.subTest(line=line):
                self.assertEqual(channel_box._parse_set_attr_line(line), expected)


class CommandHook(support.MayaTestCase):
    def setUp(self):
        super().setUp()
        channel_box._last_set_attr = None
        channel_box.disable_command_hook()

    def tearDown(self):
        channel_box.disable_command_hook()
        super().tearDown()

    def test_mel_setattr_lock_is_recorded(self):
        cmds.polyCube(name="hookCube")
        channel_box.enable_command_hook()
        mel.eval('setAttr "-l" 1 {"hookCube.visibility"};')
        self.assertEqual(channel_box.get_last_set_attr(),
                         ("hookCube", "visibility"))

    def test_python_cmds_setattr_is_not_recorded(self):
        cmds.polyCube(name="hookCube")
        channel_box.enable_command_hook()
        cmds.setAttr("hookCube.translateX", 5)
        self.assertIsNone(channel_box.get_last_set_attr())

    def test_disabled_hook_records_nothing(self):
        cmds.polyCube(name="hookCube")
        channel_box.enable_command_hook()
        channel_box.disable_command_hook()
        mel.eval('setAttr "-l" 1 {"hookCube.visibility"};')
        self.assertIsNone(channel_box.get_last_set_attr())

    def test_record_set_attr_gated_by_enabled_flag(self):
        channel_box.record_set_attr("a", "b")
        self.assertIsNone(channel_box.get_last_set_attr())

        channel_box.enable_command_hook()
        channel_box.record_set_attr("a", "b")
        self.assertEqual(channel_box.get_last_set_attr(), ("a", "b"))


class UnlockAttr(support.MayaTestCase):
    def test_unlocks_locked_attribute(self):
        cube = cmds.polyCube(name="unCube")[0]
        plug = cube + ".translateX"
        cmds.setAttr(plug, lock=True)
        self.assertTrue(channel_box.unlock_attr(cube, "translateX"))
        self.assertFalse(cmds.getAttr(plug, lock=True))

    def test_already_unlocked_returns_true(self):
        cube = cmds.polyCube(name="unCube")[0]
        self.assertTrue(channel_box.unlock_attr(cube, "translateX"))


class ChannelBoxSelection(support.MayaTestCase):
    def test_without_gui_returns_empty(self):
        nodes, attrs = channel_box.get_channelbox_selection()
        self.assertEqual(nodes, [])
        self.assertEqual(attrs, [])


if __name__ == "__main__":
    unittest.main()
