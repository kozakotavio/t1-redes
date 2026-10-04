"""Cliente TCP simples para comparar C1 e C2 entre maquinas distintas.

Uso: python tools/measure_connections.py --host 192.168.0.10 --port 8080 --mode c1
Execute C1 e C2 separadamente, com captura Wireshark ativa em cada cenario.
"""

import argparse
import socket
import time


def read_response(client, pending=b""):
    """Le exatamente uma resposta usando Content-Length e devolve a sobra."""

    buffer = bytearray(pending)
    while b"\r\n\r\n" not in buffer:
        chunk = client.recv(4096)
        if not chunk:
            raise RuntimeError("Conexao terminou antes dos cabecalhos HTTP")
        buffer.extend(chunk)

    head_end = buffer.index(b"\r\n\r\n") + 4
    lines = bytes(buffer[: head_end - 4]).decode("iso-8859-1").split("\r\n")
    status = lines[0]
    headers = {}
    for line in lines[1:]:
        if ":" not in line:
            raise RuntimeError("Cabecalho de resposta invalido")
        name, value = line.split(":", 1)
        headers[name.lower()] = value.strip()

    try:
        body_length = int(headers["content-length"])
    except (KeyError, ValueError) as exc:
        raise RuntimeError("Resposta sem Content-Length valido") from exc
    end = head_end + body_length
    while len(buffer) < end:
        chunk = client.recv(4096)
        if not chunk:
            raise RuntimeError("Conexao terminou antes do corpo completo")
        buffer.extend(chunk)

    return status, headers, bytes(buffer[head_end:end]), bytes(buffer[end:])


def make_request(host, port, path, close):
    connection = "close" if close else "keep-alive"
    return (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Connection: {connection}\r\n"
        "\r\n"
    ).encode("ascii")


def run_scenario(host, port, path, mode, count):
    """C1 abre N sockets; C2 reutiliza um socket para as N respostas."""

    first_body = None
    started = time.perf_counter()
    shared_client = None
    try:
        if mode == "c2":
            shared_client = socket.create_connection((host, port), timeout=10)
            shared_client.settimeout(10)

        for number in range(1, count + 1):
            client = shared_client
            if mode == "c1":
                client = socket.create_connection((host, port), timeout=10)
                client.settimeout(10)
            try:
                close = mode == "c1" or number == count
                client.sendall(make_request(host, port, path, close))
                status, headers, body, pending = read_response(client)
                if status != "HTTP/1.1 200 OK":
                    raise RuntimeError(f"Requisicao {number}: {status}")
                if pending:
                    raise RuntimeError("Resposta trouxe bytes inesperados apos o corpo")
                expected_connection = "close" if close else "keep-alive"
                if headers.get("connection", "").lower() != expected_connection:
                    raise RuntimeError(
                        f"Requisicao {number}: Connection diferente de {expected_connection}"
                    )
                if first_body is None:
                    first_body = body
                elif body != first_body:
                    raise RuntimeError("As respostas nao tem o mesmo corpo")
                print(f"{number:02d}: {status}; {len(body)} bytes; {expected_connection}")
            finally:
                if mode == "c1":
                    client.close()
    finally:
        if shared_client is not None:
            shared_client.close()

    elapsed = time.perf_counter() - started
    connections = count if mode == "c1" else 1
    print(f"Cenario {mode.upper()}: {count} requisicoes, {connections} conexao(oes) TCP")
    print(f"Tempo do cliente: {elapsed:.6f} s")
    print("Pacotes, bytes na rede e handshakes completos: medir no Wireshark.")


def main():
    parser = argparse.ArgumentParser(description="Comparar C1 e C2 usando sockets TCP")
    parser.add_argument("--host", required=True, help="IPv4 do servidor (ou nome resolvivel)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--path", default="/leia-me.txt")
    parser.add_argument("--mode", choices=("c1", "c2"), required=True)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    if not 1024 < args.port <= 65535:
        parser.error("--port deve ficar entre 1025 e 65535")
    if not args.path.startswith("/") or " " in args.path:
        parser.error("--path deve comecar por / e usar percent-encoding para espacos")
    if args.count < 1:
        parser.error("--count deve ser positivo")
    run_scenario(args.host, args.port, args.path, args.mode, args.count)


if __name__ == "__main__":
    main()
