# T1 - Servidor HTTP/1.1 sobre sockets TCP

Implementacao didatica das Partes 1 e 2 do trabalho de Laboratorio de Redes de
Computadores. O servidor usa diretamente a API de sockets TCP da biblioteca
padrao do Python. Nenhum framework ou servidor HTTP pronto e utilizado.

O [roteiro de testes](ROTEIRO_DE_TESTES.md) descreve a validacao entre
maquinas e a coleta C1/C2. O [relatorio tecnico](RELATORIO_TECNICO.md)
explica a arquitetura, cada modulo e as analises exigidas; ha tambem uma
[versao PDF](output/pdf/relatorio_tecnico_grupo7.pdf). Campos experimentais
seguem marcados como pendentes ate a captura entre maquinas distintas.

## Compatibilidade: Windows, macOS, Linux e VDI

O projeto usa apenas a biblioteca padrao do Python 3.9 ou superior; nao e
necessario instalar pacotes, compilar ou usar privilegios de administrador.
Os arquivos `.py` e a pasta `www/` sao os mesmos nos tres sistemas. O comando
que inicia o interpretador pode mudar:

| Sistema | Verificar Python | Testes | Iniciar servidor |
| --- | --- | --- | --- |
| Windows / VDI Windows | `py -3 --version` ou `python --version` | `py -3 -m unittest discover -s tests -v` | `py -3 server.py --port 8080 --root ./www` |
| macOS | `python3 --version` | `python3 -m unittest discover -s tests -v` | `python3 server.py --port 8080 --root ./www` |
| Linux | `python3 --version` | `python3 -m unittest discover -s tests -v` | `python3 server.py --port 8080 --root ./www` |

No Windows, se `py` nao estiver disponivel, substitua `py -3` por `python`.
Execute os comandos **na pasta do projeto**, que contem `server.py` e `www/`.
Os testes usam sockets TCP reais em `127.0.0.1` e uma porta livre escolhida
pelo sistema, sem depender da porta 8080. O GitHub Actions executa a mesma
suite em Windows, macOS e Linux a cada push; os resultados ficam na aba
**Actions** do repositorio.

### Verificacao na VDI ou no computador de um colega

1. Confirme que o Python indicado acima tem versao 3.9 ou superior.
2. Rode a suite. Todos os testes devem terminar com `OK`.
3. Inicie o servidor com o comando da tabela. A mensagem deve mostrar
   `Servidor ouvindo em 0.0.0.0:8080`.
4. Na mesma maquina, acesse `http://127.0.0.1:8080/`. Verifique se aparecem
   a imagem e o aviso `JavaScript carregado com sucesso.`
5. Descubra o IPv4 dessa maquina (`ipconfig` no Windows; `ip addr` no Linux;
   `ifconfig` ou as configuracoes de rede no macOS). De outra maquina da rede,
   acesse `http://IP_DO_SERVIDOR:8080/`.

Se a etapa 2 falhar, guarde a saida completa do teste. Se a etapa 4 funcionar
mas a 5 falhar, examine conectividade entre as maquinas (`ping`), restricoes
da rede e se a porta 8080 esta liberada para conexoes de entrada. Nao altere
regras de firewall da VDI sem orientacao do professor ou administrador.

Os testes de CI comprovam a execucao do codigo nos sistemas indicados. O
acesso entre maquinas, especialmente na VDI, depende da configuracao da rede
local e precisa ser confirmado no laboratorio.

## Execucao

Execute na maquina que sera o servidor:

```text
python3 server.py --port 8080 --root ./www
```

Use `py -3` ou `python` no Windows, conforme a tabela acima. A porta deve ser
livre e maior que 1024.

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
7. Em `server.py`, a thread repete o processamento no mesmo socket. A conexao
   permanece aberta por padrao no HTTP/1.1; `Connection: close`, desconexao ou
   5 segundos de ociosidade a encerram. A sobra preservada pelo parser permite
   processar tambem requisicoes agrupadas no mesmo `recv()`.

### Organizacao

- `server.py`: argumentos, socket, concorrencia e tratamento do cliente.
- `http_protocol.py`: buffer TCP, parser e serializacao HTTP/1.1.
- `file_service.py`: percent-decoding, seguranca de caminhos e MIME types.
- `www/`: pagina usada nos testes com navegador e interoperabilidade.
- `tests/`: testes unitarios e de integracao com sockets reais.

O identificador exigido pelo enunciado esta na constante `SERVER_ID`, em
`http_protocol.py`: `Grupo7`.

## Respostas implementadas

Todas as respostas usam HTTP/1.1 e incluem `Date`, `Server`, `Content-Length`,
`Content-Type` e `Connection`. Respostas normais usam `keep-alive`; respostas
com fechamento solicitado, metodo nao suportado ou requisicao malformada usam
`close`. Requisicoes GET/HEAD so podem ter corpo vazio; corpos e
`Transfer-Encoding` nao sao suportados por este servidor de arquivos.

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

```text
python3 -m unittest discover -s tests -v
```

Use `py -3` ou `python` no Windows. Nao ha dependencias externas a instalar.

A suite cobre fragmentacao do fluxo TCP, bytes excedentes, parsing invalido,
GET, HEAD, MIME types, codigos obrigatorios, travessias, concorrencia,
persistencia com dez requisicoes, requisicoes agrupadas, Connection: close,
timeout ocioso e fechamento seguro do servidor.

## Testes manuais com curl

O roteiro completo, com comandos para Windows, macOS e Linux, esta em
`ROTEIRO_DE_TESTES.md`. `--path-as-is` impede o curl de normalizar a travessia
antes de envia-la.

No Windows, use `curl.exe` no PowerShell. No macOS e Linux, use `curl` nos
mesmos exemplos. Substitua `192.168.0.10` pelo IPv4 real do servidor.

```text
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

## Medicao C1 x C2

Com o servidor em outra maquina e o Wireshark capturando na interface real:

```text
python3 tools/measure_connections.py --host IP_SERVIDOR --port 8080 --mode c1
python3 tools/measure_connections.py --host IP_SERVIDOR --port 8080 --mode c2
```

No Windows, use `py -3` ou `python`. O script executa dez GETs ao mesmo
recurso nos dois modos: C1 abre dez conexoes TCP; C2 reutiliza uma conexao.
Handshakes, pacotes e bytes devem ser **extraidos das capturas**, nao
inventados ou inferidos apenas pela saida do cliente.
