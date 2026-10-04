import contextlib
import io
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from server import HTTPServer
from tools.measure_connections import run_scenario


def split_response(response):
    head, body = response.split(b"\r\n\r\n", 1)
    lines = head.decode("iso-8859-1").split("\r\n")
    headers = {}
    for line in lines[1:]:
        name, value = line.split(":", 1)
        headers[name.lower()] = value.strip()
    return lines[0], headers, body


def read_response(client, pending=b"", *, expect_body=True):
    """Le uma resposta sem esperar o fechamento da conexao persistente."""

    buffer = bytearray(pending)
    while b"\r\n\r\n" not in buffer:
        chunk = client.recv(4096)
        if not chunk:
            raise AssertionError("Conexao fechou antes dos cabecalhos da resposta")
        buffer.extend(chunk)

    head_end = buffer.index(b"\r\n\r\n") + 4
    _status, headers, _body = split_response(bytes(buffer[:head_end]))
    end = head_end + (int(headers["content-length"]) if expect_body else 0)
    while len(buffer) < end:
        chunk = client.recv(4096)
        if not chunk:
            raise AssertionError("Conexao fechou antes do corpo completo")
        buffer.extend(chunk)
    return bytes(buffer[:end]), bytes(buffer[end:])


class RunningServer:
    def __init__(self, root, timeout=1.0):
        self.server = HTTPServer("127.0.0.1", 0, root, client_timeout=timeout)
        self.ready = threading.Event()
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            args=(self.ready,),
            daemon=True,
        )

    def __enter__(self):
        self.thread.start()
        if not self.ready.wait(timeout=2):
            raise RuntimeError("Servidor nao iniciou")
        return self

    def __exit__(self, _type, _value, _traceback):
        self.server.shutdown()
        self.thread.join(timeout=3)

    @property
    def address(self):
        return self.server.address

    def request(self, raw_request):
        with socket.create_connection(self.address, timeout=2) as client:
            client.sendall(raw_request)
            response, _leftover = read_response(
                client, expect_body=not raw_request.startswith(b"HEAD ")
            )
            return response


class ServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "index.html").write_text("ola rede", encoding="utf-8")
        (self.root / "imagem.png").write_bytes(b"\x89PNG\r\n\x1a\nconteudo")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_get_e_head_tem_os_mesmos_cabecalhos_de_conteudo(self):
        with RunningServer(self.root) as running:
            get_response = running.request(b"GET / HTTP/1.1\r\nHost: teste\r\n\r\n")
            head_response = running.request(b"HEAD / HTTP/1.1\r\nHost: teste\r\n\r\n")

        get_status, get_headers, get_body = split_response(get_response)
        head_status, head_headers, head_body = split_response(head_response)
        self.assertEqual(get_status, "HTTP/1.1 200 OK")
        self.assertEqual(head_status, "HTTP/1.1 200 OK")
        self.assertEqual(get_headers["content-length"], head_headers["content-length"])
        self.assertEqual(get_headers["content-type"], head_headers["content-type"])
        self.assertEqual(get_body, b"ola rede")
        self.assertEqual(head_body, b"")

    def test_png_tem_content_type_correto(self):
        with RunningServer(self.root) as running:
            response = running.request(
                b"GET /imagem.png HTTP/1.1\r\nHost: teste\r\n\r\n"
            )

        _status, headers, _body = split_response(response)
        self.assertEqual(headers["content-type"], "image/png")

    def test_status_obrigatorios(self):
        cases = (
            (b"GET * HTTP/1.1\r\nHost: teste\r\n\r\n", 400),
            (b"GET /../segredo HTTP/1.1\r\nHost: teste\r\n\r\n", 403),
            (b"GET /ausente HTTP/1.1\r\nHost: teste\r\n\r\n", 404),
            (b"POST / HTTP/1.1\r\nHost: teste\r\n\r\n", 405),
        )

        with RunningServer(self.root) as running:
            for request, expected_status in cases:
                with self.subTest(status=expected_status):
                    response = running.request(request)
                    status, headers, _body = split_response(response)
                    self.assertTrue(status.startswith(f"HTTP/1.1 {expected_status} "))
                    self.assertEqual(
                        headers["connection"],
                        "close" if expected_status in (400, 405) else "keep-alive",
                    )
                    if expected_status == 405:
                        self.assertEqual(headers["allow"], "GET, HEAD")

    def test_cliente_lento_nao_bloqueia_outro_cliente(self):
        with RunningServer(self.root) as running:
            slow_client = socket.create_connection(running.address, timeout=2)
            slow_client.sendall(b"GET / HTTP/1.1\r\nHost: lento\r\n")
            try:
                start = time.monotonic()
                response = running.request(
                    b"GET / HTTP/1.1\r\nHost: rapido\r\n\r\n"
                )
                elapsed = time.monotonic() - start
            finally:
                slow_client.close()

        status, _headers, _body = split_response(response)
        self.assertEqual(status, "HTTP/1.1 200 OK")
        self.assertLess(elapsed, 0.75)

    def test_shutdown_fecha_socket_mesmo_se_thread_limpar_atributo(self):
        server = HTTPServer("127.0.0.1", 0, self.root)

        class SocketSimulado:
            def __init__(self):
                self.closed = False

            def shutdown(self, _how):
                server._server_socket = None

            def close(self):
                self.closed = True

        socket_simulado = SocketSimulado()
        server._server_socket = socket_simulado

        server.shutdown()

        self.assertTrue(socket_simulado.closed)

    def test_dez_requisicoes_sequenciais_na_mesma_conexao(self):
        with RunningServer(self.root) as running:
            with socket.create_connection(running.address, timeout=2) as client:
                client.settimeout(2)
                for number in range(10):
                    client.sendall(b"GET / HTTP/1.1\r\nHost: teste\r\n\r\n")
                    response, leftover = read_response(client)
                    status, headers, body = split_response(response)
                    self.assertEqual(status, "HTTP/1.1 200 OK")
                    self.assertEqual(headers["connection"], "keep-alive")
                    self.assertEqual(body, b"ola rede")
                    self.assertEqual(leftover, b"", msg=f"resposta {number}")

    def test_requisicoes_agrupadas_no_mesmo_envio(self):
        with RunningServer(self.root) as running:
            with socket.create_connection(running.address, timeout=2) as client:
                client.settimeout(2)
                client.sendall(
                    b"GET / HTTP/1.1\r\nHost: teste\r\n\r\n"
                    b"GET /imagem.png HTTP/1.1\r\nHost: teste\r\n\r\n"
                )
                first, pending = read_response(client)
                second, pending = read_response(client, pending)

        self.assertEqual(split_response(first)[2], b"ola rede")
        self.assertEqual(split_response(second)[1]["content-type"], "image/png")
        self.assertEqual(pending, b"")

    def test_connection_close_devolve_cabecalho_e_fecha_socket(self):
        with RunningServer(self.root) as running:
            with socket.create_connection(running.address, timeout=2) as client:
                client.settimeout(2)
                client.sendall(
                    b"GET / HTTP/1.1\r\nHost: teste\r\nConnection: CLOSE\r\n\r\n"
                )
                response, _pending = read_response(client)
                self.assertEqual(split_response(response)[1]["connection"], "close")
                self.assertEqual(client.recv(1), b"")

    def test_timeout_fecha_conexao_ociosa_sem_resposta_extra(self):
        with RunningServer(self.root, timeout=0.25) as running:
            with socket.create_connection(running.address, timeout=2) as client:
                client.settimeout(2)
                client.sendall(b"GET / HTTP/1.1\r\nHost: teste\r\n\r\n")
                response, _pending = read_response(client)
                self.assertEqual(split_response(response)[1]["connection"], "keep-alive")
                self.assertEqual(client.recv(1), b"")

    def test_corpo_nao_suportado_retorna_400_e_fecha(self):
        with RunningServer(self.root) as running:
            response = running.request(
                b"GET / HTTP/1.1\r\nHost: teste\r\nContent-Length: 3\r\n\r\nabc"
            )

        status, headers, _body = split_response(response)
        self.assertEqual(status, "HTTP/1.1 400 Bad Request")
        self.assertEqual(headers["connection"], "close")

    def test_cliente_de_medicao_c1_e_c2(self):
        with RunningServer(self.root) as running:
            host, port = running.address
            for mode, expected_connections in (("c1", 3), ("c2", 1)):
                with self.subTest(mode=mode):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        run_scenario(host, port, "/", mode, 3)
                    self.assertIn("3 requisicoes", output.getvalue())
                    self.assertIn(
                        f"{expected_connections} conexao(oes)", output.getvalue()
                    )


if __name__ == "__main__":
    unittest.main()
