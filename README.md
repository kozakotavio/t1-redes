# T1 - Servidor HTTP/1.1 sobre sockets TCP

Implementacao didatica da Parte 1 do trabalho de Laboratorio de Redes de
Computadores. O servidor usa diretamente a API de sockets TCP da biblioteca
padrao do Python. Nenhum framework ou servidor HTTP pronto e utilizado.

## Requisitos e execucao

- Python 3.9 ou superior.
- Uma porta livre acima de 1024.
- Para os testes avaliados, duas maquinas na mesma rede.

Execute na maquina que sera o servidor:

```powershell
python server.py --port 8080 --root ./www
```

O servidor faz `bind` em `0.0.0.0`, portanto aceita conexoes por todas as
interfaces de rede. Descubra o IPv4 da maquina com `ipconfig` e, em outra
maquina, abra `http://IP_DO_SERVIDOR:8080/` no navegador.

## Como o servidor funciona

1. `server.py` cria um socket TCP, associa a porta com `bind`, inicia a fila
   com `listen` e recebe clientes com `accept`.
2. Cada cliente e entregue a uma thread. Assim, um cliente que envia dados
   lentamente nao impede os demais de serem atendidos.
3. `receive_request_head` acumula os bytes retornados por `recv` ate encontrar
   `\r\n\r\n`. Isso e necessario porque TCP fornece um fluxo: uma leitura pode
   trazer apenas parte de uma requisicao ou dados de mais de uma requisicao.
4. `parse_request` interpreta manualmente a linha de requisicao e os
   cabecalhos. Nenhum modulo de servidor HTTP e usado.
5. `file_service.py` decodifica percent-encoding, normaliza o caminho e garante
   que o arquivo resolvido continue dentro da raiz configurada.
6. `build_response` monta a linha de status e todos os cabecalhos obrigatorios.
   A resposta e enviada por `sendall`, que repete `send` ate transmitir tudo.
7. Na Parte 1, a conexao e fechada depois de uma resposta. A Parte 2 adicionara
   o laco de conexao persistente e o timeout ocioso especifico.

### Organizacao

- `server.py`: argumentos, socket, concorrencia e tratamento do cliente.
- `http_protocol.py`: buffer TCP, parser e serializacao HTTP/1.1.
- `file_service.py`: percent-decoding, seguranca de caminhos e MIME types.
- `www/`: pagina usada nos testes com navegador e interoperabilidade.
- `tests/`: testes unitarios e de integracao com sockets reais.

O identificador exigido pelo enunciado esta na constante `SERVER_ID`, em
`http_protocol.py`. O valor inicial e `Grupo-Kozak/1.0` e pode ser trocado em
um unico local quando o grupo receber seu identificador definitivo.

## Respostas implementadas

Todas as respostas usam HTTP/1.1 e incluem `Date`, `Server`, `Content-Length`,
`Content-Type` e `Connection: close`.

| Status | Situacao |
| --- | --- |
| `200 OK` | Arquivo encontrado |
| `400 Bad Request` | Linha, cabecalho, versao ou caminho malformado |
| `403 Forbidden` | Tentativa de sair do diretorio raiz |
| `404 Not Found` | Arquivo inexistente |
| `405 Method Not Allowed` | Metodo diferente de GET e HEAD |

`HEAD` produz os mesmos cabecalhos do `GET` correspondente, inclusive o
`Content-Length`, mas nao transmite o corpo.

## Testes automatizados

```powershell
python -m unittest discover -s tests -v
```

A suite cobre fragmentacao do fluxo TCP, bytes excedentes, parsing invalido,
GET, HEAD, MIME types, codigos obrigatorios, tres formas de travessia e
atendimento concorrente com um cliente lento.

## Testes manuais com curl

Substitua o IP nos exemplos. `--path-as-is` impede o curl de normalizar a
travessia antes de envia-la.

```powershell
# 200 e HEAD
curl.exe -i http://192.168.0.10:8080/
curl.exe -I http://192.168.0.10:8080/

# 400: request-target invalido para este servidor de arquivos
curl.exe -i --request-target "*" http://192.168.0.10:8080/

# 403: tres tentativas diferentes
curl.exe -i --path-as-is http://192.168.0.10:8080/../segredo.txt
curl.exe -i --path-as-is http://192.168.0.10:8080/%2e%2e/segredo.txt
curl.exe -i --path-as-is http://192.168.0.10:8080/..%5csegredo.txt

# 404 e 405
curl.exe -i http://192.168.0.10:8080/nao-existe.txt
curl.exe -i -X POST http://192.168.0.10:8080/
```

## Wireshark e interoperabilidade

Capture na interface de rede real, usando o filtro:

```text
tcp.port == 8080
```

Nao use capturas de `localhost` no relatorio. A pagina `www/index.html`
referencia CSS, JavaScript e PNG, portanto o navegador realiza varias
requisicoes e permite testar a interoperabilidade com outro grupo.

## Limites atuais

Esta entrega implementa somente a Parte 1. Cada conexao atende uma requisicao
e retorna `Connection: close`. A Parte 2 reutilizara a sobra ja preservada pelo
parser para atender varias requisicoes no mesmo socket, adicionara timeout de
conexao ociosa e produzira as medicoes comparativas C1 e C2.

