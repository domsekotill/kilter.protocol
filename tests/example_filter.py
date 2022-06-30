"""
An example filter that reports all messages sent and received through port [::]:1025
"""

from __future__ import annotations

import logging

import trio

from kilter.protocol import messages
from kilter.protocol.buffer import SimpleBuffer
from kilter.protocol.core import FilterProtocol
from kilter.protocol.core import Unimplemented


async def server() -> None:
	"""
	Open port 1025 on all interfaces; start listeners for each socket created
	"""
	async with trio.open_nursery() as nursery:
		for lnr in await trio.open_tcp_listeners(1025):
			nursery.start_soon(listen, lnr, nursery)


async def listen(lnr: trio.SocketListener, nursery: trio.Nursery) -> None:
	"""
	Listen for and accept client MTA connections
	"""
	async with lnr:
		while 1:
			nursery.start_soon(process_client, await lnr.accept(), nursery)


async def process_client(client: trio.SocketStream, nursery: trio.Nursery) -> None:
	"""
	Log an MTA's messages and queue appropriate responses
	"""
	logging.info(f"Peer connected: {client.socket.getpeername()}")

	buf = SimpleBuffer(2**20)
	proto = FilterProtocol()
	send_channel, recv_channel = trio.open_memory_channel[messages.Message](4)
	nursery.start_soon(client_sender, recv_channel, client, proto)

	async with client:
		while 1:
			data = await client.receive_some(buf.available)
			if data == b"":
				break
			buf[:] = data
			for message in proto.read_from(buf):
				logging.info(f"RECEIVED {message!r}")
				match message:
					case messages.Negotiate():
						message.protocol_flags = 0
						await send_channel.send(message)
					case messages.Macro() | messages.Abort() | messages.Close():
						continue
					case messages.Connect() | messages.Helo() | messages.EnvelopeFrom() | \
						messages.EnvelopeRecipient() | messages.Data() | \
						messages.Unknown() | messages.Header() | messages.EndOfHeaders() | \
						messages.Body() | messages.EndOfMessage():
						await send_channel.send(messages.Continue())
					case Unimplemented():
						logging.warning(f"don't know how to respond to {message!r}, send Continue")
						await send_channel.send(messages.Continue())
					case _:
						logging.warning(f"don't know how to respond to {message!r}")


async def client_sender(
	channel: trio.MemoryReceiveChannel[messages.Message],
	client: trio.SocketStream,
	proto: FilterProtocol,
) -> None:
	"""
	Pack queued, outgoing messages and copy them to the client socket's buffer
	"""
	buf = SimpleBuffer(1024)
	async with channel:
		async for message in channel:
			proto.write_to(buf, message)
			await client.send_all(buf[:])
			del buf[:]
			logging.info(f"SENT {message!r}")


if __name__ == "__main__":
	logging.basicConfig(level=logging.DEBUG)
	trio.run(server)
