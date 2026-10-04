"""Parsing e geracao das mensagens HTTP/1.1 usadas pelo servidor.

Este modulo nao usa bibliotecas que implementam um servidor HTTP. Ele trata
diretamente os bytes recebidos pelo socket para deixar explicito que TCP e um
fluxo, e nao uma sequencia de mensagens prontas.
"""

from dataclasses import dataclass
from email.utils import formatdate
from typing import Dict, Iterable, Mapping, Optional, Tuple


HEADER_TERMINATOR = b"\r\n\r\n"
MAX_HEADER_BYTES = 64 * 1024
SERVER_ID = "Grupo7"

STATUS_REASONS = {
    200: "OK",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
}

_TOKEN_CHARS = frozenset(
    "!#$%&'*+-.^_`|~0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
)


class BadRequestError(ValueError):
    """Indica que os bytes recebidos nao formam uma requisicao valida."""


class ClientDisconnected(ConnectionError):
    """O cliente encerrou uma conexao ociosa sem enviar outra requisicao."""


@dataclass(frozen=True)
class HTTPRequest:
    """Representacao minima da parte da requisicao necessaria ao trabalho."""

    method: str
    target: str
    version: str
    headers: Mapping[str, str]


def receive_request_head(
    client_socket,
    initial_data: bytes = b"",
    max_header_bytes: int = MAX_HEADER_BYTES,
) -> Tuple[bytes, bytes]:
    """Le ate o fim dos cabecalhos e devolve ``(cabecalho, sobra)``.

    A sobra e importante porque um unico ``recv`` pode conter o final da
    requisicao atual e o inicio da seguinte na mesma conexao persistente.
    """

    buffer = bytearray(initial_data)

    while True:
        terminator_index = buffer.find(HEADER_TERMINATOR)
        if terminator_index >= 0:
            if terminator_index > max_header_bytes:
                raise BadRequestError("Cabecalho maior que o limite permitido")
            head = bytes(buffer[:terminator_index])
            leftover = bytes(buffer[terminator_index + len(HEADER_TERMINATOR) :])
            return head, leftover

        if len(buffer) > max_header_bytes:
            raise BadRequestError("Cabecalho maior que o limite permitido")

        chunk = client_socket.recv(4096)
        if not chunk:
            if not buffer:
                raise ClientDisconnected()
            raise BadRequestError("Conexao encerrada antes do fim dos cabecalhos")
        buffer.extend(chunk)


def parse_request(head: bytes) -> HTTPRequest:
    """Interpreta a linha de requisicao e os cabecalhos recebidos."""

    try:
        text = head.decode("iso-8859-1")
    except UnicodeDecodeError as exc:  # pragma: no cover - ISO-8859-1 sempre decodifica
        raise BadRequestError("Cabecalho nao pode ser decodificado") from exc

    lines = text.split("\r\n")
    if not lines or not lines[0]:
        raise BadRequestError("Linha de requisicao ausente")

    request_parts = lines[0].split(" ")
    if len(request_parts) != 3 or any(not part for part in request_parts):
        raise BadRequestError("Linha de requisicao invalida")

    method, target, version = request_parts
    if not _is_token(method):
        raise BadRequestError("Metodo invalido")
    if not target.startswith("/"):
        raise BadRequestError("Request-target deve usar a forma origin")
    if version != "HTTP/1.1":
        raise BadRequestError("Somente HTTP/1.1 e aceito")

    headers: Dict[str, str] = {}
    for line in lines[1:]:
        if not line or line[0] in " \t" or ":" not in line:
            raise BadRequestError("Linha de cabecalho invalida")

        name, value = line.split(":", 1)
        if not _is_token(name):
            raise BadRequestError("Nome de cabecalho invalido")
        if "\x00" in value:
            raise BadRequestError("Valor de cabecalho invalido")

        normalized_name = name.lower()
        normalized_value = value.strip(" \t")
        if normalized_name in headers:
            headers[normalized_name] += ", " + normalized_value
        else:
            headers[normalized_name] = normalized_value

    if not headers.get("host") or "," in headers["host"]:
        raise BadRequestError("HTTP/1.1 exige exatamente um Host nao vazio")

    return HTTPRequest(method, target, version, headers)


def build_response(
    status_code: int,
    body: bytes,
    content_type: str,
    *,
    include_body: bool = True,
    close_connection: bool = False,
    extra_headers: Optional[Iterable[Tuple[str, str]]] = None,
) -> bytes:
    """Monta uma resposta HTTP/1.1 com enquadramento e politica de conexao."""

    try:
        reason = STATUS_REASONS[status_code]
    except KeyError as exc:
        raise ValueError("Codigo de status nao suportado") from exc

    headers = [
        ("Date", formatdate(usegmt=True)),
        ("Server", SERVER_ID),
        ("Content-Length", str(len(body))),
        ("Content-Type", content_type),
        ("Connection", "close" if close_connection else "keep-alive"),
    ]
    if extra_headers:
        headers.extend(extra_headers)

    response_head = [f"HTTP/1.1 {status_code} {reason}"]
    response_head.extend(f"{name}: {value}" for name, value in headers)
    encoded_head = ("\r\n".join(response_head) + "\r\n\r\n").encode("ascii")
    return encoded_head + (body if include_body else b"")


def make_error_body(status_code: int) -> bytes:
    """Cria um corpo HTML pequeno e consistente para respostas de erro."""

    reason = STATUS_REASONS[status_code]
    html = (
        "<!doctype html>\n"
        '<html lang="pt-BR"><head><meta charset="utf-8">'
        f"<title>{status_code} {reason}</title></head>"
        f"<body><h1>{status_code} {reason}</h1></body></html>\n"
    )
    return html.encode("utf-8")


def _is_token(value: str) -> bool:
    return bool(value) and all(character in _TOKEN_CHARS for character in value)
