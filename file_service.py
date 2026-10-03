"""Resolucao segura de caminhos e tipos de conteudo dos arquivos estaticos."""

from pathlib import Path
from typing import Tuple


MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
}


class ForbiddenPathError(ValueError):
    """Indica uma tentativa de acessar algo fora do diretorio raiz."""


class InvalidTargetError(ValueError):
    """Indica um request-target invalido ou percent-encoding malformado."""


class StaticFileNotFoundError(FileNotFoundError):
    """Indica que o alvo e seguro, mas nao corresponde a um arquivo."""


def resolve_target(root: Path, request_target: str) -> Tuple[Path, str]:
    """Converte um request-target em arquivo, sem permitir escapar de ``root``."""

    root = root.resolve()
    path_part = request_target.split("?", 1)[0]
    decoded_path = percent_decode_path(path_part).replace("\\", "/")
    segments = decoded_path.split("/")

    # Rejeitar a intencao de travessia tambem deixa a demonstracao inequivoca,
    # mesmo quando uma sequencia como ../www voltaria ao diretorio inicial.
    if ".." in segments:
        raise ForbiddenPathError("Segmento de travessia encontrado")

    relative_path = decoded_path.lstrip("/")
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ForbiddenPathError("Caminho fora do diretorio raiz") from exc

    if candidate.is_dir():
        candidate = (candidate / "index.html").resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ForbiddenPathError("Caminho fora do diretorio raiz") from exc

    if not candidate.is_file():
        raise StaticFileNotFoundError(str(candidate))

    return candidate, content_type_for(candidate)


def percent_decode_path(value: str) -> str:
    """Decodifica percent-encoding sem recorrer a um parser HTTP pronto."""

    decoded = bytearray()
    index = 0
    while index < len(value):
        character = value[index]
        if character == "%":
            if index + 2 >= len(value):
                raise InvalidTargetError("Percent-encoding incompleto")
            pair = value[index + 1 : index + 3]
            try:
                decoded.append(int(pair, 16))
            except ValueError as exc:
                raise InvalidTargetError("Percent-encoding invalido") from exc
            index += 3
            continue

        try:
            decoded.extend(character.encode("ascii"))
        except UnicodeEncodeError as exc:
            raise InvalidTargetError("Caracter nao ASCII deve usar percent-encoding") from exc
        index += 1

    try:
        result = decoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidTargetError("Caminho nao e UTF-8 valido") from exc

    if "\x00" in result:
        raise InvalidTargetError("Caminho contem byte nulo")
    return result


def content_type_for(path: Path) -> str:
    return MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")

