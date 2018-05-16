import asyncio
import sys
import click
from .client import Client

def main():
    client = Client(asyncio.get_event_loop())
    client.run()
