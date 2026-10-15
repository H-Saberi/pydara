import socket
import pytest

@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch):
    original_connect = socket.socket.connect
    original_socketpair = socket.socketpair

    def local_socketpair(*args, **kwargs):
        # Windows asyncio uses socketpair's loopback connection internally.
        # Permit only this synchronous stdlib operation, not arbitrary connects.
        with monkeypatch.context() as pair_patch:
            pair_patch.setattr(socket.socket, "connect", original_connect)
            return original_socketpair(*args, **kwargs)

    def fail(*args, **kwargs):
        raise AssertionError("Unit tests must never contact a real network.")
    monkeypatch.setattr(socket.socket, "connect", fail)
    monkeypatch.setattr(socket, "socketpair", local_socketpair)
