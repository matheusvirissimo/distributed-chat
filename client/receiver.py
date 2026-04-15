"""
Thread de recebimento assíncrono de mensagens do servidor
* O responsável por ficar recebendo mensagem de outros usuários sem
bloquear um ao outro

Mantém uma thread separada ouvindo notificações push do servidor
enquanto a thread principal aguarda entrada do usuário, permitindo
comunicação bidirecional simultânea.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from threading import Thread, Event
from utils.protocol import deserializar, OperacaoId


class RecebedorMensagens:
    """
    Gerenciador da thread de recebimento assíncrono de mensagens

    Executa em segundo plano e imprime no terminal quaisquer notificações
    ou respostas inesperadas recebidas do servidor, sem interferir na
    thread de entrada do usuário.

    Parameters
    ----------
    socket_cliente : socket.socket
        Socket TCP conectado ao servidor
    buffer_proxy : list
        Referência ao buffer compartilhado com o ProxyChat. Mensagens não-notificação
        são colocadas aqui para serem consumidas pelo proxy
    evento_parar : threading.Event
        Evento sinalizado para encerrar o loop de recebimento

    Attributes
    ----------
    socket_cliente : socket.socket
    _buffer_fragmentos : str
        Acumulador de fragmentos TCP.
    _evento_parar : threading.Event
    _thread : threading.Thread or None
    """

    def __init__(self, socket_cliente, evento_parar: Event):
        self.socket_cliente     = socket_cliente
        self._evento_parar      = evento_parar
        self._buffer_fragmentos = ""
        self._thread: Thread | None = None

    def iniciar(self):
        """
        Cria e inicia a thread daemon de recebimento de mensagens

        **OBS**: A thread é daemon para que seja encerrada automaticamente quando
        o processo principal terminar.
        """
        self._thread = Thread(
            target = self._loop_recebimento,
            daemon = True,
            name = "receptor-mensagens",
        )
        self._thread.start()

    def _loop_recebimento(self):
        """
        Loop principal de recebimento assíncrono.

        Lê mensagens do socket continuamente até que a conexão seja
        encerrada ou _evento_parar ocorra

        Exibe notificações diretamente no terminal. Mensagens que não
        sejam notificações (ex: respostas fora de ordem) também são exibidas com aviso.
        """
        while not self._evento_parar.is_set():
            try:
                while "\n" not in self._buffer_fragmentos:
                    dados = self.socket_cliente.recv(4096).decode("utf-8")
                    if not dados:
                        if not self._evento_parar.is_set():
                            print("\n[Sistema] Conexão com o servidor encerrada.")
                        return
                    self._buffer_fragmentos += dados

                linha, self._buffer_fragmentos = self._buffer_fragmentos.split("\n", 1)
                msg = deserializar(linha.encode("utf-8"))

                if msg.get("operacao_id") == OperacaoId.NOTIFICACAO:
                    print(f"\n  [Sistema] {msg['conteudo']}")
                else:
                    # Mensagem de resposta recebida fora do ciclo do proxy
                    print(f"\n  [?] Mensagem inesperada: {msg}")

            except Exception as e:
                if not self._evento_parar.is_set():
                    print(f"\n[Recebedor] Erro: {e}")
                return