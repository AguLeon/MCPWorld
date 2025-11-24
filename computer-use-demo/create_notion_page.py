import asyncio
import sys
import os

sys.path.insert(0, '/workspace/computer-use-demo')
from computer_use_demo.mcpclient import MCPClient

async def create_page():
    print("Creating MCP Client...")
    client = MCPClient()
    
    try:
        print("Connecting to Notion MCP server...")
        await client.connect_to_server({
            'command': 'npx',
            'args': ['@notionhq/notion-mcp-server'],
            'env': {
                'NOTION_TOKEN': '<test-notion-token>'
            }
        })
        print("✓ Connected!")
        
        # First, let's see what tools are available
        tools = await client.list_tools()
        print("\nAvailable tools:")
        for tool in tools:
            print(f"  - {tool.name} \t {tool.description} {tool.input_schema}")
        
        # Create a new page with Lorem Ipsum
        print("\nCreating new page with Lorem Ipsum...")
        result = await client.call_tool(
            'API-post-page',
            {
                'parent': {'type': 'page_id', 'page_id': '2b592b2f38bf80298c00f372b497cf04'},
                'properties': {
                    'title': [
                        {
                            'type': 'text',
                            'text': {'content': 'Lorem Ipsum Test Page'}
                        }
                    ]
                },
                'children': [
                    {
                        'object': 'block',
                        'type': 'paragraph',
                        'paragraph': {
                            'rich_text': [
                                {
                                    'type': 'text',
                                    'text': {
                                        'content': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        )
        
        print("\n✓ Page created successfully!")
        print(f"Result: {result.output}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(create_page())
