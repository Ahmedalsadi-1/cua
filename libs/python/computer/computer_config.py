"""
Configuration for the Cua Computer SDK.
"""

import os
from computer import Computer

def get_computer(
    os_type: str = "linux",
    provider_type: str = "docker",
    name: str = "cua-sandbox",
) -> Computer:
    """
    Initializes and returns a Computer instance with the specified configuration.
    """
    return Computer(
        os_type=os_type,
        provider_type=provider_type,
        name=name,
    )

async def main():
    """
    Example of how to use the get_computer function to initialize a Computer.
    """
    computer = get_computer()
    print(f"Computer initialized with the following configuration:")
    print(f"  OS Type: {computer.os_type}")
    print(f"  Provider Type: {computer.provider_type}")
    print(f"  Name: {computer.name}")

    # To run this, you would need to have the computer environment set up.
    # try:
    #     await computer.run()
    #     # You can now use the computer interface to control the sandbox
    #     # await computer.interface.screenshot()
    #     # await computer.interface.type_text("Hello, world!")
    # finally:
    #     await computer.close()
    pass

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
