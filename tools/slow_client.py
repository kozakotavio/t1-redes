"""Envia uma requisicao em duas partes para testar concorrencia do servidor."""

import argparse
import socket
import time


def main():
    parser = argparse.ArgumentParser(description="Cliente TCP lento para teste de concorrencia")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--delay", type=float, default=3.0)
    args = parser.parse_args()
    if args.delay < 0 or args.delay >= 5:
        parser.error("--delay deve ficar entre 0 e menos de 5 segundos")

    with socket.create_connection((args.host, args.port), timeout=10) as client:
        client.settimeout(10)
        client.sendall(b"GET /leia-me.txt HTTP/1.1\r\nHost: teste\r\n")
        print(f"Cabecalho parcial enviado; esperando {args.delay:.1f} s...")
        time.sleep(args.delay)
        client.sendall(b"Connection: close\r\n\r\n")
        response = bytearray()
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
    print(response.decode("iso-8859-1", errors="replace"))


if __name__ == "__main__":
    main()
