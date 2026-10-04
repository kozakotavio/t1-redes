# Roteiro completo de testes - Grupo 7

Este roteiro cobre funcionamento, seguranca, concorrencia, persistencia,
medicao e interoperabilidade. Os comandos Python usam apenas a biblioteca
padrao. O cliente deve executar em uma **maquina diferente** da que roda o
servidor para gerar as evidencias do trabalho.

## 1. Preparacao nas tres plataformas

Entre na pasta do projeto. Confira que `server.py`, `www/` e `tools/` estao
presentes. Use a coluna correspondente ao sistema:

| Acao | Windows (PowerShell) | macOS / Linux (terminal) |
| --- | --- | --- |
| Versao do Python | `py -3 --version` | `python3 --version` |
| Testes automaticos | `py -3 -m unittest discover -s tests -v` | `python3 -m unittest discover -s tests -v` |
| Iniciar servidor | `py -3 server.py --port 8080 --root ./www` | `python3 server.py --port 8080 --root ./www` |
| Cliente C1 | `py -3 tools/measure_connections.py --host IP_SERVIDOR --port 8080 --mode c1` | `python3 tools/measure_connections.py --host IP_SERVIDOR --port 8080 --mode c1` |
| Cliente C2 | `py -3 tools/measure_connections.py --host IP_SERVIDOR --port 8080 --mode c2` | `python3 tools/measure_connections.py --host IP_SERVIDOR --port 8080 --mode c2` |

No Windows, se `py` nao existir, use `python`. Use Python 3.9 ou superior.
`curl.exe` e o executavel do curl no PowerShell; em macOS/Linux use `curl`.
Substitua literalmente `IP_SERVIDOR` pelo IPv4 da maquina servidora. Use uma
porta alta livre; se alterar 8080, altere-a em **todos** os comandos e filtros.

Antes de codificar evidencias, confirme a rede: `ipconfig` no Windows;
`ip addr` no Linux; `ifconfig` ou Configuracoes de Rede no macOS. Da maquina
cliente, teste `ping IP_SERVIDOR`. Confirme que o Wireshark captura na interface
real. Se as maquinas nao se alcancarem, comunique o professor: resultados em
`127.0.0.1` nao substituem o experimento entre maquinas.

Para registrar uma amostra finita de RTT, use `ping -n 10 IP_SERVIDOR` no
Windows ou `ping -c 10 IP_SERVIDOR` no macOS/Linux. Anote a media mostrada
ao final, junto com data, horario e os dois IPs.

## 2. Funcionamento e conformidade HTTP

Inicie o servidor na maquina A. Na maquina B, abra
`http://IP_SERVIDOR:8080/` no navegador e verifique que somente a imagem
aparece na página. Abra as ferramentas de rede do navegador e confirme as
respostas 200 para o HTML e o JPEG.

No terminal da maquina B, use `curl.exe` no Windows ou `curl` nos comandos
abaixo. Para copiar e colar, substitua `IP_SERVIDOR` primeiro.

```text
curl -i http://IP_SERVIDOR:8080/
curl -I http://IP_SERVIDOR:8080/
curl -I http://IP_SERVIDOR:8080/weird.jpeg
curl -i http://IP_SERVIDOR:8080/nao-existe.txt
curl -i -X POST http://IP_SERVIDOR:8080/
curl -i --request-target "*" http://IP_SERVIDOR:8080/
```

Esperado, na ordem: `200`, `200` sem corpo, `200` com `image/jpeg` sem imprimir
o arquivo binario, `404`,
`405` com `Allow: GET, HEAD`, e `400`. Em **todas** as respostas, confira
`HTTP/1.1`, `Content-Length`, `Content-Type`, `Date` em GMT e `Server: Grupo7`.
No HEAD, `Content-Length` deve ser igual ao GET correspondente, mesmo sem
corpo. `Connection: keep-alive` e o padrao; `Connection: close` so quando o
cliente solicita ou quando a resposta encerra a conexao.

### Seguranca: tres travessias

`--path-as-is` impede que o proprio curl elimine `..` antes do envio.

```text
curl -i --path-as-is http://IP_SERVIDOR:8080/../segredo.txt
curl -i --path-as-is http://IP_SERVIDOR:8080/%2e%2e/segredo.txt
curl -i --path-as-is http://IP_SERVIDOR:8080/..%5csegredo.txt
```

As tres respostas devem ser `403 Forbidden`. Guarde a linha GET enviada e a
resposta completa no relatorio. Nenhum arquivo fora de `www/` pode ser servido.

## 3. Persistencia, fechamento e timeout

Primeiro, confira a conexao persistente com o cliente de medicao em modo C2
(secao 5): ele realiza dez GETs sequenciais no **mesmo socket** e verifica
cada resposta pelo `Content-Length`. A captura deve mostrar um handshake TCP.

Depois confira o fechamento explicito:

```text
curl -i -H "Connection: close" http://IP_SERVIDOR:8080/leia-me.txt
```

Esperado: `Connection: close` na resposta e encerramento do socket. Para o
timeout, rode `py -3 tools/idle_client.py --host IP_SERVIDOR --port 8080`
no Windows, ou `python3 tools/idle_client.py --host IP_SERVIDOR --port 8080`
no macOS/Linux. Ele deixa o socket aberto depois da resposta e confirma o
fechamento apos cerca de 5 segundos sem bytes extras. Confira tambem o log
e a captura. O teste automatizado
`test_timeout_fecha_conexao_ociosa_sem_resposta_extra` usa um timeout menor
apenas para rodar rapido.

## 4. Concorrencia entre duas maquinas clientes

Com servidor na maquina A, execute na maquina B:

```text
python3 tools/slow_client.py --host IP_SERVIDOR --port 8080 --delay 3
```

No Windows, troque `python3` por `py -3`. Durante os 3 segundos de espera,
execute na maquina C `curl -i http://IP_SERVIDOR:8080/leia-me.txt`. O GET da
maquina C deve terminar **antes** do cliente lento completar os cabecalhos.
Registre horario, IPs de B/C e os logs do servidor ou a captura. Se so houver
duas maquinas disponiveis, uma segunda janela na maquina B verifica threads,
mas a evidencia final do enunciado exige dois clientes em maquinas distintas.

## 5. Experimento C1 x C2 com Wireshark

1. Anote sistema/versao Python do servidor, IPs cliente/servidor, porta,
   interface e data. Pare outros testes na porta 8080.
2. Na maquina B, rode `ping IP_SERVIDOR` e anote o RTT medio. Use a mesma
   rede, recurso (`/leia-me.txt`), maquinas e porta nos dois cenarios.
3. No Wireshark da maquina A, selecione a interface de rede real. Use o
   **filtro de exibicao** `tcp.port == 8080 && ip.addr == IP_CLIENTE`.
4. Comece uma nova captura. Rode C1 na maquina B com o comando da tabela da
   secao 1. Pare a captura somente apos o ultimo fechamento. Salve
   `capturas/c1.pcapng`.
5. Comece outra captura limpa. Rode C2. Pare apos o fechamento final. Salve
   `capturas/c2.pcapng`.
6. Em cada arquivo, conte os handshakes completos (SYN, SYN-ACK e ACK), os
   pacotes e os bytes de **todos os quadros exibidos** pelo filtro. Registre
   o tempo entre o primeiro SYN e o ultimo pacote de encerramento. Use a
   mesma definicao de bytes e tempo nos dois cenarios.

O programa imprime dez respostas 200 em cada cenario e o tempo visto pelo
cliente. Em C1 ele abre dez sockets e envia `Connection: close` em cada GET.
Em C2 ele abre um socket, reutiliza-o dez vezes e envia `Connection: close`
apenas no decimo GET. A captura deve confirmar **10** e **1** handshakes,
respectivamente; nao use apenas a contagem impressa pelo programa como prova.

| Metrica | C1 | C2 |
| --- | ---: | ---: |
| Handshakes completos observados | preencher | preencher |
| Pacotes totais exibidos | preencher | preencher |
| Bytes totais exibidos | preencher | preencher |
| Tempo total da captura (s) | preencher | preencher |
| Tempo do cliente (s) | preencher | preencher |

Economia de pacotes = `(pacotes_C1 - pacotes_C2) / pacotes_C1 * 100`.
Economia de bytes = `(bytes_C1 - bytes_C2) / bytes_C1 * 100`.

Para estimar o overhead de C1, marque em cada fluxo os pacotes usados somente
na abertura e no encerramento TCP. Some sua contagem e seus `frame.len`.
Nao conte os pacotes HTTP nem todo ACK puro indiscriminadamente: alguns ACKs
confirmam dados da transferencia. A diferenca de **nove handshakes** sugere
aproximadamente **nove RTTs extras** de abertura em C1; compare essa previsao
com os tempos medidos e explique variacoes de agendamento e rede.

## 6. Evidencias adicionais do relatorio

- Capture um GET bem-sucedido da maquina B: destaque numeros dos pacotes do
  handshake, requisicao, resposta e FIN/ACK de encerramento.
- Guarde a tabela de conformidade com comando curl, status e cabecalhos para
  `200`, `400`, `403`, `404` e `405`.
- Guarde os tres GETs de travessia com resposta 403.
- Guarde log ou captura de atendimento simultaneo das maquinas B/C.
- Guarde RTT medio e as duas capturas `.pcapng` originais.

## 7. Teste com outro grupo e entrega

Na aula, o navegador do grupo A deve abrir a pagina do servidor do grupo B e
vice-versa. A nossa pagina so passa se o HTML e a imagem carregarem
corretamente.
Prepare todos os integrantes para explicar qualquer parte de `server.py`,
`http_protocol.py` e `file_service.py`.

Entregue um unico `.zip` ou `.tar`, por **um** integrante do grupo, com
codigo-fonte, `README.md`, `www/`, `capturas/*.pcapng` e relatorio PDF.
Nao inclua binarios, caches ou arquivos temporarios. O arquivo deve ser
testado na VDI antes do envio.
