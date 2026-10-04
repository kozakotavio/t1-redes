"""Servidor HTTP/1.1 didatico construido diretamente sobre sockets TCP."""

import argparse
import logging
import socket
import threading
from pathlib import Path
from typing import Optional, Tuple

from file_service import (
    ForbiddenPathError,
    InvalidTargetError,
    StaticFileNotFoundError,
    resolve_target,
)
from http_protocol import (
    BadRequestError,
    ClientDisconnected,
    HTTPRequest,
    build_response,
    make_error_body,
    parse_request,
    receive_request_head,
)


LOG = logging.getLogger("t1-redes")
ERROR_CONTENT_TYPE = "text/html; charset=utf-8"


class HTTPServer:
    """Servidor concorrente: uma thread por conexao TCP persistente."""

    def __init__(
        self,
        host: str,
        port: int,
        root: Path,
        *,
        client_timeout: float = 5.0,
    ) -> None:
        self.host = host
        self.port = port
        self.root = root.resolve()
        self.client_timeout = client_timeout
        self._shutdown = threading.Event()
        self._server_socket: Optional[socket.socket] = None
        self._threads = set()
        self._threads_lock = threading.Lock()
        self.address: Optional[Tuple[str, int]] = None

    def serve_forever(self, ready_event: Optional[threading.Event] = None) -> None:
        """Aceita conexoes ate ``shutdown`` ser chamado."""

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket = server_socket
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen()
        server_socket.settimeout(0.25)
        bound_host, bound_port = server_socket.getsockname()[:2]
        self.address = (bound_host, bound_port)

        LOG.info("Servidor ouvindo em %s:%s; raiz=%s", bound_host, bound_port, self.root)
        if ready_event is not None:
            ready_event.set()

        try:
            while not self._shutdown.is_set():
                try:
                    client_socket, client_address = server_socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self._shutdown.is_set():
                        break
                    raise

                worker = threading.Thread(
                    target=self._serve_client,
                    args=(client_socket, client_address),
                    daemon=True,
                    name=f"cliente-{client_address[0]}:{client_address[1]}",
                )
                with self._threads_lock:
                    self._threads.add(worker)
                worker.start()
        finally:
            try:
                server_socket.close()
            finally:
                self._server_socket = None
            self._join_workers()

    def shutdown(self) -> None:
        """Solicita o encerramento do laco de accept."""

        self._shutdown.set()
        # A thread de serve_forever pode limpar o atributo entre a verificacao
        # e o close. Guardar a referencia local evita essa corrida.
        server_socket = self._server_socket
        if server_socket is not None:
            try:
                server_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                server_socket.close()
            except OSError:
                pass

    def _serve_client(self, client_socket: socket.socket, client_address) -> None:
        pending = b""
        try:
            client_socket.settimeout(self.client_timeout)
            while not self._shutdown.is_set():
                try:
                    head, pending = receive_request_head(client_socket, pending)
                    request = parse_request(head)
                except ClientDisconnected:
                    break
                except socket.timeout:
                    LOG.info("%s:%s conexao ociosa encerrada", *client_address[:2])
                    break
                except BadRequestError as exc:
                    client_socket.sendall(_error_response(400, close_connection=True))
                    LOG.warning("%s:%s requisicao invalida: %s", *client_address[:2], exc)
                    break

                if _has_unsupported_request_body(request):
                    client_socket.sendall(_error_response(400, close_connection=True))
                    LOG.warning("%s:%s corpo de requisicao nao suportado", *client_address[:2])
                    break

                close_connection = (
                    _client_requests_close(request) or request.method not in {"GET", "HEAD"}
                )
                status_code, response = self._response_for(request, close_connection)
                client_socket.sendall(response)
                LOG.info(
                    '%s:%s "%s %s" %s conexao=%s sobra=%s',
                    client_address[0],
                    client_address[1],
                    request.method,
                    request.target,
                    status_code,
                    "close" if close_connection else "keep-alive",
                    len(pending),
                )
                if close_connection:
                    break
        except (ConnectionError, OSError) as exc:
            LOG.warning("%s:%s conexao encerrada: %s", *client_address[:2], exc)
        finally:
            try:
                client_socket.close()
            finally:
                current = threading.current_thread()
                with self._threads_lock:
                    self._threads.discard(current)

    def _response_for(self, request: HTTPRequest, close_connection: bool) -> Tuple[int, bytes]:
        if request.method not in {"GET", "HEAD"}:
            return 405, _error_response(
                405,
                close_connection=close_connection,
                extra_headers=(("Allow", "GET, HEAD"),),
            )

        include_body = request.method == "GET"
        try:
            file_path, content_type = resolve_target(self.root, request.target)
            body = file_path.read_bytes()
            return 200, build_response(
                200,
                body,
                content_type,
                include_body=include_body,
                close_connection=close_connection,
            )
        except InvalidTargetError:
            return 400, _error_response(
                400, include_body=include_body, close_connection=close_connection
            )
        except ForbiddenPathError:
            return 403, _error_response(
                403, include_body=include_body, close_connection=close_connection
            )
        except StaticFileNotFoundError:
            return 404, _error_response(
                404, include_body=include_body, close_connection=close_connection
            )
        except PermissionError:
            return 403, _error_response(
                403, include_body=include_body, close_connection=close_connection
            )

    def _join_workers(self) -> None:
        with self._threads_lock:
            workers = list(self._threads)
        for worker in workers:
            worker.join(timeout=self.client_timeout + 0.5)


def _error_response(
    status_code: int,
    *,
    include_body: bool = True,
    close_connection: bool = False,
    extra_headers=(),
) -> bytes:
    body = make_error_body(status_code)
    return build_response(
        status_code,
        body,
        ERROR_CONTENT_TYPE,
        include_body=include_body,
        close_connection=close_connection,
        extra_headers=extra_headers,
    )


def _client_requests_close(request: HTTPRequest) -> bool:
    """Connection e uma lista de tokens sem diferenca entre maiusculas/minusculas."""

    return any(
        token.strip().lower() == "close"
        for token in request.headers.get("connection", "").split(",")
    )


def _has_unsupported_request_body(request: HTTPRequest) -> bool:
    """Evita interpretar bytes de um corpo como a proxima requisicao."""

    if request.method not in {"GET", "HEAD"}:
        return False  # 405 e fechamento imediato, sem tentar ler o corpo.
    if "transfer-encoding" in request.headers:
        return True
    length = request.headers.get("content-length")
    return length is not None and (not length.isdecimal() or int(length) != 0)


def valid_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("a porta deve ser um numero inteiro") from exc
    if not 1024 < port <= 65535:
        raise argparse.ArgumentTypeError("use uma porta entre 1025 e 65535")
    return port


def existing_directory(value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError("o diretorio raiz nao existe")
    return path


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Servidor HTTP/1.1 didatico sobre sockets TCP"
    )
    parser.add_argument("--port", required=True, type=valid_port, help="porta acima de 1024")
    parser.add_argument("--root", required=True, type=existing_directory, help="diretorio raiz")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
    )
    server = HTTPServer("0.0.0.0", args.port, args.root)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Encerramento solicitado")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
