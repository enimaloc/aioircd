import os
import unittest
import trio
from trio.testing import open_stream_to_socket_listener

os.setenv('HOST', 'ip6-localhost')
os.setenv('ADDR', '::1')
os.setenv('PORT', '6667')
os.setenv('PASS', 'youwillneverguess')
os.setenv('LOGLEVEL', 'WARNING')
import aioircd


class TestProtocol(unittest.TestCase):
    def test_bigfattest(self):

        async def test_case():



        async def run():
            server = Server(ADDR, PORT, PASS)

            aioircd.servlocal.set(ServLocal(server.host, server.pwd, {}, {}))
            listeners = await nursery.start(serve_tcp, handler, 0)
            client_stream = await open_stream_to_socket_listener(listeners[0])

        trio.run(run)


if __name__ == '__main__':
    logging.basicConfig(level="WARNING")
    unittest.main()
