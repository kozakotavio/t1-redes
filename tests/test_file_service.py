import tempfile
import unittest
from pathlib import Path

from file_service import (
    ForbiddenPathError,
    InvalidTargetError,
    StaticFileNotFoundError,
    content_type_for,
    percent_decode_path,
    resolve_target,
)


class FileServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        # /var pode apontar para /private/var no macOS; o TEMP do Windows
        # tambem pode usar um alias 8.3. Compare sempre caminhos canonicos.
        self.root = Path(self.temporary_directory.name).resolve()
        (self.root / "index.html").write_text("inicio", encoding="utf-8")
        (self.root / "espaco aqui.txt").write_text("ok", encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_raiz_resolve_para_index(self):
        path, content_type = resolve_target(self.root, "/")

        self.assertEqual(path, self.root / "index.html")
        self.assertEqual(content_type, "text/html; charset=utf-8")

    def test_decodifica_percent_encoding(self):
        path, _content_type = resolve_target(self.root, "/espaco%20aqui.txt")

        self.assertEqual(path, self.root / "espaco aqui.txt")

    def test_rejeita_tres_formas_de_travessia(self):
        attempts = (
            "/../segredo.txt",
            "/%2e%2e/segredo.txt",
            "/..%5csegredo.txt",
        )

        for attempt in attempts:
            with self.subTest(attempt=attempt):
                with self.assertRaises(ForbiddenPathError):
                    resolve_target(self.root, attempt)

    def test_rejeita_percent_encoding_invalido(self):
        with self.assertRaises(InvalidTargetError):
            percent_decode_path("/%ZZ")

    def test_arquivo_inexistente_retorna_excecao_especifica(self):
        with self.assertRaises(StaticFileNotFoundError):
            resolve_target(self.root, "/nao-existe.txt")

    def test_extensao_desconhecida_usa_octet_stream(self):
        self.assertEqual(
            content_type_for(Path("arquivo.desconhecido")),
            "application/octet-stream",
        )

    def test_tipos_mime_obrigatorios(self):
        expected = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".pdf": "application/pdf",
        }
        for suffix, content_type in expected.items():
            with self.subTest(suffix=suffix):
                self.assertEqual(content_type_for(Path("arquivo" + suffix)), content_type)


if __name__ == "__main__":
    unittest.main()
