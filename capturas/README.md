# Capturas de rede

Salve aqui as evidencias feitas entre maquinas distintas no laboratorio:

- `transacao.pcapng`: GET completo, do handshake ao encerramento.
- `c1.pcapng`: dez GETs com dez conexoes TCP.
- `c2.pcapng`: dez GETs na mesma conexao TCP.
- Evidencia de concorrencia e travessias, se a entrega pedir capturas separadas.

O [roteiro de testes](../ROTEIRO_DE_TESTES.md) explica filtros, comandos e
metricas. Nenhum arquivo `.pcapng` foi gerado em loopback como se fosse uma
captura do laboratorio.
