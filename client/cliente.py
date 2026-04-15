"""
Ponto de entrada do cliente de chat distribuído com RPC/RMI

Conecta ao servidor, realiza o login e entra no loop interativo de
comandos. Utiliza duas threads:

- **Thread principal**: lê entrada do usuário e chama métodos do ProxyChat (que simulam chamadas locais).
- **Thread recebedora**: escuta notificações assíncronas do servidor por RecebedorMensagens (do receiver)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from socket import socket, AF_INET, SOCK_STREAM
from threading import Event

from client.proxy import ProxyChat
from client.receiver import RecebedorMensagens


SERVIDOR_HOST = "127.0.0.1"
SERVIDOR_PORTA = 5000


def exibir_ajuda():
    """
    Exibe no terminal os comandos disponíveis no chat.
    """
    print(
        "\n  Comandos disponíveis:\n"
        "    /p <usuario> <msg>  — mensagem privada (modo RRA)\n"
        "    /list               — listar usuários conectados (modo RR)\n"
        "    /sair               — encerrar sessão\n"
        "    <mensagem>          — broadcast para todos (modo R)\n"
        "    /ajuda              — exibe esta mensagem\n"
    )


def fazer_login(chat: ProxyChat) -> bool:
    """
    Executa o fluxo de login interativo, solicitando o nome de usuário

    Tenta registrar o nome no servidor via ProxyChat.entrar
    Em caso de falha (nome inválido ou já em uso), solicita nova tentativa

    Parameters
    ----------
    chat : ProxyChat
        Instância do proxy já conectada ao servidor.

    Returns
    -------
    bool
        True se o login foi bem-sucedido e False se o usuário
        encerrar a entrada (Ctrl+C / EOF).
    """
    while True:
        try:
            nome = input("Digite seu nome de usuário: ").strip()
        except (EOFError, KeyboardInterrupt):
            return False

        if not nome:
            print("Nome não pode ser vazio.")
            continue

        sucesso, mensagem = chat.entrar(nome)

        if sucesso:
            print(f"\n{mensagem}\n")
            return True
        else:
            print(f"[Erro] {mensagem}")


def loop_principal(chat: ProxyChat, evento_parar: Event):
    """
    Loop interativo de comandos do cliente.

    Lê comandos do terminal e os traduz em chamadas ao proxy RPC:

    - ``/p <usuario> <msg>`` → ProxyChat.mensagem_privada (RRA)
    - ``/list``              → ProxyChat.listar_usuarios (RR)
    - ``/sair``              → ProxyChat.sair (RR)
    - ``/ajuda``             → exibe ajuda local
    - ``<outro>``            → ProxyChat.enviar_mensagem (R)

    Parameters
    ----------
    chat : ProxyChat
        Proxy RPC conectado ao servidor.
    evento_parar : threading.Event
        Evento sinalizado ao encerrar a sessão para interromper a thread
        de recebimento.
    """
    exibir_ajuda()

    while True:
        try:
            entrada = input().strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not entrada:
            continue

        # /sair
        if entrada == "/sair":
            msg = chat.sair()
            print(f"[Sistema] {msg}")
            break

        # /list
        elif entrada == "/list":
            usuarios = chat.listar_usuarios()
            if usuarios:
                print(f"  Usuários conectados ({len(usuarios)}): {', '.join(usuarios)}")
            else:
                print("  Nenhum usuário conectado.")

        # /p <usuario> <msg>
        elif entrada.startswith("/p "):
            partes = entrada.split(" ", 2)
            if len(partes) < 3:
                print("  Uso: /p <usuario> <mensagem>")
                continue
            _, destino, mensagem = partes
            sucesso, info = chat.mensagem_privada(destino, mensagem)
            if sucesso:
                print(f"  [Privado → {destino}] {mensagem}")
            else:
                print(f"  [Erro] {info}")

        # /ajuda
        elif entrada == "/ajuda":
            exibir_ajuda()

        # broadcast
        else:
            chat.enviar_mensagem(entrada)

    evento_parar.set()


def iniciar_cliente():
    """
    Ponto de entrada principal do cliente de chat

    Realiza a conexão TCP com o servidor, instancia o proxy e o recebedor,
    executa o login e entra no loop de comandos.
    """
    print(f"[Cliente] Conectando a {SERVIDOR_HOST}:{SERVIDOR_PORTA}…")

    sock = socket(AF_INET, SOCK_STREAM)

    try:
        sock.connect((SERVIDOR_HOST, SERVIDOR_PORTA))
    except ConnectionRefusedError:
        print("[Erro] Não foi possível conectar ao servidor. Verifique se ele está em execução.")
        sys.exit(1)

    print("[Cliente] Conexão estabelecida.\n")

    evento_parar = Event()
    chat = ProxyChat(sock)

    # Inicia a thread de recebimento assíncrono
    recebedor = RecebedorMensagens(sock, evento_parar)
    recebedor.iniciar()

    # Login
    if not fazer_login(chat):
        evento_parar.set()
        sock.close()
        return

    # Loop principal de comandos
    try:
        loop_principal(chat, evento_parar)
    except Exception as e:
        print(f"[Erro] {e}")
    finally:
        evento_parar.set()
        sock.close()
        print("[Cliente] Conexão encerrada.")


if __name__ == "__main__":
    iniciar_cliente()