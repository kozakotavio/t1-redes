import unittest

from http_protocol import (
    BadRequestError,
    ClientDisconnected,
    build_response,
    parse_request,
    receive_request_head,
)


class FakeSocket:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def recv(self, _size):
        return self.chunks.pop(0) if self.chunks else b""


class ReceiveRequestHeadTests(unittest.TestCase):
    def test_recebe_cabecalho_fragmentado(self):
        fake = FakeSocket([b"GET / HTTP/1.1\r\nHo", b"st: teste\r\n\r\n"])

        head, leftover = receive_request_head(fake)

        self.assertEqual(head, b"GET / HTTP/1.1\r\nHost: teste")
        self.assertEqual(leftover, b"")

    def test_preserva_inicio_da_proxima_requisicao(self):
        fake = FakeSocket(
            [b"GET / HTTP/1.1\r\nHost: teste\r\n\r\nGET /dois HTTP/1.1\r\n"]
        )

        _head, leftover = receive_request_head(fake)

        self.assertEqual(leftover, b"GET /dois HTTP/1.1\r\n")

    def test_rejeita_conexao_encerrada_antes_do_terminador(self):
        with self.assertRaises(BadRequestError):
            receive_request_head(FakeSocket([b"GET / HTTP/1.1\r\n"]))

    def test_cliente_fecha_conexao_ociosa_sem_erro_http(self):
        with self.assertRaises(ClientDisconnected):
            receive_request_head(FakeSocket([]))


class ParseRequestTests(unittest.TestCase):
    def test_interpreta_requisicao_e_normaliza_nomes(self):
        request = parse_request(
            b"GET /index.html HTTP/1.1\r\nHost: exemplo\r\nX-Teste: valor"
        )

        self.assertEqual(request.method, "GET")
        self.assertEqual(request.target, "/index.html")
        self.assertEqual(request.headers["host"], "exemplo")
        self.assertEqual(request.headers["x-teste"], "valor")

    def test_rejeita_linha_de_requisicao_invalida(self):
        with self.assertRaises(BadRequestError):
            parse_request(b"GET /sem-versao\r\nHost: exemplo")

    def test_rejeita_cabecalho_sem_dois_pontos(self):
        with self.assertRaises(BadRequestError):
            parse_request(b"GET / HTTP/1.1\r\nCabecalho quebrado")

    def test_rejeita_versao_diferente(self):
        with self.assertRaises(BadRequestError):
            parse_request(b"GET / HTTP/1.0\r\nHost: exemplo")

    def test_rejeita_host_ausente_ou_duplicado(self):
        for head in (
            b"GET / HTTP/1.1",
            b"GET / HTTP/1.1\r\nHost: primeiro\r\nHost: segundo",
        ):
            with self.subTest(head=head):
                with self.assertRaises(BadRequestError):
                    parse_request(head)


class BuildResponseTests(unittest.TestCase):
    def test_head_mantem_content_length_sem_corpo(self):
        response = build_response(
            200,
            b"conteudo",
            "text/plain",
            include_body=False,
        )

        head, body = response.split(b"\r\n\r\n", 1)
        self.assertIn(b"Content-Length: 8", head)
        self.assertIn(b"Server: Grupo7", head)
        self.assertIn(b"Connection: keep-alive", head)
        self.assertEqual(body, b"")

    def test_connection_close_e_declarado_quando_solicitado(self):
        response = build_response(200, b"ok", "text/plain", close_connection=True)

        self.assertIn(b"Connection: close\r\n", response)


if __name__ == "__main__":
    unittest.main()
