"""
Ponto de entrada do servidor de chat distribuído com RPC/RMI

Inicializa o socket TCP, aceita novas conexões em loop e cria uma thread
dedicada para cada cliente, delegando o processamento ao despacho (dispatcher) 

No fim, é o arquivo mais simples de todos pois ele só recebe, não processa nada.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from socket import (socket, 
                    AF_INET, 
                    SOCK_STREAM, 
                    SOL_SOCKET, 
                    SO_REUSEADDR)
from threading import Thread

from server.logic import LogicaChat
from server.despacho import Dispatcher


PORTA_SERVIDOR = 5000


def iniciar_servidor():
    """
    Inicia o servidor de chat e entra no loop de aceitação de conexões

    Cria uma instância compartilhada de LogicaChat e, para cada nova conexão TCP aceita, instancia um
    Dispatcher e o executa em uma thread separada

    **OBS**: O servidor utiliza SO_REUSEADDR para evitar erros de "endereço já
    em uso" após reinicializações rápidas. Além disso, a thread principal atua exclusivamente como 
    listener; todo processamento de cliente ocorre nas threads filhas.
    """
    logica = LogicaChat()

    socket_servidor = socket(AF_INET, SOCK_STREAM)
    socket_servidor.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    socket_servidor.bind(("", PORTA_SERVIDOR))
    socket_servidor.listen(10)

    print(f"[Servidor] Chat RPC/RMI iniciado na porta {PORTA_SERVIDOR}.")
    print("[Servidor] Aguardando conexões…\n")

    try:
        while True:
            socket_cliente, endereco = socket_servidor.accept()
            print(f"[Servidor] Nova conexão de {endereco}")

            dispatcher = Dispatcher(logica, socket_cliente)

            thread = Thread(
                target=dispatcher.processar,
                daemon=True,
                name=f"cliente-{endereco}",
            )
            thread.start()

    except KeyboardInterrupt:
        print("\n[Servidor] Encerrando servidor…")
    finally:
        socket_servidor.close()


if __name__ == "__main__":
    iniciar_servidor()