import os
import unittest
import trio
from operator import attrgetter
from trio.testing import open_stream_to_socket_listener

os.setenv('HOST', 'ip6-localhost')
os.setenv('ADDR', '::1')
os.setenv('PORT', '6667')
os.setenv('PASS', 'youwillneverguess')
os.setenv('LOGLEVEL', 'WARNING')
import aioircd
from aioircd.states import *

async def waitfor(predicate, sentinel=True, timeout=1):
    with trio.move_on_after(timeout):
        while predicate() != sentinel:
            await trio.sleep(0.01)
        return True
    return False


class TestProtocol(unittest.TestCase):
    def test_bigfattest(self):
      async def run():
        server = Server(ADDR, PORT, PASS)
        servlocal = ServLocal(server.host, server.pwd, {}, {})
        aioircd.servlocal.set(servlocal)
        listeners = await nursery.start(serve_tcp, handler, 0)
        buffer = b''
        
        self.assertFalse(servlocal.users)
        bob_sock = await open_stream_to_socket_listener(listeners[0])
        self.assertTrue(await waitfor(lambda: bool(servlocal.users)))

        bob = next(servlocal.users)
        self.assertEqual(type(bob.state), PasswordState)
        with trio.move_on_after(0.1):
            buffer = await bob_sock.receive_some()
        self.assertFalse(buffer)

        await bob_sock.send_all(b"PASS youwillneverguess\r\n")
        self.assertEqual(type(bob.state), ConnectedState)
        with trio.move_on_after(0.1):
            buffer = await bob_sock.receive_some()
        self.assertFalse(buffer)

        await bob_sock.send_all(b"NICK bob\r\nUSER bob 0 * :Capucine\r\n")
        self.assertEqual(type(bob.state), RegisteredState)
        with trio.move_on_after(0.1):
            buffer = await bob_sock.receive_some()
        self.assertEqual(buffer, b''.join([
            b":ip6-localhost 001 bob :Welcome to the Internet Relay Network bob",
            b":ip6-localhost 002 bob :Your host is ip6-localhost",
            b":ip6-localhost 003 bob :The server was created at some point",
            f":ip6-localhost 004 bob :aioircd {aioircd.__version__}  ".encode(),
        ]))

        joe_sock = await open_stream_to_socket_listener(listeners[0])
        await joe_sock.send_all(
            b"PASS youwillneverguess\r\n"
            b"NICK joe\r\n"
            b"USER joe 0 * :Stanissiav\r\n"
        )
        with trio.move_on_after(0.1):
            await joe_sock.receive_some()
        joe = servlocal.users['joe']

        mat_sock = await open_stream_to_socket_listener(listeners[0])
        await mat_sock.send_all(
            b"PASS youwillneverguess\r\n"
            b"NICK mat\r\n"
            b"USER mat 0 * :Tomate\r\n"
        )
        with trio.move_on_after(0.1):
            await mat_sock.receive_some()
        mat = servlocal.users['mat']

        self.assertFalse(servlocal.channels)
        await bob_sock.send_all(b'JOIN #python\r\n')
        with trio.move_on_after(0.1):
            buffer = await bob_sock.receive_some()
            buffer += await bob_sock.receive_some()
            buffer += await bob_sock.receive_some()
        self.assertEqual(buffer, 
            b":bob JOIN #python\r\n"
            b":ip6-localhost 353 bob = #python :\r\n"
            b":ip6-localhost 366 bob #python :End of /NAMES list.\r\n"
        )
        self.assertTrue(servlocal.channels)
        self.assertEqual(next(servlocal.channels).users, {bob})

        await bob.send_all('PART #python\r\n')


      trio.run(run)


if __name__ == '__main__':
    logging.basicConfig(level="WARNING")
    unittest.main()
