#!/usr/bin/env python3
import asyncio

from core.tools.system_tools import list_docker_containers_async

result = asyncio.run(list_docker_containers_async())
print(result)
