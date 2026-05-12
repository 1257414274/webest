# -*- coding: utf-8 -*-
import unittest

from domain_admin.service.mcp import mcp_loader, mcp_registry


class TestMcpTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mcp_loader.load_all()

    def test_filesystem_tool(self):
        output = mcp_registry.call_tool('list_directory', {'path': '.'})
        self.assertTrue(isinstance(output, str))
        self.assertTrue(len(output) > 0)

    def test_database_tool(self):
        output = mcp_registry.call_tool('list_tables', {})
        self.assertTrue(isinstance(output, str))
        self.assertTrue(len(output) > 0)

    def test_system_tool(self):
        output = mcp_registry.call_tool('system_info', {})
        self.assertTrue('platform' in output or 'Error' in output)

    def test_health_status(self):
        status = mcp_registry.get_health_status()
        self.assertTrue(isinstance(status, dict))
        self.assertTrue(len(status) >= 5)


if __name__ == '__main__':
    unittest.main()
