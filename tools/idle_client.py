"""Verifica se uma conexao HTTP persistente ociosa fecha apos ~5 segundos."""

import argparse
import socket
import time

from measure_connections import make_request, read_response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    with socket.create_connection((args.host, args.port), timeout=10) as client:
        client.settimeout(10)
        client.sendall(make_request(args.host, args.port, "/leia-me.txt", close=False))
        status, headers, _body, pending = read_response(client)
        if status != "HTTP/1.1 200 OK" or headers.get("connection") != "keep-alive":
            raise RuntimeError("Servidor nao manteve a conexao apos o primeiro GET")
        if pending:
            raise RuntimeError("Bytes inesperados apos a resposta")

        started = time.monotonic()
        if client.recv(1):
            raise RuntimeError("Servidor enviou dados extras durante a ociosidade")
        elapsed = time.monotonic() - started
        print(f"Conexao fechada sem resposta extra apos {elapsed:.2f} s de ociosidade")
        if not 4.0 <= elapsed <= 8.0:
            raise RuntimeError("Timeout observado fora da faixa esperada de ~5 s")


if __name__ == "__main__":
    main()
