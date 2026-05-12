# -*- coding: utf-8 -*-
import unittest

from domain_admin.service.mcp import mcp_loader, mcp_registry


class TestMcpRegistry(unittest.TestCase):
    def test_load_and_list_tools(self):
        mcp_loader.load_all()
        tools = mcp_registry.list_tools()
        self.assertTrue(len(tools) >= 5)

        tool_names = {t['name'] for t in tools}
        self.assertIn('read_file', tool_names)
        self.assertIn('execute_query', tool_names)
        self.assertIn('fetch_url', tool_names)

    def test_get_anthropic_tools_schema(self):
        mcp_loader.load_all()
        tools = mcp_registry.get_anthropic_tools()
        self.assertTrue(len(tools) >= 5)
        self.assertIn('name', tools[0])
        self.assertIn('description', tools[0])
        self.assertIn('input_schema', tools[0])


if __name__ == '__main__':
    unittest.main()
