# Distributed chat with RPC/RMI

Sistema de chat multiusuário onde cada interação é tratada como uma
**invocação remota de método (RPC/RMI)**, demonstrando os conceitos de
proxy (stub), dispatcher (skeleton), protocolo de requisição-resposta
e comunicação concorrente com threads.

---

## Estrutura de Pastas

```
chat_rpc/
│
├── utils/
│   ├── __init__.py           # Protocolo compartilhado: estruturas de msg,
│   └── protocolo.py          # OperacaoId, modos R/RR/RRA, serialização JSON
│                             
│
├── servidor/
│   ├── __init__.py
│   ├── logica.py             # Lógica de negócio: broadcast, unicast,
│   │                         # registro/remoção de usuários
│   ├── dispatcher.py         # Dispatcher/Skeleton: recebe requisições,
│   │                         # identifica operação, chama logica, envia reply
│   └── servidor.py           # Ponto de entrada: aceita conexões TCP e
│                             # cria uma thread por cliente
│
└── cliente/
    ├── __init__.py
    ├── proxy.py              # Proxy/Stub: expõe métodos locais que viram
    │                         # requisições remotas JSON (doOperation)
    ├── recebedor.py          # Thread de recebimento assíncrono de notificações
    └── cliente.py            # Ponto de entrada: login, loop de comandos
```

---

## Como Executar

### 1. Iniciar o servidor

```bash
python -m server.servidor
```

### 2. Conectar um cliente (abrir em outro terminal)

```bash
python -m client.cliente
```

Abra quantos terminais desejar para testar múltiplos clientes simultaneamente.

---

## Comandos do Chat

| Comando               | Descrição                              | Modo RPC |
|-----------------------|----------------------------------------|----------|
| `<mensagem>`          | Broadcast para todos                   | R        |
| `/p <usuario> <msg>`  | Mensagem privada para um usuário       | RRA      |
| `/list`               | Listar usuários conectados             | RR       |
| `/sair`               | Encerrar sessão                        | RR       |
| `/ajuda`              | Exibir ajuda local                     | —        |

---

## Conceitos Implementados

### 1. Proxy (Stub) - `cliente/proxy.py`
A classe `ProxyChat` expõe métodos como `enviar_mensagem()` e
`mensagem_privada()` que parecem chamadas locais mas internamente:
- Criam uma requisição JSON com `request_id` único e `operacao_id`
- Serializam e enviam via TCP
- Aguardam e desserializam a resposta (modos RR/RRA)

### 2. Dispatcher - `servidor/dispatcher.py`
O `Dispatcher` opera no servidor e:
- Recebe requisições via `receber_requisicao()` (getRequest)
- Identifica o `operacao_id` em uma tabela de despacho
- Delega à lógica de negócio e envia a resposta (`sendReply`)
- Suporta os três modos: R, RR e RRA

### 3. Protocolo de Requisição-Resposta - `comum/protocolo.py`
Cada mensagem possui:
- `request_id`: UUID único para correlação de resposta
- `operacao_id`: identifica a operação remota
- `modo`: R, RR ou RRA
- `parametros`: argumentos da operação

### 4. Modos de Comunicação
- **R (Request)**: `enviar_mensagem` -> envia broadcast sem aguardar reply
- **RR (Request-Reply)**: `entrar`, `listar_usuarios`, `sair` -> aguarda resposta
- **RRA (Request-Reply-Ack)**: `mensagem_privada` -> envia ACK após receber reply

### 5. Concorrência com Threads
- **Servidor**: thread principal aceita conexões; uma thread por cliente executa o `Dispatcher`
- **Cliente**: thread principal gerencia input; thread daemon `RecebedorMensagens` escuta notificações assíncronas

### 6. Notificações Assíncronas (Push)
O servidor envia notificações sem requisição prévia (entrada/saída de usuários, mensagens recebidas) usando `criar_notificacao()`.
